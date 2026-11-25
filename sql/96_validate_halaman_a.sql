-- Validasi Halaman A (Perkembangan Terbarukan). Pembanding untuk angka di dashboard.
-- Semua query dihitung LANGSUNG dari tabel fakta di schema dw (bukan dari view mart), jadi independen dari
-- apa yang dibaca dashboard. Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw).
-- Aturan pembulatan: round(numeric, 1) PostgreSQL (setengah ke atas). Selisih dihitung dari angka yang dibulatkan.

-- A1) Empat kartu KPI, semua negara, 2023 dan 2022 dibandingkan 2019
-- harapan (kolom kartu_* = angka di kartu; selisih* = angka delta di bawahnya):
--   2019 -> 26.1 | median 22.3 | 57 negara | 212 dari 221 (pembanding)
--   2022 -> 29.5 (+3.4) | median 26.7 (+4.4) | 64 negara (+7) | 212 dari 221
--   2023 -> 30.4 (+4.3) | median 26.6 (+4.3) | 65 negara (+8) | 210 dari 221
-- catatan: median 2019 persis 22.25 dan dibulatkan SQL menjadi 22.3 (setengah ke atas)
WITH e AS (
    SELECT y.year_value AS tahun, c.continent, n.renewables_share_elec AS pangsa, n.electricity_generation AS bobot
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
tot AS (
    SELECT y.year_value AS tahun, count(DISTINCT x.country_key) AS total_negara
    FROM (SELECT country_key, year_key FROM dw.fact_energy_country_year
          UNION SELECT country_key, year_key FROM dw.fact_emissions_country_year) x
    JOIN dw.dim_year y USING (year_key) GROUP BY y.year_value),
k AS (
    SELECT tahun,
           round((sum(pangsa * bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0))::numeric, 1) AS terbarukan,
           round((percentile_cont(0.5) WITHIN GROUP (ORDER BY pangsa))::numeric, 1) AS median,
           count(*) FILTER (WHERE round(pangsa::numeric, 1) >= 50) AS n_ge50,
           count(pangsa) AS cakupan
    FROM e GROUP BY tahun)
SELECT k.tahun, k.terbarukan AS kartu_terbarukan, k.terbarukan - p.terbarukan AS selisih,
       k.median AS kartu_median, k.median - p.median AS selisih_median,
       k.n_ge50 AS kartu_n_ge50, k.n_ge50 - p.n_ge50 AS selisih_n,
       k.cakupan || ' dari ' || tot.total_negara AS kartu_cakupan
FROM k JOIN tot USING (tahun) CROSS JOIN (SELECT * FROM k WHERE tahun = 2019) p
WHERE k.tahun IN (2019, 2022, 2023) ORDER BY k.tahun;

-- A2) Kartu KPI dengan filter benua = Asia (pilih hanya "Asia" di sidebar), 2023 dan 2021 dibandingkan 2019
-- harapan: 2019 -> 21.5 | median 14.6 | 8 negara | 49 dari 49 (pembanding)
--          2021 -> 23.3 (+1.8) | median 17.1 (+2.5) | 9 negara (+1) | 49 dari 49
--          2023 -> 25.1 (+3.6) | median 18.6 (+4.0) | 8 negara (0) | 49 dari 49
WITH e AS (
    SELECT y.year_value AS tahun, n.renewables_share_elec AS pangsa, n.electricity_generation AS bobot
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE COALESCE(c.continent, 'Tidak diketahui') = 'Asia'),
k AS (
    SELECT tahun,
           round((sum(pangsa * bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0))::numeric, 1) AS terbarukan,
           round((percentile_cont(0.5) WITHIN GROUP (ORDER BY pangsa))::numeric, 1) AS median,
           count(*) FILTER (WHERE round(pangsa::numeric, 1) >= 50) AS n_ge50,
           count(pangsa) AS cakupan, count(*) AS negara
    FROM e GROUP BY tahun)
SELECT k.tahun, k.terbarukan AS kartu_terbarukan, k.terbarukan - p.terbarukan AS selisih,
       k.median AS kartu_median, k.median - p.median AS selisih_median,
       k.n_ge50 AS kartu_n_ge50, k.n_ge50 - p.n_ge50 AS selisih_n, k.cakupan || ' dari ' || k.negara AS kartu_cakupan
