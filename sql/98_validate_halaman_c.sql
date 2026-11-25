-- Validasi Halaman C (Bauran Pembangkitan). Pembanding untuk angka di dashboard.
-- Setiap blok (C1 sampai C8) menampilkan tiga hal:
--   *_dw    = ACTUAL, dihitung langsung dari tabel fakta dw.fact_generation_source (+ dimensi), independen dari dashboard
--   *_mart  = EXPECTED dari view mart.v_generation_mix, yaitu data yang dibaca dashboard
--   harapan = nilai acuan tetap untuk dataset proyek ini
-- kolom status = OK jika ketiganya sama, BEDA jika ada yang tidak sama.
-- Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw).
-- Aturan: pangsa = TWh kategori / TWh total x 100 (dari jumlah, bukan rata-rata antarnegara); round(numeric, 1) setengah ke atas.
-- Kolom di view mart: source_category dan source_name (bukan category / source).

-- C1) Total pembangkitan dan pangsa kategori, DUNIA, 2023
-- harapan: Fossil 18113.9 TWh 61.0% | Nuklir 2644.6 TWh 8.9% | Renewable 8924.3 TWh 30.1% | TOTAL 29682.7 TWh
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER ())::numeric, 1) AS pangsa
      FROM dw_rows WHERE tahun = 2023 GROUP BY kategori),
m AS (SELECT kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER ())::numeric, 1) AS pangsa
      FROM mart_rows WHERE tahun = 2023 GROUP BY kategori),
e(kategori, twh, pangsa) AS (VALUES ('Fossil', 18113.9, 61.0), ('Nuklir', 2644.6, 8.9), ('Renewable', 8924.3, 30.1))
SELECT 'C1' AS blok, a.kategori, round(a.twh::numeric, 1) AS twh_dw, round(m.twh::numeric, 1) AS twh_mart, e.twh AS harapan_twh,
       a.pangsa AS pangsa_dw, m.pangsa AS pangsa_mart, e.pangsa AS harapan_pangsa,
       CASE WHEN round(a.twh::numeric, 1) = round(m.twh::numeric, 1) AND round(a.twh::numeric, 1) = e.twh
             AND a.pangsa = m.pangsa AND a.pangsa = e.pangsa THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (kategori) JOIN e USING (kategori)
UNION ALL
SELECT 'C1', 'TOTAL', round((SELECT sum(twh) FROM dw_rows WHERE tahun = 2023)::numeric, 1),
       round((SELECT sum(twh) FROM mart_rows WHERE tahun = 2023)::numeric, 1), 29682.7,
       (SELECT sum(pangsa) FROM a), (SELECT sum(pangsa) FROM m), 100.0,
       CASE WHEN round((SELECT sum(twh) FROM dw_rows WHERE tahun = 2023)::numeric, 1) = round((SELECT sum(twh) FROM mart_rows WHERE tahun = 2023)::numeric, 1)
             AND round((SELECT sum(twh) FROM dw_rows WHERE tahun = 2023)::numeric, 1) = 29682.7 THEN 'OK' ELSE 'BEDA' END
ORDER BY 2;

-- C2) Total dan pangsa kategori, DUNIA, 2019 dan 2023, beserta selisih pangsa (poin, dari angka yang dibulatkan)
-- harapan 2019: Fossil 63.8 | Nuklir 10.2 | Renewable 26.0 (total 26900.7 TWh)
--         2023: Fossil 61.0 | Nuklir 8.9 | Renewable 30.1 ; selisih: -2.8 | -1.3 | +4.1
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT tahun, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY tahun))::numeric, 1) AS pangsa
      FROM dw_rows WHERE tahun IN (2019, 2023) GROUP BY tahun, kategori),
m AS (SELECT tahun, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY tahun))::numeric, 1) AS pangsa
      FROM mart_rows WHERE tahun IN (2019, 2023) GROUP BY tahun, kategori),
e(tahun, kategori, pangsa) AS (VALUES (2019, 'Fossil', 63.8), (2019, 'Nuklir', 10.2), (2019, 'Renewable', 26.0),
                                      (2023, 'Fossil', 61.0), (2023, 'Nuklir', 8.9), (2023, 'Renewable', 30.1))
