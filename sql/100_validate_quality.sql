-- Validasi Fase 4-3e (Kualitas Data): pembanding untuk angka di halaman Kualitas dan bukti lineage.
-- Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw/stg/ops). Hanya SELECT, tidak mengubah data.
-- Setiap blok (Q1 sampai Q9) membandingkan tiga hal:
--   *_dw    = ACTUAL, dihitung langsung dari tabel dw (dan stg/ops) dengan query independen dari dashboard
--   *_mart  = dari view mart.* (yang dibaca dashboard)
--   harapan = nilai acuan tetap dataset proyek ini (diverifikasi dari hasil query, bukan ditebak)
-- kolom status = OK jika semua sama, BEDA jika ada yang tidak sama. BEDA belum tentu error: periksa penyebabnya dulu
-- (misalnya dataset diperbarui, sehingga acuan literal perlu diperbarui, atau ETL belum dijalankan ulang).
-- Aturan: NULL tidak diimputasi; negara master = dw.dim_country (setiap negara pada setiap tahun, 5 tahun).
-- Q7 menelusuri asal nilai kosong: staging (hasil preprocessing CSV) -> dw. Penelusuran dari berkas mentah data/raw
-- ke hasil preprocessing dilakukan oleh dashboard/tests/test_halaman_kualitas.py (SQL tidak membaca CSV).

-- Q1) Cakupan per tahun dan indikator: jumlah negara yang memiliki NILAI (bukan NULL)
-- harapan: lihat daftar VALUES (tahun, indikator, jumlah); 'bauran_emb' = negara dengan baris sumber pembangkitan bernilai
WITH dwcy AS (
    SELECT c.iso3_code, c.continent, y.year_value AS yr,
           e.renewables_share_elec AS s_ren, e.electricity_generation AS g_ren, e.renewables_share_energy AS s_pri,
           (e.energy_fact_key IS NOT NULL) AS has_e,
           m.renewables_share_pct AS s_emb, m.total_generation_twh AS g_emb, m.emissions_intensity_gco2e_kwh AS inten,
           (m.emissions_fact_key IS NOT NULL) AS has_m
    FROM dw.dim_country c CROSS JOIN dw.dim_year y
    LEFT JOIN dw.fact_energy_country_year e ON e.country_key = c.country_key AND e.year_key = y.year_key
    LEFT JOIN dw.fact_emissions_country_year m ON m.country_key = c.country_key AND m.year_key = y.year_key),
mcy AS (
    SELECT iso3_code, continent, year AS yr, renewables_share_elec AS s_ren, electricity_generation_twh AS g_ren,
           renewables_share_energy AS s_pri, has_energy_fact AS has_e, ember_renewables_share_pct AS s_emb,
           total_generation_twh AS g_emb, emissions_intensity_gco2e_kwh AS inten, has_emissions_fact AS has_m
    FROM mart.v_country_year),
g AS (SELECT 'dw' AS src, * FROM dwcy UNION ALL SELECT 'mart', * FROM mcy),
cov AS (
    SELECT g.src, g.yr, k.kode, count(k.v) AS n
    FROM g CROSS JOIN LATERAL (VALUES ('pangsa_listrik_ren', g.s_ren::float8), ('pembangkitan_ren', g.g_ren::float8),
         ('pangsa_primer_ren', g.s_pri::float8), ('pangsa_listrik_emb', g.s_emb::float8),
         ('pembangkitan_emb', g.g_emb::float8), ('intensitas_emb', g.inten::float8)) k(kode, v)
    GROUP BY g.src, g.yr, k.kode
    UNION ALL
    SELECT 'dw', y.year_value, 'bauran_emb', count(DISTINCT c.iso3_code)
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE f.generation_twh IS NOT NULL GROUP BY y.year_value
    UNION ALL
    SELECT 'mart', year, 'bauran_emb', count(DISTINCT iso3_code) FROM mart.v_generation_mix
    WHERE generation_twh IS NOT NULL GROUP BY year),
