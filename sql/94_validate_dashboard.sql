-- Validasi lapisan data mart dan hak akses dashboard (Tahap 4-1).
-- Jalankan di pgAdmin (database np_energy_dw) SETELAH 07_mart_views.sql dan 08_dashboard_role.sql.
-- Tujuan: membuktikan bahwa angka yang nanti tampil di dashboard (diambil dari view mart)
-- sama dengan angka yang dihitung langsung dari tabel fakta di Data Warehouse.

-- D1) Jumlah baris view vs sumbernya
-- harapan: baris_view sama dengan pembanding pada setiap baris (1105, 9118, 1039)
SELECT 'v_country_year (negara x tahun)' AS view_mart,
       (SELECT count(*) FROM mart.v_country_year) AS baris_view,
       (SELECT count(*) FROM (SELECT iso_code, year FROM stg.renewable_energy
                              UNION
                              SELECT iso_3_code, year FROM stg.ember_generation
                              WHERE electricity_source = 'Total generation') u) AS pembanding_dari_staging
UNION ALL
SELECT 'v_generation_mix (negara x tahun x sumber)',
       (SELECT count(*) FROM mart.v_generation_mix),
       (SELECT count(*) FROM dw.fact_generation_source)
UNION ALL
SELECT 'v_source_comparison (ada di kedua sumber)',
       (SELECT count(*) FROM mart.v_source_comparison),
       (SELECT count(*) FROM dw.fact_energy_country_year n
        JOIN dw.fact_emissions_country_year e USING (country_key, year_key))
UNION ALL
SELECT 'v_etl_status (harus tepat 1 baris)',
       (SELECT count(*) FROM mart.v_etl_status), 1;

-- D2) Cakupan negara pada v_country_year (harapan: 221 negara total; hanya_ember 5 baris = Kosovo;
--     hanya_renewable 61 baris = 12 negara x 5 tahun + 1 negara-tahun yang tidak ada di Ember 2023;
--     baris_tanpa_kelompok 0)
SELECT count(DISTINCT iso3_code) AS negara,
       count(*) FILTER (WHERE NOT has_energy_fact)    AS baris_hanya_ember,
       count(*) FILTER (WHERE NOT has_emissions_fact) AS baris_hanya_renewable,
       count(*) FILTER (WHERE group_label IS NULL)    AS baris_tanpa_kelompok
FROM mart.v_country_year;

-- D3) KPI agregat per tahun: nilai dari view mart vs hitungan LANGSUNG dari tabel fakta (formulasi independen)
-- Definisi (K3, tertimbang pembangkitan):
--   terbarukan/fosil = SUM(pangsa x pembangkitan listrik) / SUM(pembangkitan listrik), baris yang bernilai saja
--   intensitas       = SUM(intensitas x total pembangkitan) / SUM(total pembangkitan), baris yang bernilai saja
-- harapan: kolom selisih_maks 0.000 pada semua tahun. Nilai: terbarukan 26.1 28.0 28.1 29.5 30.4;
--          fosil 63.7 62.1 62.1 61.4 60.7; intensitas 507 494 497 492 486.
WITH dari_view AS (
    SELECT year,
        sum(renewables_share_elec * electricity_generation_twh)
            FILTER (WHERE renewables_share_elec IS NOT NULL AND electricity_generation_twh > 0)
          / sum(electricity_generation_twh)
            FILTER (WHERE renewables_share_elec IS NOT NULL AND electricity_generation_twh > 0) AS terbarukan,
        sum(fossil_share_elec * electricity_generation_twh)
            FILTER (WHERE fossil_share_elec IS NOT NULL AND electricity_generation_twh > 0)
          / sum(electricity_generation_twh)
            FILTER (WHERE fossil_share_elec IS NOT NULL AND electricity_generation_twh > 0) AS fosil,
        sum(emissions_intensity_gco2e_kwh * total_generation_twh)
            FILTER (WHERE emissions_intensity_gco2e_kwh IS NOT NULL AND total_generation_twh > 0)
          / sum(total_generation_twh)
            FILTER (WHERE emissions_intensity_gco2e_kwh IS NOT NULL AND total_generation_twh > 0) AS intensitas
    FROM mart.v_country_year GROUP BY year),
