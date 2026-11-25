-- dim_country_group: satu baris per kombinasi unik 5 flag keanggotaan (dari Ember).
-- Baris "Tidak diketahui" sudah ada dari seed (05_seed_reference_data.sql) dan tidak disentuh di sini.

-- @@ source
CREATE TEMP TABLE src_dim_country_group ON COMMIT DROP AS
SELECT f.*,
       -- concat_ws melewati nilai NULL; hasil kosong berarti tidak ada keanggotaan sama sekali
       COALESCE(NULLIF(concat_ws(', ',
           CASE WHEN f.is_eu_member    THEN 'EU'    END,
           CASE WHEN f.is_oecd_member  THEN 'OECD'  END,
           CASE WHEN f.is_g20_member   THEN 'G20'   END,
           CASE WHEN f.is_g7_member    THEN 'G7'    END,
           CASE WHEN f.is_asean_member THEN 'ASEAN' END), ''),
           'Bukan anggota kelompok') AS group_label
FROM (SELECT DISTINCT
             eu_member    AS is_eu_member,
             oecd_member  AS is_oecd_member,
             g20_member   AS is_g20_member,
             g7_member    AS is_g7_member,
             asean_member AS is_asean_member
      FROM stg.ember_generation) f;

-- @@ merge
MERGE INTO dw.dim_country_group AS t
USING src_dim_country_group AS s
   ON  t.is_eu_member    = s.is_eu_member
   AND t.is_oecd_member  = s.is_oecd_member
   AND t.is_g20_member   = s.is_g20_member
   AND t.is_g7_member    = s.is_g7_member
   AND t.is_asean_member = s.is_asean_member
WHEN MATCHED AND t.group_label IS DISTINCT FROM s.group_label THEN
    UPDATE SET group_label = s.group_label
WHEN NOT MATCHED THEN
    INSERT (group_label, is_eu_member, is_oecd_member, is_g20_member, is_g7_member, is_asean_member)
    VALUES (s.group_label, s.is_eu_member, s.is_oecd_member, s.is_g20_member, s.is_g7_member, s.is_asean_member);

-- @@ present
SELECT count(*)
FROM dw.dim_country_group t
JOIN src_dim_country_group s
  ON  t.is_eu_member    = s.is_eu_member
  AND t.is_oecd_member  = s.is_oecd_member
  AND t.is_g20_member   = s.is_g20_member
  AND t.is_g7_member    = s.is_g7_member
  AND t.is_asean_member = s.is_asean_member
WHERE t.group_label = s.group_label;
