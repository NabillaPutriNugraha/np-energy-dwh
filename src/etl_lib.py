"""Fungsi pendukung ETL: logging ke file, koneksi database, pencatatan run/step
ke tabel ops, dan pemuatan CSV ke staging dengan gerbang validasi."""
import io
import logging
import sys
from contextlib import contextmanager

import pandas as pd
import psycopg

import config


class EtlError(Exception):
    """Kesalahan validasi/proses ETL yang disengaja (bukan bug program)."""


# ---------------------------------------------------------------- logging file
def setup_logging() -> logging.Logger:
    config.LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("etl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for h in (logging.FileHandler(config.LOG_DIR / "etl.log", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)):
            h.setFormatter(fmt)
            logger.addHandler(h)
    return logger


log = setup_logging()


# -------------------------------------------------------------------- koneksi
def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(**config.db_settings(), autocommit=autocommit)


# ------------------------------------------------------ pencatatan run dan step
class RunLogger:
    """Menulis log ke ops.etl_run dan ops.etl_step lewat koneksi AUTOCOMMIT
    yang terpisah, sehingga log tetap tersimpan walau proses muat data di-ROLLBACK."""

    def __init__(self):
        self.conn = None
        self.run_id = None

    def start_run(self) -> int:
        self.conn = connect(autocommit=True)
        self.run_id = self.conn.execute(
            "INSERT INTO ops.etl_run DEFAULT VALUES RETURNING run_id").fetchone()[0]
        log.info("Run ETL dimulai, run_id=%s", self.run_id)
        return self.run_id

    def end_run(self, status: str, error: str | None = None):
        self.conn.execute(
            "UPDATE ops.etl_run SET finished_at = now(), status = %s, error_message = %s "
            "WHERE run_id = %s", (status, error, self.run_id))
        log.info("Run ETL selesai, run_id=%s, status=%s", self.run_id, status)

    @contextmanager
    def step(self, name: str):
        """Mencatat satu langkah. Isi dict 'info' dengan expected/actual/message."""
        step_id = self.conn.execute(
            "INSERT INTO ops.etl_step (run_id, step_name) VALUES (%s, %s) RETURNING step_id",
            (self.run_id, name)).fetchone()[0]
        info = {}
        log.info("MULAI   %s", name)
        try:
            yield info
        except Exception as exc:
            self._end_step(step_id, "FAILED", info, str(exc))
            log.error("GAGAL   %s: %s", name, exc)
            raise
        self._end_step(step_id, "SUCCESS", info, info.get("message"))
        log.info("SELESAI %s | diharapkan=%s | aktual=%s", name,
                 info.get("expected"), info.get("actual"))

    def _end_step(self, step_id, status, info, message):
        self.conn.execute(
            "UPDATE ops.etl_step SET finished_at = now(), status = %s, rows_expected = %s, "
            "rows_actual = %s, message = %s WHERE step_id = %s",
            (status, info.get("expected"), info.get("actual"),
             (message or "")[:1000], step_id))

    def close(self):
        if self.conn is not None:
            self.conn.close()


# ------------------------------------------------------------ langkah: preflight
def preflight(run: RunLogger):
    """Memastikan semua syarat tersedia sebelum data disentuh."""
    with run.step("preflight") as info:
        missing = [p.name for p in (config.EMBER_CSV, config.RENEWABLE_CSV) if not p.exists()]
        if missing:
            raise EtlError(f"File CSV tidak ditemukan di data/processed: {missing}. "
                           "Jalankan python src/preprocess.py terlebih dahulu.")
        rows = run.conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'stg' AND table_name IN ('ember_generation','renewable_energy')"
        ).fetchall()
        if len(rows) != 2:
            raise EtlError("Tabel staging belum lengkap. Jalankan sql/02_staging_tables.sql.")
        info["message"] = "CSV ada dan tabel staging tersedia"


# --------------------------------------------------------- langkah: load staging
AUDIT_COLUMNS = {"stg_row_id", "batch_id", "source_file", "loaded_at"}

# Peta target: tabel staging, file CSV, dan kunci alami untuk cek duplikasi.
STAGING_TARGETS = [
    {"table": "stg.ember_generation", "csv": config.EMBER_CSV,
     "keys": ["iso_3_code", "year", "electricity_source"]},
    {"table": "stg.renewable_energy", "csv": config.RENEWABLE_CSV,
     "keys": ["iso_code", "year"]},
]