SELECT 'C2' AS blok, a.tahun, a.kategori, round(a.twh::numeric, 1) AS twh_dw, round(m.twh::numeric, 1) AS twh_mart,
       a.pangsa AS pangsa_dw, m.pangsa AS pangsa_mart, e.pangsa AS harapan,
       a.pangsa - (SELECT x.pangsa FROM a x WHERE x.kategori = a.kategori AND x.tahun = 2019) AS selisih_poin_dw,
       CASE WHEN round(a.twh::numeric, 1) = round(m.twh::numeric, 1) AND a.pangsa = m.pangsa AND a.pangsa = e.pangsa
            THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (tahun, kategori) JOIN e USING (tahun, kategori) ORDER BY a.tahun, a.kategori;

-- C3) Validasi KATEGORI: kategori yang dipakai harus berasal dari data aktual
-- harapan: tepat 3 kategori (Fossil, Nuklir, Renewable); ada di fakta dw, di view mart, dan di daftar acuan
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
k AS (SELECT kategori FROM dw_rows UNION SELECT kategori FROM mart_rows UNION SELECT unnest(ARRAY['Fossil', 'Nuklir', 'Renewable']))
SELECT 'C3' AS blok, k.kategori,
       EXISTS (SELECT 1 FROM dw_rows d WHERE d.kategori = k.kategori) AS ada_di_dw,
       EXISTS (SELECT 1 FROM mart_rows m WHERE m.kategori = k.kategori) AS ada_di_mart,
       k.kategori = ANY (ARRAY['Fossil', 'Nuklir', 'Renewable']) AS ada_di_acuan,
       CASE WHEN EXISTS (SELECT 1 FROM dw_rows d WHERE d.kategori = k.kategori) AND EXISTS (SELECT 1 FROM mart_rows m WHERE m.kategori = k.kategori)
             AND k.kategori = ANY (ARRAY['Fossil', 'Nuklir', 'Renewable']) THEN 'OK' ELSE 'BEDA' END AS status
FROM k ORDER BY 2;

-- C4) Validasi SUMBER: sumber yang dipakai harus berasal dari data aktual (kategori tiap sumber ikut diperiksa)
-- harapan: tepat 9 sumber: Fossil = Coal, Gas, Other fossil | Nuklir = Nuclear | Renewable = Bioenergy, Hydro, Other renewables, Solar, Wind
-- (tidak ada sumber 'Oil' atau 'Hydropower' di data)
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
e(sumber, kategori) AS (VALUES ('Coal', 'Fossil'), ('Gas', 'Fossil'), ('Other fossil', 'Fossil'), ('Nuclear', 'Nuklir'),
                               ('Bioenergy', 'Renewable'), ('Hydro', 'Renewable'), ('Other renewables', 'Renewable'),
                               ('Solar', 'Renewable'), ('Wind', 'Renewable')),
s AS (SELECT sumber FROM dw_rows UNION SELECT sumber FROM mart_rows UNION SELECT sumber FROM e)
SELECT 'C4' AS blok, s.sumber,
       (SELECT min(kategori) FROM dw_rows d WHERE d.sumber = s.sumber) AS kategori_dw,
       (SELECT min(kategori) FROM mart_rows m WHERE m.sumber = s.sumber) AS kategori_mart,
       (SELECT kategori FROM e WHERE e.sumber = s.sumber) AS kategori_harapan,
       CASE WHEN (SELECT min(kategori) FROM dw_rows d WHERE d.sumber = s.sumber) = (SELECT min(kategori) FROM mart_rows m WHERE m.sumber = s.sumber)
             AND (SELECT min(kategori) FROM dw_rows d WHERE d.sumber = s.sumber) = (SELECT kategori FROM e WHERE e.sumber = s.sumber)
            THEN 'OK' ELSE 'BEDA' END AS status
FROM s ORDER BY 3, 2;

