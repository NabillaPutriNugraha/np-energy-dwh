-- fact_energy_country_year. Grain: satu baris per negara per tahun (sumber: staging Renewable).
-- Status kualitas = indikator kelengkapan pada DUA kolom saja: renewables_share_energy dan renewables_share_elec.
-- "Valid dengan indikator kosong" artinya salah satu dari dua kolom itu NULL; bukan berarti baris tidak punya data.
-- Nilai NULL tidak pernah diganti dengan angka apa pun.

-- @@ source
CREATE TEMP TABLE src_fact_energy ON COMMIT DROP AS
SELECT c.country_key,
       y.year_key,
       m.country_group_key,
       ds.data_source_key,
       q.quality_key,
       r.renewables_share_energy,
       r.renewables_share_elec,
       r.fossil_share_energy,
       r.fossil_share_elec,
       r.low_carbon_share_energy,
       r.low_carbon_share_elec,
       r.electricity_generation,
       r.electricity_demand,
       r.primary_energy_consumption,
       r.population,
       r.gdp
FROM stg.renewable_energy r
JOIN dw.dim_country c        ON c.iso3_code  = r.iso_code
JOIN dw.dim_year y           ON y.year_value = r.year
JOIN tmp_country_group_map m ON m.iso3_code  = r.iso_code
JOIN dw.dim_data_source ds   ON ds.source_name = 'Renewable Energy Share by Country 2000-2025'
JOIN dw.dim_quality_status q ON q.status_name =
     CASE WHEN r.renewables_share_energy IS NULL OR r.renewables_share_elec IS NULL
          THEN 'Valid dengan indikator kosong' ELSE 'Valid lengkap' END;

-- @@ merge
MERGE INTO dw.fact_energy_country_year AS t
USING src_fact_energy AS s
   ON t.country_key = s.country_key AND t.year_key = s.year_key
WHEN MATCHED AND (t.country_group_key, t.data_source_key, t.quality_key,
                  t.renewables_share_energy, t.renewables_share_elec,
                  t.fossil_share_energy, t.fossil_share_elec,
                  t.low_carbon_share_energy, t.low_carbon_share_elec,
                  t.electricity_generation, t.electricity_demand,
                  t.primary_energy_consumption, t.population, t.gdp)
         IS DISTINCT FROM (s.country_group_key, s.data_source_key, s.quality_key,
                  s.renewables_share_energy, s.renewables_share_elec,
                  s.fossil_share_energy, s.fossil_share_elec,
                  s.low_carbon_share_energy, s.low_carbon_share_elec,
                  s.electricity_generation, s.electricity_demand,
                  s.primary_energy_consumption, s.population, s.gdp) THEN
    UPDATE SET country_group_key = s.country_group_key, data_source_key = s.data_source_key,
               quality_key = s.quality_key,
               renewables_share_energy = s.renewables_share_energy,
               renewables_share_elec = s.renewables_share_elec,
               fossil_share_energy = s.fossil_share_energy, fossil_share_elec = s.fossil_share_elec,
               low_carbon_share_energy = s.low_carbon_share_energy,
               low_carbon_share_elec = s.low_carbon_share_elec,
               electricity_generation = s.electricity_generation,
               electricity_demand = s.electricity_demand,
               primary_energy_consumption = s.primary_energy_consumption,
               population = s.population, gdp = s.gdp
WHEN NOT MATCHED THEN
    INSERT (country_key, year_key, country_group_key, data_source_key, quality_key,
            renewables_share_energy, renewables_share_elec, fossil_share_energy, fossil_share_elec,
            low_carbon_share_energy, low_carbon_share_elec, electricity_generation,
            electricity_demand, primary_energy_consumption, population, gdp)
    VALUES (s.country_key, s.year_key, s.country_group_key, s.data_source_key, s.quality_key,
            s.renewables_share_energy, s.renewables_share_elec, s.fossil_share_energy, s.fossil_share_elec,
            s.low_carbon_share_energy, s.low_carbon_share_elec, s.electricity_generation,
            s.electricity_demand, s.primary_energy_consumption, s.population, s.gdp);

-- @@ present
-- Baris sumber yang kini ada di fakta dengan SEMUA nilai persis sama (termasuk NULL yang tetap NULL).
SELECT count(*)
FROM dw.fact_energy_country_year t
JOIN src_fact_energy s ON t.country_key = s.country_key AND t.year_key = s.year_key
WHERE (t.country_group_key, t.data_source_key, t.quality_key,
       t.renewables_share_energy, t.renewables_share_elec, t.fossil_share_energy, t.fossil_share_elec,
       t.low_carbon_share_energy, t.low_carbon_share_elec, t.electricity_generation,
       t.electricity_demand, t.primary_energy_consumption, t.population, t.gdp)
      IS NOT DISTINCT FROM
      (s.country_group_key, s.data_source_key, s.quality_key,
       s.renewables_share_energy, s.renewables_share_elec, s.fossil_share_energy, s.fossil_share_elec,
       s.low_carbon_share_energy, s.low_carbon_share_elec, s.electricity_generation,
       s.electricity_demand, s.primary_energy_consumption, s.population, s.gdp);
