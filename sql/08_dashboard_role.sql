-- Role database untuk dashboard (RBAC, least privilege). Jalankan SETELAH 07_mart_views.sql.
-- Prinsip: dashboard hanya boleh MEMBACA view di schema mart; tidak boleh membaca stg/dw/ops dan tidak boleh menulis.
-- Pembagian dua role:
--   np_dashboard_reader : role KELOMPOK (NOLOGIN) yang memegang hak akses. File ini membuatnya.
--   np_dashboard        : role LOGIN yang dipakai aplikasi. Dibuat lewat 08b_dashboard_login_template.sql
--                         dengan password yang Anda ketik sendiri (password tidak boleh ada di repositori).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'np_dashboard_reader') THEN
        CREATE ROLE np_dashboard_reader NOLOGIN;
    END IF;
END $$;

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO np_dashboard_reader', current_database());
END $$;

GRANT USAGE ON SCHEMA mart TO np_dashboard_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO np_dashboard_reader;      -- semua view mart yang ada sekarang
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO np_dashboard_reader;  -- view mart di masa depan

-- Tidak ada GRANT apa pun pada schema stg, dw, dan ops: akses ke sana ditolak secara default.
COMMENT ON ROLE np_dashboard_reader IS 'Hak baca-saja pada schema mart untuk dashboard BI';
