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

    db.generate_mapping(create_tables=False, check_tables=False)

    with db_session:
        def _table_exists(table: str) -> bool:
            cur = db.execute(
                f"""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = '{table}'
                LIMIT 1
                """
            )
            return cur.fetchone() is not None

        def _setter_table_exists() -> bool:
            return _table_exists("setter_report")

        def _setter_has_column(column: str) -> bool:
            cur = db.execute(
                f"""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'setter_report'
                  AND column_name = '{column}'
                LIMIT 1
                """
            )
            return cur.fetchone() is not None

        def _setter_rename_column(old: str, new: str) -> None:
            if _setter_has_column(old) and not _setter_has_column(new):
                db.execute(f'ALTER TABLE setter_report RENAME COLUMN "{old}" TO "{new}"')

        if _setter_table_exists():
            # Orden: el agendas_ads histórico (campo suelto, dato real) pasa a youtube_directo
            # ANTES de reutilizar el nombre agendas_ads para el canal ex-WhatsApp.
            _setter_rename_column("agendas_ads", "agendas_youtube_directo")
            _setter_rename_column("agendas_whatsapp", "agendas_ads")
            _setter_rename_column("conversaciones_whatsapp", "conversaciones_ads")
            _setter_rename_column("links_enviados_whatsapp", "links_enviados_ads")

            for col, tipo in [
                ("conversaciones_stories", "INTEGER NOT NULL DEFAULT 0"),
                ("conversaciones_reels", "INTEGER NOT NULL DEFAULT 0"),
                ("conversaciones_youtube", "INTEGER NOT NULL DEFAULT 0"),
                ("conversaciones_ads", "INTEGER NOT NULL DEFAULT 0"),
                ("chats_youtube", "INTEGER NOT NULL DEFAULT 0"),
                ("chats_ads", "INTEGER NOT NULL DEFAULT 0"),
                ("agendas_stories", "INTEGER NOT NULL DEFAULT 0"),
                ("agendas_reels", "INTEGER NOT NULL DEFAULT 0"),
                ("agendas_youtube", "INTEGER NOT NULL DEFAULT 0"),
                ("agendas_ads", "INTEGER NOT NULL DEFAULT 0"),
                ("agendas_youtube_directo", "INTEGER NOT NULL DEFAULT 0"),
                ("links_enviados_stories", "INTEGER NOT NULL DEFAULT 0"),
                ("links_enviados_reels", "INTEGER NOT NULL DEFAULT 0"),
                ("links_enviados_youtube", "INTEGER NOT NULL DEFAULT 0"),
                ("links_enviados_ads", "INTEGER NOT NULL DEFAULT 0"),
            ]:
                db.execute(f"""
                    ALTER TABLE setter_report
                    ADD COLUMN IF NOT EXISTS {col} {tipo}
                """)

        if _table_exists("closer_report"):
            for col, tipo in [
                ("shows_organico", "INTEGER NOT NULL DEFAULT 0"),
                ("shows_ads", "INTEGER NOT NULL DEFAULT 0"),
                ("cierres_organico", "INTEGER NOT NULL DEFAULT 0"),
                ("cierres_ads", "INTEGER NOT NULL DEFAULT 0"),
                ("reservas", "INTEGER NOT NULL DEFAULT 0"),
                ("seguimiento", "INTEGER NOT NULL DEFAULT 0"),
                ("facturacion", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
            ]:
                db.execute(f"""
                    ALTER TABLE closer_report
                    ADD COLUMN IF NOT EXISTS {col} {tipo}
                """)

        if _table_exists("lead"):
            for col, tipo in [
                ("ingresos_rango", "VARCHAR DEFAULT ''"),
                ("email", "VARCHAR DEFAULT ''"),
                ("objetivo", "VARCHAR DEFAULT ''"),
            ]:
                db.execute(f"""
                    ALTER TABLE lead
                    ADD COLUMN IF NOT EXISTS {col} {tipo}
                """)

    db.create_tables(check_tables=True)

    print(f"[db] Base de datos lista ({time.time() - t0:.1f}s)")