e(yr, kode, n) AS (VALUES (2019, 'pangsa_listrik_ren', 212), (2019, 'pembangkitan_ren', 213), (2019, 'pangsa_primer_ren', 79), (2019, 'pangsa_listrik_emb', 209), (2019, 'pembangkitan_emb', 209), (2019, 'intensitas_emb', 209), (2019, 'bauran_emb', 209), (2020, 'pangsa_listrik_ren', 212), (2020, 'pembangkitan_ren', 213), (2020, 'pangsa_primer_ren', 79), (2020, 'pangsa_listrik_emb', 209), (2020, 'pembangkitan_emb', 209), (2020, 'intensitas_emb', 209), (2020, 'bauran_emb', 209), (2021, 'pangsa_listrik_ren', 212), (2021, 'pembangkitan_ren', 213), (2021, 'pangsa_primer_ren', 79), (2021, 'pangsa_listrik_emb', 209), (2021, 'pembangkitan_emb', 209), (2021, 'intensitas_emb', 209), (2021, 'bauran_emb', 209), (2022, 'pangsa_listrik_ren', 212), (2022, 'pembangkitan_ren', 213), (2022, 'pangsa_primer_ren', 79), (2022, 'pangsa_listrik_emb', 209), (2022, 'pembangkitan_emb', 209), (2022, 'intensitas_emb', 209), (2022, 'bauran_emb', 209), (2023, 'pangsa_listrik_ren', 210), (2023, 'pembangkitan_ren', 212), (2023, 'pangsa_primer_ren', 79), (2023, 'pangsa_listrik_emb', 207), (2023, 'pembangkitan_emb', 208), (2023, 'intensitas_emb', 207), (2023, 'bauran_emb', 208))
SELECT 'Q1' AS blok, e.yr AS tahun, e.kode AS indikator, a.n AS tersedia_dw, m.n AS tersedia_mart, e.n AS harapan,
       CASE WHEN a.n = m.n AND a.n = e.n THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN cov a ON a.src = 'dw' AND a.yr = e.yr AND a.kode = e.kode JOIN cov m ON m.src = 'mart' AND m.yr = e.yr AND m.kode = e.kode
ORDER BY e.yr, e.kode;

-- Q2) Negara master vs negara yang punya BARIS di sumber (berbeda dari negara yang punya nilai, lihat Q1)
-- harapan (tahun, master, punya baris Renewable, punya baris Ember, di kedua sumber): lihat VALUES
WITH dwcy AS (
    SELECT c.iso3_code, c.continent, y.year_value AS yr,
           e.renewables_share_elec AS s_ren, e.electricity_generation AS g_ren, e.renewables_share_energy AS s_pri,
           (e.energy_fact_key IS NOT NULL) AS has_e,
           m.renewables_share_pct AS s_emb, m.total_generation_twh AS g_emb, m.emissions_intensity_gco2e_kwh AS inten,
           (m.emissions_fact_key IS NOT NULL) AS has_m
    FROM dw.dim_country c CROSS JOIN dw.dim_year y
    LEFT JOIN dw.fact_energy_country_year e ON e.country_key = c.country_key AND e.year_key = y.year_key
    LEFT JOIN dw.fact_emissions_country_year m ON m.country_key = c.country_key AND m.year_key = y.year_key),
mcy AS (
    SELECT iso3_code, continent, year AS yr, renewables_share_elec AS s_ren, electricity_generation_twh AS g_ren,
           renewables_share_energy AS s_pri, has_energy_fact AS has_e, ember_renewables_share_pct AS s_emb,
           total_generation_twh AS g_emb, emissions_intensity_gco2e_kwh AS inten, has_emissions_fact AS has_m
    FROM mart.v_country_year),
g AS (SELECT 'dw' AS src, * FROM dwcy UNION ALL SELECT 'mart', * FROM mcy),
s AS (SELECT src, yr, count(*) AS master, count(*) FILTER (WHERE has_e) AS ada_ren, count(*) FILTER (WHERE has_m) AS ada_emb,
             count(*) FILTER (WHERE has_e AND has_m) AS kedua
      FROM g GROUP BY src, yr),
e(yr, master, ada_ren, ada_emb, kedua) AS (VALUES (2019, 221, 220, 209, 208), (2020, 221, 220, 209, 208), (2021, 221, 220, 209, 208), (2022, 221, 220, 209, 208), (2023, 221, 220, 208, 207))
SELECT 'Q2' AS blok, e.yr AS tahun, a.master AS master_dw, m.master AS master_mart, e.master AS harapan_master,
       a.ada_ren AS ren_dw, m.ada_ren AS ren_mart, e.ada_ren AS harapan_ren, a.ada_emb AS emb_dw, m.ada_emb AS emb_mart,
       e.ada_emb AS harapan_emb, a.kedua AS kedua_dw, m.kedua AS kedua_mart, e.kedua AS harapan_kedua,
       CASE WHEN a.master = m.master AND a.master = e.master AND a.ada_ren = m.ada_ren AND a.ada_ren = e.ada_ren
             AND a.ada_emb = m.ada_emb AND a.ada_emb = e.ada_emb AND a.kedua = m.kedua AND a.kedua = e.kedua THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN s a ON a.src = 'dw' AND a.yr = e.yr JOIN s m ON m.src = 'mart' AND m.yr = e.yr
ORDER BY e.yr;

