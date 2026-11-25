-- Query validasi Data Warehouse. Bagian B: dimensi (Fase 3B-1). Bagian C: tabel fakta (Fase 3B-2).
-- Jalankan di pgAdmin (database np_energy_dw) setelah: python src/run_etl.py

-- B1) Jumlah baris dimensi (harapan: dim_country 221, dim_country_group 11)
SELECT 'dim_country' AS tabel, count(*) AS jumlah_baris FROM dw.dim_country
UNION ALL SELECT 'dim_country_group', count(*) FROM dw.dim_country_group;

-- B2) Asal atribut negara (harapan: dengan_wilayah 209 = ada di Ember, tanpa_wilayah 12 = hanya di Renewable)
SELECT count(*) FILTER (WHERE continent IS NOT NULL) AS dengan_wilayah,
       count(*) FILTER (WHERE continent IS NULL)     AS tanpa_wilayah
FROM dw.dim_country;

-- B3) Kelompok negara dan jumlah negara tiap kelompok, dihitung dari staging (independen dari dimensi)
-- harapan: Bukan anggota kelompok 149, EU, OECD 19, ASEAN 9, OECD 8, G20 7, EU 5, OECD, G20 4,
--          OECD, G20, G7 4, EU, OECD, G20, G7 3, G20, ASEAN 1, Tidak diketahui 12 (total 221)
WITH ember AS (
    SELECT DISTINCT ON (iso_3_code) iso_3_code, eu_member, oecd_member, g20_member, g7_member, asean_member
    FROM stg.ember_generation ORDER BY iso_3_code, year DESC),
semua AS (
    SELECT iso_3_code AS iso FROM stg.ember_generation
    UNION SELECT iso_code FROM stg.renewable_energy)
SELECT COALESCE(g.group_label, 'Tidak diketahui') AS kelompok, count(*) AS jumlah_negara
FROM semua s
LEFT JOIN ember e ON e.iso_3_code = s.iso
LEFT JOIN dw.dim_country_group g
       ON e.iso_3_code IS NOT NULL
      AND g.is_eu_member = e.eu_member AND g.is_oecd_member = e.oecd_member
      AND g.is_g20_member = e.g20_member AND g.is_g7_member = e.g7_member
      AND g.is_asean_member = e.asean_member
GROUP BY 1 ORDER BY 2 DESC, 1;

-- B4) Negara yang namanya berbeda antar sumber (harapan: 17 baris). Dimensi memakai nama Ember.
SELECT c.iso3_code, c.country_name AS nama_di_dim_country, r.country AS nama_di_renewable
FROM dw.dim_country c
JOIN (SELECT DISTINCT iso_code, country FROM stg.renewable_energy) r ON r.iso_code = c.iso3_code
WHERE c.country_name <> r.country
ORDER BY c.iso3_code;

-- B5) 12 negara yang hanya ada di Renewable (harapan: 12 baris, tanpa continent/ember_region)
SELECT c.iso3_code, c.country_name, c.continent, c.ember_region
FROM dw.dim_country c
WHERE NOT EXISTS (SELECT 1 FROM stg.ember_generation e WHERE e.iso_3_code = c.iso3_code)
ORDER BY c.iso3_code;

-- B6) Isi dimensi kelompok negara (harapan: 11 baris termasuk "Tidak diketahui" dengan flag NULL)
SELECT country_group_key, group_label, is_eu_member, is_oecd_member, is_g20_member, is_g7_member, is_asean_member
FROM dw.dim_country_group ORDER BY country_group_key;

-- B7) Kestabilan surrogate key (untuk uji idempotensi): catat hasil ini, jalankan ETL lagi, bandingkan.
-- Harapan: jumlah_key, key_terkecil, key_terbesar, dan jumlah_seluruh_key TIDAK berubah setelah run ulang.
SELECT 'dim_country' AS tabel, count(*) AS jumlah_key, min(country_key) AS key_terkecil,
       max(country_key) AS key_terbesar, sum(country_key) AS jumlah_seluruh_key FROM dw.dim_country
UNION ALL
SELECT 'dim_country_group', count(*), min(country_group_key), max(country_group_key),
       sum(country_group_key) FROM dw.dim_country_group;

-- B8) Penghitung identity (harapan: last_value TIDAK naik pada run ulang tanpa perubahan data,
--     karena MERGE hanya memakai nomor identity untuk baris yang benar-benar baru)
SELECT sequencename, last_value FROM pg_sequences
WHERE schemaname = 'dw' AND sequencename IN
      ('dim_country_country_key_seq', 'dim_country_group_country_group_key_seq')