langsung AS (
    SELECT y.year_value AS year,
        (SELECT sum(n.renewables_share_elec * n.electricity_generation) / sum(n.electricity_generation)
           FROM dw.fact_energy_country_year n
          WHERE n.year_key = y.year_key AND n.renewables_share_elec IS NOT NULL AND n.electricity_generation > 0) AS terbarukan,
        (SELECT sum(n.fossil_share_elec * n.electricity_generation) / sum(n.electricity_generation)
           FROM dw.fact_energy_country_year n
          WHERE n.year_key = y.year_key AND n.fossil_share_elec IS NOT NULL AND n.electricity_generation > 0) AS fosil,
        (SELECT sum(e.emissions_intensity_gco2e_kwh * e.total_generation_twh) / sum(e.total_generation_twh)
           FROM dw.fact_emissions_country_year e
          WHERE e.year_key = y.year_key AND e.emissions_intensity_gco2e_kwh IS NOT NULL AND e.total_generation_twh > 0) AS intensitas
    FROM dw.dim_year y)
SELECT v.year AS tahun,
       round(v.terbarukan::numeric, 1) AS terbarukan_view, round(l.terbarukan::numeric, 1) AS terbarukan_fakta,
       round(v.fosil::numeric, 1)      AS fosil_view,      round(l.fosil::numeric, 1)      AS fosil_fakta,
       round(v.intensitas::numeric, 0) AS intensitas_view, round(l.intensitas::numeric, 0) AS intensitas_fakta,
       round(greatest(abs(v.terbarukan - l.terbarukan), abs(v.fosil - l.fosil),
                      abs(v.intensitas - l.intensitas))::numeric, 3) AS selisih_maks
FROM dari_view v JOIN langsung l USING (year) ORDER BY v.year;

-- D4) Rata-rata sederhana antarnegara vs tertimbang (bahan halaman Metodologi; alasan K3)
-- harapan 2019: terbarukan sederhana 32.8 vs tertimbang 26.1; 2023: 36.7 vs 30.4 (intensitas 2019: 460 vs 507; 2023: 433 vs 486)
SELECT year AS tahun,
       round(avg(renewables_share_elec)::numeric, 1) AS terbarukan_sederhana,
       round((sum(renewables_share_elec * electricity_generation_twh)
              FILTER (WHERE renewables_share_elec IS NOT NULL AND electricity_generation_twh > 0)
            / sum(electricity_generation_twh)
              FILTER (WHERE renewables_share_elec IS NOT NULL AND electricity_generation_twh > 0))::numeric, 1) AS terbarukan_tertimbang,
       round(avg(emissions_intensity_gco2e_kwh)::numeric, 0) AS intensitas_sederhana,
       round((sum(emissions_intensity_gco2e_kwh * total_generation_twh)
              FILTER (WHERE emissions_intensity_gco2e_kwh IS NOT NULL AND total_generation_twh > 0)
            / sum(total_generation_twh)
              FILTER (WHERE emissions_intensity_gco2e_kwh IS NOT NULL AND total_generation_twh > 0))::numeric, 0) AS intensitas_tertimbang
FROM mart.v_country_year GROUP BY year ORDER BY year;

-- D5) Cakupan indikator per tahun (bahan halaman Kualitas Data)
-- harapan: negara 221 pada semua tahun (termasuk Kosovo), pangsa_listrik 212 212 212 212 210,
--          pangsa_energi 79 pada semua tahun, intensitas 209 209 209 209 207
SELECT year AS tahun, count(*) AS negara,
       count(renewables_share_elec) AS pangsa_listrik,
       count(renewables_share_energy) AS pangsa_energi_primer,
       count(emissions_intensity_gco2e_kwh) AS intensitas_emisi
FROM mart.v_country_year GROUP BY year ORDER BY year;

