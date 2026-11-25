-- fact_generation_source. Grain: satu baris per negara per tahun per sumber listrik murni (sumber: staging Ember).
-- Baris agregat ("Total generation", "Renewables") tidak dimuat di sini; keduanya ada di fact_emissions_country_year.
-- Status kualitas = indikator kelengkapan pada DUA kolom saja: generation_twh dan share_of_generation_pct.
-- Kolom capacity_gw TIDAK dihitung dalam status karena kosong secara struktural di sumber (bukan kesalahan ETL).
-- "Valid dengan indikator kosong" artinya salah satu dari dua kolom itu NULL; bukan berarti baris tidak punya data.

-- @@ source
CREATE TEMP TABLE src_fact_generation_source ON COMMIT DROP AS
SELECT c.country_key,
       y.year_key,
       sr.source_key,
       ds.data_source_key,
       q.quality_key,
       e.generation_twh,
       e.share_of_generation_pct,
       e.capacity_gw,
       e.emissions_mtco2e
FROM stg.ember_generation e
JOIN dw.dim_country c            ON c.iso3_code   = e.iso_3_code
JOIN dw.dim_year y               ON y.year_value  = e.year
JOIN dw.dim_electricity_source sr ON sr.source_name = e.electricity_source
JOIN dw.dim_data_source ds       ON ds.source_name = 'Ember Yearly Electricity Data'
JOIN dw.dim_quality_status q     ON q.status_name =
     CASE WHEN e.generation_twh IS NULL OR e.share_of_generation_pct IS NULL
          THEN 'Valid dengan indikator kosong' ELSE 'Valid lengkap' END
WHERE e.electricity_source NOT IN ('Total generation', 'Renewables');

-- @@ merge
MERGE INTO dw.fact_generation_source AS t
USING src_fact_generation_source AS s
   ON t.country_key = s.country_key AND t.year_key = s.year_key AND t.source_key = s.source_key
WHEN MATCHED AND (t.data_source_key, t.quality_key, t.generation_twh,
                  t.share_of_generation_pct, t.capacity_gw, t.emissions_mtco2e)
         IS DISTINCT FROM (s.data_source_key, s.quality_key, s.generation_twh,
                  s.share_of_generation_pct, s.capacity_gw, s.emissions_mtco2e) THEN
    UPDATE SET data_source_key = s.data_source_key, quality_key = s.quality_key,
               generation_twh = s.generation_twh,
               share_of_generation_pct = s.share_of_generation_pct,
               capacity_gw = s.capacity_gw, emissions_mtco2e = s.emissions_mtco2e
WHEN NOT MATCHED THEN
    INSERT (country_key, year_key, source_key, data_source_key, quality_key,
            generation_twh, share_of_generation_pct, capacity_gw, emissions_mtco2e)
    VALUES (s.country_key, s.year_key, s.source_key, s.data_source_key, s.quality_key,
            s.generation_twh, s.share_of_generation_pct, s.capacity_gw, s.emissions_mtco2e);

-- @@ present
SELECT count(*)
FROM dw.fact_generation_source t
JOIN src_fact_generation_source s
  ON t.country_key = s.country_key AND t.year_key = s.year_key AND t.source_key = s.source_key
WHERE (t.data_source_key, t.quality_key, t.generation_twh, t.share_of_generation_pct,
       t.capacity_gw, t.emissions_mtco2e)
      IS NOT DISTINCT FROM
      (s.data_source_key, s.quality_key, s.generation_twh, s.share_of_generation_pct,
       s.capacity_gw, s.emissions_mtco2e);
