"""Koneksi ke PostgreSQL sebagai akun baca-saja np_dashboard, dengan cache dan pesan error yang ramah."""
import pandas as pd
import psycopg
import streamlit as st

import settings


class DataError(Exception):
    """Kesalahan data/koneksi yang pesannya aman ditampilkan kepada pengguna."""

    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Menjalankan satu query SELECT berparameter dan mengembalikan DataFrame.
    Hasil disimpan 5 menit (cache) menurut kombinasi SQL + parameter. Parameter TIDAK ditempel ke teks SQL
    (dikirim terpisah oleh psycopg), sehingga aman dari SQL injection."""
    try:
        cfg = settings.db_settings()
    except settings.SettingsError as exc:
        raise DataError(str(exc)) from exc
    try:
        with psycopg.connect(**cfg, connect_timeout=5, application_name="np_dashboard_app") as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [c.name for c in cur.description]
                rows = cur.fetchall()
    except psycopg.OperationalError as exc:
        raise DataError(
            "Tidak dapat terhubung ke database PostgreSQL. Pastikan layanan PostgreSQL berjalan, "
            "serta DB_NAME, DASHBOARD_DB_USER, dan DASHBOARD_DB_PASSWORD di file .env sudah benar.",
            detail=str(exc).strip().splitlines()[0] if str(exc).strip() else "") from exc
    except psycopg.errors.InsufficientPrivilege as exc:
        raise DataError("Akun dashboard tidak memiliki hak akses untuk data yang diminta. "
                        "Periksa pengaturan role np_dashboard (sql/08_dashboard_role.sql).",
                        detail=str(exc).strip()) from exc
    except psycopg.Error as exc:
        raise DataError("Query ke database gagal. Pastikan view mart sudah dibuat (sql/07_mart_views.sql).",
                        detail=str(exc).strip().splitlines()[0]) from exc
    return pd.DataFrame(rows, columns=columns)


def show_error(exc: DataError):
    """Menampilkan pesan error ramah lalu menghentikan penggambaran halaman."""
    st.error(str(exc))
    if exc.detail:
        st.caption(f"Detail teknis: {exc.detail}")
    st.stop()


def safe(fn, *args):
    """Memanggil fungsi query; jika gagal, tampilkan pesan ramah (bukan jejak error Python)."""
    try:
        return fn(*args)
    except DataError as exc:
        show_error(exc)