-- Q3) Nilai kosong penting per tahun dan penyebab yang dapat dibuktikan dari data
-- harapan (tahun, Ember kosong, di antaranya tanpa baris, pembangkitan 0, pembangkitan NULL | Renewable kosong, tanpa baris, pembangkitan 0, pembangkitan NULL): lihat VALUES
WITH dwcy AS (
    SELECT c.iso3_code, c.continent, y.year_value AS yr,
           e.renewables_share_elec AS s_ren, e.electricity_generation AS g_ren, e.renewables_share_energy AS s_pri,
           (e.energy_fact_key IS NOT NULL) AS has_e,
           m.renewables_share_pct AS s_emb, m.total_generation_twh AS g_emb, m.emissions_intensity_gco2e_kwh AS inten,
           (m.emissions_fact_key IS NOT NULL) AS has_m
    FROM dw.dim_country c CROSS JOIN dw.dim_year y
    LEFT JOIN dw.fact_energy_country_year e ON e.country_key = c.country_key AND e.year_key = y.year_key
    LEFT JOIN dw.fact_emissions_country_year m ON m.country_key = c.country_key AND m.year_key = y.year_key),
mcy AS (
    SELECT iso3_code, continent, year AS yr, renewables_share_elec AS s_ren, electricity_generation_twh AS g_ren,
           renewables_share_energy AS s_pri, has_energy_fact AS has_e, ember_renewables_share_pct AS s_emb,
           total_generation_twh AS g_emb, emissions_intensity_gco2e_kwh AS inten, has_emissions_fact AS has_m
    FROM mart.v_country_year),
g AS (SELECT 'dw' AS src, * FROM dwcy UNION ALL SELECT 'mart', * FROM mcy),
s AS (
    SELECT src, yr,
           count(*) FILTER (WHERE s_emb IS NULL OR inten IS NULL) AS emb_kosong,
           count(*) FILTER (WHERE (s_emb IS NULL OR inten IS NULL) AND NOT has_m) AS emb_tanpa_baris,
           count(*) FILTER (WHERE (s_emb IS NULL OR inten IS NULL) AND has_m AND g_emb = 0) AS emb_gen0,
           count(*) FILTER (WHERE (s_emb IS NULL OR inten IS NULL) AND has_m AND g_emb IS NULL) AS emb_gen_null,
           count(*) FILTER (WHERE s_ren IS NULL) AS ren_kosong,
           count(*) FILTER (WHERE s_ren IS NULL AND NOT has_e) AS ren_tanpa_baris,
           count(*) FILTER (WHERE s_ren IS NULL AND has_e AND g_ren = 0) AS ren_gen0,
           count(*) FILTER (WHERE s_ren IS NULL AND has_e AND g_ren IS NULL) AS ren_gen_null
    FROM g GROUP BY src, yr),
e(yr, emb_kosong, emb_tanpa_baris, emb_gen0, emb_gen_null, ren_kosong, ren_tanpa_baris, ren_gen0, ren_gen_null) AS (VALUES (2019, 12, 12, 0, 0, 9, 1, 1, 7), (2020, 12, 12, 0, 0, 9, 1, 1, 7), (2021, 12, 12, 0, 0, 9, 1, 1, 7), (2022, 12, 12, 0, 0, 9, 1, 1, 7), (2023, 14, 13, 1, 0, 11, 1, 2, 8))
SELECT 'Q3' AS blok, e.yr AS tahun,
       ARRAY[a.emb_kosong, a.emb_tanpa_baris, a.emb_gen0, a.emb_gen_null, a.ren_kosong, a.ren_tanpa_baris, a.ren_gen0, a.ren_gen_null] AS hitung_dw,
       ARRAY[m.emb_kosong, m.emb_tanpa_baris, m.emb_gen0, m.emb_gen_null, m.ren_kosong, m.ren_tanpa_baris, m.ren_gen0, m.ren_gen_null] AS hitung_mart,
       ARRAY[e.emb_kosong, e.emb_tanpa_baris, e.emb_gen0, e.emb_gen_null, e.ren_kosong, e.ren_tanpa_baris, e.ren_gen0, e.ren_gen_null] AS harapan,
       CASE WHEN (a.emb_kosong, a.emb_tanpa_baris, a.emb_gen0, a.emb_gen_null, a.ren_kosong, a.ren_tanpa_baris, a.ren_gen0, a.ren_gen_null)
               = (m.emb_kosong, m.emb_tanpa_baris, m.emb_gen0, m.emb_gen_null, m.ren_kosong, m.ren_tanpa_baris, m.ren_gen0, m.ren_gen_null)
             AND (a.emb_kosong, a.emb_tanpa_baris, a.emb_gen0, a.emb_gen_null, a.ren_kosong, a.ren_tanpa_baris, a.ren_gen0, a.ren_gen_null)
               = (e.emb_kosong, e.emb_tanpa_baris, e.emb_gen0, e.emb_gen_null, e.ren_kosong, e.ren_tanpa_baris, e.ren_gen0, e.ren_gen_null)
            THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN s a ON a.src = 'dw' AND a.yr = e.yr JOIN s m ON m.src = 'mart' AND m.yr = e.yr
ORDER BY e.yr;

