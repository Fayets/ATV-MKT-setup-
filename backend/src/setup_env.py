"""Lectura/escritura de `backend/.env` para el flujo de primera instalación."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

_BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = _BACKEND_DIR / ".env"


def bootstrap_environment() -> None:
    """Carga `backend/.env` en `os.environ` antes de importar módulos que usan decouple.

    Si falta el archivo o `MANYCHAT_WEBHOOK_TOKEN`, crea/actualiza `.env` (obligatorio para arrancar).
    """
    parsed = _parse_env_file()
    changed = False
    if not (parsed.get("MANYCHAT_WEBHOOK_TOKEN") or os.environ.get("MANYCHAT_WEBHOOK_TOKEN") or "").strip():
        parsed["MANYCHAT_WEBHOOK_TOKEN"] = secrets.token_hex(32)
        changed = True
    if not ENV_PATH.is_file():
        parsed.setdefault("JWT_SECRET", secrets.token_urlsafe(32))
        parsed.setdefault("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        parsed.setdefault("REGISTER_ADMIN_KEY", secrets.token_urlsafe(24))
        changed = True
    if changed:
        _write_env_map(parsed)
    for key, value in _parse_env_file().items():
        os.environ.setdefault(key, value)


def _write_env_map(values: dict[str, str]) -> None:
    """Persiste variables en backend/.env (sin borrar comentarios de plantilla si el archivo no existía)."""
    if ENV_PATH.is_file():
        merged = _parse_env_file()
        merged.update(values)
        values = merged
    lines = ["# backend/.env — no commitear"]
    for key in sorted(values.keys()):
        lines.append(f"{key}={values[key]}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_env_file() -> dict[str, str]:
    if not ENV_PATH.is_file():
        return {}
    out: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def get_database_url() -> str:
    env = _parse_env_file()
    url = (env.get("DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    return url


def is_db_configured() -> bool:
    return bool(get_database_url())


def _parse_postgres_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError("La URL debe ser postgresql://…")
    db_name = (parsed.path or "").lstrip("/").split("?")[0]
    if not db_name:
        raise ValueError("Falta el nombre de la base en la URL")
    qs = parse_qs(parsed.query)
    sslmode = (qs.get("sslmode") or [""])[0] or "require"
    return {
        "DATABASE_URL": url.strip(),
        "DB_PROVIDER": "postgres",
        "DB_USER": unquote(parsed.username or ""),
        "DB_PASS": unquote(parsed.password or ""),
        "DB_HOST": parsed.hostname or "",
        "DB_NAME": db_name,
        "DB_PORT": str(parsed.port or 5432),
        "DB_SSLMODE": sslmode,
    }


def write_env_from_connection_string(connection_string: str) -> None:
    """Valida formato, escribe `.env` y actualiza `os.environ` para decouple."""
    vars_map = _parse_postgres_url(connection_string.strip())
    existing = _parse_env_file()
    jwt = existing.get("JWT_SECRET") or secrets.token_urlsafe(32)
    cors = existing.get("CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000"
    register_key = existing.get("REGISTER_ADMIN_KEY") or secrets.token_urlsafe(24)
    manychat_webhook = (existing.get("MANYCHAT_WEBHOOK_TOKEN") or "").strip() or secrets.token_hex(32)
    site_url = (existing.get("SITE_URL") or "").strip()

    lines = [
        "# Generado por POST /api/setup/db-connect",
        f"DATABASE_URL={vars_map['DATABASE_URL']}",
        f"DB_PROVIDER={vars_map['DB_PROVIDER']}",
        f"DB_USER={vars_map['DB_USER']}",
        f"DB_PASS={vars_map['DB_PASS']}",
        f"DB_HOST={vars_map['DB_HOST']}",
        f"DB_NAME={vars_map['DB_NAME']}",
        f"DB_PORT={vars_map['DB_PORT']}",
        f"DB_SSLMODE={vars_map['DB_SSLMODE']}",
        f"JWT_SECRET={jwt}",
        f"CORS_ORIGINS={cors}",
        f"REGISTER_ADMIN_KEY={register_key}",
        f"MANYCHAT_WEBHOOK_TOKEN={manychat_webhook}",
    ]
    if site_url:
        lines.append(f"SITE_URL={site_url}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env_updates = {
        **vars_map,
        "JWT_SECRET": jwt,
        "CORS_ORIGINS": cors,
        "REGISTER_ADMIN_KEY": register_key,
        "MANYCHAT_WEBHOOK_TOKEN": manychat_webhook,
    }
    if site_url:
        env_updates["SITE_URL"] = site_url
    for key, value in env_updates.items():
        os.environ[key] = value


def load_db_bind_kwargs() -> dict | None:
    """Argumentos para `db.bind()` si hay configuración."""
    url = get_database_url()
    if url:
        return {"provider": "postgres", "dsn": url}

    env = _parse_env_file()
    provider = (env.get("DB_PROVIDER") or os.environ.get("DB_PROVIDER") or "").strip()
    host = (env.get("DB_HOST") or os.environ.get("DB_HOST") or "").strip()
    if not provider or not host:
        return None

    return {
        "provider": provider,
        "user": env.get("DB_USER") or os.environ.get("DB_USER") or "",
        "password": env.get("DB_PASS") or os.environ.get("DB_PASS") or "",
        "host": host,
        "database": env.get("DB_NAME") or os.environ.get("DB_NAME") or "",
    }
