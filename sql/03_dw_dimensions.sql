-- Dimensi: surrogate key (identity) sebagai PK, kunci alami dibuat UNIQUE.
CREATE TABLE IF NOT EXISTS dw.dim_country (
    country_key  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    iso3_code    CHAR(3)  NOT NULL UNIQUE,
    country_name TEXT     NOT NULL,
    continent    TEXT,
    ember_region TEXT
);
CREATE TABLE IF NOT EXISTS dw.dim_year (
    year_key   SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    year_value SMALLINT NOT NULL UNIQUE CHECK (year_value BETWEEN 1990 AND 2100)
);
CREATE TABLE IF NOT EXISTS dw.dim_electricity_source (
    source_key      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name     TEXT    NOT NULL UNIQUE,
    source_category TEXT    NOT NULL CHECK (source_category IN ('Fossil','Renewable','Nuklir')),
    is_renewable    BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS dw.dim_country_group (
    country_group_key SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_label       TEXT NOT NULL UNIQUE,
    is_eu_member      BOOLEAN,
    is_oecd_member    BOOLEAN,
    is_g20_member     BOOLEAN,
    is_g7_member      BOOLEAN,
    is_asean_member   BOOLEAN,
    UNIQUE NULLS NOT DISTINCT (is_eu_member, is_oecd_member, is_g20_member, is_g7_member, is_asean_member)
);
CREATE TABLE IF NOT EXISTS dw.dim_data_source (
    data_source_key SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name     TEXT NOT NULL UNIQUE,
    publisher       TEXT NOT NULL,
    file_name       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dw.dim_quality_status (
    quality_key SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE
);
