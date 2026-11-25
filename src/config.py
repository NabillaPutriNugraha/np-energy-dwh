"""Konfigurasi proyek: lokasi file dan pengaturan koneksi database.
Password dibaca dari file .env (tidak pernah ditulis di kode)."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

PROCESSED = ROOT / "data" / "processed"
LOG_DIR = ROOT / "logs"

# File hasil preprocessing (Fase 1) yang menjadi input ETL.
EMBER_CSV = PROCESSED / "ember_cleaned_2019_2023.csv"
RENEWABLE_CSV = PROCESSED / "renewable_cleaned_2019_2023.csv"


class ConfigError(Exception):
    """Dilempar jika konfigurasi wajib belum diisi."""


def db_settings() -> dict:
    password = os.getenv("DB_PASSWORD")
    if not password or password.startswith("isi_password"):
        raise ConfigError(
            "DB_PASSWORD belum diisi. Salin .env.example menjadi .env, "
            "lalu isi password PostgreSQL Anda di file .env."
        )
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "np_energy_dw"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": password,
    }
