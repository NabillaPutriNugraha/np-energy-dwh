-- Validasi halaman Ringkasan (Tahap 4-2): pembanding untuk angka yang tampil di dashboard.
-- Semua query menghitung LANGSUNG dari tabel fakta di schema dw (bukan dari view mart), sehingga independen
-- dari apa yang dibaca dashboard. Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw).
-- Aturan tampilan dashboard: selisih = (nilai tahun terpilih dibulatkan) - (nilai 2019 dibulatkan).
-- Pangsa dibulatkan 1 desimal; intensitas 0 desimal.

-- R1) KPI semua negara: 2019 (pembanding), 2022, dan 2023
-- harapan (kolom kartu_* = angka di kartu KPI; selisih_* = angka delta):
--   2019: 26.1 / 63.7 / 507 / 212 dari 221
--   2022: 29.5 (+3.4) / 61.4 (-2.3) / 492 (-15) / 212 dari 221
--   2023: 30.4 (+4.3) / 60.7 (-3.0) / 486 (-21) / 210 dari 221
WITH energi AS (
    SELECT y.year_value AS tahun, c.continent, n.renewables_share_elec AS terbarukan, n.fossil_share_elec AS fosil,
           n.electricity_generation AS bobot
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
emisi AS (
    SELECT y.year_value AS tahun, c.continent, e.emissions_intensity_gco2e_kwh AS intensitas, e.total_generation_twh AS bobot
    FROM dw.fact_emissions_country_year e JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)),
a AS (
    SELECT tahun,
           round((sum(terbarukan * bobot) FILTER (WHERE terbarukan IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE terbarukan IS NOT NULL AND bobot > 0))::numeric, 1) AS terbarukan,
           round((sum(fosil * bobot) FILTER (WHERE fosil IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE fosil IS NOT NULL AND bobot > 0))::numeric, 1) AS fosil,
           count(terbarukan) AS cakupan
    FROM energi GROUP BY tahun),
b AS (
    SELECT tahun,
           round((sum(intensitas * bobot) FILTER (WHERE intensitas IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE intensitas IS NOT NULL AND bobot > 0))::numeric, 0) AS intensitas
    FROM emisi GROUP BY tahun),
t AS (
    SELECT y.year_value AS tahun, count(DISTINCT x.country_key) AS total_negara
    FROM (SELECT country_key, year_key FROM dw.fact_energy_country_year
          UNION SELECT country_key, year_key FROM dw.fact_emissions_country_year) x
    JOIN dw.dim_year y USING (year_key) GROUP BY y.year_value),
g AS (SELECT a.tahun, a.terbarukan, a.fosil, b.intensitas, a.cakupan, t.total_negara
      FROM a JOIN b USING (tahun) JOIN t USING (tahun))
SELECT g.tahun,
       g.terbarukan AS kartu_terbarukan, g.terbarukan - p.terbarukan AS selisih_terbarukan,
       g.fosil AS kartu_fosil,           g.fosil - p.fosil AS selisih_fosil,
       g.intensitas AS kartu_intensitas, g.intensitas - p.intensitas AS selisih_intensitas,
       g.cakupan || ' dari ' || g.total_negara AS kartu_cakupan
FROM g CROSS JOIN (SELECT * FROM g WHERE tahun = 2019) p
WHERE g.tahun IN (2019, 2022, 2023) ORDER BY g.tahun;

-- R2) KPI dengan filter benua = Asia (sama seperti memilih "Asia" di sidebar), tahun 2023 vs 2019
-- harapan: 2019: 21.5 / 73.9 / 622 / 49 dari 49 ; 2023: 25.1 (+3.6) / 70.0 (-3.9) / 595 (-27) / 49 dari 49
WITH energi AS (
    SELECT y.year_value AS tahun, n.renewables_share_elec AS terbarukan, n.fossil_share_elec AS fosil,
           n.electricity_generation AS bobot
    FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE COALESCE(c.continent, 'Tidak diketahui') = 'Asia'),
emisi AS (
    SELECT y.year_value AS tahun, e.emissions_intensity_gco2e_kwh AS intensitas, e.total_generation_twh AS bobot
    FROM dw.fact_emissions_country_year e JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE COALESCE(c.continent, 'Tidak diketahui') = 'Asia'),
a AS (
    SELECT tahun,
           round((sum(terbarukan * bobot) FILTER (WHERE terbarukan IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE terbarukan IS NOT NULL AND bobot > 0))::numeric, 1) AS terbarukan,
           round((sum(fosil * bobot) FILTER (WHERE fosil IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE fosil IS NOT NULL AND bobot > 0))::numeric, 1) AS fosil,
           count(terbarukan) AS cakupan, count(*) AS negara
    FROM energi GROUP BY tahun),
