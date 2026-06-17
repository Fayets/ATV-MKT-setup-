#!/usr/bin/env python3
"""Datos de prueba locales. Uso: desde backend/ → python seed.py"""

from __future__ import annotations

from datetime import datetime, timedelta

from pony.orm import db_session

from src.db import init_db
from src.models import ApiConnection, AuthUser, Lead
from src.setup_env import bootstrap_environment

BIO_SEED_IG_PREFIX = "bio_seed_"
BIO_KEYWORD_DEFAULT = "info"


def _bio_keyword_for_user(uid: int) -> str:
    with db_session:
        rows = [c for c in list(ApiConnection.select()) if int(c.user_id) == uid and c.platform == "manychat"]
        if not rows:
            return BIO_KEYWORD_DEFAULT
        creds = rows[0].credentials if isinstance(rows[0].credentials, dict) else {}
        raw = str(creds.get("bio_keyword") or "").strip()
        return raw.lower() if raw else BIO_KEYWORD_DEFAULT


def seed_bio_leads(*, user_id: int | None = None, force: bool = False) -> int:
    """Inserta 5 leads BIO de prueba (keyword del perfil ManyChat). Idempotente por prefijo IG."""
    init_db()
    with db_session:
        if user_id is None:
            users = list(AuthUser.select())
            if not users:
                raise RuntimeError("No hay usuarios. Completá /setup antes de correr el seed.")
            user_id = int(users[0].id)

        uid = int(user_id)
        bio_kw = _bio_keyword_for_user(uid)

        existing = [
            r
            for r in list(Lead.select())
            if int(r.user_id) == uid and str(r.ig or "").startswith(BIO_SEED_IG_PREFIX)
        ]
        if existing and not force:
            print(f"Seed BIO: ya existen {len(existing)} leads ({BIO_SEED_IG_PREFIX}*). Usá force=True para recrear.")
            return 0

        if existing and force:
            for row in existing:
                row.delete()

        now = datetime.utcnow()
        base = now.replace(day=min(10, now.day), hour=12, minute=0, second=0, microsecond=0)

        samples = [
            {
                "ig": f"{BIO_SEED_IG_PREFIX}ana_fit",
                "nombre": "Ana BIO (seed)",
                "keyword": bio_kw,
                "via": "Perfil",
                "status": "Cerrado",
                "respondio_auto": True,
                "agendo": base - timedelta(days=5),
                "pago": 800.0,
                "programa_ofrecido": "Boost",
                "setter": "Setter Demo",
            },
            {
                "ig": f"{BIO_SEED_IG_PREFIX}lucas_coach",
                "nombre": "Lucas BIO (seed)",
                "keyword": bio_kw,
                "via": "Automático - ManyChat",
                "status": "Agendado",
                "respondio_auto": False,
                "agendo": base - timedelta(days=3),
                "pago": 0.0,
                "programa_ofrecido": "Mentoría",
                "setter": "Setter Demo",
            },
            {
                "ig": f"{BIO_SEED_IG_PREFIX}maria_pro",
                "nombre": "María BIO (seed)",
                "keyword": bio_kw,
                "via": "Perfil",
                "status": "En conversación",
                "respondio_auto": True,
                "agendo": None,
                "pago": 0.0,
                "programa_ofrecido": "",
                "setter": "",
            },
            {
                "ig": f"{BIO_SEED_IG_PREFIX}juan_vip",
                "nombre": "Juan BIO (seed)",
                "keyword": bio_kw,
                "via": "Perfil",
                "status": "Cerrado",
                "respondio_auto": True,
                "agendo": base - timedelta(days=1),
                "pago": 1200.0,
                "programa_ofrecido": "Elite",
                "setter": "Setter Demo",
            },
            {
                "ig": f"{BIO_SEED_IG_PREFIX}sofia_new",
                "nombre": "Sofía BIO (seed)",
                "keyword": bio_kw,
                "via": "Referido",
                "status": "Nuevo",
                "respondio_auto": False,
                "agendo": None,
                "pago": 0.0,
                "programa_ofrecido": "",
                "setter": "",
            },
        ]

        created = 0
        for i, s in enumerate(samples):
            bot_at = base - timedelta(days=7 - i)
            agendo_dt = s["agendo"]
            Lead(
                user_id=uid,
                nombre=s["nombre"],
                ig=s["ig"],
                keyword=s["keyword"],
                origen="Perfil",
                via=s["via"],
                status=s["status"],
                estado=s["status"],
                respondio_auto=bool(s["respondio_auto"]),
                fecha_bot=bot_at,
                created_at=bot_at,
                agendo=agendo_dt,
                agendo_en="Chat" if agendo_dt else "",
                pago=float(s["pago"]),
                programa_ofrecido=s["programa_ofrecido"],
                setter=s["setter"],
                punto_agenda="bio",
                content_url=f"https://manychat.example/{s['ig']}",
            )
            created += 1

        print(f"Seed BIO: {created} leads creados para user_id={uid} (keyword={bio_kw!r}).")
        return created


def main() -> None:
    bootstrap_environment()
    seed_bio_leads()


if __name__ == "__main__":
    main()
