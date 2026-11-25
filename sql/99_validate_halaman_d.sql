-- Validasi Halaman D (Pangsa Terbarukan vs Intensitas Emisi). Pembanding untuk angka di dashboard.
-- Setiap blok (D1 sampai D5) menampilkan tiga hal:
--   *_dw    = ACTUAL, dihitung langsung dari tabel fakta dw.fact_emissions_country_year (+ dimensi), independen dari dashboard
--   *_mart  = EXPECTED dari view mart.v_country_year, yaitu data yang dibaca dashboard
--   harapan = nilai acuan tetap untuk dataset proyek ini
-- kolom status = OK jika ketiganya sama, BEDA jika ada yang tidak sama.
-- Jalankan di pgAdmin sebagai user postgres (np_dashboard tidak punya akses ke dw). Hanya SELECT.
-- Aturan: negara-tahun valid = pangsa terbarukan (Ember) dan intensitas terisi dan pembangkitan > 0; NULL tidak diisi.
-- Spearman dihitung di sini dengan CARA BERBEDA dari dashboard (peringkat rata-rata lewat sub-query penghitung,
-- bukan fungsi jendela rank()), sehingga cocoknya hasil memang membuktikan perhitungan independen.
-- Pembulatan: round(numeric, n) setengah ke atas, sama dengan dashboard.

-- D1) Korelasi, lereng, R2 per tahun, DUNIA (semua negara valid)
-- harapan (n, Pearson, Spearman, lereng, R2): 2019 209 -0.87 -0.88 -6.6 0.76 | 2020 209 -0.88 -0.88 -6.6 0.77 | 2021 209 -0.88 -0.89 -6.6 0.77
--                                           | 2022 209 -0.88 -0.89 -6.6 0.77 | 2023 207 -0.88 -0.90 -6.6 0.78
WITH base AS (
    SELECT 'dw' AS src, y.year_value AS tahun, c.iso3_code, m.renewables_share_pct AS x,
           m.emissions_intensity_gco2e_kwh AS yv, m.total_generation_twh AS g
    FROM dw.fact_emissions_country_year m JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    UNION ALL
    SELECT 'mart', year, iso3_code, ember_renewables_share_pct, emissions_intensity_gco2e_kwh, total_generation_twh
    FROM mart.v_country_year WHERE has_emissions_fact),
d AS (SELECT * FROM base WHERE x IS NOT NULL AND yv IS NOT NULL AND g > 0),
rk AS (
    SELECT d.*,
           (SELECT count(*) FILTER (WHERE d2.x < d.x) + (count(*) FILTER (WHERE d2.x = d.x) + 1) / 2.0
              FROM d d2 WHERE d2.src = d.src AND d2.tahun = d.tahun) AS rx,
           (SELECT count(*) FILTER (WHERE d2.yv < d.yv) + (count(*) FILTER (WHERE d2.yv = d.yv) + 1) / 2.0
              FROM d d2 WHERE d2.src = d.src AND d2.tahun = d.tahun) AS ry
    FROM d),
s AS (SELECT src, tahun, count(*) AS n, round(corr(x, yv)::numeric, 2) AS p, round(corr(rx, ry)::numeric, 2) AS sp,
             round(regr_slope(yv, x)::numeric, 1) AS b, round(regr_r2(yv, x)::numeric, 2) AS r2
      FROM rk GROUP BY src, tahun),
e(tahun, n, p, sp, b, r2) AS (VALUES (2019, 209, -0.87, -0.88, -6.6, 0.76), (2020, 209, -0.88, -0.88, -6.6, 0.77),
                                     (2021, 209, -0.88, -0.89, -6.6, 0.77), (2022, 209, -0.88, -0.89, -6.6, 0.77),
                                     (2023, 207, -0.88, -0.90, -6.6, 0.78))