-- C5) Sumber teratas menurut pembangkitan, DUNIA, 2023 (urut TWh menurun)
-- harapan: Coal 10508.5 (35.4%) | Gas 6703.3 (22.6%) | Hydro 4240.9 (14.3%) | Nuclear 2644.6 (8.9%) | Wind 2316.4 (7.8%)
--          Solar 1664.1 (5.6%) | Other fossil 902.1 (3.0%) | Bioenergy 614.4 (2.1%) | Other renewables 88.4 (0.3%)
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT sumber, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER ())::numeric, 1) AS pangsa FROM dw_rows WHERE tahun = 2023 GROUP BY sumber),
m AS (SELECT sumber, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER ())::numeric, 1) AS pangsa FROM mart_rows WHERE tahun = 2023 GROUP BY sumber),
e(sumber, twh, pangsa) AS (VALUES ('Coal', 10508.5, 35.4), ('Gas', 6703.3, 22.6), ('Hydro', 4240.9, 14.3), ('Nuclear', 2644.6, 8.9),
                                  ('Wind', 2316.4, 7.8), ('Solar', 1664.1, 5.6), ('Other fossil', 902.1, 3.0),
                                  ('Bioenergy', 614.4, 2.1), ('Other renewables', 88.4, 0.3))
SELECT 'C5' AS blok, row_number() OVER (ORDER BY a.twh DESC) AS peringkat, a.sumber,
       round(a.twh::numeric, 1) AS twh_dw, round(m.twh::numeric, 1) AS twh_mart, e.twh AS harapan_twh,
       a.pangsa AS pangsa_dw, m.pangsa AS pangsa_mart, e.pangsa AS harapan_pangsa,
       CASE WHEN round(a.twh::numeric, 1) = round(m.twh::numeric, 1) AND round(a.twh::numeric, 1) = e.twh
             AND a.pangsa = m.pangsa AND a.pangsa = e.pangsa THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (sumber) JOIN e USING (sumber) ORDER BY a.twh DESC;

-- C6a) Aturan treemap: hanya TWh > 0. Komposisi nilai pada tingkat baris (negara x sumber), 2023
-- harapan: 1816 baris = 1007 positif + 809 nol + 0 negatif + 0 NULL; hasil dw dan mart harus sama
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix)
SELECT 'C6a' AS blok, 'dw' AS asal, count(*) AS baris, count(*) FILTER (WHERE twh > 0) AS positif, count(*) FILTER (WHERE twh = 0) AS nol,
       count(*) FILTER (WHERE twh < 0) AS negatif, count(*) FILTER (WHERE twh IS NULL) AS kosong,
       CASE WHEN count(*) = 1816 AND count(*) FILTER (WHERE twh > 0) = 1007 AND count(*) FILTER (WHERE twh = 0) = 809
             AND count(*) FILTER (WHERE twh < 0) = 0 AND count(*) FILTER (WHERE twh IS NULL) = 0 THEN 'OK' ELSE 'BEDA' END AS status
FROM dw_rows WHERE tahun = 2023
UNION ALL
SELECT 'C6a', 'mart', count(*), count(*) FILTER (WHERE twh > 0), count(*) FILTER (WHERE twh = 0), count(*) FILTER (WHERE twh < 0),
       count(*) FILTER (WHERE twh IS NULL),
       CASE WHEN count(*) = 1816 AND count(*) FILTER (WHERE twh > 0) = 1007 AND count(*) FILTER (WHERE twh = 0) = 809
             AND count(*) FILTER (WHERE twh < 0) = 0 AND count(*) FILTER (WHERE twh IS NULL) = 0 THEN 'OK' ELSE 'BEDA' END
FROM mart_rows WHERE tahun = 2023;

-- C6b) Treemap pada filter Oceania 2023: sumber yang digambar hanya yang TWh > 0
-- harapan: 8 sumber digambar; Nuclear = 0.00 TWh TIDAK digambar (tetap ada di data dan tabel)
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT sumber, sum(twh) AS twh FROM dw_rows WHERE tahun = 2023 AND benua = 'Oceania' GROUP BY sumber),
m AS (SELECT sumber, sum(twh) AS twh FROM mart_rows WHERE tahun = 2023 AND benua = 'Oceania' GROUP BY sumber)
SELECT 'C6b' AS blok, a.sumber, round(a.twh::numeric, 2) AS twh_dw, round(m.twh::numeric, 2) AS twh_mart,
       a.twh > 0 AS digambar_di_treemap,
       CASE WHEN round(a.twh::numeric, 2) = round(m.twh::numeric, 2) AND (a.twh > 0) = (a.sumber <> 'Nuclear') THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (sumber) ORDER BY a.twh DESC;