-- Q4) Kasus kosong yang diketahui (nilai harapan semuanya TRUE): sisi dw dan sisi mart
--   Lesotho 2023: ada baris Ember, pembangkitan 0, pangsa dan intensitas NULL (bukan 0); pangsa listrik Renewable NULL
--   Ukraine 2023: TIDAK ada baris Ember; baris Renewable ada tetapi pembangkitan dan pangsa listrik NULL, pangsa energi primer terisi
--   Kosovo: tidak ada baris Renewable sama sekali; negara tanpa atribut benua = 12, semuanya tanpa baris Ember
WITH dwcy AS (
    SELECT c.iso3_code, c.continent, y.year_value AS yr,
           e.renewables_share_elec AS s_ren, e.electricity_generation AS g_ren, e.renewables_share_energy AS s_pri,
           (e.energy_fact_key IS NOT NULL) AS has_e,
           m.renewables_share_pct AS s_emb, m.total_generation_twh AS g_emb, m.emissions_intensity_gco2e_kwh AS inten,
           (m.emissions_fact_key IS NOT NULL) AS has_m
    FROM dw.dim_country c CROSS JOIN dw.dim_year y
    LEFT JOIN dw.fact_energy_country_year e ON e.country_key = c.country_key AND e.year_key = y.year_key
    LEFT JOIN dw.fact_emissions_country_year m ON m.country_key = c.country_key AND m.year_key = y.year_key),
mcy AS (
    SELECT iso3_code, continent, year AS yr, renewables_share_elec AS s_ren, electricity_generation_twh AS g_ren,
           renewables_share_energy AS s_pri, has_energy_fact AS has_e, ember_renewables_share_pct AS s_emb,
           total_generation_twh AS g_emb, emissions_intensity_gco2e_kwh AS inten, has_emissions_fact AS has_m
    FROM mart.v_country_year),
g AS (SELECT 'dw' AS src, * FROM dwcy UNION ALL SELECT 'mart', * FROM mcy),
k AS (
    SELECT src,
      bool_or(iso3_code = 'LSO' AND yr = 2023 AND has_m AND g_emb = 0 AND s_emb IS NULL AND inten IS NULL AND s_ren IS NULL) AS lso_2023,
      bool_or(iso3_code = 'UKR' AND yr = 2023 AND NOT has_m) AS ukr_tanpa_ember_2023,
      bool_or(iso3_code = 'UKR' AND yr = 2023 AND has_e AND g_ren IS NULL AND s_ren IS NULL AND s_pri IS NOT NULL) AS ukr_renewable_2023,
      bool_and(NOT has_e) FILTER (WHERE iso3_code = 'XKX') AS xkx_tanpa_renewable,
      (SELECT count(DISTINCT iso3_code) FROM g g2 WHERE g2.src = g.src AND g2.continent IS NULL) = 12 AS tanpa_benua_sesuai,
      bool_and(NOT has_m) FILTER (WHERE continent IS NULL) AS tanpa_benua_tanpa_ember
    FROM g GROUP BY src)
SELECT 'Q4' AS blok, a.lso_2023 AS lso_dw, m.lso_2023 AS lso_mart, a.ukr_tanpa_ember_2023 AS ukr_ember_dw, m.ukr_tanpa_ember_2023 AS ukr_ember_mart,
       a.ukr_renewable_2023 AS ukr_ren_dw, m.ukr_renewable_2023 AS ukr_ren_mart, a.xkx_tanpa_renewable AS xkx_dw, m.xkx_tanpa_renewable AS xkx_mart,
       a.tanpa_benua_sesuai AND a.tanpa_benua_tanpa_ember AS benua_dw, m.tanpa_benua_sesuai AND m.tanpa_benua_tanpa_ember AS benua_mart,
       CASE WHEN a.lso_2023 AND m.lso_2023 AND a.ukr_tanpa_ember_2023 AND m.ukr_tanpa_ember_2023 AND a.ukr_renewable_2023 AND m.ukr_renewable_2023
             AND a.xkx_tanpa_renewable AND m.xkx_tanpa_renewable AND a.tanpa_benua_sesuai AND a.tanpa_benua_tanpa_ember
             AND m.tanpa_benua_sesuai AND m.tanpa_benua_tanpa_ember THEN 'OK' ELSE 'BEDA' END AS status
FROM k a JOIN k m ON a.src = 'dw' AND m.src = 'mart';

-- Q5) Ember vs Renewable per tahun (negara di kedua sumber): pasangan, pembangkitan beda > 5%, pangsa beda > 2 poin
-- (ambang 5% dan 2 poin = keputusan desain; selisih pangsa dari angka dibulatkan 1 desimal; selisih pembangkitan dari round(.., 2))
-- harapan (tahun, pasangan, pembangkitan dapat dibandingkan, beda > 5%, pangsa dapat dibandingkan, beda > 2 poin): lihat VALUES
WITH dwp AS (
    SELECT y.year_value AS yr, m.total_generation_twh AS g_emb, e.electricity_generation AS g_ren,
           m.renewables_share_pct AS s_emb, e.renewables_share_elec AS s_ren
    FROM dw.fact_energy_country_year e
    JOIN dw.fact_emissions_country_year m ON m.country_key = e.country_key AND m.year_key = e.year_key
    JOIN dw.dim_year y ON y.year_key = e.year_key),