FROM k CROSS JOIN (SELECT * FROM k WHERE tahun = 2019) p WHERE k.tahun IN (2019, 2021, 2023) ORDER BY k.tahun;

-- A3) Tingkat "Benua": pangsa tertimbang per benua, 2019 dan 2023 (termasuk "Tidak diketahui")
-- harapan (pangsa 2019 -> 2023, perubahan): Africa 20.6 -> 24.5 (+3.9); Asia 21.5 -> 25.1 (+3.6); Europe 31.7 -> 40.1 (+8.4);
--   North America 24.4 -> 27.9 (+3.5); Oceania 29.2 -> 41.6 (+12.4); South America 69.2 -> 77.2 (+8.0);
--   Tidak diketahui 0.7 -> 0.7 (12 negara, 4 berdata pangsa)
WITH e AS (
    SELECT y.year_value AS tahun, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           n.renewables_share_elec AS pangsa, n.electricity_generation AS bobot
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
k AS (
    SELECT tahun, benua, count(*) AS negara, count(pangsa) AS berdata,
           round((sum(pangsa * bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0)
                / NULLIF(sum(bobot) FILTER (WHERE pangsa IS NOT NULL AND bobot > 0), 0))::numeric, 1) AS pangsa
    FROM e GROUP BY tahun, benua)
SELECT b.benua, b.negara AS negara_2023, b.berdata AS berdata_2023, a.pangsa AS pangsa_2019, b.pangsa AS pangsa_2023,
       b.pangsa - a.pangsa AS perubahan_poin
FROM k a JOIN k b ON a.benua = b.benua AND a.tahun = 2019 AND b.tahun = 2023
ORDER BY (b.benua = 'Tidak diketahui'), b.benua;

-- A4) Peringkat 2023, ambang pembangkitan >= 10 TWh: 10 tertinggi dan 10 terendah
-- Urutan: pangsa (dibulatkan 1 desimal), lalu pembangkitan terbesar, lalu nama.
-- harapan tertinggi: Paraguay, Iceland, Ethiopia, Congo (DRC), Bhutan, Nepal (semuanya 100.0), Costa Rica 99.9, Norway 98.5,
--   Tajikistan 94.2, Uruguay 92.4
-- harapan terendah: Libya 0.0, Turkmenistan 0.0, Bahrain 0.2, Algeria 0.9, Hong Kong 1.0, Saudi Arabia 1.1, Iraq 1.2,
--   Bangladesh 1.7, Kuwait 2.1, Belarus 3.2
(SELECT 'tertinggi' AS peringkat, row_number() OVER (ORDER BY round(n.renewables_share_elec::numeric, 1) DESC, n.electricity_generation DESC, c.country_name) AS no,
        c.country_name, round(n.renewables_share_elec::numeric, 1) AS pangsa, round(n.electricity_generation::numeric, 1) AS twh
 FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
 WHERE y.year_value = 2023 AND n.renewables_share_elec IS NOT NULL AND n.electricity_generation >= 10
 ORDER BY pangsa DESC, n.electricity_generation DESC, c.country_name LIMIT 10)
UNION ALL
(SELECT 'terendah', row_number() OVER (ORDER BY round(n.renewables_share_elec::numeric, 1) ASC, n.electricity_generation DESC, c.country_name),
        c.country_name, round(n.renewables_share_elec::numeric, 1), round(n.electricity_generation::numeric, 1)
 FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
 WHERE y.year_value = 2023 AND n.renewables_share_elec IS NOT NULL AND n.electricity_generation >= 10
 ORDER BY 4 ASC, n.electricity_generation DESC, c.country_name LIMIT 10)
ORDER BY peringkat DESC, no;

