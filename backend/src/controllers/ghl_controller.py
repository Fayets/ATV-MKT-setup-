"""Go High Level: sync manual de appointments vía API v2 (Private Integration Token)."""
from __future__ import annotations
import calendar
import time
import traceback
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pony.orm import ObjectNotFound, db_session
from pydantic import BaseModel, Field

from src.db_query_utils import rows_for_user
from src.lead_display_utils import compute_dias_para_agendar
from src.models import ApiConnection, Lead

router = APIRouter(prefix="/ghl", tags=["ghl"], redirect_slashes=False)

_GHL_API = "https://services.leadconnectorhq.com"
_GHL_VERSION = "2021-07-28"
_PAGE_SIZE = 100
_MAX_CONTACT_PAGES = 50
_REQUEST_DELAY_S = 0.2

class GHLSyncRequest(BaseModel):
    month: str | None = Field(default=None, description="YYYY-MM opcional para filtrar appointments")

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

def _month_bounds_iso(month: str) -> tuple[str, str]:
    """Devuelve (start_iso, end_iso) para filtrar por mes."""
    try:
        year, mon = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="month debe tener formato YYYY-MM.")
    last_day = calendar.monthrange(year, mon)[1]
    start = f"{year:04d}-{mon:02d}-01 00:00:00"
    end = f"{year:04d}-{mon:02d}-{last_day:02d} 23:59:59"
    return start, end

def _parse_ghl_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None

def _ghl_get(
    client: httpx.Client,
    token: str,
    path: str,
    params: dict | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": _GHL_VERSION,
    }
    url = path if path.startswith("http") else f"{_GHL_API}{path}"
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.get(url, headers=headers, params=params)
            if response.status_code == 429:
                time.sleep(60)
                response = client.get(url, headers=headers, params=params)
            if response.status_code == 400 and "Timeout" in response.text:
                wait_s = 2 ** attempt
                print(f"[ghl] GHL timeout en {path}, reintento {attempt + 1}/3 en {wait_s}s", flush=True)
                time.sleep(wait_s)
                continue
            response.raise_for_status()
            body = response.json()
            return body if isinstance(body, dict) else {}
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 400 and "Timeout" in exc.response.text and attempt < 2:
                wait_s = 2 ** attempt
                print(f"[ghl] GHL timeout en {path}, reintento {attempt + 1}/3 en {wait_s}s", flush=True)
                time.sleep(wait_s)
                continue
            detail = ""
            try:
                detail = exc.response.text[:500]
            except Exception:
                pass
            raise HTTPException(
                status_code=502,
                detail=f"Error GHL {exc.response.status_code}: {detail}",
            ) from exc
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise HTTPException(status_code=502, detail=f"No se pudo contactar a GHL: {exc!s}") from exc
    if isinstance(last_exc, httpx.HTTPStatusError):
        detail = last_exc.response.text[:500] if last_exc.response else ""
        raise HTTPException(
            status_code=502,
            detail=f"Error GHL {last_exc.response.status_code}: {detail}",
        ) from last_exc
    raise HTTPException(status_code=502, detail=f"No se pudo contactar a GHL: {last_exc!s}")

def _iter_contacts_with_appointments(
    client: httpx.Client,
    token: str,
    location_id: str,
    calendar_id: str,
    month: str | None,
) -> Iterator[dict[str, Any]]:
    """Pagina contactos, filtra los del calendario por attributions, y yield appointments."""
    month_start, month_end = _month_bounds_iso(month) if month else (None, None)
    start_after: str | None = None
    start_after_id: str | None = None
    page = 0
    total = 0

    while page < _MAX_CONTACT_PAGES:
        page += 1
        params: dict[str, Any] = {
            "locationId": location_id,
            "limit": _PAGE_SIZE,
        }
        if start_after:
            params["startAfter"] = start_after
        if start_after_id:
            params["startAfterId"] = start_after_id

        data = _ghl_get(client, token, "/contacts/", params=params)
        contacts = data.get("contacts") or []
        print(f"[ghl] página {page}: {len(contacts)} contactos", flush=True)

        for contact in contacts:
            contact_id = contact.get("id")
            if not contact_id:
                continue

            attributions = contact.get("attributions") or []
            came_from_calendar = any(
                str(a.get("mediumId") or "") == calendar_id
                for a in attributions
                if isinstance(a, dict)
            )
            if not came_from_calendar:
                continue

            time.sleep(_REQUEST_DELAY_S)
            appt_data = _ghl_get(client, token, f"/contacts/{contact_id}/appointments")
            events = appt_data.get("events") or []

            for event in events:
                if not isinstance(event, dict):
                    continue
                if event.get("calendarId") != calendar_id:
                    continue
                start_time_raw = str(event.get("startTime") or "")
                if month_start and month_end:
                    if not (month_start <= start_time_raw <= month_end):
                        continue
                status = str(event.get("appointmentStatus") or "").lower()
                if status in ("cancelled", "canceled"):
                    continue
                total += 1
                print(
                    f"[ghl] appointment encontrado: {contact.get('contactName')} {start_time_raw}",
                    flush=True,
                )
                yield {
                    "contact": contact,
                    "appointment": event,
                }

        meta = data.get("meta") or {}
        next_page = meta.get("nextPage")
        if not next_page:
            print(f"[ghl] fin de paginación en página {page}", flush=True)
            break
        start_after = str(meta.get("startAfter") or "")
        start_after_id = str(meta.get("startAfterId") or "")

    print(f"[ghl] total appointments a importar: {total}", flush=True)