dws AS (
    SELECT yr, count(*) AS n_pasang,
           count(*) FILTER (WHERE g_emb IS NOT NULL AND g_ren IS NOT NULL AND g_ren <> 0) AS n_gen,
           count(*) FILTER (WHERE g_ren <> 0 AND abs(round((100 * (g_emb / g_ren - 1))::numeric, 2)) > 5) AS n_gen_besar,
           count(*) FILTER (WHERE s_emb IS NOT NULL AND s_ren IS NOT NULL) AS n_pangsa,
           count(*) FILTER (WHERE abs(round(s_emb::numeric, 1) - round(s_ren::numeric, 1)) > 2) AS n_pangsa_besar
    FROM dwp GROUP BY yr),
ms AS (
    SELECT year AS yr, count(*) AS n_pasang, count(*) FILTER (WHERE selisih_persen IS NOT NULL) AS n_gen,
           count(*) FILTER (WHERE abs(selisih_persen) > 5) AS n_gen_besar,
           count(*) FILTER (WHERE ember_renewables_share_pct IS NOT NULL AND renewable_renewables_share_pct IS NOT NULL) AS n_pangsa,
           count(*) FILTER (WHERE abs(round(ember_renewables_share_pct::numeric, 1) - round(renewable_renewables_share_pct::numeric, 1)) > 2) AS n_pangsa_besar
    FROM mart.v_source_comparison GROUP BY year),
e(yr, n_pasang, n_gen, n_gen_besar, n_pangsa, n_pangsa_besar) AS (VALUES (2019, 208, 208, 2, 208, 1), (2020, 208, 208, 4, 208, 1), (2021, 208, 208, 4, 208, 1), (2022, 208, 208, 4, 208, 3), (2023, 207, 206, 5, 206, 3))
SELECT 'Q5' AS blok, e.yr AS tahun,
       ARRAY[a.n_pasang, a.n_gen, a.n_gen_besar, a.n_pangsa, a.n_pangsa_besar] AS hitung_dw,
       ARRAY[m.n_pasang, m.n_gen, m.n_gen_besar, m.n_pangsa, m.n_pangsa_besar] AS hitung_mart,
       ARRAY[e.n_pasang, e.n_gen, e.n_gen_besar, e.n_pangsa, e.n_pangsa_besar] AS harapan,
       CASE WHEN (a.n_pasang, a.n_gen, a.n_gen_besar, a.n_pangsa, a.n_pangsa_besar) = (m.n_pasang, m.n_gen, m.n_gen_besar, m.n_pangsa, m.n_pangsa_besar)
             AND (a.n_pasang, a.n_gen, a.n_gen_besar, a.n_pangsa, a.n_pangsa_besar) = (e.n_pasang, e.n_gen, e.n_gen_besar, e.n_pangsa, e.n_pangsa_besar)
            THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN dws a ON a.yr = e.yr JOIN ms m ON m.yr = e.yr
ORDER BY e.yr;

-- Q6) Rata-rata sederhana vs tertimbang pembangkitan (semua negara), per tahun
-- harapan (tahun, pangsa sederhana, tertimbang, tertimbang 2 desimal, bobot Ember 2 desimal, intensitas sederhana, tertimbang): lihat VALUES
WITH dwcy AS (
    SELECT c.iso3_code, c.continent, y.year_value AS yr,
           e.renewables_share_elec AS s_ren, e.electricity_generation AS g_ren, e.renewables_share_energy AS s_pri,
           (e.energy_fact_key IS NOT NULL) AS has_e,
           m.renewables_share_pct AS s_emb, m.total_generation_twh AS g_emb, m.emissions_intensity_gco2e_kwh AS inten,
           (m.emissions_fact_key IS NOT NULL) AS has_m
    FROM dw.dim_country c CROSS JOIN dw.dim_year y
    LEFT JOIN dw.fact_energy_country_year e ON e.country_key = c.country_key AND e.year_key = y.year_key
    LEFT JOIN dw.fact_emissions_country_year m ON m.country_key = c.country_key AND m.year_key = y.year_key),
mcy AS (
    SELECT iso3_code, continent, year AS yr, renewables_share_elec AS s_ren, electricity_generation_twh AS g_ren,
           renewables_share_energy AS s_pri, has_energy_fact AS has_e, ember_renewables_share_pct AS s_emb,
           total_generation_twh AS g_emb, emissions_intensity_gco2e_kwh AS inten, has_emissions_fact AS has_m
    FROM mart.v_country_year),
