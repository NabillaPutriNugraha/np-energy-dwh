"""Menjalankan ETL. Fase 3A: preflight dan pemuatan CSV ke staging.
Fase 3B-1: pemuatan dimensi ke Data Warehouse (tabel fakta menyusul di 3B-2).
Jalankan dari folder proyek:  python src/run_etl.py
Hanya staging (perilaku Fase 3A):  python src/run_etl.py --staging-only
Kode keluar: 0 = sukses, 1 = ETL gagal, 2 = masalah konfigurasi/koneksi."""
import argparse
import sys

import psycopg

import config
from etl_lib import EtlError, RunLogger, load_staging, log, preflight
from load_dw import load_dw


def main(staging_only: bool = False) -> int:
    log.info("=" * 70)
    log.info("ETL dimulai")
    try:
        config.db_settings()
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 2

    run = RunLogger()
    try:
        run.start_run()
    except psycopg.OperationalError as exc:
        log.error("Tidak dapat terhubung ke PostgreSQL. Periksa layanan PostgreSQL, "
                  "nama database, user, dan password di .env. Detail: %s", str(exc).strip())
        return 2
    except psycopg.errors.UndefinedTable:
        log.error("Tabel log belum ada. Jalankan sql/06_etl_log.sql di pgAdmin terlebih dahulu.")
        return 2

    try:
        preflight(run)
        load_staging(run)
        if not staging_only:
            load_dw(run)
        run.end_run("SUCCESS")
        return 0
    except (EtlError, psycopg.Error) as exc:
        run.end_run("FAILED", str(exc))
        log.error("ETL GAGAL: %s", exc)
        return 1
    except Exception as exc:  # kesalahan tak terduga (bug)
        run.end_run("FAILED", f"{type(exc).__name__}: {exc}")
        log.exception("ETL GAGAL karena kesalahan tak terduga")
        return 1
    finally:
        run.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ETL NP Energy Intelligence")
    ap.add_argument("--staging-only", action="store_true",
                    help="hanya memuat staging (perilaku Fase 3A)")
    sys.exit(main(staging_only=ap.parse_args().staging_only))