-- C7) Filter ASIA: total dan pangsa kategori, 2023 (dan selisih terhadap 2019)
-- harapan 2023: Fossil 12087.4 TWh 70.5% | Nuklir 823.6 TWh 4.8% | Renewable 4237.0 TWh 24.7% (total 17148.0)
--         2019: Fossil 74.1% | Nuklir 4.6% | Renewable 21.3% ; selisih poin: -3.6 | +0.2 | +3.4
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT tahun, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY tahun))::numeric, 1) AS pangsa
      FROM dw_rows WHERE benua = 'Asia' AND tahun IN (2019, 2023) GROUP BY tahun, kategori),
m AS (SELECT tahun, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY tahun))::numeric, 1) AS pangsa
      FROM mart_rows WHERE benua = 'Asia' AND tahun IN (2019, 2023) GROUP BY tahun, kategori),
e(tahun, kategori, twh, pangsa) AS (VALUES (2019, 'Fossil', 10660.8, 74.1), (2019, 'Nuklir', 655.2, 4.6), (2019, 'Renewable', 3069.4, 21.3),
                                           (2023, 'Fossil', 12087.4, 70.5), (2023, 'Nuklir', 823.6, 4.8), (2023, 'Renewable', 4237.0, 24.7))
SELECT 'C7' AS blok, a.tahun, a.kategori, round(a.twh::numeric, 1) AS twh_dw, round(m.twh::numeric, 1) AS twh_mart, e.twh AS harapan_twh,
       a.pangsa AS pangsa_dw, m.pangsa AS pangsa_mart, e.pangsa AS harapan_pangsa,
       a.pangsa - (SELECT x.pangsa FROM a x WHERE x.kategori = a.kategori AND x.tahun = 2019) AS selisih_poin_dw,
       CASE WHEN round(a.twh::numeric, 1) = round(m.twh::numeric, 1) AND round(a.twh::numeric, 1) = e.twh
             AND a.pangsa = m.pangsa AND a.pangsa = e.pangsa THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (tahun, kategori) JOIN e USING (tahun, kategori) ORDER BY a.tahun, a.kategori;

-- C8) Beberapa negara, 2023: pangsa kategori dari pembangkitan negara itu sendiri
-- harapan: IDN Fossil 84.9 | Renewable 15.1 (TANPA baris Nuklir) ; CHN 65.4 | 4.6 | 30.0 ; IND 78.3 | 2.5 | 19.2 ;
--          FRA 7.9 | 65.2 | 26.9 ; DEU 43.9 | 1.4 | 54.7 ; USA 59.1 | 18.2 | 22.7 ; BRA 9.0 | 2.0 | 89.0   (urutan Fossil | Nuklir | Renewable)
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix),
a AS (SELECT iso3_code, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY iso3_code))::numeric, 1) AS pangsa
      FROM dw_rows WHERE tahun = 2023 AND iso3_code IN ('IDN', 'CHN', 'IND', 'FRA', 'DEU', 'USA', 'BRA') GROUP BY iso3_code, kategori),
m AS (SELECT iso3_code, kategori, sum(twh) AS twh, round((100 * sum(twh) / sum(sum(twh)) OVER (PARTITION BY iso3_code))::numeric, 1) AS pangsa
      FROM mart_rows WHERE tahun = 2023 AND iso3_code IN ('IDN', 'CHN', 'IND', 'FRA', 'DEU', 'USA', 'BRA') GROUP BY iso3_code, kategori),