g AS (SELECT 'dw' AS src, * FROM dwcy UNION ALL SELECT 'mart', * FROM mcy),
w AS (
    SELECT src, yr,
           round(avg(s_ren)::numeric, 1) AS sed,
           round((sum(s_ren * g_ren) FILTER (WHERE s_ren IS NOT NULL AND g_ren > 0) / NULLIF(sum(g_ren) FILTER (WHERE s_ren IS NOT NULL AND g_ren > 0), 0))::numeric, 1) AS tim,
           round((sum(s_ren * g_ren) FILTER (WHERE s_ren IS NOT NULL AND g_ren > 0) / NULLIF(sum(g_ren) FILTER (WHERE s_ren IS NOT NULL AND g_ren > 0), 0))::numeric, 2) AS tim2,
           round((sum(s_ren * g_emb) FILTER (WHERE s_ren IS NOT NULL AND g_emb > 0) / NULLIF(sum(g_emb) FILTER (WHERE s_ren IS NOT NULL AND g_emb > 0), 0))::numeric, 2) AS tim_e2,
           round(avg(inten)::numeric, 0) AS isd,
           round((sum(inten * g_emb) FILTER (WHERE inten IS NOT NULL AND g_emb > 0) / NULLIF(sum(g_emb) FILTER (WHERE inten IS NOT NULL AND g_emb > 0), 0))::numeric, 0) AS itm
    FROM g GROUP BY src, yr),
e(yr, sed, tim, tim2, tim_e2, isd, itm) AS (VALUES (2019, 32.8, 26.1, 26.08, 26.04, 460, 507), (2020, 34.3, 28.0, 27.99, 27.95, 450, 494), (2021, 35.4, 28.1, 28.11, 28.07, 442, 497), (2022, 36.2, 29.5, 29.48, 29.43, 437, 492), (2023, 36.7, 30.4, 30.36, 30.29, 433, 486))
SELECT 'Q6' AS blok, e.yr AS tahun,
       ARRAY[a.sed, a.tim, a.tim2, a.tim_e2, a.isd, a.itm] AS hitung_dw, ARRAY[m.sed, m.tim, m.tim2, m.tim_e2, m.isd, m.itm] AS hitung_mart,
       ARRAY[e.sed, e.tim, e.tim2, e.tim_e2, e.isd, e.itm] AS harapan,
       CASE WHEN (a.sed, a.tim, a.tim2, a.tim_e2, a.isd, a.itm) = (m.sed, m.tim, m.tim2, m.tim_e2, m.isd, m.itm)
             AND (a.sed, a.tim, a.tim2, a.tim_e2, a.isd, a.itm) = (e.sed, e.tim, e.tim2, e.tim_e2, e.isd, e.itm) THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN w a ON a.src = 'dw' AND a.yr = e.yr JOIN w m ON m.src = 'mart' AND m.yr = e.yr
ORDER BY e.yr;

-- Q7) Penelusuran asal nilai: staging (hasil preprocessing) -> dw. Menjawab: apakah ETL menghilangkan atau mengosongkan nilai?
-- Ember: negara-tahun dengan baris 'Total generation' DAN 'Renewables' di stg = baris fakta emisi di dw. Renewable: baris stg = fakta energi.
-- Semua hitungan 'hilang' dan 'kosong baru' harus 0 (nilai kosong di dw sudah kosong di stg). Hasil OK = kekosongan berasal dari sumber, bukan ETL.
WITH ember_stg AS (
    SELECT t.iso_3_code, t.year, t.generation_twh AS gen_t, t.emissions_intensity_gco2e_kwh AS inten_t, rn.share_of_generation_pct AS share_rn
    FROM (SELECT * FROM stg.ember_generation WHERE electricity_source = 'Total generation') t
    JOIN (SELECT * FROM stg.ember_generation WHERE electricity_source = 'Renewables') rn ON rn.iso_3_code = t.iso_3_code AND rn.year = t.year),
ember_dw AS (
    SELECT c.iso3_code, y.year_value AS year, f.total_generation_twh, f.emissions_intensity_gco2e_kwh, f.renewables_share_pct
    FROM dw.fact_emissions_country_year f JOIN dw.dim_country c USING (country_key) JOIN dw.dim_year y USING (year_key)),
ember_chk AS (
    SELECT 'Ember' AS sumber, y.year_value AS tahun,
           (SELECT count(*) FROM ember_stg s WHERE s.year = y.year_value) AS baris_stg,
           (SELECT count(*) FROM ember_dw d WHERE d.year = y.year_value) AS baris_dw,
           (SELECT count(*) FROM ember_stg s WHERE s.year = y.year_value AND NOT EXISTS
               (SELECT 1 FROM ember_dw d WHERE d.iso3_code = s.iso_3_code AND d.year = s.year)) AS hilang_di_dw,
           (SELECT count(*) FROM ember_stg s JOIN ember_dw d ON d.iso3_code = s.iso_3_code AND d.year = s.year
             WHERE s.year = y.year_value AND ((s.gen_t IS NOT NULL AND d.total_generation_twh IS NULL)
               OR (s.inten_t IS NOT NULL AND d.emissions_intensity_gco2e_kwh IS NULL) OR (s.share_rn IS NOT NULL AND d.renewables_share_pct IS NULL))) AS kosong_baru_di_dw,
           (SELECT count(*) FROM ember_stg s JOIN ember_dw d ON d.iso3_code = s.iso_3_code AND d.year = s.year
             WHERE s.year = y.year_value AND (s.gen_t IS DISTINCT FROM d.total_generation_twh OR s.inten_t IS DISTINCT FROM d.emissions_intensity_gco2e_kwh
               OR s.share_rn IS DISTINCT FROM d.renewables_share_pct)) AS nilai_beda
    FROM dw.dim_year y),
