-- Peta negara -> kelompok negara, dipakai tabel fakta (Fase 3B-2) untuk mengisi country_group_key.
-- Aturan: negara yang ada di Ember mendapat kelompok sesuai flag Ember tahun terbaru;
--         negara yang TIDAK ada di Ember (12 negara) mendapat kelompok "Tidak diketahui".
-- Tabel sementara: hilang otomatis saat transaksi selesai, tidak menambah objek permanen.

-- @@ map
CREATE TEMP TABLE tmp_country_group_map ON COMMIT DROP AS
SELECT c.iso3_code,
       COALESCE(g.country_group_key, u.country_group_key) AS country_group_key,
       (e.iso_3_code IS NULL)                              AS is_unknown
FROM dw.dim_country c
LEFT JOIN (SELECT DISTINCT ON (iso_3_code) *
           FROM stg.ember_generation
           ORDER BY iso_3_code, year DESC) e
       ON e.iso_3_code = c.iso3_code
-- join ke grup HANYA bila negara ada di Ember (sehingga flag NULL tidak cocok "secara kebetulan")
LEFT JOIN dw.dim_country_group g
       ON e.iso_3_code IS NOT NULL
      AND g.is_eu_member    = e.eu_member
      AND g.is_oecd_member  = e.oecd_member
      AND g.is_g20_member   = e.g20_member
      AND g.is_g7_member    = e.g7_member
      AND g.is_asean_member = e.asean_member
CROSS JOIN (SELECT country_group_key FROM dw.dim_country_group
            WHERE group_label = 'Tidak diketahui') u;