e(iso3_code, kategori, twh, pangsa) AS (VALUES
   ('IDN', 'Fossil', 402.8, 84.9), ('IDN', 'Renewable', 71.6, 15.1),
   ('CHN', 'Fossil', 6147.1, 65.4), ('CHN', 'Nuklir', 434.7, 4.6), ('CHN', 'Renewable', 2820.9, 30.0),
   ('IND', 'Fossil', 1500.1, 78.3), ('IND', 'Nuklir', 48.2, 2.5), ('IND', 'Renewable', 368.6, 19.2),
   ('FRA', 'Fossil', 41.1, 7.9), ('FRA', 'Nuklir', 338.2, 65.2), ('FRA', 'Renewable', 139.5, 26.9),
   ('DEU', 'Fossil', 222.4, 43.9), ('DEU', 'Nuklir', 7.2, 1.4), ('DEU', 'Renewable', 277.1, 54.7),
   ('USA', 'Fossil', 2514.3, 59.1), ('USA', 'Nuklir', 774.9, 18.2), ('USA', 'Renewable', 964.7, 22.7),
   ('BRA', 'Fossil', 63.4, 9.0), ('BRA', 'Nuklir', 14.5, 2.0), ('BRA', 'Renewable', 630.2, 89.0))
SELECT 'C8' AS blok, a.iso3_code, a.kategori, round(a.twh::numeric, 1) AS twh_dw, round(m.twh::numeric, 1) AS twh_mart, e.twh AS harapan_twh,
       a.pangsa AS pangsa_dw, m.pangsa AS pangsa_mart, e.pangsa AS harapan_pangsa,
       CASE WHEN round(a.twh::numeric, 1) = round(m.twh::numeric, 1) AND round(a.twh::numeric, 1) = e.twh
             AND a.pangsa = m.pangsa AND a.pangsa = e.pangsa THEN 'OK' ELSE 'BEDA' END AS status
FROM a JOIN m USING (iso3_code, kategori) JOIN e USING (iso3_code, kategori) ORDER BY a.iso3_code, a.kategori;

-- C8b) Indonesia tidak punya baris Nuklir (kategori tanpa baris data tidak dianggap 0)
-- harapan: 0 baris Nuklir pada dw dan mart untuk Indonesia, semua tahun
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix)
SELECT 'C8b' AS blok, (SELECT count(*) FROM dw_rows WHERE iso3_code = 'IDN' AND kategori = 'Nuklir') AS baris_nuklir_dw,
       (SELECT count(*) FROM mart_rows WHERE iso3_code = 'IDN' AND kategori = 'Nuklir') AS baris_nuklir_mart,
       CASE WHEN (SELECT count(*) FROM dw_rows WHERE iso3_code = 'IDN' AND kategori = 'Nuklir') = 0
             AND (SELECT count(*) FROM mart_rows WHERE iso3_code = 'IDN' AND kategori = 'Nuklir') = 0 THEN 'OK' ELSE 'BEDA' END AS status;

-- C9) Ringkasan: jumlah blok yang statusnya BEDA harus 0. Periksa kolom status pada C1 sampai C8b di atas;
-- baris di bawah ini mengulang pemeriksaan inti (total 2023 dan jumlah pangsa = 100) dalam satu baris.
WITH dw_rows AS (
    SELECT y.year_value AS tahun, c.iso3_code, c.country_name, COALESCE(c.continent, 'Tidak diketahui') AS benua,
           s.source_category AS kategori, s.source_name AS sumber, f.generation_twh AS twh
    FROM dw.fact_generation_source f JOIN dw.dim_year y USING (year_key)
    JOIN dw.dim_country c USING (country_key) JOIN dw.dim_electricity_source s USING (source_key)),
mart_rows AS (
    SELECT year AS tahun, iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           source_category AS kategori, source_name AS sumber, generation_twh AS twh
    FROM mart.v_generation_mix)
SELECT 'C9' AS blok,
       round((SELECT sum(twh) FROM dw_rows WHERE tahun = 2023)::numeric, 1) AS total_2023_dw,
       round((SELECT sum(twh) FROM mart_rows WHERE tahun = 2023)::numeric, 1) AS total_2023_mart,
       (SELECT count(DISTINCT kategori) FROM dw_rows) AS jumlah_kategori, (SELECT count(DISTINCT sumber) FROM dw_rows) AS jumlah_sumber,
       CASE WHEN round((SELECT sum(twh) FROM dw_rows WHERE tahun = 2023)::numeric, 1) = round((SELECT sum(twh) FROM mart_rows WHERE tahun = 2023)::numeric, 1)
             AND (SELECT count(DISTINCT kategori) FROM dw_rows) = 3 AND (SELECT count(DISTINCT sumber) FROM dw_rows) = 9 THEN 'OK' ELSE 'BEDA' END AS status;