ren_dw AS (
    SELECT c.iso3_code, y.year_value AS year, f.renewables_share_elec, f.renewables_share_energy, f.electricity_generation
    FROM dw.fact_energy_country_year f JOIN dw.dim_country c USING (country_key) JOIN dw.dim_year y USING (year_key)),
ren_chk AS (
    SELECT 'Renewable' AS sumber, y.year_value AS tahun,
           (SELECT count(*) FROM stg.renewable_energy s WHERE s.year = y.year_value) AS baris_stg,
           (SELECT count(*) FROM ren_dw d WHERE d.year = y.year_value) AS baris_dw,
           (SELECT count(*) FROM stg.renewable_energy s WHERE s.year = y.year_value AND NOT EXISTS
               (SELECT 1 FROM ren_dw d WHERE d.iso3_code = s.iso_code AND d.year = s.year)) AS hilang_di_dw,
           (SELECT count(*) FROM stg.renewable_energy s JOIN ren_dw d ON d.iso3_code = s.iso_code AND d.year = s.year
             WHERE s.year = y.year_value AND ((s.renewables_share_elec IS NOT NULL AND d.renewables_share_elec IS NULL)
               OR (s.renewables_share_energy IS NOT NULL AND d.renewables_share_energy IS NULL)
               OR (s.electricity_generation IS NOT NULL AND d.electricity_generation IS NULL))) AS kosong_baru_di_dw,
           (SELECT count(*) FROM stg.renewable_energy s JOIN ren_dw d ON d.iso3_code = s.iso_code AND d.year = s.year
             WHERE s.year = y.year_value AND (s.renewables_share_elec IS DISTINCT FROM d.renewables_share_elec
               OR s.renewables_share_energy IS DISTINCT FROM d.renewables_share_energy
               OR s.electricity_generation IS DISTINCT FROM d.electricity_generation)) AS nilai_beda
    FROM dw.dim_year y)
SELECT 'Q7' AS blok, sumber, tahun, baris_stg, baris_dw, hilang_di_dw, kosong_baru_di_dw, nilai_beda,
       CASE WHEN baris_stg = baris_dw AND hilang_di_dw = 0 AND kosong_baru_di_dw = 0 AND nilai_beda = 0 THEN 'OK' ELSE 'BEDA' END AS status
FROM (SELECT * FROM ember_chk UNION ALL SELECT * FROM ren_chk) u
ORDER BY sumber, tahun;