def _fetch_contacts_with_appointments(
    client: httpx.Client,
    token: str,
    location_id: str,
    calendar_id: str,
    month: str | None,
) -> list[dict[str, Any]]:
    return list(_iter_contacts_with_appointments(client, token, location_id, calendar_id, month))

@db_session
def _apply_appointment_to_lead(
    user_id: int,
    *,
    name: str,
    email: str,
    phone: str,
    call_at: datetime | None,
    agendo_at: datetime | None,
    ghl_contact_id: str,
) -> str:
    """Upsert lead por email o ghl_contact_id. Returns 'created' o 'updated'."""
    display_name = name.strip() or (email.split("@")[0] if email else "Lead GHL")

    # Buscar lead existente por ghl_contact_id en notas
    row: Lead | None = None
    if ghl_contact_id:
        for r in rows_for_user(Lead, user_id):
            if f"GHL contact_id: {ghl_contact_id}" in str(r.notas or ""):
                row = r
                break

    # Si no encontró por contact_id, buscar por email
    if row is None and email:
        email_key = email.strip().casefold()
        for r in rows_for_user(Lead, user_id):
            if f"ghl email: {email_key}" in str(r.notas or "").casefold():
                row = r
                break

    if row is not None:
        if display_name:
            row.nombre = display_name
        if call_at is not None:
            row.call = call_at
        if agendo_at is not None:
            row.agendo = agendo_at
        row.status = "Agendado"
        row.agendo_en = "GHL"
        row.dias_para_agendar = compute_dias_para_agendar(row.primer_contacto, row.agendo)
        return "updated"

    # Crear nuevo lead con todos los campos requeridos
    notas_parts: list[str] = []
    if email:
        notas_parts.append(f"GHL email: {email}")
    if phone:
        notas_parts.append(f"GHL phone: {phone}")
    if ghl_contact_id:
        notas_parts.append(f"GHL contact_id: {ghl_contact_id}")

    now = datetime.utcnow()
    Lead(
        user_id=user_id,
        nombre=display_name,
        telefono=phone or "",
        origen="GHL",
        notas="\n".join(notas_parts),
        primer_contacto=agendo_at or now,
        call=call_at,
        agendo=agendo_at or call_at,
        status="Agendado",
        agendo_en="GHL",
        dias_para_agendar=compute_dias_para_agendar(agendo_at or now, agendo_at or now),
    )
    return "created"

@router.post("/sync")
def sync_ghl(
    background_tasks: BackgroundTasks,
    user_id: Annotated[str, Depends(require_user_id)],
    body: GHLSyncRequest | None = None,
    month: str | None = Query(default=None, description="YYYY-MM opcional"),
):
    uid = _uid_int(user_id)
    sync_month = (body.month.strip() if body and body.month else None) or (month.strip() if month else None)

    with db_session:
        try:
            conn = ApiConnection.get(user_id=uid, platform="ghl")
        except ObjectNotFound:
            raise HTTPException(status_code=400, detail="No hay conexión GHL.")
        creds = conn.credentials if isinstance(conn.credentials, dict) else {}
        token = str(creds.get("access_token") or "").strip()
        location_id = str(creds.get("location_id") or "").strip()
        calendar_id = str(creds.get("calendar_id") or "").strip()
        if not token or not location_id or not calendar_id:
            raise HTTPException(status_code=400, detail="Faltan credenciales GHL.")

    background_tasks.add_task(_run_ghl_sync, uid, token, location_id, calendar_id, sync_month)
    return {"status": "started", "month": sync_month, "message": "Sync iniciado en background. Los leads aparecerán en minutos."}


def _run_ghl_sync(uid: int, token: str, location_id: str, calendar_id: str, sync_month: str | None) -> None:
    print(f"[ghl] sync background iniciado user_id={uid} month={sync_month}", flush=True)
    created = 0
    updated = 0
    try:
        with httpx.Client(timeout=300.0) as client:
            items = _fetch_contacts_with_appointments(client, token, location_id, calendar_id, sync_month)
            print(f"[ghl] fetch completado: {len(items)} items", flush=True)
            for item in items:
                contact = item["contact"]
                appointment = item["appointment"]
                name = str(contact.get("contactName") or contact.get("firstName") or "").strip()
                email = str(contact.get("email") or "").strip()
                phone = str(contact.get("phone") or "").strip()
                ghl_contact_id = str(contact.get("id") or "").strip()
                call_at = _parse_ghl_datetime(appointment.get("startTime"))
                agendo_at = _parse_ghl_datetime(appointment.get("dateAdded"))
                try:
                    result = _apply_appointment_to_lead(
                        uid,
                        name=name,
                        email=email,
                        phone=phone,
                        call_at=call_at,
                        agendo_at=agendo_at,
                        ghl_contact_id=ghl_contact_id,
                    )
                    print(f"[ghl] lead {result}: {name}", flush=True)
                    if result == "created":
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    print(f"[ghl] ERROR guardando lead {name}: {exc}", flush=True)
        _touch_ghl_last_sync(uid)
        print(f"[ghl] sync background listo created={created} updated={updated}", flush=True)
    except Exception as exc:
        print(f"[ghl] ERROR en sync background: {type(exc).__name__}: {exc}", flush=True)
        import traceback
        traceback.print_exc()

@db_session
def _touch_ghl_last_sync(user_id: int) -> None:
    try:
        conn_row = ApiConnection.get(user_id=user_id, platform="ghl")
        now = datetime.utcnow()
        conn_row.last_sync_at = now
        conn_row.updated_at = now
    except ObjectNotFound:
        pass