def _staging_name(csv_column: str) -> str:
    """Aturan pemetaan kolom CSV -> kolom staging: tanda '/' diganti '_'."""
    return csv_column.replace("/", "_")


def _prepare_frame(target: dict, batch_id: int, conn) -> pd.DataFrame:
    df = pd.read_csv(target["csv"])
    df.columns = [_staging_name(c) for c in df.columns]

    # 1. Pemetaan kolom harus cocok persis dengan tabel staging.
    schema, table = target["table"].split(".")
    db_cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s", (schema, table)).fetchall()}
    db_data_cols = db_cols - AUDIT_COLUMNS
    csv_cols = set(df.columns)
    if csv_cols != db_data_cols:
        raise EtlError(f"Kolom {target['csv'].name} tidak cocok dengan {target['table']}. "
                       f"Hanya di CSV: {sorted(csv_cols - db_data_cols)}; "
                       f"hanya di tabel: {sorted(db_data_cols - csv_cols)}")

    # 2. Kunci tidak boleh kosong (tidak ada imputasi).
    for key in target["keys"]:
        n_null = int(df[key].isna().sum())
        if n_null:
            raise EtlError(f"{target['csv'].name}: kolom kunci '{key}' kosong pada {n_null} baris")

    # 3. Validasi tahun harus bilangan bulat
    year_numeric = pd.to_numeric(df["year"], errors="coerce")

    if year_numeric.isna().any():
        raise EtlError(
            f"{target['csv'].name}: terdapat nilai tahun kosong atau tidak valid"
        )

    if not year_numeric.mod(1).eq(0).all():
        raise EtlError(
            f"{target['csv'].name}: terdapat nilai tahun yang bukan bilangan bulat"
        )

    df["year"] = year_numeric.astype("int64")

    df.insert(0, "source_file", target["csv"].name)
    df.insert(0, "batch_id", batch_id)
    return df


def load_staging(run: RunLogger):
    """Kosongkan staging lalu muat kedua CSV dalam SATU transaksi.
    Jika ada gerbang validasi yang gagal, semuanya di-ROLLBACK dan isi staging lama utuh."""
    with run.step("load_staging") as info:
        total_expected = total_actual = 0
        details = []
        with connect() as conn:  # commit jika sukses, rollback otomatis jika ada error
            conn.execute("TRUNCATE stg.ember_generation, stg.renewable_energy RESTART IDENTITY")
            for t in STAGING_TARGETS:
                df = _prepare_frame(t, run.run_id, conn)
                cols = ", ".join(df.columns)
                buf = io.StringIO()
                df.to_csv(buf, index=False, header=False, na_rep="", lineterminator="\n")
                with conn.cursor() as cur:
                    with cur.copy(f"COPY {t['table']} ({cols}) FROM STDIN "
                                  "WITH (FORMAT csv, NULL '')") as cp:
                        cp.write(buf.getvalue())

                # Gerbang 1: jumlah baris staging harus sama dengan jumlah baris CSV.
                actual = conn.execute(
                    f"SELECT count(*) FROM {t['table']} WHERE batch_id = %s",
                    (run.run_id,)).fetchone()[0]
                if actual != len(df):
                    raise EtlError(f"{t['table']}: baris CSV={len(df)} tetapi staging={actual}")

                # Gerbang 2: tidak boleh ada duplikasi pada kunci alami.
                keys = ", ".join(t["keys"])
                dup = conn.execute(
                    f"SELECT count(*) FROM (SELECT 1 FROM {t['table']} "
                    f"GROUP BY {keys} HAVING count(*) > 1) d").fetchone()[0]
                if dup:
                    raise EtlError(f"{t['table']}: ada {dup} kombinasi ({keys}) yang duplikat")

                log.info("  %s: CSV=%d, staging=%d, duplikat kunci=0", t["table"], len(df), actual)
                total_expected += len(df)
                total_actual += actual
                details.append(f"{t['table']}={actual}/{len(df)}")
        info.update(expected=total_expected, actual=total_actual, message="; ".join(details))
