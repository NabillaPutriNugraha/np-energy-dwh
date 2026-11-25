-- Uji constraint. Dijalankan dalam transaksi lalu di-ROLLBACK, sehingga tidak meninggalkan data.
-- Harapan: semua pesan NOTICE berawal "LULUS".
BEGIN;
DO $$
DECLARE c INT; y INT; g INT; d INT; q INT; s INT;
BEGIN
  INSERT INTO dw.dim_country (iso3_code, country_name) VALUES ('ZZZ','Negara Uji') RETURNING country_key INTO c;
  SELECT year_key INTO y FROM dw.dim_year WHERE year_value=2019;
  SELECT country_group_key INTO g FROM dw.dim_country_group WHERE group_label='Tidak diketahui';
  SELECT data_source_key INTO d FROM dw.dim_data_source LIMIT 1;
  SELECT quality_key INTO q FROM dw.dim_quality_status LIMIT 1;
  SELECT source_key INTO s FROM dw.dim_electricity_source WHERE source_name='Coal';

  INSERT INTO dw.fact_energy_country_year (country_key,year_key,country_group_key,data_source_key,quality_key)
  VALUES (c,y,g,d,q);
  RAISE NOTICE 'LULUS: insert fakta valid berhasil';

  BEGIN  -- duplikat grain harus ditolak
    INSERT INTO dw.fact_energy_country_year (country_key,year_key,country_group_key,data_source_key,quality_key)
    VALUES (c,y,g,d,q);
    RAISE NOTICE 'GAGAL: duplikat grain lolos';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'LULUS: duplikat (country,year) ditolak';
  END;

  BEGIN  -- FK ke dimensi yang tidak ada harus ditolak
    INSERT INTO dw.fact_emissions_country_year (country_key,year_key,country_group_key,data_source_key,quality_key)
    VALUES (999999,y,g,d,q);
    RAISE NOTICE 'GAGAL: FK tidak valid lolos';
  EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'LULUS: FK country_key tidak valid ditolak';
  END;

  BEGIN  -- kunci alami negara duplikat harus ditolak
    INSERT INTO dw.dim_country (iso3_code, country_name) VALUES ('ZZZ','Duplikat');
    RAISE NOTICE 'GAGAL: ISO3 duplikat lolos';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'LULUS: ISO3 duplikat ditolak';
  END;

  INSERT INTO dw.fact_generation_source (country_key,year_key,source_key,data_source_key,quality_key)
  VALUES (c,y,s,d,q);
  BEGIN
    INSERT INTO dw.fact_generation_source (country_key,year_key,source_key,data_source_key,quality_key)
    VALUES (c,y,s,d,q);
    RAISE NOTICE 'GAGAL: duplikat grain sumber lolos';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'LULUS: duplikat (country,year,source) ditolak';
  END;

  BEGIN  -- kategori sumber di luar daftar harus ditolak
    INSERT INTO dw.dim_electricity_source (source_name, source_category, is_renewable) VALUES ('Uji','Lainnya',false);
    RAISE NOTICE 'GAGAL: kategori tidak valid lolos';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'LULUS: kategori sumber tidak valid ditolak';
  END;
END $$;
ROLLBACK;
