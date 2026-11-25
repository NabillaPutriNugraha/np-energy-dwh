-- Fakta: PK surrogate, FK ke dimensi, dan UNIQUE pada kombinasi grain.
-- Ukuran sengaja tanpa CHECK rentang; anomali ditangani oleh query validasi (peringatan), bukan ditolak.

-- Grain: satu baris per negara per tahun (sumber: Renewable Energy Share)
CREATE TABLE IF NOT EXISTS dw.fact_energy_country_year (
    energy_fact_key          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_key              INTEGER  NOT NULL REFERENCES dw.dim_country(country_key),
    year_key                 SMALLINT NOT NULL REFERENCES dw.dim_year(year_key),
    country_group_key        SMALLINT NOT NULL REFERENCES dw.dim_country_group(country_group_key),
    data_source_key          SMALLINT NOT NULL REFERENCES dw.dim_data_source(data_source_key),
    quality_key              SMALLINT NOT NULL REFERENCES dw.dim_quality_status(quality_key),
    renewables_share_energy  DOUBLE PRECISION,
    renewables_share_elec    DOUBLE PRECISION,
    fossil_share_energy      DOUBLE PRECISION,
    fossil_share_elec        DOUBLE PRECISION,
    low_carbon_share_energy  DOUBLE PRECISION,
    low_carbon_share_elec    DOUBLE PRECISION,
    electricity_generation   DOUBLE PRECISION,
    electricity_demand       DOUBLE PRECISION,
    primary_energy_consumption DOUBLE PRECISION,
    population               DOUBLE PRECISION,
    gdp                      DOUBLE PRECISION,
    UNIQUE (country_key, year_key)
);

-- Grain: satu baris per negara per tahun (sumber: Ember, baris Total generation + Renewables)
CREATE TABLE IF NOT EXISTS dw.fact_emissions_country_year (
    emissions_fact_key          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_key                 INTEGER  NOT NULL REFERENCES dw.dim_country(country_key),
    year_key                    SMALLINT NOT NULL REFERENCES dw.dim_year(year_key),
    country_group_key           SMALLINT NOT NULL REFERENCES dw.dim_country_group(country_group_key),
    data_source_key             SMALLINT NOT NULL REFERENCES dw.dim_data_source(data_source_key),
    quality_key                 SMALLINT NOT NULL REFERENCES dw.dim_quality_status(quality_key),
    total_generation_twh        DOUBLE PRECISION,
    renewables_generation_twh   DOUBLE PRECISION,
    renewables_share_pct        DOUBLE PRECISION,
    total_emissions_mtco2e      DOUBLE PRECISION,
    emissions_intensity_gco2e_kwh DOUBLE PRECISION,
    UNIQUE (country_key, year_key)
);

-- Grain: satu baris per negara per tahun per sumber listrik murni (sumber: Ember)
CREATE TABLE IF NOT EXISTS dw.fact_generation_source (
    generation_fact_key   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_key           INTEGER  NOT NULL REFERENCES dw.dim_country(country_key),
    year_key              SMALLINT NOT NULL REFERENCES dw.dim_year(year_key),
    source_key            SMALLINT NOT NULL REFERENCES dw.dim_electricity_source(source_key),
    data_source_key       SMALLINT NOT NULL REFERENCES dw.dim_data_source(data_source_key),
    quality_key           SMALLINT NOT NULL REFERENCES dw.dim_quality_status(quality_key),
    generation_twh        DOUBLE PRECISION,
    share_of_generation_pct DOUBLE PRECISION,
    capacity_gw           DOUBLE PRECISION,
    emissions_mtco2e      DOUBLE PRECISION,
    UNIQUE (country_key, year_key, source_key)
);

-- Indeks pada FK untuk mempercepat join dashboard (PK dan UNIQUE sudah otomatis berindeks).
CREATE INDEX IF NOT EXISTS ix_fenergy_year   ON dw.fact_energy_country_year (year_key);
CREATE INDEX IF NOT EXISTS ix_femis_year     ON dw.fact_emissions_country_year (year_key);
CREATE INDEX IF NOT EXISTS ix_fgen_year      ON dw.fact_generation_source (year_key);
CREATE INDEX IF NOT EXISTS ix_fgen_source    ON dw.fact_generation_source (source_key);
