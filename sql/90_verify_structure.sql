-- Verifikasi struktur: hasil yang diharapkan tertulis di komentar.
-- 1) Tabel per skema (harapan: stg=2, dw=9)
SELECT table_schema, count(*) AS jumlah_tabel
FROM information_schema.tables
WHERE table_schema IN ('stg','dw') AND table_type='BASE TABLE'
GROUP BY table_schema ORDER BY table_schema;

-- 2) Jumlah kolom staging (harapan: ember_generation=28, renewable_energy=37)
SELECT table_name, count(*) AS jumlah_kolom
FROM information_schema.columns WHERE table_schema='stg'
GROUP BY table_name ORDER BY table_name;

-- 3) Foreign key (harapan: 15 = 3 fakta x dimensi: 5+5+5)
SELECT conrelid::regclass AS tabel_fakta, count(*) AS jumlah_fk
FROM pg_constraint WHERE contype='f' AND connamespace='dw'::regnamespace
GROUP BY conrelid ORDER BY 1;

-- 4) Baris data referensi (harapan: year=5, source=9, data_source=2, quality=2, group=1, country=0)
SELECT 'dim_year' AS tabel, count(*) FROM dw.dim_year
UNION ALL SELECT 'dim_electricity_source', count(*) FROM dw.dim_electricity_source
UNION ALL SELECT 'dim_data_source', count(*) FROM dw.dim_data_source
UNION ALL SELECT 'dim_quality_status', count(*) FROM dw.dim_quality_status
UNION ALL SELECT 'dim_country_group', count(*) FROM dw.dim_country_group
UNION ALL SELECT 'dim_country', count(*) FROM dw.dim_country;