b AS (
    SELECT tahun,
           round((sum(intensitas * bobot) FILTER (WHERE intensitas IS NOT NULL AND bobot > 0)
                / sum(bobot) FILTER (WHERE intensitas IS NOT NULL AND bobot > 0))::numeric, 0) AS intensitas
    FROM emisi GROUP BY tahun),
g AS (SELECT a.*, b.intensitas FROM a JOIN b USING (tahun))
SELECT g.tahun, g.terbarukan AS kartu_terbarukan, g.terbarukan - p.terbarukan AS selisih_terbarukan,
       g.fosil AS kartu_fosil, g.fosil - p.fosil AS selisih_fosil,
       g.intensitas AS kartu_intensitas, g.intensitas - p.intensitas AS selisih_intensitas,
       g.cakupan || ' dari ' || g.negara AS kartu_cakupan
FROM g CROSS JOIN (SELECT * FROM g WHERE tahun = 2019) p WHERE g.tahun IN (2019, 2023) ORDER BY g.tahun;

-- R3) Peringkat "Kenaikan pangsa terbarukan terbesar": 2019 -> 2023, ambang pembangkitan >= 10 TWh (pada 2023)
-- harapan: 10 baris, urutan: Venezuela 31.9, Netherlands 28.4, Portugal 21.4, Sudan 17.3, Chile 16.9,
--          North Korea 16.3, Greece 16.2, Sri Lanka 14.8, Germany 14.5, Spain 14.2
-- (perubahan = selisih pangsa yang dibulatkan 1 desimal, sama dengan label di dashboard)
SELECT row_number() OVER (ORDER BY round(b.renewables_share_elec::numeric, 1) - round(a.renewables_share_elec::numeric, 1) DESC, c.country_name) AS no,
       c.country_name,
       round(a.renewables_share_elec::numeric, 1) AS pangsa_2019,
       round(b.renewables_share_elec::numeric, 1) AS pangsa_2023,
       round(b.renewables_share_elec::numeric, 1) - round(a.renewables_share_elec::numeric, 1) AS perubahan,
       round(b.electricity_generation::numeric, 1) AS pembangkitan_twh_2023
FROM dw.fact_energy_country_year a
JOIN dw.fact_energy_country_year b ON b.country_key = a.country_key
JOIN dw.dim_year ya ON ya.year_key = a.year_key AND ya.year_value = 2019
JOIN dw.dim_year yb ON yb.year_key = b.year_key AND yb.year_value = 2023
JOIN dw.dim_country c ON c.country_key = a.country_key
WHERE a.renewables_share_elec IS NOT NULL AND b.renewables_share_elec IS NOT NULL
  AND b.electricity_generation >= 10
ORDER BY perubahan DESC, c.country_name LIMIT 10;

-- R4) Jumlah negara yang memenuhi ambang (angka "N negara memenuhi ambang ini" pada keterangan grafik)
-- harapan: ambang 0 -> 210; 1 -> 157; 5 -> 128; 10 -> 108; 25 -> 75; 50 -> 54; 100 -> 36
SELECT ambang AS ambang_twh, count(*) AS negara_memenuhi
FROM (VALUES (0), (1), (5), (10), (25), (50), (100)) AS v(ambang)
JOIN (SELECT b.electricity_generation AS twh
      FROM dw.fact_energy_country_year a
      JOIN dw.fact_energy_country_year b ON b.country_key = a.country_key
      JOIN dw.dim_year ya ON ya.year_key = a.year_key AND ya.year_value = 2019
      JOIN dw.dim_year yb ON yb.year_key = b.year_key AND yb.year_value = 2023
      WHERE a.renewables_share_elec IS NOT NULL AND b.renewables_share_elec IS NOT NULL) x
  ON x.twh >= v.ambang
GROUP BY ambang ORDER BY ambang;

-- R5) Peta: jumlah negara berwarna per tahun (negara dengan pangsa listrik terisi)
-- harapan: 212, 212, 212, 212, 210 untuk 2019..2023
SELECT y.year_value AS tahun, count(*) FILTER (WHERE n.renewables_share_elec IS NOT NULL) AS negara_berwarna
FROM dw.fact_energy_country_year n JOIN dw.dim_year y USING (year_key) GROUP BY y.year_value ORDER BY 1;

-- R6) Garis negara sorotan (Indonesia) pada grafik tren
-- harapan: terbarukan 16.3, 18.1, 18.2, 19.6, 18.6 ; intensitas 699, 692, 697, 702, 710 (2019..2023)
SELECT y.year_value AS tahun, round(n.renewables_share_elec::numeric, 1) AS terbarukan,
       round(e.emissions_intensity_gco2e_kwh::numeric, 0) AS intensitas
FROM dw.dim_country c
JOIN dw.fact_energy_country_year n ON n.country_key = c.country_key
JOIN dw.fact_emissions_country_year e ON e.country_key = c.country_key AND e.year_key = n.year_key
JOIN dw.dim_year y ON y.year_key = n.year_key
WHERE c.iso3_code = 'IDN' ORDER BY y.year_value;
