
"""Pengaturan dashboard: membaca konfigurasi lokal atau Streamlit Secrets.
Dashboard memakai akun BACA-SAJA (np_dashboard), bukan akun ETL/admin.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class SettingsError(Exception):
    """Dilempar jika konfigurasi akun dashboard belum diisi."""


def _secret_or_env(key: str, default: str | None = None) -> str | None:
    """Ambil nilai dari Streamlit Secrets jika tersedia, lalu fallback ke .env."""
    try:
        import streamlit as st

        value = st.secrets.get(key)
        if value is not None and str(value).strip():
            return str(value)
    except Exception:
        pass

    return os.getenv(key, default)


def db_settings() -> dict:
    user = _secret_or_env("DASHBOARD_DB_USER")
    password = _secret_or_env("DASHBOARD_DB_PASSWORD")

    if (
        not user
        or not password
        or password.startswith("isi_password")
    ):
        raise SettingsError(
            "Akun dashboard belum dikonfigurasi. "
            "Untuk lokal, isi DASHBOARD_DB_USER dan DASHBOARD_DB_PASSWORD "
            "di file .env. Untuk Streamlit Cloud, isi keduanya di Secrets."
        )

    host = _secret_or_env("DB_HOST", "localhost")

    return {
        "host": host,
        "port": int(_secret_or_env("DB_PORT", "5432")),
        "dbname": _secret_or_env("DB_NAME", "np_energy_dw"),
        "user": user,
        "password": password,
        "sslmode": "disable" if host in ("localhost", "127.0.0.1", "::1") else "require",
    }
