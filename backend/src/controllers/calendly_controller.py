"""Calendly: sync manual vía API v2 (PAT en ApiConnection)."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pony.orm import ObjectNotFound, db_session

from src.controllers.webhook_controller import (
    _merge_calendly_email_notas,
    _parse_calendly_start_time,
)
from src.lead_display_utils import compute_dias_para_agendar
from src.models import ApiConnection, Lead

router = APIRouter(prefix="/calendly", tags=["calendly"], redirect_slashes=False)

_CALENDLY_API = "https://api.calendly.com"
_MAX_EVENT_PAGES = 1
_PAGE_COUNT = 20
_INVITEE_REQUEST_DELAY_S = 0.3
_RATE_LIMIT_MESSAGE = "Rate limit de Calendly alcanzado. Esperá 1 minuto y volvé a intentar."


class CalendlyRateLimitError(Exception):
    pass


def require_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    if x_user_id is None or not x_user_id.strip():
        raise HTTPException(
            status_code=401,
            detail="Se requiere el header X-User-Id con el id del usuario autenticado.",
        )
    return x_user_id.strip()


def _uid_int(user_id: str) -> int:
    try:
        return int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-User-Id debe ser numérico.")


def _uri_uuid(uri: str) -> str:
    return str(uri or "").strip().rstrip("/").split("/")[-1]


def _email_from_notas(notas: str | None) -> str:
    for line in (notas or "").splitlines():
        match = re.match(r"Calendly email:\s*(.+)", line.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _find_lead_by_email(user_id: int, email: str) -> Lead | None:
    key = email.strip().casefold()
    if not key:
        return None
    matches: list[Lead] = []
    for row in Lead.select(lambda l: l.user_id == user_id):
        stored = _email_from_notas(row.notas)
        if stored and stored.casefold() == key:
            matches.append(row)
    if not matches:
        return None
    matches.sort(key=lambda r: r.created_at.timestamp() if r.created_at else 0.0, reverse=True)
    return matches[0]


def _retry_after_seconds(response: httpx.Response) -> float:
    raw = str(response.headers.get("Retry-After") or "").strip()
    if not raw:
        return 60.0
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return 60.0


def _calendly_get(
    client: httpx.Client,
    path: str,
    headers: dict[str, str],
    params: dict | None = None,
    *,
    retried: bool = False,
) -> dict:
    url = path if path.startswith("http") else f"{_CALENDLY_API}{path}"
    try:
        response = client.get(url, headers=headers, params=params)
        if response.status_code == 429:
            if not retried:
                time.sleep(_retry_after_seconds(response))
                return _calendly_get(client, path, headers, params, retried=True)
            raise CalendlyRateLimitError
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {}
    except CalendlyRateLimitError:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise CalendlyRateLimitError from exc
        detail = ""
        try:
            detail = exc.response.text[:500]
        except Exception:
            pass
        if exc.response.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail="Calendly rechazó el Personal Access Token (revisá que sea válido y tenga permisos).",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"Error Calendly {exc.response.status_code}: {detail}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar a Calendly: {exc!s}") from exc


def _fetch_scheduled_events(
    client: httpx.Client,
    headers: dict[str, str],
    *,
    user_uri: str,
    org_uri: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token: str | None = None

    for _ in range(_MAX_EVENT_PAGES):
        params: dict[str, str | int] = {
            "user": user_uri,
            "count": _PAGE_COUNT,
            "sort": "start_time:desc",
        }
        if org_uri:
            params["organization"] = org_uri
        if page_token:
            params["page_token"] = page_token

        data = _calendly_get(client, "/scheduled_events", headers, params)
        collection = data.get("collection") or []
        if isinstance(collection, list):
            events.extend(item for item in collection if isinstance(item, dict))

        pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
        next_token = str(pagination.get("next_page_token") or "").strip()
        if not next_token:
            break
        page_token = next_token

    return events


def _fetch_event_invitees(
    client: httpx.Client,
    headers: dict[str, str],
    event_uuid: str,
) -> list[dict[str, Any]]:
    invitees: list[dict[str, Any]] = []
    page_token: str | None = None

    for page_index in range(_MAX_EVENT_PAGES):
        if page_index > 0:
            time.sleep(_INVITEE_REQUEST_DELAY_S)
        path = f"/scheduled_events/{event_uuid}/invitees"
        params: dict[str, str | int] = {"count": _PAGE_COUNT}
        if page_token:
            params["page_token"] = page_token

        data = _calendly_get(client, path, headers, params)
        collection = data.get("collection") or []
        if isinstance(collection, list):
            invitees.extend(item for item in collection if isinstance(item, dict))

        pagination = data.get("pagination") if isinstance(data.get("pagination"), dict) else {}
        next_token = str(pagination.get("next_page_token") or "").strip()
        if not next_token:
            break
        page_token = next_token

    return invitees


@db_session
def _apply_invitee_to_lead(
    user_id: int,
    *,
    name: str,
    email: str,
    call_at: datetime | None,
    agendo_at: datetime | None,
) -> str:
    """Returns 'created' or 'updated'."""
    display_name = name.strip() or (email.split("@")[0] if email else "Invitado Calendly")
    row = _find_lead_by_email(user_id, email) if email else None

    if row is not None:
        if display_name:
            row.nombre = display_name
        if email:
            row.notas = _merge_calendly_email_notas(row.notas, email)
        if call_at is not None:
            row.call = call_at
        if agendo_at is not None:
            row.agendo = agendo_at
        row.status = "Agendado"
        row.agendo_en = "Calendly"
        row.dias_para_agendar = compute_dias_para_agendar(row.primer_contacto, row.agendo)
        return "updated"

    notas_parts: list[str] = []
    if email:
        notas_parts.append(f"Calendly email: {email}")
    if call_at is not None:
        notas_parts.append(f"Cita: {call_at.isoformat()}")

    Lead(
        user_id=user_id,
        nombre=display_name,
        notas="\n".join(notas_parts),
        call=call_at,
        agendo=agendo_at or call_at,
        status="Agendado",
        agendo_en="Calendly",
    )
    return "created"


@router.post("/sync")
def sync_calendly(user_id: Annotated[str, Depends(require_user_id)]):
    uid = _uid_int(user_id)
    try:
        return _run_calendly_sync(uid)
    except CalendlyRateLimitError:
        return JSONResponse(status_code=429, content={"error": _RATE_LIMIT_MESSAGE})


def _run_calendly_sync(uid: int) -> dict[str, int]:
    with db_session:
        try:
            conn = ApiConnection.get(user_id=uid, platform="calendly")
        except ObjectNotFound:
            raise HTTPException(
                status_code=400,
                detail='No hay conexión Calendly. Configurá la plataforma "calendly" en Conexiones API.',
            )
        creds = conn.credentials if isinstance(conn.credentials, dict) else {}
        api_key = str(creds.get("api_key") or "").strip()
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="Falta api_key (Personal Access Token) en las credenciales de Calendly.",
            )

    headers = {"Authorization": f"Bearer {api_key}"}
    created = 0
    updated = 0

    with httpx.Client(timeout=60.0) as client:
        me = _calendly_get(client, "/users/me", headers)
        resource = me.get("resource") if isinstance(me.get("resource"), dict) else {}
        user_uri = str(resource.get("uri") or "").strip()
        org_uri = str(resource.get("current_organization") or "").strip()
        if not user_uri:
            raise HTTPException(status_code=502, detail="Calendly no devolvió current_user.uri.")

        events = _fetch_scheduled_events(client, headers, user_uri=user_uri, org_uri=org_uri)

        pending: list[dict[str, Any]] = []
        invitee_request_count = 0
        for event in events:
            event_uuid = _uri_uuid(str(event.get("uri") or ""))
            if not event_uuid:
                continue
            start_dt = _parse_calendly_start_time(str(event.get("start_time") or ""))
            if invitee_request_count > 0:
                time.sleep(_INVITEE_REQUEST_DELAY_S)
            invitee_request_count += 1
            invitees = _fetch_event_invitees(client, headers, event_uuid)

            for invitee in invitees:
                status = str(invitee.get("status") or "active").strip().casefold()
                if status == "canceled":
                    continue

                email = str(invitee.get("email") or "").strip()
                if not email:
                    continue

                pending.append(
                    {
                        "name": str(invitee.get("name") or "").strip(),
                        "email": email,
                        "call_at": start_dt,
                        "agendo_at": _parse_calendly_start_time(str(invitee.get("created_at") or "")),
                    }
                )

    for item in pending:
        result = _apply_invitee_to_lead(
            uid,
            name=item["name"],
            email=item["email"],
            call_at=item["call_at"],
            agendo_at=item["agendo_at"],
        )
        if result == "created":
            created += 1
        else:
            updated += 1

    _touch_calendly_last_sync(uid)

    synced = created + updated
    return {"synced": synced, "created": created, "updated": updated}


@db_session
def _touch_calendly_last_sync(user_id: int) -> None:
    try:
        conn_row = ApiConnection.get(user_id=user_id, platform="calendly")
        now = datetime.utcnow()
        conn_row.last_sync_at = now
        conn_row.updated_at = now
    except ObjectNotFound:
        pass