-- D6) Contoh negara: Indonesia dari view vs angka yang sudah divalidasi di Fase 3B-2
-- harapan: 2019 -> 16.3 / 83.7 / 8.6 / 699 ; 2023 -> 18.6 / 81.4 / 10.7 / 710
SELECT year AS tahun, round(renewables_share_elec::numeric, 1) AS terbarukan_listrik,
       round(fossil_share_elec::numeric, 1) AS fosil_listrik,
       round(renewables_share_energy::numeric, 1) AS terbarukan_energi_primer,
       round(emissions_intensity_gco2e_kwh::numeric, 0) AS intensitas
FROM mart.v_country_year WHERE iso3_code = 'IDN' ORDER BY year;

-- D7) Bauran pembangkitan global per kategori (view vs perhitungan langsung dari fakta)
-- harapan: 2019 Fossil 63.8 / Nuklir 10.2 / Renewable 26.0 ; 2023 Fossil 61.0 / Nuklir 8.9 / Renewable 30.1
WITH v AS (
    SELECT year, source_category, sum(generation_twh) AS twh FROM mart.v_generation_mix
    WHERE year IN (2019, 2023) GROUP BY year, source_category),
f AS (
    SELECT y.year_value AS year, s.source_category, sum(g.generation_twh) AS twh
    FROM dw.fact_generation_source g
    JOIN dw.dim_year y USING (year_key) JOIN dw.dim_electricity_source s USING (source_key)
    WHERE y.year_value IN (2019, 2023) GROUP BY y.year_value, s.source_category)
SELECT v.year AS tahun, v.source_category AS kategori,
       round((100 * v.twh / sum(v.twh) OVER (PARTITION BY v.year))::numeric, 1) AS persen_view,
       round((100 * f.twh / sum(f.twh) OVER (PARTITION BY f.year))::numeric, 1) AS persen_fakta
FROM v JOIN f USING (year, source_category) ORDER BY v.year, v.source_category;

-- D8) Tidak ada data yang hilang atau berubah di view: jumlah ukuran view = jumlah di fakta
-- harapan: tiga baris, kolom view dan fakta sama (140729.794 ; 140729.809 ; 140260.360)
SELECT 'total_generation_twh' AS ukuran,
       (SELECT round(sum(total_generation_twh)::numeric, 3) FROM mart.v_country_year) AS view_mart,
       (SELECT round(sum(total_generation_twh)::numeric, 3) FROM dw.fact_emissions_country_year) AS fakta
UNION ALL
SELECT 'generation_twh (per sumber)',
       (SELECT round(sum(generation_twh)::numeric, 3) FROM mart.v_generation_mix),
       (SELECT round(sum(generation_twh)::numeric, 3) FROM dw.fact_generation_source)
UNION ALL
SELECT 'electricity_generation_twh',
       (SELECT round(sum(electricity_generation_twh)::numeric, 3) FROM mart.v_country_year),
       (SELECT round(sum(electricity_generation)::numeric, 3) FROM dw.fact_energy_country_year);

-- D9) Hak akses role dashboard (np_dashboard_reader) tanpa perlu login sebagai role itu
-- harapan: semua view mart = true; semua objek di dw, stg, ops = false; INSERT pada mart = false
SELECT objek, hak, has_table_privilege('np_dashboard_reader', objek, hak) AS diizinkan
FROM (VALUES
    ('mart.v_country_year', 'SELECT'), ('mart.v_generation_mix', 'SELECT'),
    ('mart.v_source_comparison', 'SELECT'), ('mart.v_etl_status', 'SELECT'),
    ('mart.v_country_year', 'INSERT'),
    ('dw.fact_energy_country_year', 'SELECT'), ('dw.dim_country', 'SELECT'),
    ('stg.ember_generation', 'SELECT'), ('ops.etl_run', 'SELECT')
) AS t(objek, hak)
ORDER BY objek, hak;

SELECT schema_name, has_schema_privilege('np_dashboard_reader', schema_name, 'USAGE') AS boleh_masuk_schema
FROM (VALUES ('mart'), ('dw'), ('stg'), ('ops')) AS s(schema_name) ORDER BY schema_name;
-- harapan: mart = true; dw, ops, stg = false

-- D10) Status ETL yang akan ditampilkan sebagai "kesegaran data" di dashboard
-- harapan: 1 baris, status SUCCESS, rows_loaded_dw = 11493
SELECT * FROM mart.v_etl_status;