ORDER BY sequencename;

-- B9) Riwayat run dan langkah ETL terakhir
SELECT run_id, started_at, finished_at, status, left(error_message, 100) AS error_message
FROM ops.etl_run ORDER BY run_id DESC LIMIT 5;
SELECT run_id, step_name, status, rows_expected, rows_actual, message
FROM ops.etl_step ORDER BY step_id DESC LIMIT 6;

-- ======================================================================
-- BAGIAN C: TABEL FAKTA (Fase 3B-2)
-- Catatan status kualitas: "Valid dengan indikator kosong" HANYA berarti ada nilai kosong (NULL) pada kolom
-- indikator yang ditetapkan untuk fakta tersebut. Itu bukan penilaian bahwa seluruh baris tidak punya data.
-- Kolom indikator: fact_energy = renewables_share_energy dan renewables_share_elec;
--                  fact_emissions = emissions_intensity_gco2e_kwh dan renewables_share_pct;
--                  fact_generation_source = generation_twh dan share_of_generation_pct (capacity_gw tidak dihitung).
-- ======================================================================

-- C1) Rekonsiliasi jumlah baris: CSV -> staging -> fakta
-- csv_target adalah jumlah baris yang diharapkan untuk dataset proyek ini (dari log preprocessing dan Fase 3A).
-- harapan: ketiga kolom (csv_target, staging, fakta) sama pada setiap baris.
SELECT 'Renewable -> fact_energy_country_year' AS alur, 1100 AS csv_target,
       (SELECT count(*) FROM stg.renewable_energy) AS staging,
       (SELECT count(*) FROM dw.fact_energy_country_year) AS fakta
UNION ALL
SELECT 'Ember (Total generation + Renewables) -> fact_emissions_country_year', 1044,
       (SELECT count(*) FROM stg.ember_generation WHERE electricity_source = 'Total generation'),
       (SELECT count(*) FROM dw.fact_emissions_country_year)
UNION ALL
SELECT 'Ember (9 sumber murni) -> fact_generation_source', 9118,
       (SELECT count(*) FROM stg.ember_generation WHERE electricity_source NOT IN ('Total generation','Renewables')),
       (SELECT count(*) FROM dw.fact_generation_source);

-- C2) Sebaran status kualitas per fakta (indikator kelengkapan kolom indikator, bukan penilaian baris)
-- harapan: energy lengkap 394 / kosong 706; emissions lengkap 1043 / kosong 1; generation lengkap 9109 / kosong 9
SELECT 'fact_energy_country_year' AS fakta, q.status_name, count(*) AS jumlah_baris
FROM dw.fact_energy_country_year f JOIN dw.dim_quality_status q USING (quality_key) GROUP BY q.status_name
UNION ALL
SELECT 'fact_emissions_country_year', q.status_name, count(*)
FROM dw.fact_emissions_country_year f JOIN dw.dim_quality_status q USING (quality_key) GROUP BY q.status_name
UNION ALL
SELECT 'fact_generation_source', q.status_name, count(*)
FROM dw.fact_generation_source f JOIN dw.dim_quality_status q USING (quality_key) GROUP BY q.status_name
ORDER BY 1, 2;

-- C3) Duplikasi grain dan foreign key yatim (harapan: semua 0)
SELECT 'duplikasi fact_energy' AS pemeriksaan, count(*) AS jumlah FROM (
    SELECT 1 FROM dw.fact_energy_country_year GROUP BY country_key, year_key HAVING count(*) > 1) d
UNION ALL SELECT 'duplikasi fact_emissions', count(*) FROM (
    SELECT 1 FROM dw.fact_emissions_country_year GROUP BY country_key, year_key HAVING count(*) > 1) d
UNION ALL SELECT 'duplikasi fact_generation_source', count(*) FROM (
    SELECT 1 FROM dw.fact_generation_source GROUP BY country_key, year_key, source_key HAVING count(*) > 1) d
UNION ALL SELECT 'FK yatim fact_energy', count(*) FROM dw.fact_energy_country_year f
    WHERE NOT EXISTS (SELECT 1 FROM dw.dim_country x WHERE x.country_key = f.country_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_year x WHERE x.year_key = f.year_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_country_group x WHERE x.country_group_key = f.country_group_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_data_source x WHERE x.data_source_key = f.data_source_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_quality_status x WHERE x.quality_key = f.quality_key)
