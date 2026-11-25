-- Validasi Halaman B (Ketergantungan pada Fosil). Pembanding untuk angka di dashboard.
-- Semua query dihitung LANGSUNG dari tabel fakta di schema dw (bukan dari view mart), jadi independen dari
-- apa yang dibaca dashboard. Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw).
-- Aturan pembulatan (sama dengan dashboard): round(numeric, 1) PostgreSQL (setengah ke atas); selisih dan sisa
-- dihitung dari angka yang sudah dibulatkan; sisa = 100 - fosil - terbarukan (angka yang tampil).

-- B1) Tiga kartu KPI + cakupan, semua negara, 2019 / 2022 / 2023 (selisih terhadap 2019)
-- Himpunan negara: pangsa fosil DAN terbarukan terisi, pembangkitan > 0; bobot = pembangkitan listrik.
-- harapan:  2019 -> 63.7 | 26.1 | sisa 10.2 | 212 dari 221
--           2022 -> 61.4 (-2.3) | 29.5 (+3.4) | sisa 9.1 (-1.1) | 212 dari 221
--           2023 -> 60.7 (-3.0) | 30.4 (+4.3) | sisa 8.9 (-1.3) | 210 dari 221
-- kolom sisa_tertimbang_asli = sisa tanpa pembulatan (pembanding; boleh berbeda hingga 0.1 dari sisa_tampil)
WITH e AS (
    SELECT y.year_value AS tahun, c.continent, n.fossil_share_elec AS f, n.renewables_share_elec AS t,
           n.electricity_generation AS w
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
tot AS (
    SELECT y.year_value AS tahun, count(DISTINCT x.country_key) AS total_negara
    FROM (SELECT country_key, year_key FROM dw.fact_energy_country_year
          UNION SELECT country_key, year_key FROM dw.fact_emissions_country_year) x
    JOIN dw.dim_year y USING (year_key) GROUP BY y.year_value),
k AS (
    SELECT tahun,
           count(*) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) AS berbobot,
           round((sum(f * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0)
                / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS fosil,
           round((sum(t * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0)
                / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS terbarukan,
           round((sum((100 - f - t) * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0)
                / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 2) AS sisa_asli
    FROM e GROUP BY tahun),
g AS (SELECT k.*, 100 - k.fosil - k.terbarukan AS sisa, tot.total_negara FROM k JOIN tot USING (tahun))
SELECT g.tahun, g.fosil AS kartu_fosil, g.fosil - p.fosil AS selisih_fosil,
       g.terbarukan AS kartu_terbarukan, g.terbarukan - p.terbarukan AS selisih_terbarukan,
       g.sisa AS kartu_sisa_tampil, g.sisa - p.sisa AS selisih_sisa, g.sisa_asli AS sisa_tertimbang_asli,
       g.fosil + g.terbarukan + g.sisa AS jumlah_kartu, g.berbobot || ' dari ' || g.total_negara AS kartu_cakupan
FROM g CROSS JOIN (SELECT * FROM g WHERE tahun = 2019) p
WHERE g.tahun IN (2019, 2022, 2023) ORDER BY g.tahun;

-- B2) Kartu KPI dengan filter benua (pilih hanya satu benua di sidebar), 2023 dan 2021 dibandingkan 2019
-- Penyebut cakupan = semua negara pada benua itu di data energi ATAU emisi (Kosovo hanya ada di Ember, tetap dihitung).
-- harapan: Asia 2021 -> 72.0 (-1.9) | 23.3 (+1.8) | sisa 4.7 (+0.1) | 49 dari 49
--          Asia 2023 -> 70.0 (-3.9) | 25.1 (+3.6) | sisa 4.9 (+0.3) | 49 dari 49
--          Europe 2021 -> 42.3 (-2.3) | 34.9 (+3.2) | sisa 22.8 (-0.9) | 41 dari 42
--          Europe 2023 -> 39.8 (-4.8) | 40.1 (+8.4) | sisa 20.1 (-3.6) | 40 dari 42 (Ukraine tanpa pangsa listrik 2023)
WITH semua AS (
    SELECT country_key, year_key FROM dw.fact_energy_country_year
    UNION SELECT country_key, year_key FROM dw.fact_emissions_country_year),
tot AS (
    SELECT y.year_value AS tahun, COALESCE(c.continent, 'Tidak diketahui') AS benua, count(*) AS negara
    FROM semua s JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key) GROUP BY 1, 2),
e AS (
    SELECT y.year_value AS tahun, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           n.fossil_share_elec AS f, n.renewables_share_elec AS t, n.electricity_generation AS w
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
k AS (
    SELECT benua, tahun,
           count(*) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) AS berbobot,
           round((sum(f * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0)
                / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS fosil,
           round((sum(t * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0)
                / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS terbarukan
    FROM e WHERE benua IN ('Asia', 'Europe') GROUP BY benua, tahun)
SELECT k.benua, k.tahun, k.fosil AS kartu_fosil, k.fosil - p.fosil AS selisih_fosil,
       k.terbarukan AS kartu_terbarukan, k.terbarukan - p.terbarukan AS selisih_terbarukan,
       100 - k.fosil - k.terbarukan AS kartu_sisa, (100 - k.fosil - k.terbarukan) - (100 - p.fosil - p.terbarukan) AS selisih_sisa,
       k.berbobot || ' dari ' || tot.negara AS kartu_cakupan
FROM k JOIN k p ON p.benua = k.benua AND p.tahun = 2019
JOIN tot ON tot.benua = k.benua AND tot.tahun = k.tahun
WHERE k.tahun IN (2021, 2023) ORDER BY k.benua, k.tahun;

-- B3) Garis tren (semua negara): fosil dan terbarukan per tahun, dan sisa
-- harapan: fosil 63.7, 62.1, 62.1, 61.4, 60.7 ; terbarukan 26.1, 28.0, 28.1, 29.5, 30.4 ; sisa 10.2, 9.9, 9.8, 9.1, 8.9
WITH e AS (
    SELECT y.year_value AS tahun, n.fossil_share_elec AS f, n.renewables_share_elec AS t, n.electricity_generation AS w
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key))
SELECT tahun,
       round((sum(f * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS fosil,
       round((sum(t * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS terbarukan,
       100 - round((sum(f * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1)
           - round((sum(t * w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0) / sum(w) FILTER (WHERE f IS NOT NULL AND t IS NOT NULL AND w > 0))::numeric, 1) AS sisa
FROM e GROUP BY tahun ORDER BY tahun;

-- B4) Dasar kartu "Nuklir dan lainnya (sisa)": hubungan pangsa fosil, terbarukan, dan low-carbon di sumber
-- Diperiksa pada seluruh negara-tahun (2019-2023) yang ketiga nilainya terisi.
-- harapan: 1058 baris; selisih maksimum |fosil + low_carbon - 100| = 0.001 (presisi sumber 3 desimal; hanya 2 baris
--          di atas 0.0005: Japan 2020 dan Venezuela 2021); low_carbon - terbarukan tidak pernah negatif (minimum 0)
SELECT count(*) AS negara_tahun,
       round(max(abs(f + lc - 100))::numeric, 4) AS selisih_maks_dari_100,
       count(*) FILTER (WHERE abs(f + lc - 100) > 0.0005) AS baris_selisih_gt_0_0005,
       count(*) FILTER (WHERE abs(f + lc - 100) > 0.01) AS baris_selisih_gt_0_01,
       round(min(lc - t)::numeric, 4) AS minimum_lowcarbon_dikurangi_terbarukan
FROM (SELECT n.fossil_share_elec AS f, n.low_carbon_share_elec AS lc, n.renewables_share_elec AS t
      FROM dw.fact_energy_country_year n
      WHERE n.fossil_share_elec IS NOT NULL AND n.low_carbon_share_elec IS NOT NULL AND n.renewables_share_elec IS NOT NULL) x;

-- B5) Dumbbell: 10 negara dengan pembangkitan listrik terbesar pada 2023 (urutan menurut PEMBANGKITAN, bukan pangsa fosil)
-- harapan: China, United States, India, Russia, Japan, Brazil, Canada, South Korea, France, Germany
--          (fosil 2019 -> 2023: China 68.5 -> 64.8 ; Brazil 16.1 -> 9.0 ; Canada 19.3 -> 20.8 ; Russia 63.8 -> 63.8)
--          di Top 10: 8 pangsa fosil lebih rendah daripada 2019, 1 lebih tinggi (Canada), 1 sama (Russia)
SELECT row_number() OVER (ORDER BY b.electricity_generation DESC, c.country_name) AS peringkat_pembangkitan,
       c.country_name, round(b.electricity_generation::numeric, 1) AS twh_2023,
       round(a.fossil_share_elec::numeric, 1) AS fosil_2019, round(b.fossil_share_elec::numeric, 1) AS fosil_2023,
       round(b.fossil_share_elec::numeric, 1) - round(a.fossil_share_elec::numeric, 1) AS perubahan_poin
FROM dw.fact_energy_country_year b
JOIN dw.dim_year yb ON yb.year_key = b.year_key AND yb.year_value = 2023
JOIN dw.dim_country c ON c.country_key = b.country_key
LEFT JOIN dw.fact_energy_country_year a ON a.country_key = b.country_key
     AND a.year_key = (SELECT year_key FROM dw.dim_year WHERE year_value = 2019)
WHERE b.electricity_generation IS NOT NULL
ORDER BY b.electricity_generation DESC, c.country_name LIMIT 15;
-- harapan peringkat 11-15: Saudi Arabia, Iran, Mexico, Indonesia (peringkat 14, ikut muncul pada pilihan Top 15), Turkiye

-- B6) Cakupan energi primer per tahun dan hasil perbandingan dengan pangsa listrik (pada 1 desimal)
-- harapan: berdata_primer 79 pada semua tahun; pasangan_valid 79, 79, 79, 79, 78 ;
--          energi_lebih_rendah 78, 78, 77, 77, 76 ; sama 1, 1, 2, 2, 2 ; lebih_tinggi 0 pada semua tahun
SELECT y.year_value AS tahun,
       count(n.renewables_share_energy) AS berdata_primer,
       count(*) FILTER (WHERE n.renewables_share_energy IS NOT NULL AND n.renewables_share_elec IS NOT NULL) AS pasangan_valid,
       count(*) FILTER (WHERE round(n.renewables_share_elec::numeric, 1) > round(n.renewables_share_energy::numeric, 1)) AS energi_lebih_rendah,
       count(*) FILTER (WHERE round(n.renewables_share_elec::numeric, 1) = round(n.renewables_share_energy::numeric, 1)) AS sama,
       count(*) FILTER (WHERE round(n.renewables_share_elec::numeric, 1) < round(n.renewables_share_energy::numeric, 1)) AS lebih_tinggi
FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key)
GROUP BY y.year_value ORDER BY 1;

-- B7) Sebaran cakupan energi primer per benua, 2023 (seluruh negara; tidak dipengaruhi filter)
-- harapan: Africa 4 dari 55 ; Asia 28 dari 49 ; Europe 34 dari 42 ; North America 4 dari 33 ; Oceania 2 dari 15 ;
--          South America 7 dari 15 ; Tidak diketahui 0 dari 12 ; jumlah 79 dari 221 (Kosovo hanya ada di Ember, ikut dihitung 221)
WITH semua AS (
    SELECT country_key FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023
    UNION
    SELECT country_key FROM dw.fact_emissions_country_year e JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023)
SELECT COALESCE(c.continent, 'Tidak diketahui') AS benua, count(*) AS negara,
       count(n.renewables_share_energy) AS berdata_primer
FROM semua s JOIN dw.dim_country c USING (country_key)
LEFT JOIN (SELECT n.country_key, n.renewables_share_energy FROM dw.fact_energy_country_year n
           JOIN dw.dim_year y USING (year_key) WHERE y.year_value = 2023) n USING (country_key)
GROUP BY 1 ORDER BY (COALESCE(c.continent, 'Tidak diketahui') = 'Tidak diketahui'), 1;

-- B8) Contoh baris tabel pasangan 2023 (listrik vs energi primer), selisih dari angka yang dibulatkan
-- harapan: Indonesia 18.6 vs 10.7 (selisih 7.9) ; Ukraine: pangsa listrik KOSONG (bukan 0), energi primer terisi ;
--          dua negara berstatus "sama" (selisih 0.0): Hong Kong (1.0 vs 1.0) dan Turkmenistan (0.0 vs 0.0)
SELECT c.country_name, round(n.renewables_share_elec::numeric, 1) AS listrik, round(n.renewables_share_energy::numeric, 1) AS primer,
       round(n.renewables_share_elec::numeric, 1) - round(n.renewables_share_energy::numeric, 1) AS selisih,
       round(n.electricity_generation::numeric, 1) AS twh
FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
WHERE y.year_value = 2023 AND n.renewables_share_energy IS NOT NULL
  AND (c.iso3_code IN ('IDN', 'UKR', 'CHN', 'IND', 'DEU')
       OR round(n.renewables_share_elec::numeric, 1) = round(n.renewables_share_energy::numeric, 1))
ORDER BY (round(n.renewables_share_elec::numeric, 1) = round(n.renewables_share_energy::numeric, 1)) DESC, c.country_name;
