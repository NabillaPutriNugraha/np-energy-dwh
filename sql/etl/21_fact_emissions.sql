-- fact_emissions_country_year. Grain: satu baris per negara per tahun (sumber: staging Ember).
-- Satu baris fakta dibentuk dari DUA baris Ember: "Total generation" dan "Renewables" (negara dan tahun sama).
-- Status kualitas = indikator kelengkapan pada DUA kolom saja: emissions_intensity_gco2e_kwh dan renewables_share_pct.
-- "Valid dengan indikator kosong" artinya salah satunya NULL; bukan berarti baris tidak punya data.

-- @@ source
CREATE TEMP TABLE src_fact_emissions ON COMMIT DROP AS
SELECT c.country_key,
       y.year_key,
       m.country_group_key,
       ds.data_source_key,
       q.quality_key,
       t.generation_twh                  AS total_generation_twh,
       rn.generation_twh                 AS renewables_generation_twh,
       rn.share_of_generation_pct        AS renewables_share_pct,
       t.emissions_mtco2e                AS total_emissions_mtco2e,
       t.emissions_intensity_gco2e_kwh   AS emissions_intensity_gco2e_kwh
FROM (SELECT * FROM stg.ember_generation WHERE electricity_source = 'Total generation') t
JOIN (SELECT * FROM stg.ember_generation WHERE electricity_source = 'Renewables') rn
  ON rn.iso_3_code = t.iso_3_code AND rn.year = t.year
JOIN dw.dim_country c        ON c.iso3_code  = t.iso_3_code
JOIN dw.dim_year y           ON y.year_value = t.year
JOIN tmp_country_group_map m ON m.iso3_code  = t.iso_3_code
JOIN dw.dim_data_source ds   ON ds.source_name = 'Ember Yearly Electricity Data'
JOIN dw.dim_quality_status q ON q.status_name =
     CASE WHEN t.emissions_intensity_gco2e_kwh IS NULL OR rn.share_of_generation_pct IS NULL
          THEN 'Valid dengan indikator kosong' ELSE 'Valid lengkap' END;

-- @@ merge
MERGE INTO dw.fact_emissions_country_year AS t
USING src_fact_emissions AS s
   ON t.country_key = s.country_key AND t.year_key = s.year_key
WHEN MATCHED AND (t.country_group_key, t.data_source_key, t.quality_key,
                  t.total_generation_twh, t.renewables_generation_twh, t.renewables_share_pct,
                  t.total_emissions_mtco2e, t.emissions_intensity_gco2e_kwh)
         IS DISTINCT FROM (s.country_group_key, s.data_source_key, s.quality_key,
                  s.total_generation_twh, s.renewables_generation_twh, s.renewables_share_pct,
                  s.total_emissions_mtco2e, s.emissions_intensity_gco2e_kwh) THEN
    UPDATE SET country_group_key = s.country_group_key, data_source_key = s.data_source_key,
               quality_key = s.quality_key,
               total_generation_twh = s.total_generation_twh,
               renewables_generation_twh = s.renewables_generation_twh,
               renewables_share_pct = s.renewables_share_pct,
               total_emissions_mtco2e = s.total_emissions_mtco2e,
               emissions_intensity_gco2e_kwh = s.emissions_intensity_gco2e_kwh
WHEN NOT MATCHED THEN
    INSERT (country_key, year_key, country_group_key, data_source_key, quality_key,
            total_generation_twh, renewables_generation_twh, renewables_share_pct,
            total_emissions_mtco2e, emissions_intensity_gco2e_kwh)
    VALUES (s.country_key, s.year_key, s.country_group_key, s.data_source_key, s.quality_key,
            s.total_generation_twh, s.renewables_generation_twh, s.renewables_share_pct,
            s.total_emissions_mtco2e, s.emissions_intensity_gco2e_kwh);

-- @@ present
SELECT count(*)
FROM dw.fact_emissions_country_year t
JOIN src_fact_emissions s ON t.country_key = s.country_key AND t.year_key = s.year_key
WHERE (t.country_group_key, t.data_source_key, t.quality_key, t.total_generation_twh,
       t.renewables_generation_twh, t.renewables_share_pct, t.total_emissions_mtco2e,
       t.emissions_intensity_gco2e_kwh)
      IS NOT DISTINCT FROM
      (s.country_group_key, s.data_source_key, s.quality_key, s.total_generation_twh,
       s.renewables_generation_twh, s.renewables_share_pct, s.total_emissions_mtco2e,
       s.emissions_intensity_gco2e_kwh);
