import time

from pony.orm import *

db = Database()
_db_bound = False


def ensure_db_bound() -> bool:
    """Enlaza Pony con Postgres cuando existe `DATABASE_URL` o variables DB_* en `.env`."""
    global _db_bound
    if _db_bound:
        return True
    from src.setup_env import load_db_bind_kwargs

    kwargs = load_db_bind_kwargs()
    if not kwargs:
        return False
    db.bind(**kwargs)
    _db_bound = True
    return True


def init_db() -> None:
    if not ensure_db_bound():
        raise RuntimeError("Base de datos no configurada. Configurá DATABASE_URL en backend/.env.")

    t0 = time.time()
    print("[db] Inicializando base de datos...")

    import src.models  # noqa: F401 — registrar entidades Pony antes del mapping

    db.generate_mapping(create_tables=True)

    print(f"[db] Base de datos lista ({time.time() - t0:.1f}s)")
