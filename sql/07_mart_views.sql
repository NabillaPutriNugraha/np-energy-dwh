-- Lapisan data mart untuk dashboard: view SQL di schema "mart".
-- Fungsi: (1) satu tempat untuk gabungan fakta + dimensi, sehingga dashboard tidak berisi join rumit;
--         (2) dashboard cukup diberi hak baca pada schema ini (least privilege).
-- View bersifat baca-saja dan selalu mengikuti isi DW terbaru (bukan salinan data).
-- Aman dijalankan berulang (CREATE OR REPLACE).

CREATE SCHEMA IF NOT EXISTS mart;
COMMENT ON SCHEMA mart IS 'Data mart untuk dashboard: view baca-saja di atas schema dw';

-- 1) Satu baris per negara per tahun (gabungan fakta energi dan fakta emisi).
-- FULL OUTER JOIN: Kosovo (XKX) hanya ada di Ember dan 12 negara hanya ada di Renewable;
-- dengan INNER/LEFT JOIN salah satunya akan hilang dari dashboard.
-- Kolom yang tidak tersedia dari salah satu sumber dibiarkan NULL (tidak diisi/diimputasi).
CREATE OR REPLACE VIEW mart.v_country_year AS
SELECT c.iso3_code::text                      AS iso3_code,
       c.country_name,
       c.continent,
       c.ember_region,
       g.group_label,
       y.year_value                           AS year,
       -- dari fact_energy_country_year (sumber: Renewable Energy Share)
       n.renewables_share_elec,
       n.fossil_share_elec,
       n.low_carbon_share_elec,
       n.renewables_share_energy,
       n.fossil_share_energy,
       n.low_carbon_share_energy,
       n.electricity_generation               AS electricity_generation_twh,
       -- dari fact_emissions_country_year (sumber: Ember)
       m.total_generation_twh,
       m.renewables_generation_twh,
       m.renewables_share_pct                 AS ember_renewables_share_pct,
       m.total_emissions_mtco2e,
       m.emissions_intensity_gco2e_kwh,
       -- indikator kelengkapan (bukan penilaian seluruh baris)
       qn.status_name                         AS energy_quality_status,
       qm.status_name                         AS emissions_quality_status,
       (n.energy_fact_key IS NOT NULL)        AS has_energy_fact,
       (m.emissions_fact_key IS NOT NULL)     AS has_emissions_fact
FROM dw.fact_energy_country_year n
FULL OUTER JOIN dw.fact_emissions_country_year m
       ON m.country_key = n.country_key AND m.year_key = n.year_key
JOIN dw.dim_country c        ON c.country_key = COALESCE(n.country_key, m.country_key)
JOIN dw.dim_year y           ON y.year_key    = COALESCE(n.year_key, m.year_key)
JOIN dw.dim_country_group g  ON g.country_group_key = COALESCE(m.country_group_key, n.country_group_key)
LEFT JOIN dw.dim_quality_status qn ON qn.quality_key = n.quality_key
LEFT JOIN dw.dim_quality_status qm ON qm.quality_key = m.quality_key;
COMMENT ON VIEW mart.v_country_year IS
 'Negara x tahun: pangsa listrik/energi (Renewable), pembangkitan dan intensitas emisi (Ember), status kelengkapan';

-- 2) Satu baris per negara per tahun per sumber listrik murni (bauran pembangkitan, analisis C).
-- Kelompok negara diambil dari fact_emissions (negara Ember); jika tidak ada, "Tidak diketahui".
CREATE OR REPLACE VIEW mart.v_generation_mix AS
SELECT c.iso3_code::text                      AS iso3_code,
       c.country_name,
       c.continent,
       c.ember_region,
       COALESCE(g.group_label, 'Tidak diketahui') AS group_label,
       y.year_value                           AS year,
       s.source_name,
       s.source_category,
       s.is_renewable,
       f.generation_twh,
       f.share_of_generation_pct,
       f.capacity_gw,
       f.emissions_mtco2e,
       q.status_name                          AS quality_status
FROM dw.fact_generation_source f
JOIN dw.dim_country c             ON c.country_key = f.country_key
JOIN dw.dim_year y                ON y.year_key    = f.year_key
JOIN dw.dim_electricity_source s  ON s.source_key  = f.source_key
JOIN dw.dim_quality_status q      ON q.quality_key = f.quality_key
LEFT JOIN dw.fact_emissions_country_year m
       ON m.country_key = f.country_key AND m.year_key = f.year_key
LEFT JOIN dw.dim_country_group g  ON g.country_group_key = m.country_group_key;
COMMENT ON VIEW mart.v_generation_mix IS
 'Negara x tahun x sumber listrik murni (Ember): pembangkitan, pangsa, kapasitas, emisi';

-- 3) Perbandingan dua sumber untuk indikator yang sama (halaman Kualitas Data dan Metodologi).
-- Hanya negara-tahun yang ada di KEDUA sumber. selisih_persen NULL jika nilai Renewable 0 atau kosong.
CREATE OR REPLACE VIEW mart.v_source_comparison AS
SELECT c.iso3_code::text                      AS iso3_code,
       c.country_name,
       y.year_value                           AS year,
       m.total_generation_twh                 AS ember_generation_twh,
       n.electricity_generation               AS renewable_generation_twh,
       round((100 * (m.total_generation_twh / NULLIF(n.electricity_generation, 0) - 1))::numeric, 2)
                                              AS selisih_persen,
       m.renewables_share_pct                 AS ember_renewables_share_pct,
       n.renewables_share_elec                AS renewable_renewables_share_pct
FROM dw.fact_energy_country_year n
JOIN dw.fact_emissions_country_year m
       ON m.country_key = n.country_key AND m.year_key = n.year_key
JOIN dw.dim_country c ON c.country_key = n.country_key
JOIN dw.dim_year y    ON y.year_key    = n.year_key;
COMMENT ON VIEW mart.v_source_comparison IS
 'Ember vs Renewable untuk negara-tahun yang ada di keduanya (pembangkitan dan pangsa terbarukan)';

-- 4) Status ETL terakhir yang benar-benar MEMUAT DW (lineage/kesegaran data di dashboard).
-- Run "--staging-only" tidak dihitung, karena tidak mengubah isi DW.
-- Dashboard tidak perlu hak akses ke schema ops: view dijalankan dengan hak pemilik view.
CREATE OR REPLACE VIEW mart.v_etl_status AS
SELECT r.run_id,
       r.started_at,
       r.finished_at,
       r.status,
       s.rows_actual AS rows_loaded_dw
FROM ops.etl_run r
JOIN ops.etl_step s ON s.run_id = r.run_id AND s.step_name = 'load_dw' AND s.status = 'SUCCESS'
WHERE r.status = 'SUCCESS'
ORDER BY r.run_id DESC
LIMIT 1;
COMMENT ON VIEW mart.v_etl_status IS 'Satu baris: eksekusi ETL terakhir yang sukses memuat Data Warehouse (load_dw)';