SELECT 'D1' AS blok, e.tahun, a.n AS n_dw, m.n AS n_mart, e.n AS harapan_n,
       a.p AS pearson_dw, m.p AS pearson_mart, e.p AS harapan_pearson,
       a.sp AS spearman_dw, m.sp AS spearman_mart, e.sp AS harapan_spearman,
       a.b AS lereng_dw, m.b AS lereng_mart, e.b AS harapan_lereng,
       a.r2 AS r2_dw, m.r2 AS r2_mart, e.r2 AS harapan_r2,
       CASE WHEN a.n = m.n AND a.n = e.n AND a.p = m.p AND a.p = e.p AND a.sp = m.sp AND a.sp = e.sp
             AND a.b = m.b AND a.b = e.b AND a.r2 = m.r2 AND a.r2 = e.r2 THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN s a ON a.src = 'dw' AND a.tahun = e.tahun JOIN s m ON m.src = 'mart' AND m.tahun = e.tahun
ORDER BY e.tahun;

-- D2) Korelasi Pearson dan jumlah negara per benua, 2023 (benua dengan n >= 10 ditampilkan dashboard)
-- harapan (n, Pearson): Africa 54 -0.97 | Asia 49 -0.82 | Europe 41 -0.67 | North America 33 -0.98 | Oceania 15 -0.97 | South America 15 -0.99
WITH base AS (
    SELECT 'dw' AS src, COALESCE(c.continent, 'Tidak diketahui') AS benua, m.renewables_share_pct AS x,
           m.emissions_intensity_gco2e_kwh AS yv, m.total_generation_twh AS g, y.year_value AS tahun
    FROM dw.fact_emissions_country_year m JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    UNION ALL
    SELECT 'mart', COALESCE(continent, 'Tidak diketahui'), ember_renewables_share_pct, emissions_intensity_gco2e_kwh,
           total_generation_twh, year FROM mart.v_country_year WHERE has_emissions_fact),
s AS (SELECT src, benua, count(*) AS n, round(corr(x, yv)::numeric, 2) AS p
      FROM base WHERE tahun = 2023 AND x IS NOT NULL AND yv IS NOT NULL AND g > 0 GROUP BY src, benua),
e(benua, n, p) AS (VALUES ('Africa', 54, -0.97), ('Asia', 49, -0.82), ('Europe', 41, -0.67),
                          ('North America', 33, -0.98), ('Oceania', 15, -0.97), ('South America', 15, -0.99))
SELECT 'D2' AS blok, e.benua, a.n AS n_dw, m.n AS n_mart, e.n AS harapan_n, a.p AS pearson_dw, m.p AS pearson_mart,
       e.p AS harapan_pearson, (a.n >= 10) AS ditampilkan,
       CASE WHEN a.n = m.n AND a.n = e.n AND a.p = m.p AND a.p = e.p THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN s a ON a.src = 'dw' AND a.benua = e.benua JOIN s m ON m.src = 'mart' AND m.benua = e.benua
ORDER BY e.benua;

-- D3) Garis regresi 2023 (dasar pencilan): intersep dan lereng, DUNIA
-- harapan: intersep 679.3 ; lereng -6.60 (dibulatkan 2 desimal)
WITH base AS (
    SELECT 'dw' AS src, m.renewables_share_pct AS x, m.emissions_intensity_gco2e_kwh AS yv
    FROM dw.fact_emissions_country_year m JOIN dw.dim_year y USING (year_key)
    WHERE y.year_value = 2023 AND m.renewables_share_pct IS NOT NULL AND m.emissions_intensity_gco2e_kwh IS NOT NULL
      AND m.total_generation_twh > 0
    UNION ALL
    SELECT 'mart', ember_renewables_share_pct, emissions_intensity_gco2e_kwh FROM mart.v_country_year
    WHERE year = 2023 AND ember_renewables_share_pct IS NOT NULL AND emissions_intensity_gco2e_kwh IS NOT NULL
      AND total_generation_twh > 0),
