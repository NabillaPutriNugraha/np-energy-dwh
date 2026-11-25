"""Fase 3B-1 dan 3B-2: transformasi dan pemuatan DIMENSI (3B-1) serta TABEL FAKTA (3B-2)
ke Data Warehouse (staging -> dw).

Seluruh pemuatan berjalan dalam SATU transaksi:
  * jika semua langkah dan gerbang validasi lolos  -> COMMIT
  * jika ada satu saja yang gagal                  -> ROLLBACK (DW kembali seperti sebelum run)
Log kegagalan tetap tersimpan karena ditulis RunLogger lewat koneksi terpisah.

Catatan status kualitas (dipakai pada tabel fakta): status "Valid dengan indikator
kosong" hanya berarti ada NILAI KOSONG pada kolom indikator yang ditetapkan (keputusan D4).
Ini bukan penilaian bahwa seluruh baris tidak punya data. Nilai kosong tidak pernah diimputasi.
"""
import re

import config
from etl_lib import EtlError, RunLogger, connect, log

SQL_DIR = config.ROOT / "sql" / "etl"


def read_sections(filename: str) -> dict:
    """Memecah file SQL menjadi blok bernama. Penanda blok: baris '-- @@ nama'."""
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    parts = re.split(r"^-- @@ (\w+)\s*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def scalar(cur, sql: str):
    cur.execute(sql)
    return cur.fetchone()[0]


def gate(cur, name: str, actual_sql: str, expected=0):
    """Gerbang validasi: nilai aktual harus sama dengan harapan, kalau tidak proses dihentikan."""
    actual = scalar(cur, actual_sql)
    exp = scalar(cur, expected) if isinstance(expected, str) else expected
    if actual != exp:
        raise EtlError(f"Gerbang '{name}' gagal: aktual={actual}, harapan={exp}")
    log.info("  gerbang OK  %-52s nilai=%s", name, actual)


def merge_table(cur, filename: str, target: str, source_table: str) -> dict:
    """Menjalankan blok source -> merge -> present untuk satu dimensi dan menghitung
    jumlah baris yang di-insert, di-update, dan tidak berubah."""
    sec = read_sections(filename)
    cur.execute(sec["source"])
    n_source = scalar(cur, f"SELECT count(*) FROM {source_table}")
    before = scalar(cur, f"SELECT count(*) FROM {target}")

    cur.execute(sec["merge"])
    affected = cur.rowcount            # baris yang di-INSERT atau di-UPDATE oleh MERGE
    after = scalar(cur, f"SELECT count(*) FROM {target}")

    inserted = after - before
    updated = affected - inserted
    unchanged = n_source - affected
    present = scalar(cur, sec["present"])
    if present != n_source or updated < 0 or unchanged < 0:
        raise EtlError(f"{target}: hasil MERGE tidak konsisten (sumber={n_source}, "
                       f"insert={inserted}, update={updated}, tetap={unchanged}, cocok={present})")
    log.info("  %-24s sumber=%d  insert=%d  update=%d  tetap=%d  | baris di tabel=%d",
             target, n_source, inserted, updated, unchanged, after)
    return {"table": target, "source": n_source, "inserted": inserted, "updated": updated,
            "unchanged": unchanged, "present": present, "total": after}


def gate_value(name: str, actual, expected):
    """Seperti gate(), tetapi nilai aktual sudah dihitung di Python."""
    if actual != expected:
        raise EtlError(f"Gerbang '{name}' gagal: aktual={actual}, harapan={expected}")
    log.info("  gerbang OK  %-52s nilai=%s", name, actual)


def check_measures(cur, label: str, src: str, measures: list):
    """Memastikan setiap kolom ukuran di tabel sumber fakta sama dengan staging:
    (a) jumlah nilai NON-NULL sama  -> bukti NULL tidak diisi/diimputasi
    (b) jumlah total (SUM) sama     -> bukti tidak ada nilai yang berubah atau hilang."""
    for src_col, stg_from, stg_col in measures:
        cur.execute(f"SELECT sum({src_col}), count({src_col}) FROM {src}")
        s_sum, s_cnt = cur.fetchone()
        cur.execute(f"SELECT sum({stg_col}), count({stg_col}) FROM {stg_from}")
        t_sum, t_cnt = cur.fetchone()
        if s_cnt != t_cnt:
            raise EtlError(f"{label}.{src_col}: nilai non-NULL fakta={s_cnt}, staging={t_cnt}")
        s_sum, t_sum = float(s_sum or 0), float(t_sum or 0)
        if abs(s_sum - t_sum) > 1e-9 * max(1.0, abs(t_sum)):
            raise EtlError(f"{label}.{src_col}: SUM fakta={s_sum}, staging={t_sum}")
    log.info("  gerbang OK  %-52s kolom=%d", f"{label}: SUM dan jumlah non-NULL = staging", len(measures))


EMBER = "stg.ember_generation"
TG = f"{EMBER} WHERE electricity_source = 'Total generation'"
RN = f"{EMBER} WHERE electricity_source = 'Renewables'"
PURE = f"{EMBER} WHERE electricity_source NOT IN ('Total generation', 'Renewables')"
SRC_REN, SRC_EMB = "Renewable Energy Share by Country 2000-2025", "Ember Yearly Electricity Data"
STD_FKS = [("dw.dim_country", "country_key"), ("dw.dim_year", "year_key"),
           ("dw.dim_data_source", "data_source_key"), ("dw.dim_quality_status", "quality_key")]

# Spesifikasi tiga tabel fakta. Satu daftar ini mengatur seluruh pemuatan dan gerbang validasinya.
FACTS = [
    {"short": "fact_energy", "file": "20_fact_energy.sql", "target": "dw.fact_energy_country_year",
     "src": "src_fact_energy", "grain": "country_key, year_key", "source_name": SRC_REN,
     "expected_rows": "SELECT count(*) FROM stg.renewable_energy",
     "fks": STD_FKS + [("dw.dim_country_group", "country_group_key")],
     "measures": [(c, "stg.renewable_energy", c) for c in (
         "renewables_share_energy", "renewables_share_elec", "fossil_share_energy", "fossil_share_elec",
         "low_carbon_share_energy", "low_carbon_share_elec", "electricity_generation",
         "electricity_demand", "primary_energy_consumption", "population", "gdp")],
     "empty_src": "(s.renewables_share_energy IS NULL OR s.renewables_share_elec IS NULL)",
     "empty_stg": "SELECT count(*) FROM stg.renewable_energy "
                  "WHERE renewables_share_energy IS NULL OR renewables_share_elec IS NULL",
     # 12 negara hanya-Renewable (x 5 tahun) harus memakai kelompok 'Tidak diketahui'
     "unknown_expected": "SELECT count(*) FROM stg.renewable_energy "
                         "WHERE iso_code NOT IN (SELECT iso_3_code FROM stg.ember_generation)"},
    {"short": "fact_emissions", "file": "21_fact_emissions.sql", "target": "dw.fact_emissions_country_year",
     "src": "src_fact_emissions", "grain": "country_key, year_key", "source_name": SRC_EMB,
     "expected_rows": f"SELECT count(*) FROM {TG}", "also_equal": f"SELECT count(*) FROM {RN}",
     "fks": STD_FKS + [("dw.dim_country_group", "country_group_key")],
     "measures": [("total_generation_twh", TG, "generation_twh"),
                  ("renewables_generation_twh", RN, "generation_twh"),
                  ("renewables_share_pct", RN, "share_of_generation_pct"),
                  ("total_emissions_mtco2e", TG, "emissions_mtco2e"),
                  ("emissions_intensity_gco2e_kwh", TG, "emissions_intensity_gco2e_kwh")],
     "empty_src": "(s.emissions_intensity_gco2e_kwh IS NULL OR s.renewables_share_pct IS NULL)",
     "empty_stg": f"SELECT count(*) FROM (SELECT * FROM {TG}) t JOIN (SELECT * FROM {RN}) r "
                  "ON r.iso_3_code = t.iso_3_code AND r.year = t.year "
                  "WHERE t.emissions_intensity_gco2e_kwh IS NULL OR r.share_of_generation_pct IS NULL",
     "unknown_expected": "SELECT 0"},
    {"short": "fact_generation_source", "file": "22_fact_generation_source.sql",
     "target": "dw.fact_generation_source", "src": "src_fact_generation_source",
     "grain": "country_key, year_key, source_key", "source_name": SRC_EMB,
     "expected_rows": f"SELECT count(*) FROM {PURE}",
     "fks": STD_FKS + [("dw.dim_electricity_source", "source_key")],
     "measures": [(c, PURE, c) for c in ("generation_twh", "share_of_generation_pct",
                                         "capacity_gw", "emissions_mtco2e")],
     "empty_src": "(s.generation_twh IS NULL OR s.share_of_generation_pct IS NULL)",
     # PURE sudah memuat WHERE, jadi kondisi tambahan memakai AND
     "empty_stg": f"SELECT count(*) FROM {PURE} AND (generation_twh IS NULL "
                  "OR share_of_generation_pct IS NULL)",
     "unknown_expected": None},
]
QUALITY_EMPTY = "'Valid dengan indikator kosong'"


def load_fact(cur, f: dict) -> dict:
    """Memuat satu tabel fakta lalu menjalankan gerbang validasinya."""
    res = merge_table(cur, f["file"], f["target"], f["src"])
    n, src, short = res["source"], f["src"], f["short"]

    # 1. Tidak ada baris yang hilang diam-diam saat join ke dimensi
    gate_value(f"{short}: baris sumber = baris staging", n, scalar(cur, f["expected_rows"]))
    if f.get("also_equal"):
        gate_value(f"{short}: baris Total generation = baris Renewables", n,
                   scalar(cur, f["also_equal"]))
    # 2. Tidak ada duplikasi pada grain
    gate(cur, f"{short}: tidak ada duplikasi grain",
         f"SELECT count(*) FROM (SELECT 1 FROM {src} GROUP BY {f['grain']} HAVING count(*) > 1) d")
    # 3. Integritas referensial: tidak ada foreign key tanpa induk
    orphan = " OR ".join(f"NOT EXISTS (SELECT 1 FROM {d} x WHERE x.{k} = f.{k})" for d, k in f["fks"])
    gate(cur, f"{short}: tidak ada foreign key yatim",
         f"SELECT count(*) FROM {f['target']} f WHERE {orphan}")
    # 4. Pemetaan sumber data sesuai seed dim_data_source
    gate(cur, f"{short}: data_source_key sesuai seed Fase 2",
         f"SELECT count(*) FROM {src} s JOIN dw.dim_data_source d ON d.data_source_key = s.data_source_key "
         f"WHERE d.source_name <> '{f['source_name']}'")
    # 5. Nilai ukuran = staging (SUM dan jumlah non-NULL), artinya NULL tidak diimputasi
    check_measures(cur, short, src, f["measures"])
    # 6. Status kualitas: setiap baris sesuai aturan D4, dan jumlahnya sama dengan hitungan dari staging
    gate(cur, f"{short}: status kualitas sesuai aturan D4 (tiap baris)",
         f"SELECT count(*) FROM {src} s JOIN dw.dim_quality_status q ON q.quality_key = s.quality_key "
         f"WHERE (q.status_name = 'Valid lengkap' AND {f['empty_src']}) "
         f"OR (q.status_name = {QUALITY_EMPTY} AND NOT {f['empty_src']})")
    gate(cur, f"{short}: jumlah status 'indikator kosong' = hitungan staging",
         f"SELECT count(*) FROM {src} s JOIN dw.dim_quality_status q ON q.quality_key = s.quality_key "
         f"WHERE q.status_name = {QUALITY_EMPTY}", f["empty_stg"])
    # 7. Kelompok negara "Tidak diketahui" hanya untuk negara yang tidak ada di Ember
    if f["unknown_expected"] is not None:
        gate(cur, f"{short}: baris kelompok 'Tidak diketahui' sesuai harapan",
             f"SELECT count(*) FROM {src} s JOIN dw.dim_country_group g "
             "ON g.country_group_key = s.country_group_key WHERE g.group_label = 'Tidak diketahui'",
             f["unknown_expected"])
    return res


def reconcile_sources(cur):
    """Rekonsiliasi lintas fakta (PERINGATAN, bukan penghenti): total pembangkitan per negara-tahun
    di fact_emissions harus sama dengan jumlah pembangkitan semua sumber murni di fact_generation_source.
    Selisih kecil (pembulatan) wajar; ini sifat sumber data, bukan kesalahan ETL."""
    cur.execute(
        "SELECT count(*), count(*) FILTER (WHERE abs(e.total_generation_twh - g.total) > 0.05), "
        "COALESCE(max(abs(e.total_generation_twh - g.total)), 0) "
        "FROM dw.fact_emissions_country_year e JOIN (SELECT country_key, year_key, "
        "sum(generation_twh) AS total FROM dw.fact_generation_source GROUP BY country_key, year_key) g "
        "ON g.country_key = e.country_key AND g.year_key = e.year_key")
    pairs, bad, max_diff = cur.fetchone()
    no_src = scalar(cur, "SELECT count(*) FROM dw.fact_emissions_country_year e WHERE NOT EXISTS ("
                         "SELECT 1 FROM dw.fact_generation_source g WHERE g.country_key = e.country_key "
                         "AND g.year_key = e.year_key)")
    level = log.warning if (bad or no_src) else log.info
    level("  rekonsiliasi total vs jumlah sumber: pasangan=%d, selisih>0.05 TWh=%d, selisih maksimum=%.4f TWh, "
          "negara-tahun tanpa baris sumber=%d", pairs, bad, float(max_diff), no_src)


def load_dw(run: RunLogger):
    with run.step("load_dw") as info:
        results = []
        with connect() as conn:            # satu transaksi: commit jika sukses, rollback jika error
            with conn.cursor() as cur:
                # --- Gerbang awal: staging harus berasal dari run ini dan tidak kosong
                gate(cur, "staging berasal dari run ini (batch_id)",
                     f"SELECT count(*) FROM (SELECT batch_id FROM stg.ember_generation "
                     f"UNION ALL SELECT batch_id FROM stg.renewable_energy) b "
                     f"WHERE b.batch_id <> {run.run_id}")
                gate(cur, "staging tidak kosong",
                     "SELECT (SELECT count(*) FROM stg.ember_generation) = 0 "
                     "OR (SELECT count(*) FROM stg.renewable_energy) = 0", False)
                # Konsistensi kode negara: harus 3 huruf kapital pada kedua sumber
                gate(cur, "kode ISO3 staging berformat 3 huruf kapital",
                     "SELECT count(*) FROM (SELECT iso_3_code AS iso FROM stg.ember_generation "
                     "UNION ALL SELECT iso_code FROM stg.renewable_energy) x "
                     "WHERE x.iso !~ '^[A-Z]{3}$'")

                # --- Pemuatan dimensi
                results.append(merge_table(cur, "10_dim_country.sql",
                                           "dw.dim_country", "src_dim_country"))
                results.append(merge_table(cur, "11_dim_country_group.sql",
                                           "dw.dim_country_group", "src_dim_country_group"))
                cur.execute(read_sections("12_country_group_map.sql")["map"])

                # --- Gerbang validasi dimensi (rumusan berbeda dari kode pemuatan, agar independen)
                ember_latest = ("(SELECT DISTINCT ON (iso_3_code) * FROM stg.ember_generation "
                                "ORDER BY iso_3_code, year DESC)")
                ren_only = ("(SELECT DISTINCT ON (iso_code) iso_code, country FROM stg.renewable_energy "
                            "WHERE iso_code NOT IN (SELECT iso_3_code FROM stg.ember_generation) "
                            "ORDER BY iso_code, year DESC)")
                gate(cur, "setiap ISO staging ada di dim_country",
                     "SELECT count(*) FROM (SELECT iso_3_code AS iso FROM stg.ember_generation "
                     "UNION SELECT iso_code FROM stg.renewable_energy) u "
                     "WHERE NOT EXISTS (SELECT 1 FROM dw.dim_country c WHERE c.iso3_code = u.iso)")
                gate(cur, "nama negara Ember = nama di dim_country",
                     f"SELECT count(*) FROM {ember_latest} e JOIN dw.dim_country c "
                     "ON c.iso3_code = e.iso_3_code WHERE c.country_name IS DISTINCT FROM e.area")
                gate(cur, "atribut wilayah Ember = atribut di dim_country",
                     f"SELECT count(*) FROM {ember_latest} e JOIN dw.dim_country c "
                     "ON c.iso3_code = e.iso_3_code WHERE (c.continent, c.ember_region) "
                     "IS DISTINCT FROM (e.continent, e.ember_region)")
                gate(cur, "negara hanya-Renewable: nama dari Renewable, wilayah kosong",
                     f"SELECT count(*) FROM {ren_only} r JOIN dw.dim_country c "
                     "ON c.iso3_code = r.iso_code WHERE c.country_name IS DISTINCT FROM r.country "
                     "OR c.continent IS NOT NULL OR c.ember_region IS NOT NULL")
                gate(cur, "setiap kombinasi flag Ember ada di dim_country_group",
                     "SELECT count(*) FROM (SELECT DISTINCT eu_member, oecd_member, g20_member, "
                     "g7_member, asean_member FROM stg.ember_generation) f WHERE NOT EXISTS ("
                     "SELECT 1 FROM dw.dim_country_group g WHERE g.is_eu_member = f.eu_member "
                     "AND g.is_oecd_member = f.oecd_member AND g.is_g20_member = f.g20_member "
                     "AND g.is_g7_member = f.g7_member AND g.is_asean_member = f.asean_member)")
                gate(cur, "baris 'Tidak diketahui' tepat satu",
                     "SELECT count(*) FROM dw.dim_country_group WHERE group_label = 'Tidak diketahui'", 1)

                # --- Gerbang peta kelompok negara (menjamin 12 negara hanya-Renewable = Tidak diketahui)
                gate(cur, "semua negara di dim_country punya kelompok",
                     "SELECT count(*) FROM dw.dim_country c WHERE NOT EXISTS "
                     "(SELECT 1 FROM tmp_country_group_map m WHERE m.iso3_code = c.iso3_code)")
                gate(cur, "negara hanya-Renewable -> kelompok 'Tidak diketahui'",
                     "SELECT count(*) FROM tmp_country_group_map m WHERE m.is_unknown AND m.iso3_code "
                     "IN (SELECT iso_code FROM stg.renewable_energy)",
                     "SELECT count(DISTINCT iso_code) FROM stg.renewable_energy "
                     "WHERE iso_code NOT IN (SELECT iso_3_code FROM stg.ember_generation)")
                gate(cur, "negara Ember tidak ada yang 'Tidak diketahui'",
                     "SELECT count(*) FROM tmp_country_group_map m WHERE m.is_unknown AND m.iso3_code "
                     "IN (SELECT iso_3_code FROM stg.ember_generation)")
                gate(cur, "kelompok hasil peta = flag Ember terbaru",
                     f"SELECT count(*) FROM {ember_latest} e "
                     "JOIN tmp_country_group_map m ON m.iso3_code = e.iso_3_code "
                     "JOIN dw.dim_country_group g ON g.country_group_key = m.country_group_key "
                     "WHERE (g.is_eu_member, g.is_oecd_member, g.is_g20_member, g.is_g7_member, "
                     "g.is_asean_member) IS DISTINCT FROM (e.eu_member, e.oecd_member, e.g20_member, "
                     "e.g7_member, e.asean_member)")

                # ===================== Fase 3B-2: tabel fakta =====================
                # Gerbang awal: tahun dan sumber listrik di staging harus dikenal dimensi, supaya tidak
                # ada baris yang terbuang diam-diam oleh JOIN.
                gate(cur, "semua tahun staging ada di dim_year",
                     "SELECT count(*) FROM (SELECT year FROM stg.ember_generation UNION "
                     "SELECT year FROM stg.renewable_energy) y "
                     "WHERE y.year NOT IN (SELECT year_value FROM dw.dim_year)")
                gate(cur, "semua sumber listrik Ember dikenal (9 murni + 2 agregat)",
                     "SELECT count(DISTINCT electricity_source) FROM stg.ember_generation "
                     "WHERE electricity_source NOT IN ('Total generation', 'Renewables') "
                     "AND electricity_source NOT IN (SELECT source_name FROM dw.dim_electricity_source)")
                for spec in FACTS:
                    results.append(load_fact(cur, spec))
                reconcile_sources(cur)


        # Sampai baris ini transaksi sudah di-COMMIT (keluar dari 'with connect()' tanpa error).
        info["expected"] = sum(r["source"] for r in results)
        info["actual"] = sum(r["present"] for r in results)
        info["message"] = " | ".join(
            f"{r['table']}: sumber={r['source']} insert={r['inserted']} "
            f"update={r['updated']} tetap={r['unchanged']}" for r in results)