-- Q8) Rekonsiliasi DW -> Mart: jumlah baris, jumlah negara, total pembangkitan, indikator utama
-- harapan: fakta energi 1100 baris | fakta emisi 1044 | fakta bauran 9118 | negara master 221
WITH t AS (
    SELECT 'baris fakta energi (dw) vs baris dengan penanda sumber Renewable (mart)' AS pemeriksaan,
           (SELECT count(*) FROM dw.fact_energy_country_year)::numeric AS nilai_dw,
           (SELECT count(*) FROM mart.v_country_year WHERE has_energy_fact)::numeric AS nilai_mart, 1100::numeric AS harapan
    UNION ALL SELECT 'baris fakta emisi (dw) vs baris dengan penanda sumber Ember (mart)',
           (SELECT count(*) FROM dw.fact_emissions_country_year), (SELECT count(*) FROM mart.v_country_year WHERE has_emissions_fact), 1044
    UNION ALL SELECT 'baris fakta bauran per sumber (dw) vs v_generation_mix (mart)',
           (SELECT count(*) FROM dw.fact_generation_source), (SELECT count(*) FROM mart.v_generation_mix), 9118
    UNION ALL SELECT 'negara master (dw.dim_country) vs negara unik v_country_year',
           (SELECT count(*) FROM dw.dim_country), (SELECT count(DISTINCT iso3_code) FROM mart.v_country_year), 221
    UNION ALL SELECT 'baris v_country_year = negara master x tahun',
           (SELECT count(*) FROM dw.dim_country) * (SELECT count(*) FROM dw.dim_year), (SELECT count(*) FROM mart.v_country_year), 1105
    UNION ALL SELECT 'jumlah negara pada bauran: dw vs mart (distinct)',
           (SELECT count(DISTINCT country_key) FROM dw.fact_generation_source), (SELECT count(DISTINCT iso3_code) FROM mart.v_generation_mix),
           (SELECT count(DISTINCT iso3_code) FROM mart.v_country_year WHERE has_emissions_fact)
    UNION ALL SELECT 'jumlah nilai pangsa listrik Renewable (bukan NULL): dw vs mart',
           (SELECT count(renewables_share_elec) FROM dw.fact_energy_country_year), (SELECT count(renewables_share_elec) FROM mart.v_country_year),
           (SELECT count(renewables_share_elec) FROM mart.v_country_year)
    UNION ALL SELECT 'jumlah nilai intensitas emisi (bukan NULL): dw vs mart',
           (SELECT count(emissions_intensity_gco2e_kwh) FROM dw.fact_emissions_country_year), (SELECT count(emissions_intensity_gco2e_kwh) FROM mart.v_country_year),
           (SELECT count(emissions_intensity_gco2e_kwh) FROM mart.v_country_year)
    UNION ALL SELECT 'jumlah pangsa listrik Renewable (dibulatkan 3 desimal): dw vs mart',
           (SELECT round(sum(renewables_share_elec)::numeric, 3) FROM dw.fact_energy_country_year), (SELECT round(sum(renewables_share_elec)::numeric, 3) FROM mart.v_country_year),
           (SELECT round(sum(renewables_share_elec)::numeric, 3) FROM mart.v_country_year)
    UNION ALL SELECT 'jumlah intensitas emisi (3 desimal): dw vs mart',
           (SELECT round(sum(emissions_intensity_gco2e_kwh)::numeric, 3) FROM dw.fact_emissions_country_year), (SELECT round(sum(emissions_intensity_gco2e_kwh)::numeric, 3) FROM mart.v_country_year),
           (SELECT round(sum(emissions_intensity_gco2e_kwh)::numeric, 3) FROM mart.v_country_year)),
ty AS (
    SELECT e.yr, e.tg AS harapan_total_negara, e.tm AS harapan_total_bauran,
           (SELECT round(sum(f.total_generation_twh)::numeric, 1) FROM dw.fact_emissions_country_year f JOIN dw.dim_year y USING (year_key) WHERE y.year_value = e.yr) AS tg_dw,
           (SELECT round(sum(total_generation_twh)::numeric, 1) FROM mart.v_country_year WHERE year = e.yr) AS tg_mart,
           (SELECT round(sum(f.generation_twh)::numeric, 1) FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key) WHERE y.year_value = e.yr) AS tm_dw,
           (SELECT round(sum(generation_twh)::numeric, 1) FROM mart.v_generation_mix WHERE year = e.yr) AS tm_mart
    FROM (VALUES (2019, 26900.7, 26900.7), (2020, 26801.7, 26801.7), (2021, 28344.5, 28344.5), (2022, 29000.2, 29000.2), (2023, 29682.7, 29682.7)) e(yr, tg, tm))
SELECT 'Q8' AS blok, pemeriksaan, nilai_dw, nilai_mart, harapan, CASE WHEN nilai_dw = nilai_mart AND nilai_dw = harapan THEN 'OK' ELSE 'BEDA' END AS status FROM t
UNION ALL
SELECT 'Q8', 'total pembangkitan Ember ' || yr || ' (TWh): dw vs mart (bauran dw ' || tm_dw || ' vs mart ' || tm_mart || ')', tg_dw, tg_mart, harapan_total_negara,
       CASE WHEN tg_dw = tg_mart AND tg_dw = harapan_total_negara AND tm_dw = tm_mart AND tm_dw = harapan_total_bauran THEN 'OK' ELSE 'BEDA' END FROM ty
ORDER BY 2;

-- Q9) Status ETL: mart.v_etl_status harus sama dengan run sukses terakhir (load_dw) di ops (informasi; tidak ada harapan literal)
-- Catatan: rows_loaded_dw = jumlah baris yang dicatat langkah load_dw pada run itu, bukan jumlah baris fakta saat ini.
SELECT 'Q9' AS blok, v.run_id AS run_id_mart, o.run_id AS run_id_ops, v.finished_at AS selesai_mart, o.finished_at AS selesai_ops,
       v.rows_loaded_dw AS baris_dimuat_mart, o.rows_actual AS baris_dimuat_ops,
       CASE WHEN v.run_id = o.run_id AND v.finished_at = o.finished_at AND v.rows_loaded_dw = o.rows_actual AND v.finished_at IS NOT NULL THEN 'OK' ELSE 'BEDA' END AS status
FROM mart.v_etl_status v
JOIN (SELECT r.run_id, r.finished_at, s.rows_actual FROM ops.etl_run r JOIN ops.etl_step s ON s.run_id = r.run_id AND s.step_name = 'load_dw' AND s.status = 'SUCCESS'
      WHERE r.status = 'SUCCESS' ORDER BY r.run_id DESC LIMIT 1) o ON true;