s AS (SELECT src, round(regr_intercept(yv, x)::numeric, 1) AS a, round(regr_slope(yv, x)::numeric, 2) AS b FROM base GROUP BY src)
SELECT 'D3' AS blok, d.a AS intersep_dw, m.a AS intersep_mart, 679.3 AS harapan_intersep,
       d.b AS lereng_dw, m.b AS lereng_mart, -6.60 AS harapan_lereng,
       CASE WHEN d.a = m.a AND d.a = 679.3 AND d.b = m.b AND d.b = -6.60 THEN 'OK' ELSE 'BEDA' END AS status
FROM s d JOIN s m ON d.src = 'dw' AND m.src = 'mart';

-- D4) Perubahan 2019 ke 2023, DUNIA: negara berdata Ember, berdata lengkap, median selisih (dari angka tampil),
--     dan korelasi antar-selisih untuk negara berpembangkitan >= 10 TWh pada 2023
-- harapan: daftar 209 | lengkap 207 | median selisih pangsa +1.9 poin | median selisih intensitas -13.2 | n korelasi 108 | r -0.84
WITH base AS (
    SELECT 'dw' AS src, c.iso3_code, y.year_value AS tahun, m.renewables_share_pct AS x,
           m.emissions_intensity_gco2e_kwh AS yv, m.total_generation_twh AS g
    FROM dw.fact_emissions_country_year m JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE y.year_value IN (2019, 2023)
    UNION ALL
    SELECT 'mart', iso3_code, year, ember_renewables_share_pct, emissions_intensity_gco2e_kwh, total_generation_twh
    FROM mart.v_country_year WHERE year IN (2019, 2023) AND has_emissions_fact),
s AS (
    SELECT src, iso3_code,
           max(CASE WHEN tahun = 2019 AND g > 0 THEN x END)  AS x0, max(CASE WHEN tahun = 2023 AND g > 0 THEN x END)  AS x1,
           max(CASE WHEN tahun = 2019 AND g > 0 THEN yv END) AS y0, max(CASE WHEN tahun = 2023 AND g > 0 THEN yv END) AS y1,
           max(CASE WHEN tahun = 2023 THEN g END) AS g1
    FROM base GROUP BY src, iso3_code),
c AS (SELECT s.*, (x0 IS NOT NULL AND x1 IS NOT NULL AND y0 IS NOT NULL AND y1 IS NOT NULL) AS lengkap,
             round(x1::numeric, 1) - round(x0::numeric, 1) AS dx, round(y1::numeric, 1) - round(y0::numeric, 1) AS dy FROM s),
r AS (SELECT src, count(*) AS n_daftar, count(*) FILTER (WHERE lengkap) AS n_lengkap,
             round((percentile_cont(0.5) WITHIN GROUP (ORDER BY dx::float8) FILTER (WHERE lengkap))::numeric, 1) AS med_dx,
             round((percentile_cont(0.5) WITHIN GROUP (ORDER BY dy::float8) FILTER (WHERE lengkap))::numeric, 1) AS med_dy,
             count(*) FILTER (WHERE lengkap AND g1 >= 10) AS n_kor,
             round((corr(x1 - x0, y1 - y0) FILTER (WHERE lengkap AND g1 >= 10))::numeric, 2) AS kor
      FROM c GROUP BY src)
SELECT 'D4' AS blok, a.n_daftar AS daftar_dw, m.n_daftar AS daftar_mart, 209 AS harapan_daftar,
       a.n_lengkap AS lengkap_dw, m.n_lengkap AS lengkap_mart, 207 AS harapan_lengkap,
       a.med_dx AS med_pangsa_dw, m.med_dx AS med_pangsa_mart, 1.9 AS harapan_med_pangsa,
       a.med_dy AS med_intens_dw, m.med_dy AS med_intens_mart, -13.2 AS harapan_med_intens,
       a.n_kor AS n_kor_dw, m.n_kor AS n_kor_mart, 108 AS harapan_n_kor,
       a.kor AS kor_dw, m.kor AS kor_mart, -0.84 AS harapan_kor,
       CASE WHEN a.n_daftar = m.n_daftar AND a.n_daftar = 209 AND a.n_lengkap = m.n_lengkap AND a.n_lengkap = 207
             AND a.med_dx = m.med_dx AND a.med_dx = 1.9 AND a.med_dy = m.med_dy AND a.med_dy = -13.2
             AND a.n_kor = m.n_kor AND a.n_kor = 108 AND a.kor = m.kor AND a.kor = -0.84 THEN 'OK' ELSE 'BEDA' END AS status
