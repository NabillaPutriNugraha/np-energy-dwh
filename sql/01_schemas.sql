-- Dua skema memisahkan lapisan data: stg = staging, dw = dimensional warehouse.
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dw;
COMMENT ON SCHEMA stg IS 'Staging: salinan hasil preprocessing, belum dimodelkan';
COMMENT ON SCHEMA dw  IS 'Data Warehouse: galaxy schema (6 dimensi, 3 fakta)';
