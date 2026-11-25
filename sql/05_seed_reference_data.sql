-- Data referensi tetap. Dimensi negara dan kelompok negara diisi oleh ETL dari data.
INSERT INTO dw.dim_year (year_value) SELECT g FROM generate_series(2019, 2023) g
ON CONFLICT (year_value) DO NOTHING;

INSERT INTO dw.dim_electricity_source (source_name, source_category, is_renewable) VALUES
 ('Coal','Fossil',false), ('Gas','Fossil',false), ('Other fossil','Fossil',false),
 ('Nuclear','Nuklir',false),
 ('Bioenergy','Renewable',true), ('Hydro','Renewable',true), ('Solar','Renewable',true),
 ('Wind','Renewable',true), ('Other renewables','Renewable',true)
ON CONFLICT (source_name) DO NOTHING;

INSERT INTO dw.dim_data_source (source_name, publisher, file_name) VALUES
 ('Ember Yearly Electricity Data','Ember','release_generation_yearly_global.csv'),
 ('Renewable Energy Share by Country 2000-2025','Kaggle','renewable_energy_share_2000_2025.csv')
ON CONFLICT (source_name) DO NOTHING;

INSERT INTO dw.dim_quality_status (status_name) VALUES
 ('Valid lengkap'), ('Valid dengan indikator kosong')
ON CONFLICT (status_name) DO NOTHING;

INSERT INTO dw.dim_country_group (group_label) VALUES ('Tidak diketahui')
ON CONFLICT (group_label) DO NOTHING;
