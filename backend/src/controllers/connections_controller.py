"""Conexiones API durante el setup (sin JWT; usa el primer AuthUser)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pony.orm import db_session

from src.db import ensure_db_bound
from src.models import AuthUser
from src.schemas import ApiConnectionResponse, ApiConnectionUpsertRequest
from src.services.conexiones_services import ConexionesServices
from src.setup_env import is_db_configured

router = APIRouter(prefix="/api/connections", tags=["connections-setup"])
service = ConexionesServices()


def _first_user_id() -> int:
    if not is_db_configured() or not ensure_db_bound():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base de datos no configurada")
    with db_session:
        user = AuthUser.select().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completá el onboarding antes de configurar APIs.",
            )
        return user.id


@router.get("", response_model=list[ApiConnectionResponse])
def list_connections(user_id: Annotated[int, Depends(_first_user_id)]) -> list[ApiConnectionResponse]:
    try:
        return service.list_by_user(user_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error al listar conexiones.")


@router.post("/{platform}", response_model=ApiConnectionResponse)
def upsert_connection(
    platform: str,
    body: ApiConnectionUpsertRequest,
    user_id: Annotated[int, Depends(_first_user_id)],
) -> ApiConnectionResponse:
    try:
        return service.upsert(user_id, platform, body)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error al guardar la conexión.")