UNION ALL SELECT 'FK yatim fact_emissions', count(*) FROM dw.fact_emissions_country_year f
    WHERE NOT EXISTS (SELECT 1 FROM dw.dim_country x WHERE x.country_key = f.country_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_year x WHERE x.year_key = f.year_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_country_group x WHERE x.country_group_key = f.country_group_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_data_source x WHERE x.data_source_key = f.data_source_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_quality_status x WHERE x.quality_key = f.quality_key)
UNION ALL SELECT 'FK yatim fact_generation_source', count(*) FROM dw.fact_generation_source f
    WHERE NOT EXISTS (SELECT 1 FROM dw.dim_country x WHERE x.country_key = f.country_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_year x WHERE x.year_key = f.year_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_electricity_source x WHERE x.source_key = f.source_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_data_source x WHERE x.data_source_key = f.data_source_key)
       OR NOT EXISTS (SELECT 1 FROM dw.dim_quality_status x WHERE x.quality_key = f.quality_key);

-- C4) Kelompok "Tidak diketahui" pada fakta (harapan: fact_energy 60 baris dari 12 negara; fact_emissions 0)
SELECT 'fact_energy' AS fakta, count(*) AS jumlah_baris, count(DISTINCT f.country_key) AS jumlah_negara
FROM dw.fact_energy_country_year f JOIN dw.dim_country_group g USING (country_group_key)
WHERE g.group_label = 'Tidak diketahui'
UNION ALL
SELECT 'fact_emissions', count(*), count(DISTINCT f.country_key)
FROM dw.fact_emissions_country_year f JOIN dw.dim_country_group g USING (country_group_key)
WHERE g.group_label = 'Tidak diketahui';

-- C5) Pemetaan sumber data (harapan: fact_energy hanya Renewable Energy Share; dua fakta lain hanya Ember)
SELECT 'fact_energy' AS fakta, d.source_name, count(*) AS jumlah_baris
FROM dw.fact_energy_country_year f JOIN dw.dim_data_source d USING (data_source_key) GROUP BY d.source_name
UNION ALL
SELECT 'fact_emissions', d.source_name, count(*)
FROM dw.fact_emissions_country_year f JOIN dw.dim_data_source d USING (data_source_key) GROUP BY d.source_name
UNION ALL
SELECT 'fact_generation_source', d.source_name, count(*)
FROM dw.fact_generation_source f JOIN dw.dim_data_source d USING (data_source_key) GROUP BY d.source_name
ORDER BY 1;

-- C6) NULL dipertahankan apa adanya, tanpa imputasi: jumlah NULL di fakta = jumlah NULL di staging
SELECT 'fact_energy.renewables_share_energy' AS kolom,
       (SELECT count(*) FROM dw.fact_energy_country_year WHERE renewables_share_energy IS NULL) AS null_di_fakta,
       (SELECT count(*) FROM stg.renewable_energy WHERE renewables_share_energy IS NULL) AS null_di_staging
UNION ALL SELECT 'fact_energy.renewables_share_elec',
       (SELECT count(*) FROM dw.fact_energy_country_year WHERE renewables_share_elec IS NULL),
       (SELECT count(*) FROM stg.renewable_energy WHERE renewables_share_elec IS NULL)
UNION ALL SELECT 'fact_energy.gdp',
       (SELECT count(*) FROM dw.fact_energy_country_year WHERE gdp IS NULL),
       (SELECT count(*) FROM stg.renewable_energy WHERE gdp IS NULL)
UNION ALL SELECT 'fact_emissions.emissions_intensity_gco2e_kwh',
       (SELECT count(*) FROM dw.fact_emissions_country_year WHERE emissions_intensity_gco2e_kwh IS NULL),
       (SELECT count(*) FROM stg.ember_generation WHERE electricity_source = 'Total generation'
                                                     AND emissions_intensity_gco2e_kwh IS NULL)
UNION ALL SELECT 'fact_generation_source.share_of_generation_pct',
       (SELECT count(*) FROM dw.fact_generation_source WHERE share_of_generation_pct IS NULL),
       (SELECT count(*) FROM stg.ember_generation WHERE electricity_source NOT IN ('Total generation','Renewables')
                                                     AND share_of_generation_pct IS NULL)
UNION ALL SELECT 'fact_generation_source.capacity_gw',
       (SELECT count(*) FROM dw.fact_generation_source WHERE capacity_gw IS NULL),
       (SELECT count(*) FROM stg.ember_generation WHERE electricity_source NOT IN ('Total generation','Renewables')
                                                     AND capacity_gw IS NULL);
-- harapan: kedua kolom jumlah NULL sama pada tiap baris (energy 705, 42, 440; emissions 1; generation 9 dan 1255).