FROM r a JOIN r m ON a.src = 'dw' AND m.src = 'mart';

-- D5) 10 negara pencilan 2023 (|selisih| terbesar dari garis regresi, pembangkitan >= 10 TWh), DUNIA
-- Selisih = intensitas aktual dikurangi intensitas menurut garis, dari angka yang dibulatkan 1 desimal.
-- harapan peringkat 1-10: TKM +627.1 | UZB +499.2 | FRA -448.6 | SVK -414.0 | BEL -324.0 | HUN -309.5 | BLR -297.9 | FIN -255.5 | KAZ +229.2 | CHE -227.6
-- harapan jumlah negara dalam kumpulan pencilan (>= 10 TWh): 108
WITH base AS (
    SELECT 'dw' AS src, c.iso3_code, m.renewables_share_pct AS x, m.emissions_intensity_gco2e_kwh AS yv,
           m.total_generation_twh AS g, c.country_name
    FROM dw.fact_emissions_country_year m JOIN dw.dim_year y USING (year_key) JOIN dw.dim_country c USING (country_key)
    WHERE y.year_value = 2023 AND m.renewables_share_pct IS NOT NULL AND m.emissions_intensity_gco2e_kwh IS NOT NULL
      AND m.total_generation_twh > 0
    UNION ALL
    SELECT 'mart', iso3_code, ember_renewables_share_pct, emissions_intensity_gco2e_kwh, total_generation_twh, country_name
    FROM mart.v_country_year
    WHERE year = 2023 AND ember_renewables_share_pct IS NOT NULL AND emissions_intensity_gco2e_kwh IS NOT NULL
      AND total_generation_twh > 0),
m AS (SELECT src, regr_intercept(yv, x) AS a, regr_slope(yv, x) AS b FROM base GROUP BY src),
p AS (SELECT base.src, iso3_code, country_name, g,
             round(yv::numeric, 1) - round((m.a + m.b * x)::numeric, 1) AS res
      FROM base JOIN m USING (src) WHERE g >= 10),
rk AS (SELECT src, iso3_code, country_name, res,
              row_number() OVER (PARTITION BY src ORDER BY abs(res) DESC, g DESC, country_name) AS peringkat FROM p),
e(peringkat, iso3_code, res) AS (VALUES (1, 'TKM', 627.1), (2, 'UZB', 499.2), (3, 'FRA', -448.6), (4, 'SVK', -414.0),
                                        (5, 'BEL', -324.0), (6, 'HUN', -309.5), (7, 'BLR', -297.9), (8, 'FIN', -255.5),
                                        (9, 'KAZ', 229.2), (10, 'CHE', -227.6))
SELECT 'D5' AS blok, e.peringkat, e.iso3_code AS harapan_iso, a.iso3_code AS iso_dw, d.iso3_code AS iso_mart,
       a.country_name AS negara, e.res AS harapan_selisih, a.res AS selisih_dw, d.res AS selisih_mart,
       (SELECT count(*) FROM p WHERE src = 'dw') AS n_pool_dw, (SELECT count(*) FROM p WHERE src = 'mart') AS n_pool_mart,
       CASE WHEN a.iso3_code = d.iso3_code AND a.iso3_code = e.iso3_code AND a.res = d.res AND a.res = e.res
             AND (SELECT count(*) FROM p WHERE src = 'dw') = 108 AND (SELECT count(*) FROM p WHERE src = 'mart') = 108
            THEN 'OK' ELSE 'BEDA' END AS status
FROM e JOIN rk a ON a.src = 'dw' AND a.peringkat = e.peringkat JOIN rk d ON d.src = 'mart' AND d.peringkat = e.peringkat
ORDER BY e.peringkat;
