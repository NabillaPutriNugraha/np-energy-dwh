-- dim_country: satu baris per negara (kunci alami: kode ISO3).
-- Prioritas nama dan atribut: Ember dahulu; Renewable hanya untuk negara yang tidak ada di Ember.
-- Setiap blok "-- @@ nama" dijalankan terpisah oleh src/load_dw.py.

-- @@ source
-- Sumber sementara (hilang otomatis saat transaksi selesai). DISTINCT ON + ORDER BY year DESC
-- mengambil baris tahun terbaru per negara agar hasilnya pasti (deterministik).
CREATE TEMP TABLE src_dim_country ON COMMIT DROP AS
SELECT COALESCE(e.iso3, r.iso3)  AS iso3_code,
       COALESCE(e.area, r.country) AS country_name,
       e.continent,
       e.ember_region
FROM (SELECT DISTINCT ON (iso_3_code)
             iso_3_code AS iso3, area, continent, ember_region
      FROM stg.ember_generation
      ORDER BY iso_3_code, year DESC) e
FULL JOIN
     (SELECT DISTINCT ON (iso_code)
             iso_code AS iso3, country
      FROM stg.renewable_energy
      ORDER BY iso_code, year DESC) r
  ON e.iso3 = r.iso3;

-- @@ merge
-- MERGE = upsert. Baris baru di-INSERT; baris yang sudah ada di-UPDATE HANYA jika nilainya berubah.
-- Nomor surrogate key (identity) hanya terpakai untuk baris yang benar-benar baru.
MERGE INTO dw.dim_country AS t
USING src_dim_country AS s
   ON t.iso3_code = s.iso3_code
WHEN MATCHED AND (t.country_name, t.continent, t.ember_region)
              IS DISTINCT FROM (s.country_name, s.continent, s.ember_region) THEN
    UPDATE SET country_name = s.country_name,
               continent    = s.continent,
               ember_region = s.ember_region
WHEN NOT MATCHED THEN
    INSERT (iso3_code, country_name, continent, ember_region)
    VALUES (s.iso3_code, s.country_name, s.continent, s.ember_region);

-- @@ present
-- Berapa baris sumber yang sekarang ada di dimensi DENGAN nilai atribut yang persis sama?
SELECT count(*)
FROM dw.dim_country t
JOIN src_dim_country s ON t.iso3_code = s.iso3_code
WHERE (t.country_name, t.continent, t.ember_region)
      IS NOT DISTINCT FROM (s.country_name, s.continent, s.ember_region);