-- A5) Negara seri pada peringkat: jumlah negara yang memenuhi ambang, dan jumlah yang berpangsa sama di kedua ujung
-- harapan: ambang 10 -> 108 negara, 6 di 100.0, 2 di 0.0 ; ambang 50 -> 54 negara, 1 di 100.0, 1 di 0.9
SELECT ambang AS ambang_twh, count(*) AS negara_memenuhi,
       max(p) AS nilai_tertinggi, count(*) FILTER (WHERE p = (SELECT max(round(renewables_share_elec::numeric, 1))
            FROM dw.fact_energy_country_year n2 JOIN dw.dim_year y2 USING (year_key)
            WHERE y2.year_value = 2023 AND n2.renewables_share_elec IS NOT NULL AND n2.electricity_generation >= ambang)) AS n_di_tertinggi,
       min(p) AS nilai_terendah, count(*) FILTER (WHERE p = (SELECT min(round(renewables_share_elec::numeric, 1))
            FROM dw.fact_energy_country_year n2 JOIN dw.dim_year y2 USING (year_key)
            WHERE y2.year_value = 2023 AND n2.renewables_share_elec IS NOT NULL AND n2.electricity_generation >= ambang)) AS n_di_terendah
FROM (VALUES (10), (50)) AS v(ambang)
JOIN LATERAL (SELECT round(n.renewables_share_elec::numeric, 1) AS p
              FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key)
              WHERE y.year_value = 2023 AND n.renewables_share_elec IS NOT NULL AND n.electricity_generation >= v.ambang) x ON true
GROUP BY ambang ORDER BY ambang;

-- A6) Tingkat "Negara": pilihan awal (negara sorotan IDN + 5 pembangkit terbesar 2023) dan deret pangsanya
-- harapan: pembangkit terbesar 2023 = CHN, USA, IND, RUS, JPN (pilihan awal: IDN, CHN, USA, IND, RUS, JPN)
SELECT c.iso3_code, y.year_value AS tahun, round(n.renewables_share_elec::numeric, 1) AS pangsa
FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
WHERE c.iso3_code IN ('IDN', 'CHN', 'USA', 'IND', 'RUS', 'JPN', 'DEU', 'UKR')
ORDER BY c.iso3_code, y.year_value;

SELECT c.iso3_code, round(n.electricity_generation::numeric, 1) AS twh_2023
FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
WHERE y.year_value = 2023 AND n.electricity_generation IS NOT NULL
ORDER BY n.electricity_generation DESC, c.country_name LIMIT 5;

-- A7) Tabel detail 2023: jumlah baris, negara bernilai, negara kosong (nilai kosong tidak diisi perkiraan)
-- harapan: 221 baris (220 negara di data energi + Kosovo yang hanya ada di Ember) ; 210 bernilai ; 11 kosong
WITH semua AS (
    SELECT country_key FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023
    UNION
    SELECT country_key FROM dw.fact_emissions_country_year e JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023)
SELECT count(*) AS baris_tabel,
       count(n.renewables_share_elec) AS pangsa_terisi,
       count(*) - count(n.renewables_share_elec) AS pangsa_kosong
FROM semua s
LEFT JOIN (SELECT n.country_key, n.renewables_share_elec FROM dw.fact_energy_country_year n
           JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023) n USING (country_key);

-- A8) Contoh baris tabel (pangsa 2019, 2023, perubahan dari angka dibulatkan, pembangkitan 2023)
-- harapan: Indonesia 16.3 -> 18.6 (+2.3), 350.6 TWh ; Lesotho: 100.0 (2019), pangsa 2023 kosong, 0.0 TWh ;
--   Ukraine: 7.7 (2019), pangsa 2023 kosong dan pembangkitan 2023 kosong
SELECT c.country_name,
       round(a.renewables_share_elec::numeric, 1) AS pangsa_2019,
       round(b.renewables_share_elec::numeric, 1) AS pangsa_2023,
       round(b.renewables_share_elec::numeric, 1) - round(a.renewables_share_elec::numeric, 1) AS perubahan_poin,
       round(b.electricity_generation::numeric, 1) AS pembangkitan_2023_twh
FROM dw.dim_country c
JOIN dw.fact_energy_country_year a ON a.country_key = c.country_key
JOIN dw.dim_year ya ON ya.year_key = a.year_key AND ya.year_value = 2019
JOIN dw.fact_energy_country_year b ON b.country_key = c.country_key
JOIN dw.dim_year yb ON yb.year_key = b.year_key AND yb.year_value = 2023
WHERE c.iso3_code IN ('IDN', 'LSO', 'UKR') ORDER BY c.country_name;