-- C7) Agregasi: jumlah ukuran di fakta = jumlah di staging (selisih harus ~0)
SELECT 'total_generation_twh (fact_emissions)' AS ukuran,
       (SELECT round(sum(total_generation_twh)::numeric, 3) FROM dw.fact_emissions_country_year) AS fakta,
       (SELECT round(sum(generation_twh)::numeric, 3) FROM stg.ember_generation
         WHERE electricity_source = 'Total generation') AS staging
UNION ALL SELECT 'generation_twh (fact_generation_source)',
       (SELECT round(sum(generation_twh)::numeric, 3) FROM dw.fact_generation_source),
       (SELECT round(sum(generation_twh)::numeric, 3) FROM stg.ember_generation
         WHERE electricity_source NOT IN ('Total generation','Renewables'))
UNION ALL SELECT 'electricity_generation (fact_energy)',
       (SELECT round(sum(electricity_generation)::numeric, 3) FROM dw.fact_energy_country_year),
       (SELECT round(sum(electricity_generation)::numeric, 3) FROM stg.renewable_energy);
-- harapan: total_generation_twh = 140729.794 (fakta = staging); generation_twh sumber = 140729.809 (fakta = staging).

-- C8) Rekonsiliasi lintas fakta: total pembangkitan per negara-tahun vs jumlah sumber murni
-- harapan: pasangan 1044, selisih_di_atas_0_05_twh 0, selisih_maksimum_twh 0.002
SELECT count(*) AS pasangan,
       count(*) FILTER (WHERE abs(e.total_generation_twh - g.total) > 0.05) AS selisih_di_atas_0_05_twh,
       round(max(abs(e.total_generation_twh - g.total))::numeric, 4) AS selisih_maksimum_twh
FROM dw.fact_emissions_country_year e
JOIN (SELECT country_key, year_key, sum(generation_twh) AS total
      FROM dw.fact_generation_source GROUP BY country_key, year_key) g USING (country_key, year_key);

-- C9) Perbedaan nyata ANTAR SUMBER (informasi untuk laporan, bukan kesalahan ETL):
-- pembangkitan total Ember vs electricity_generation Renewable berbeda >5%.
-- harapan: 19 baris dari 5 negara (IDN, MEX, MYS, PAK, THA). Dimensi tidak menghapus salah satu sumber.
SELECT c.iso3_code, c.country_name, y.year_value,
       round(e.total_generation_twh::numeric, 1) AS ember_twh,
       round(n.electricity_generation::numeric, 1) AS renewable_twh,
       round((100 * (e.total_generation_twh / NULLIF(n.electricity_generation, 0) - 1))::numeric, 1) AS selisih_persen
FROM dw.fact_emissions_country_year e
JOIN dw.fact_energy_country_year n USING (country_key, year_key)
JOIN dw.dim_country c USING (country_key)
JOIN dw.dim_year y USING (year_key)
WHERE abs(e.total_generation_twh / NULLIF(n.electricity_generation, 0) - 1) > 0.05  -- NULLIF: abaikan baris dengan nilai Renewable 0
ORDER BY c.iso3_code, y.year_value;

-- C10) Kestabilan surrogate key fakta (uji idempotensi): catat, jalankan ETL lagi, bandingkan.
-- harapan: semua angka dan last_value TIDAK berubah setelah run ulang tanpa perubahan data.
SELECT 'fact_energy' AS tabel, count(*) AS jumlah_key, min(energy_fact_key) AS key_terkecil,
       max(energy_fact_key) AS key_terbesar, sum(energy_fact_key) AS jumlah_seluruh_key
FROM dw.fact_energy_country_year
UNION ALL SELECT 'fact_emissions', count(*), min(emissions_fact_key), max(emissions_fact_key),
       sum(emissions_fact_key) FROM dw.fact_emissions_country_year
UNION ALL SELECT 'fact_generation_source', count(*), min(generation_fact_key), max(generation_fact_key),
       sum(generation_fact_key) FROM dw.fact_generation_source;

SELECT sequencename, last_value FROM pg_sequences
WHERE schemaname = 'dw' AND sequencename LIKE '%fact_key_seq' ORDER BY sequencename;

-- C11) Riwayat run dan langkah ETL terakhir (langkah load_dw mencatat insert/update/tetap per tabel)
SELECT run_id, started_at, finished_at, status, left(error_message, 100) AS error_message
FROM ops.etl_run ORDER BY run_id DESC LIMIT 5;
SELECT run_id, step_name, status, rows_expected, rows_actual, message
FROM ops.etl_step ORDER BY step_id DESC LIMIT 4;
