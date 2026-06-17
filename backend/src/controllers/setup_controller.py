import uuid
from datetime import datetime
from pathlib import Path

import bcrypt
import psycopg2
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pony.orm import db_session
from pydantic import BaseModel, Field

from src.db import ensure_db_bound, init_db
from src.models import AuthUser, CompanyConfig
from src.setup_env import is_db_configured, write_env_from_connection_string

router = APIRouter(prefix="/api/setup", tags=["setup"])

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
LOGO_DIR = _BACKEND_DIR / "media" / "logo"
ALLOWED_LOGO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_LOGO_BYTES = 6 * 1024 * 1024


class DbConnectBody(BaseModel):
    connection_string: str = Field(min_length=8)


class SetupInitBody(BaseModel):
    company_name: str = Field(min_length=1)
    company_tagline: str = ""
    logo_url: str = ""
    username: str = Field(min_length=1)
    password: str = Field(min_length=6)


def _system_has_user() -> bool:
    if not is_db_configured() or not ensure_db_bound():
        return False
    with db_session:
        return AuthUser.select().count() > 0


@router.get("/db-status")
def db_status():
    return {"configured": is_db_configured()}


@router.post("/db-connect")
def db_connect(body: DbConnectBody):
    conn_str = body.connection_string.strip()
    if not conn_str:
        return {"success": False, "error": "La cadena de conexión no puede estar vacía."}

    try:
        conn = psycopg2.connect(conn_str)
        conn.close()
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    try:
        write_env_from_connection_string(conn_str)
        if not ensure_db_bound():
            return {"success": False, "error": "No se pudo enlazar la base de datos."}
        init_db()
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {"success": True}


@router.get("/status")
def setup_status():
    return {"configured": _system_has_user()}


@router.get("/config")
def setup_config():
    if not is_db_configured() or not ensure_db_bound():
        return {
            "company_name": "ATV",
            "company_tagline": "",
            "logo_url": "",
        }

    with db_session:
        row = CompanyConfig.get(id=1)
        if not row:
            return {
                "company_name": "ATV",
                "company_tagline": "",
                "logo_url": "",
            }
        return {
            "company_name": row.company_name,
            "company_tagline": row.company_tagline or "",
            "logo_url": row.logo_url or "",
        }


@router.post("/upload-logo")
async def upload_logo(file: UploadFile = File(...)):
    if not is_db_configured() or not ensure_db_bound():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base de datos no configurada")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_LOGO_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no permitido. Usá jpeg, png, webp o gif.",
        )

    data = await file.read()
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo supera 6 MB.")

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = LOGO_DIR / name
    dest.write_bytes(data)

    return {"url": f"/media/logo/{name}"}


@router.post("/init")
def setup_init(body: SetupInitBody):
    if not is_db_configured() or not ensure_db_bound():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base de datos no configurada")

    username = body.username.strip()
    company_name = body.company_name.strip()
    if not username or not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario y empresa son obligatorios.")

    with db_session:
        if AuthUser.select().count() > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El sistema ya fue inicializado.",
            )

        password_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        now = datetime.utcnow()
        AuthUser(username=username, password_hash=password_hash, updated_at=now)
        CompanyConfig(
            id=1,
            company_name=company_name,
            company_tagline=(body.company_tagline or "").strip(),
            logo_url=(body.logo_url or "").strip(),
            updated_at=now,
        )

    return {"success": True}
