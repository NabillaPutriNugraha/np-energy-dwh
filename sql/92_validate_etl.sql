-- Query validasi ETL. Bagian A: staging (Fase 3A). Bagian dimensi dan fakta ditambahkan di Fase 3B.

-- A1) Jumlah baris staging dan batch yang memuatnya (harapan: ember 11206, renewable 1100, satu batch_id yang sama)
SELECT 'stg.ember_generation' AS tabel, count(*) AS jumlah_baris, min(batch_id) AS batch_min, max(batch_id) AS batch_max
FROM stg.ember_generation
UNION ALL
SELECT 'stg.renewable_energy', count(*), min(batch_id), max(batch_id) FROM stg.renewable_energy;

-- A2) Duplikasi kunci alami (harapan: kedua hasil 0)
SELECT 'ember' AS tabel, count(*) AS kombinasi_duplikat FROM (
    SELECT 1 FROM stg.ember_generation GROUP BY iso_3_code, year, electricity_source HAVING count(*) > 1) d
UNION ALL
SELECT 'renewable', count(*) FROM (
    SELECT 1 FROM stg.renewable_energy GROUP BY iso_code, year HAVING count(*) > 1) d;

-- A3) Baris per sumber listrik pada staging Ember (harapan: 11 sumber = 9 sumber murni + Total generation + Renewables)
SELECT electricity_source, count(*) AS jumlah_baris
FROM stg.ember_generation GROUP BY electricity_source ORDER BY electricity_source;

-- A4) Jumlah negara dan tahun (harapan: ember 209 negara, renewable 220 negara, masing-masing 5 tahun)
SELECT 'ember' AS sumber, count(DISTINCT iso_3_code) AS negara, count(DISTINCT year) AS tahun FROM stg.ember_generation
UNION ALL
SELECT 'renewable', count(DISTINCT iso_code), count(DISTINCT year) FROM stg.renewable_energy;

-- A5) NULL pada kolom indikator utama (dicatat apa adanya, tanpa imputasi)
-- harapan: renewables_share_energy 705, renewables_share_elec 42
SELECT count(*) FILTER (WHERE renewables_share_energy IS NULL) AS share_energy_null,
       count(*) FILTER (WHERE renewables_share_elec   IS NULL) AS share_elec_null
FROM stg.renewable_energy;

-- A6) Riwayat eksekusi ETL (10 terakhir) dan langkahnya
SELECT run_id, started_at, finished_at, status, error_message
FROM ops.etl_run ORDER BY run_id DESC LIMIT 10;

SELECT run_id, step_name, status, rows_expected, rows_actual, message
FROM ops.etl_step ORDER BY step_id DESC LIMIT 10;
