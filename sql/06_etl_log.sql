-- Log ETL di dalam database. Ditulis lewat koneksi terpisah (autocommit) supaya
-- catatan kegagalan tidak ikut hilang ketika proses muat data di-ROLLBACK.
CREATE SCHEMA IF NOT EXISTS ops;
COMMENT ON SCHEMA ops IS 'Operasional: log eksekusi ETL';

-- Satu baris per eksekusi ETL (satu kali menjalankan run_etl.py).
CREATE TABLE IF NOT EXISTS ops.etl_run (
    run_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
    error_message TEXT
);

-- Satu baris per langkah di dalam sebuah eksekusi.
CREATE TABLE IF NOT EXISTS ops.etl_step (
    step_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES ops.etl_run(run_id),
    step_name     TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','SUCCESS','FAILED')),
    rows_expected BIGINT,
    rows_actual   BIGINT,
    message       TEXT
);
CREATE INDEX IF NOT EXISTS ix_etl_step_run ON ops.etl_step (run_id);
