"""Seluruh SQL dashboard dan definisi KPI ada di file ini (satu tempat).
Sumber data HANYA view di schema mart (akun dashboard tidak punya hak ke schema lain).

Definisi KPI agregat (keputusan K3, tertimbang pembangkitan):
  pangsa terbarukan / fosil  = SUM(pangsa x pembangkitan listrik) / SUM(pembangkitan listrik)
                               hanya pada negara yang bernilai dan pembangkitannya > 0
  intensitas emisi           = SUM(intensitas x total pembangkitan) / SUM(total pembangkitan)
                               hanya pada negara yang bernilai dan pembangkitannya > 0
Nilai kosong (NULL) tidak pernah diganti angka; negara tanpa nilai tidak ikut dihitung dan
jumlahnya ditampilkan sebagai cakupan."""
import streamlit as st

from db import run_query

BASE_YEAR = 2019   # tahun pembanding tetap (K7)


def _weighted(value: str, weight: str) -> str:
    cond = f"{value} IS NOT NULL AND {weight} > 0"
    return (f"(sum({value} * {weight}) FILTER (WHERE {cond}) "
            f"/ NULLIF(sum({weight}) FILTER (WHERE {cond}), 0))::float8")


def _scope(alias: str = "") -> str:
    """Filter wilayah. Negara tanpa data benua diperlakukan sebagai 'Tidak diketahui' agar tidak hilang diam-diam."""
    p = f"{alias}." if alias else ""
    return (f"COALESCE({p}continent, 'Tidak diketahui') = ANY(%(continents)s) "
            f"AND {p}group_label = ANY(%(groups)s)")


KPI_SQL = f"""
SELECT year,
       count(*)                                  AS negara_total,
       count(renewables_share_elec)              AS negara_pangsa,
       count(emissions_intensity_gco2e_kwh)      AS negara_intensitas,
       {_weighted('renewables_share_elec', 'electricity_generation_twh')}          AS terbarukan,
       {_weighted('fossil_share_elec', 'electricity_generation_twh')}              AS fosil,
       {_weighted('emissions_intensity_gco2e_kwh', 'total_generation_twh')}        AS intensitas
FROM mart.v_country_year
WHERE {_scope()}
GROUP BY year
ORDER BY year
""".strip()

MOVERS_FROM = f"""
FROM mart.v_country_year a
JOIN mart.v_country_year b ON b.iso3_code = a.iso3_code AND a.year = %(base)s AND b.year = %(year)s
WHERE a.renewables_share_elec IS NOT NULL AND b.renewables_share_elec IS NOT NULL
  AND b.electricity_generation_twh >= %(min_twh)s
  AND {_scope('b')}
""".strip()

MOVERS_SQL = f"""
SELECT b.iso3_code, b.country_name,
       round(a.renewables_share_elec::numeric, 1)::float8 AS pangsa_awal,
       round(b.renewables_share_elec::numeric, 1)::float8 AS pangsa_akhir,
       (round(b.renewables_share_elec::numeric, 1) - round(a.renewables_share_elec::numeric, 1))::float8 AS perubahan,
       b.electricity_generation_twh::float8 AS pembangkitan_twh
{MOVERS_FROM}
ORDER BY perubahan DESC, b.country_name
LIMIT 10
""".strip()

MOVERS_POOL_SQL = f"SELECT count(*) AS jumlah {MOVERS_FROM}"

MAP_SQL = f"""
SELECT iso3_code, country_name, renewables_share_elec::float8 AS pangsa
FROM mart.v_country_year
WHERE year = %(year)s AND renewables_share_elec IS NOT NULL AND {_scope()}
ORDER BY country_name
""".strip()

COUNTRY_SQL = """
SELECT year,
       renewables_share_elec::float8 AS terbarukan,
       fossil_share_elec::float8 AS fosil,
       emissions_intensity_gco2e_kwh::float8 AS intensitas
FROM mart.v_country_year WHERE iso3_code = %(iso)s ORDER BY year
""".strip()

ETL_SQL = "SELECT run_id, finished_at, rows_loaded_dw FROM mart.v_etl_status"


# ---------------------------------------------------------------- fungsi pemanggil
def _lists(continents, groups) -> dict:
    return {"continents": list(continents), "groups": list(groups)}


def filter_options() -> dict:
    cont = run_query("SELECT DISTINCT COALESCE(continent, 'Tidak diketahui') AS v "
                     "FROM mart.v_country_year ORDER BY 1")
    grp = run_query("SELECT DISTINCT group_label AS v FROM mart.v_country_year ORDER BY 1")
    ctr = run_query("SELECT DISTINCT iso3_code, country_name FROM mart.v_country_year ORDER BY country_name")
    yrs = run_query("SELECT DISTINCT year AS v FROM mart.v_country_year ORDER BY 1")
    return {"continents": cont["v"].tolist(), "groups": grp["v"].tolist(),
            "countries": list(zip(ctr["iso3_code"], ctr["country_name"])),
            "years": [int(y) for y in yrs["v"]]}


def kpi_by_year(continents, groups):
    return run_query(KPI_SQL, _lists(continents, groups))


def movers(year, continents, groups, min_twh):
    return run_query(MOVERS_SQL, {**_lists(continents, groups), "base": BASE_YEAR,
                                  "year": int(year), "min_twh": float(min_twh)})


def movers_pool(year, continents, groups, min_twh) -> int:
    df = run_query(MOVERS_POOL_SQL, {**_lists(continents, groups), "base": BASE_YEAR,
                                     "year": int(year), "min_twh": float(min_twh)})
    return int(df["jumlah"].iloc[0])


def map_data(year, continents, groups):
    return run_query(MAP_SQL, {**_lists(continents, groups), "year": int(year)})


def country_series(iso):
    return run_query(COUNTRY_SQL, {"iso": iso})


def etl_status():
    return run_query(ETL_SQL)


def current_filters() -> dict:
    """Nilai filter global dari sidebar (disimpan Streamlit di session_state)."""
    ss = st.session_state
    return {"year": int(ss["f_year"]), "continents": tuple(ss["f_continents"]),
            "groups": tuple(ss["f_groups"]), "country": ss["f_country"]}


# =====================================================================================
# Halaman A: Perkembangan Terbarukan (Fase 4-3a). Semua sumber: mart.v_country_year.
# Aturan bersama: nilai dibulatkan 1 desimal untuk urutan, selisih, dan batas (50%, 100%, 0%) sehingga
# yang diurutkan, dihitung, dan diberi label sama dengan angka yang TAMPIL di layar.
# =====================================================================================
UNKNOWN_CONTINENT = "Tidak diketahui"

# Statistik antarnegara per tahun: median (tidak tertimbang), jumlah negara pada batas pangsa, cakupan.
STATS_SQL = f"""
SELECT year,
       count(*)                                                               AS negara_total,
       count(renewables_share_elec)                                           AS negara_pangsa,
       -- median dibulatkan di SQL (setengah ke atas, sama dengan peringkat dan tabel) agar yang tampil dan yang
       -- dipakai menghitung selisih identik; pembulatan Python membulatkan nilai persis .x5 ke genap
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY renewables_share_elec))::numeric, 1)::float8 AS median,
       count(*) FILTER (WHERE round(renewables_share_elec::numeric, 1) >= 50)  AS n_ge50,
       count(*) FILTER (WHERE round(renewables_share_elec::numeric, 1) >= 100) AS n_100,
       count(*) FILTER (WHERE round(renewables_share_elec::numeric, 1) = 0)    AS n_nol
FROM mart.v_country_year
WHERE {_scope()}
GROUP BY year
ORDER BY year
""".strip()

# Pangsa tertimbang per benua per tahun (negara tanpa data benua menjadi baris 'Tidak diketahui').
CONTINENT_SQL = f"""
SELECT COALESCE(continent, 'Tidak diketahui') AS benua,
       year,
       count(*)                      AS negara,
       count(renewables_share_elec)  AS negara_pangsa,
       {_weighted('renewables_share_elec', 'electricity_generation_twh')} AS terbarukan
FROM mart.v_country_year
WHERE {_scope()}
GROUP BY 1, 2
ORDER BY 1, 2
""".strip()

# Peringkat: hanya negara bernilai dan berpembangkitan >= ambang (keputusan desain, bukan standar ilmiah).
_RANK_POOL = f"""
FROM mart.v_country_year
WHERE year = %(year)s AND renewables_share_elec IS NOT NULL
  AND electricity_generation_twh >= %(min_twh)s AND {_scope()}"""

_RANK_COLS = ("SELECT iso3_code, country_name, round(renewables_share_elec::numeric, 1)::float8 AS pangsa, "
              "electricity_generation_twh::float8 AS pembangkitan_twh")

# Urutan: pangsa (dibulatkan 1 desimal), lalu pembangkitan terbesar untuk memecahkan nilai seri (K3), lalu nama.
RANK_TOP_SQL = f"{_RANK_COLS} {_RANK_POOL} ORDER BY pangsa DESC, pembangkitan_twh DESC, country_name LIMIT 10"
RANK_BOTTOM_SQL = f"{_RANK_COLS} {_RANK_POOL} ORDER BY pangsa ASC, pembangkitan_twh DESC, country_name LIMIT 10"

RANK_TIES_SQL = f"""
WITH p AS (SELECT round(renewables_share_elec::numeric, 1) AS v {_RANK_POOL})
SELECT count(*)                                           AS n_pool,
       (SELECT max(v) FROM p)::float8                     AS nilai_tertinggi,
       count(*) FILTER (WHERE v = (SELECT max(v) FROM p)) AS n_tertinggi,
       (SELECT min(v) FROM p)::float8                     AS nilai_terendah,
       count(*) FILTER (WHERE v = (SELECT min(v) FROM p)) AS n_terendah
FROM p
""".strip()

COUNTRIES_SQL = """
SELECT iso3_code, country_name, year, renewables_share_elec::float8 AS pangsa
FROM mart.v_country_year
WHERE iso3_code = ANY(%(isos)s)
ORDER BY country_name, year
""".strip()

TOP_GENERATORS_SQL = """
SELECT iso3_code FROM mart.v_country_year
WHERE year = %(year)s AND electricity_generation_twh IS NOT NULL
ORDER BY electricity_generation_twh DESC, country_name
LIMIT %(n)s
""".strip()

# Tabel detail seluruh negara pada filter aktif. Nilai kosong tetap kosong (tidak diisi perkiraan).
TABLE_SQL = f"""
SELECT b.iso3_code,
       b.country_name,
       COALESCE(b.continent, 'Tidak diketahui')   AS benua,
       b.group_label                              AS kelompok,
       a.renewables_share_elec::float8            AS pangsa_awal,
       b.renewables_share_elec::float8            AS pangsa_tahun,
       (round(b.renewables_share_elec::numeric, 1)
        - round(a.renewables_share_elec::numeric, 1))::float8 AS perubahan,
       b.electricity_generation_twh::float8       AS pembangkitan_twh,
       b.energy_quality_status                    AS status_kelengkapan
FROM mart.v_country_year b
LEFT JOIN mart.v_country_year a ON a.iso3_code = b.iso3_code AND a.year = %(base)s
WHERE b.year = %(year)s AND {_scope('b')}
ORDER BY b.country_name
""".strip()


def stats_by_year(continents, groups):
    return run_query(STATS_SQL, _lists(continents, groups))


def continent_series(continents, groups):
    return run_query(CONTINENT_SQL, _lists(continents, groups))


def ranking(year, continents, groups, min_twh, arah):
    """arah: 'atas' (pangsa tertinggi) atau 'bawah' (pangsa terendah). SQL dipilih dari dua konstanta tetap."""
    sql = {"atas": RANK_TOP_SQL, "bawah": RANK_BOTTOM_SQL}[arah]
    return run_query(sql, {**_lists(continents, groups), "year": int(year), "min_twh": float(min_twh)})


def ranking_ties(year, continents, groups, min_twh):
    return run_query(RANK_TIES_SQL, {**_lists(continents, groups), "year": int(year),
                                     "min_twh": float(min_twh)})


def countries_series(isos):
    return run_query(COUNTRIES_SQL, {"isos": list(isos)})


def top_generators(year, n=5):
    return run_query(TOP_GENERATORS_SQL, {"year": int(year), "n": int(n)})


def country_table(year, continents, groups):
    return run_query(TABLE_SQL, {**_lists(continents, groups), "base": BASE_YEAR, "year": int(year)})


# =====================================================================================
# Halaman B: Ketergantungan pada Fosil (Fase 4-3b). Sumber: mart.v_country_year (data Renewable Energy Share).
# KPI memakai SATU himpunan negara untuk fosil, terbarukan, dan sisa: negara yang kedua pangsa listriknya terisi
# dan pembangkitannya > 0, dengan bobot pembangkitan listrik yang sama. Himpunan ini identik dengan himpunan
# KPI Ringkasan (diverifikasi), sehingga angka fosil dan terbarukan sama dengan Ringkasan.
# =====================================================================================
_B_COND = ("fossil_share_elec IS NOT NULL AND renewables_share_elec IS NOT NULL "
           "AND electricity_generation_twh > 0")


def _b_weighted(expr: str) -> str:
    return (f"(sum(({expr}) * electricity_generation_twh) FILTER (WHERE {_B_COND}) "
            f"/ NULLIF(sum(electricity_generation_twh) FILTER (WHERE {_B_COND}), 0))")


B_KPI_SQL = f"""
SELECT year,
       count(*)                                       AS negara_total,
       count(*) FILTER (WHERE {_B_COND})              AS negara_berbobot,
       {_b_weighted('fossil_share_elec')}::float8          AS fosil,
       {_b_weighted('renewables_share_elec')}::float8      AS terbarukan,
       {_b_weighted('100 - fossil_share_elec - renewables_share_elec')}::float8 AS sisa_tertimbang,
       -- angka yang TAMPIL: dibulatkan 1 desimal (setengah ke atas); sisa dihitung dari angka fosil dan terbarukan
       -- yang tampil, sehingga ketiganya berjumlah tepat 100,0
       round({_b_weighted('fossil_share_elec')}::numeric, 1)::float8     AS fosil_bulat,
       round({_b_weighted('renewables_share_elec')}::numeric, 1)::float8 AS terbarukan_bulat,
       (100 - round({_b_weighted('fossil_share_elec')}::numeric, 1)
            - round({_b_weighted('renewables_share_elec')}::numeric, 1))::float8 AS sisa_tampil
FROM mart.v_country_year
WHERE {_scope()}
GROUP BY year
ORDER BY year
""".strip()

# Dumbbell fosil: N negara dengan PEMBANGKITAN listrik terbesar pada tahun terpilih (bukan menurut pangsa fosil).
B_TOPN_SQL = f"""
SELECT b.iso3_code, b.country_name,
       b.electricity_generation_twh::float8                       AS pembangkitan_twh,
       round(a.fossil_share_elec::numeric, 1)::float8             AS fosil_awal,
       round(b.fossil_share_elec::numeric, 1)::float8             AS fosil_tahun,
       (round(b.fossil_share_elec::numeric, 1) - round(a.fossil_share_elec::numeric, 1))::float8 AS perubahan
FROM mart.v_country_year b
LEFT JOIN mart.v_country_year a ON a.iso3_code = b.iso3_code AND a.year = %(base)s
WHERE b.year = %(year)s AND b.electricity_generation_twh IS NOT NULL AND {_scope('b')}
ORDER BY b.electricity_generation_twh DESC, b.country_name
LIMIT %(n)s
""".strip()

# Semua negara pada filter yang punya pangsa energi primer; pasangan valid = pangsa listrik juga terisi.
B_PAIRS_SQL = f"""
SELECT iso3_code, country_name,
       COALESCE(continent, 'Tidak diketahui')                     AS benua,
       round(renewables_share_elec::numeric, 1)::float8           AS terbarukan_listrik,
       round(renewables_share_energy::numeric, 1)::float8         AS terbarukan_primer,
       (round(renewables_share_elec::numeric, 1)
        - round(renewables_share_energy::numeric, 1))::float8     AS selisih,
       electricity_generation_twh::float8                         AS pembangkitan_twh
FROM mart.v_country_year
WHERE year = %(year)s AND renewables_share_energy IS NOT NULL AND {_scope()}
ORDER BY electricity_generation_twh DESC NULLS LAST, country_name
""".strip()

# Cakupan energi primer: seluruh negara (TIDAK dipengaruhi filter), agar terlihat sampelnya mewakili dunia atau tidak.
B_COVERAGE_SQL = """
SELECT COALESCE(continent, 'Tidak diketahui')                     AS benua,
       count(*)                                                    AS negara,
       count(renewables_share_energy)                              AS berdata_primer,
       count(*) FILTER (WHERE renewables_share_energy IS NOT NULL
                          AND renewables_share_elec IS NOT NULL)   AS pasangan_valid
FROM mart.v_country_year
WHERE year = %(year)s
GROUP BY 1
ORDER BY 1
""".strip()


def b_kpi(continents, groups):
    return run_query(B_KPI_SQL, _lists(continents, groups))


def b_topn(year, continents, groups, n):
    return run_query(B_TOPN_SQL, {**_lists(continents, groups), "base": BASE_YEAR, "year": int(year), "n": int(n)})


def b_pairs(year, continents, groups):
    return run_query(B_PAIRS_SQL, {**_lists(continents, groups), "year": int(year)})


def b_coverage(year):
    return run_query(B_COVERAGE_SQL, {"year": int(year)})


# =====================================================================================
# Halaman C: Bauran Pembangkitan (Fase 4-3c). Sumber: HANYA mart.v_generation_mix (data Ember).
# Pangsa = TWh kategori (atau sumber) / TWh total x 100, dihitung dari jumlah pembangkitan (BUKAN rata-rata
# antarnegara). Sumber yang tidak punya baris pada suatu negara tidak menambah pembangkitan (jumlah semua sumber
# yang ada sama dengan total pembangkitan Ember). Nilai dibulatkan 1 desimal (setengah ke atas) di SQL.
# Daftar kategori dan sumber TIDAK ditulis di sini: seluruhnya berasal dari data.
# =====================================================================================
_C_SOURCE_TEMPLATE = """
WITH g AS (
    SELECT year, source_category AS kategori, source_name AS sumber,
           sum(generation_twh) AS twh, count(DISTINCT iso3_code) AS negara
    FROM mart.v_generation_mix
    WHERE {where}
    GROUP BY 1, 2, 3)
SELECT year, kategori, sumber, twh::float8 AS twh, negara,
       (100 * twh / NULLIF(sum(twh) OVER (PARTITION BY year), 0))::float8 AS pangsa_total,
       round((100 * twh / NULLIF(sum(twh) OVER (PARTITION BY year), 0))::numeric, 1)::float8 AS pangsa_total_bulat,
       round((100 * twh / NULLIF(sum(twh) OVER (PARTITION BY year, kategori), 0))::numeric, 1)::float8
           AS pangsa_kategori_bulat
FROM g
ORDER BY year, kategori, sumber
""".strip()

_C_CATEGORY_TEMPLATE = """
WITH g AS (
    SELECT year, source_category AS kategori, sum(generation_twh) AS twh
    FROM mart.v_generation_mix
    WHERE {where}
    GROUP BY 1, 2)
SELECT year, kategori, twh::float8 AS twh,
       (100 * twh / NULLIF(sum(twh) OVER (PARTITION BY year), 0))::float8 AS pangsa,
       round((100 * twh / NULLIF(sum(twh) OVER (PARTITION BY year), 0))::numeric, 1)::float8 AS pangsa_bulat,
       (sum(twh) OVER (PARTITION BY year))::float8 AS total_twh
FROM g
ORDER BY year, kategori
""".strip()

C_SOURCE_SQL = _C_SOURCE_TEMPLATE.format(where=_scope())
C_SOURCE_COUNTRY_SQL = _C_SOURCE_TEMPLATE.format(where="iso3_code = %(iso)s")
C_CATEGORY_SQL = _C_CATEGORY_TEMPLATE.format(where=_scope())
C_CATEGORY_COUNTRY_SQL = _C_CATEGORY_TEMPLATE.format(where="iso3_code = %(iso)s")

# Cakupan: negara berdata Ember pada filter, dan seluruh negara pada filter yang sama (termasuk yang tanpa data Ember).
C_COUNT_SQL = f"""
SELECT year, count(DISTINCT iso3_code) AS negara_berdata
FROM mart.v_generation_mix WHERE {_scope()} GROUP BY year ORDER BY year
""".strip()
C_TOTAL_SQL = f"""
SELECT year, count(*) AS negara_total
FROM mart.v_country_year WHERE {_scope()} GROUP BY year ORDER BY year
""".strip()

C_COUNTRIES_SQL = "SELECT DISTINCT iso3_code, country_name FROM mart.v_generation_mix ORDER BY country_name"

# Tabel detail: negara x sumber pada tahun terpilih. Baris 0 TWh disembunyikan kecuali diminta; jumlah baris dibatasi.
_C_DETAIL_FROM = f"""
FROM mart.v_generation_mix
WHERE year = %(year)s AND {_scope()}
  AND (%(isos)s::text[] IS NULL OR iso3_code = ANY(%(isos)s::text[]))
  AND (%(kat)s::text IS NULL OR source_category = %(kat)s::text)
  AND (%(nol)s::boolean OR generation_twh > 0)"""
C_DETAIL_SQL = ("SELECT country_name AS negara, year AS tahun, source_category AS kategori, source_name AS sumber, "
                "generation_twh::float8 AS twh, share_of_generation_pct::float8 AS pangsa_negara "
                + _C_DETAIL_FROM + " ORDER BY generation_twh DESC, country_name, source_name LIMIT %(lim)s")
C_DETAIL_COUNT_SQL = "SELECT count(*) AS baris " + _C_DETAIL_FROM


def c_source(continents, groups):
    return run_query(C_SOURCE_SQL, _lists(continents, groups))


def c_source_country(iso):
    return run_query(C_SOURCE_COUNTRY_SQL, {"iso": iso})


def c_category(continents, groups):
    return run_query(C_CATEGORY_SQL, _lists(continents, groups))


def c_category_country(iso):
    return run_query(C_CATEGORY_COUNTRY_SQL, {"iso": iso})


def c_counts(continents, groups):
    return run_query(C_COUNT_SQL, _lists(continents, groups))


def c_totals(continents, groups):
    return run_query(C_TOTAL_SQL, _lists(continents, groups))


def c_countries():
    return run_query(C_COUNTRIES_SQL)


def _c_detail_params(year, continents, groups, isos, kategori, nol):
    return {**_lists(continents, groups), "year": int(year), "isos": list(isos) if isos else None,
            "kat": kategori, "nol": bool(nol)}


def c_detail(year, continents, groups, isos, kategori, nol, limit):
    return run_query(C_DETAIL_SQL, {**_c_detail_params(year, continents, groups, isos, kategori, nol),
                                    "lim": int(limit)})


def c_detail_count(year, continents, groups, isos, kategori, nol):
    return int(run_query(C_DETAIL_COUNT_SQL, _c_detail_params(year, continents, groups, isos, kategori, nol))
               ["baris"].iloc[0])

# Katalog kategori dan sumber yang ADA di data (dipakai untuk kartu, pilihan, dan tabel; tidak ditulis manual).
C_CATALOG_SQL = ("SELECT DISTINCT source_category AS kategori, source_name AS sumber "
                 "FROM mart.v_generation_mix ORDER BY 1, 2")


def c_catalog():
    return run_query(C_CATALOG_SQL)


# =====================================================================================
# Halaman D: Pangsa Terbarukan vs Intensitas Emisi (Fase 4-3d). Sumber: HANYA mart.v_country_year, kolom Ember
# (ember_renewables_share_pct, emissions_intensity_gco2e_kwh, total_generation_twh). Pangsa Renewable Energy Share
# (renewables_share_elec) TIDAK dipakai di sini, supaya kedua indikator berasal dari satu sumber.
# Satuan analisis = satu negara per tahun (tidak tertimbang pembangkitan). Korelasi dihitung di SQL (corr, regr_*);
# Spearman = korelasi Pearson atas peringkat rata-rata (nilai seri mendapat peringkat rata-rata).
# Keputusan desain (BUKAN standar ilmiah): ambang minimum 10 TWh untuk daftar pencilan dan korelasi perubahan,
# ambang minimum 10 negara untuk korelasi per benua. Nilai tampil dibulatkan di SQL (setengah ke atas).
# =====================================================================================
D_MIN_TWH = 10          # pembangkitan minimum untuk pencilan dan korelasi perubahan (keputusan desain)
D_MIN_N = 10            # jumlah negara minimum untuk korelasi per benua (dan peringatan pada KPI)
D_MIN_N_KPI = 3         # di bawah ini korelasi tidak bermakna dan tidak ditampilkan
NUCLEAR_CATEGORY = "Nuklir"   # nilai source_category di mart.v_generation_mix (diperiksa oleh test_halaman_d)

# Negara-tahun yang dipakai: kedua indikator Ember terisi dan pembangkitan > 0 (NULL tidak diisi apa pun).
_D_VALID = ("ember_renewables_share_pct IS NOT NULL AND emissions_intensity_gco2e_kwh IS NOT NULL "
            "AND total_generation_twh > 0")

D_STATS_SQL = f"""
WITH d AS (
    SELECT year, ember_renewables_share_pct AS x, emissions_intensity_gco2e_kwh AS y
    FROM mart.v_country_year
    WHERE {_D_VALID} AND {_scope()}),
r AS (
    SELECT year, x, y,
           rank() OVER (PARTITION BY year ORDER BY x) + (count(*) OVER (PARTITION BY year, x) - 1) / 2.0 AS rx,
           rank() OVER (PARTITION BY year ORDER BY y) + (count(*) OVER (PARTITION BY year, y) - 1) / 2.0 AS ry
    FROM d)
SELECT year, count(*) AS n,
       corr(x, y)::float8                          AS pearson,
       round(corr(x, y)::numeric, 2)::float8       AS pearson_bulat,
       corr(rx, ry)::float8                        AS spearman,
       round(corr(rx, ry)::numeric, 2)::float8     AS spearman_bulat,
       regr_slope(y, x)::float8                    AS lereng,
       round(regr_slope(y, x)::numeric, 1)::float8 AS lereng_bulat,
       regr_intercept(y, x)::float8                AS intersep,
       regr_r2(y, x)::float8                       AS r2,
       round(regr_r2(y, x)::numeric, 2)::float8    AS r2_bulat,
       min(x)::float8 AS x_min, max(x)::float8 AS x_max
FROM r
GROUP BY year
ORDER BY year
""".strip()

# Cakupan: negara berdata Ember pada filter (dengan atau tanpa kedua indikator) dan seluruh negara pada filter.
D_COVER_SQL = f"""
SELECT year, count(*) FILTER (WHERE has_emissions_fact) AS negara_ember, count(*) AS negara_total
FROM mart.v_country_year WHERE {_scope()} GROUP BY year ORDER BY year
""".strip()

_D_POINT_COLS = """iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
       ember_renewables_share_pct::float8 AS pangsa, emissions_intensity_gco2e_kwh::float8 AS intensitas,
       total_generation_twh::float8 AS pembangkitan_twh,
       round(ember_renewables_share_pct::numeric, 1)::float8 AS pangsa_bulat,
       round(emissions_intensity_gco2e_kwh::numeric, 1)::float8 AS intensitas_bulat,
       round(total_generation_twh::numeric, 1)::float8 AS pembangkitan_bulat"""
D_POINTS_SQL = (f"SELECT {_D_POINT_COLS} FROM mart.v_country_year "
                f"WHERE year = %(year)s AND {_D_VALID} AND {_scope()} ORDER BY benua, country_name")
D_POINT_COUNTRY_SQL = (f"SELECT {_D_POINT_COLS} FROM mart.v_country_year "
                       f"WHERE year = %(year)s AND iso3_code = %(iso)s AND {_D_VALID}")

# Korelasi per benua pada tahun terpilih. Nilai korelasi hanya diisi jika n >= ambang (selain itu NULL).
D_CONTINENT_SQL = f"""
WITH d AS (
    SELECT COALESCE(continent, 'Tidak diketahui') AS benua,
           ember_renewables_share_pct AS x, emissions_intensity_gco2e_kwh AS y
    FROM mart.v_country_year
    WHERE year = %(year)s AND {_D_VALID} AND {_scope()}),
r AS (
    SELECT benua, x, y,
           rank() OVER (PARTITION BY benua ORDER BY x) + (count(*) OVER (PARTITION BY benua, x) - 1) / 2.0 AS rx,
           rank() OVER (PARTITION BY benua ORDER BY y) + (count(*) OVER (PARTITION BY benua, y) - 1) / 2.0 AS ry
    FROM d)
SELECT benua, count(*) AS n,
       CASE WHEN count(*) >= %(min_n)s THEN round(corr(x, y)::numeric, 2)::float8 END       AS pearson_bulat,
       CASE WHEN count(*) >= %(min_n)s THEN round(corr(rx, ry)::numeric, 2)::float8 END     AS spearman_bulat,
       CASE WHEN count(*) >= %(min_n)s THEN round(regr_slope(y, x)::numeric, 1)::float8 END AS lereng_bulat
FROM r GROUP BY benua ORDER BY benua
""".strip()

# Pencilan: garis regresi dihitung dari SEMUA negara valid pada filter (garis yang sama dengan grafik);
# daftar hanya memuat negara berpembangkitan >= ambang. Selisih = intensitas aktual dikurangi intensitas menurut
# garis, dari angka yang tampil (dibulatkan 1 desimal). Urutan = |selisih tampil| terbesar, lalu pembangkitan, lalu nama.
# Pangsa nuklir: pangsa kategori nuklir dari Ember; NULL jika tidak ada baris nuklir (tidak dianggap 0).
D_OUTLIER_SQL = f"""
WITH d AS (
    SELECT iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
           ember_renewables_share_pct AS x, emissions_intensity_gco2e_kwh AS y, total_generation_twh AS twh
    FROM mart.v_country_year
    WHERE year = %(year)s AND {_D_VALID} AND {_scope()}),
m AS (SELECT regr_intercept(y, x) AS a, regr_slope(y, x) AS b FROM d),
nuk AS (
    SELECT iso3_code, sum(share_of_generation_pct) AS pangsa_nuklir
    FROM mart.v_generation_mix WHERE year = %(year)s AND source_category = %(nuklir)s GROUP BY iso3_code),
p AS (
    SELECT d.*, round(d.x::numeric, 1) AS xb, round(d.y::numeric, 1) AS yb, round(d.twh::numeric, 1) AS tb,
           round((m.a + m.b * d.x)::numeric, 1) AS pb
    FROM d CROSS JOIN m WHERE d.twh >= %(min_twh)s)
SELECT row_number() OVER (ORDER BY abs(p.yb - p.pb) DESC, p.twh DESC, p.country_name)::int AS peringkat,
       p.iso3_code, p.country_name, p.benua,
       p.xb::float8 AS pangsa, round(nuk.pangsa_nuklir::numeric, 1)::float8 AS pangsa_nuklir,
       p.yb::float8 AS intensitas, p.pb::float8 AS intensitas_garis, (p.yb - p.pb)::float8 AS selisih,
       p.tb::float8 AS pembangkitan_twh
FROM p LEFT JOIN nuk ON nuk.iso3_code = p.iso3_code
ORDER BY peringkat
""".strip()

# Perubahan tahun pembanding -> tahun terpilih. Daftar = negara berdata Ember pada salah satu tahun (pada filter).
# Nilai kosong tetap kosong; selisih hanya jika kedua nilai ada, dihitung dari angka yang tampil.
_D_CHANGE_CTE = f"""
WITH s AS (
    SELECT iso3_code, max(country_name) AS country_name, max(COALESCE(continent, 'Tidak diketahui')) AS benua,
           max(CASE WHEN year = %(base)s AND total_generation_twh > 0 THEN ember_renewables_share_pct END) AS x0,
           max(CASE WHEN year = %(year)s AND total_generation_twh > 0 THEN ember_renewables_share_pct END) AS x1,
           max(CASE WHEN year = %(base)s AND total_generation_twh > 0 THEN emissions_intensity_gco2e_kwh END) AS y0,
           max(CASE WHEN year = %(year)s AND total_generation_twh > 0 THEN emissions_intensity_gco2e_kwh END) AS y1,
           max(CASE WHEN year = %(year)s THEN total_generation_twh END) AS g1
    FROM mart.v_country_year
    WHERE year IN (%(base)s, %(year)s) AND has_emissions_fact AND {_scope()}
    GROUP BY iso3_code),
c AS (
    SELECT s.*,
           round(x0::numeric, 1) AS x0b, round(x1::numeric, 1) AS x1b,
           round(y0::numeric, 1) AS y0b, round(y1::numeric, 1) AS y1b,
           (round(x1::numeric, 1) - round(x0::numeric, 1)) AS dxb,
           (round(y1::numeric, 1) - round(y0::numeric, 1)) AS dyb,
           (x0 IS NOT NULL AND x1 IS NOT NULL AND y0 IS NOT NULL AND y1 IS NOT NULL) AS lengkap
    FROM s)
""".strip()

D_CHANGE_SQL = _D_CHANGE_CTE + """
SELECT iso3_code, country_name, benua, x0b::float8 AS pangsa_awal, x1b::float8 AS pangsa_akhir, dxb::float8 AS d_pangsa,
       y0b::float8 AS intensitas_awal, y1b::float8 AS intensitas_akhir, dyb::float8 AS d_intensitas,
       round(g1::numeric, 1)::float8 AS pembangkitan_twh, g1::float8 AS pembangkitan_raw, lengkap
FROM c ORDER BY country_name
"""

# Ringkasan perubahan: cakupan, median selisih (tidak tertimbang; dari angka tampil, setengah ke atas), dan korelasi
# antar-selisih HANYA untuk negara berpembangkitan >= ambang pada tahun terpilih (keputusan desain).
D_CHANGE_STATS_SQL = _D_CHANGE_CTE + """
SELECT count(*) AS n_daftar,
       count(*) FILTER (WHERE lengkap) AS n_lengkap,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY dxb::float8) FILTER (WHERE lengkap))::numeric, 1)::float8
           AS median_d_pangsa,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY dyb::float8) FILTER (WHERE lengkap))::numeric, 1)::float8
           AS median_d_intensitas,
       count(*) FILTER (WHERE lengkap AND g1 >= %(min_twh)s) AS n_korelasi,
       round((corr(x1 - x0, y1 - y0) FILTER (WHERE lengkap AND g1 >= %(min_twh)s))::numeric, 2)::float8
           AS korelasi_perubahan
FROM c
"""


def d_stats(continents, groups):
    return run_query(D_STATS_SQL, _lists(continents, groups))


def d_cover(continents, groups):
    return run_query(D_COVER_SQL, _lists(continents, groups))


def d_points(year, continents, groups):
    return run_query(D_POINTS_SQL, {**_lists(continents, groups), "year": int(year)})


def d_point_country(year, iso):
    return run_query(D_POINT_COUNTRY_SQL, {"year": int(year), "iso": iso})


def d_continent(year, continents, groups):
    return run_query(D_CONTINENT_SQL, {**_lists(continents, groups), "year": int(year), "min_n": D_MIN_N})


def d_outliers(year, continents, groups):
    return run_query(D_OUTLIER_SQL, {**_lists(continents, groups), "year": int(year), "min_twh": float(D_MIN_TWH),
                                     "nuklir": NUCLEAR_CATEGORY})


def _d_change_params(year, continents, groups):
    return {**_lists(continents, groups), "base": BASE_YEAR, "year": int(year), "min_twh": float(D_MIN_TWH)}


def d_change(year, continents, groups):
    return run_query(D_CHANGE_SQL, _d_change_params(year, continents, groups))


def d_change_stats(year, continents, groups):
    return run_query(D_CHANGE_STATS_SQL, _d_change_params(year, continents, groups))


# =====================================================================================
# Halaman Kualitas Data dan Metodologi (Fase 4-3e). Sumber: HANYA view mart (akun dashboard tidak punya akses ke dw/stg).
# Halaman ini memakai SELURUH data (tidak dipengaruhi filter benua/kelompok); hanya tahun terpilih yang dipakai untuk
# bagian per tahun. Coverage = nilai tersedia / negara master x 100, dengan "negara master" = seluruh negara pada
# mart.v_country_year per tahun (bukan hanya negara yang punya data). Tidak ada nilai yang diimputasi.
# Rekonsiliasi DW -> Mart yang membutuhkan akses ke schema dw dilakukan di sql/100_validate_quality.sql (bukan di sini).
# Keputusan desain (BUKAN standar ilmiah): ambang selisih pembangkitan 5% dan selisih pangsa 2 poin antara Ember dan
# Renewable, toleransi 0,05 TWh pada penjumlahan bauran, dan 15 baris pada tabel selisih terbesar.
# =====================================================================================
K_GEN_PCT = 5        # selisih pembangkitan Ember vs Renewable yang ditandai (persen; keputusan desain)
K_SHARE_PTS = 2      # selisih pangsa terbarukan Ember vs Renewable yang ditandai (poin; keputusan desain)
K_TOL_TWH = 0.05     # toleransi jumlah semua sumber vs total pembangkitan Ember (TWh; keputusan desain)
K_TOP_N = 15         # jumlah baris pada tabel selisih terbesar

# (kode, indikator, sumber, kolom nilai di mart.v_country_year, kolom penanda ada-tidaknya baris di sumber itu)
K_INDICATORS = [
    ("pangsa_listrik_ren", "Pangsa listrik terbarukan", "Renewable", "renewables_share_elec", "has_energy_fact"),
    ("pembangkitan_ren", "Pembangkitan listrik", "Renewable", "electricity_generation_twh", "has_energy_fact"),
    ("pangsa_primer_ren", "Pangsa terbarukan energi primer", "Renewable", "renewables_share_energy", "has_energy_fact"),
    ("pangsa_listrik_emb", "Pangsa listrik terbarukan", "Ember", "ember_renewables_share_pct", "has_emissions_fact"),
    ("pembangkitan_emb", "Pembangkitan listrik", "Ember", "total_generation_twh", "has_emissions_fact"),
    ("intensitas_emb", "Intensitas emisi", "Ember", "emissions_intensity_gco2e_kwh", "has_emissions_fact"),
]
K_MIX_CODE = "bauran_emb"
K_MIX_LABEL = ("Bauran pembangkitan per sumber", "Ember")


def _k_cover_sql() -> str:
    bagian = [f"SELECT year, '{kode}' AS kode, '{ind}' AS indikator, '{src}' AS sumber, {i} AS urut, "
              f"count(*) AS negara_master, count(*) FILTER (WHERE {ada}) AS punya_baris, count({kol}) AS tersedia "
              f"FROM mart.v_country_year GROUP BY year"
              for i, (kode, ind, src, kol, ada) in enumerate(K_INDICATORS)]
    bagian.append(f"SELECT g.year, '{K_MIX_CODE}', '{K_MIX_LABEL[0]}', '{K_MIX_LABEL[1]}', {len(K_INDICATORS)}, "
                  f"(SELECT count(*) FROM mart.v_country_year c WHERE c.year = g.year), count(DISTINCT g.iso3_code), "
                  f"count(DISTINCT g.iso3_code) FILTER (WHERE g.generation_twh IS NOT NULL) "
                  f"FROM mart.v_generation_mix g GROUP BY g.year")
    return ("SELECT year, kode, indikator, sumber, negara_master, punya_baris, tersedia,\n"
            "       round(100.0 * tersedia / NULLIF(negara_master, 0), 1)::float8 AS coverage\n"
            "FROM (\n" + "\nUNION ALL\n".join(bagian) + "\n) u\nORDER BY year, urut")


K_COVER_SQL = _k_cover_sql()

# Cakupan energi primer menurut benua pada satu tahun (cakupan terbatas dan tidak merata; tidak ada agregat global).
K_PRIMARY_SQL = """
SELECT COALESCE(continent, 'Tidak diketahui') AS benua, count(*) AS negara_master,
       count(renewables_share_energy) AS tersedia,
       round(100.0 * count(renewables_share_energy) / count(*), 1)::float8 AS coverage
FROM mart.v_country_year WHERE year = %(year)s GROUP BY 1 ORDER BY 1
""".strip()

# Status kelengkapan (kolom status di fakta) pada satu tahun; "Tidak ada baris" = negara tanpa baris di sumber itu.
K_STATUS_SQL = """
SELECT 'Renewable (fakta energi)' AS sumber, COALESCE(energy_quality_status, 'Tidak ada baris') AS status, count(*) AS jumlah
FROM mart.v_country_year WHERE year = %(year)s GROUP BY 2
UNION ALL
SELECT 'Ember (fakta emisi)', COALESCE(emissions_quality_status, 'Tidak ada baris'), count(*)
FROM mart.v_country_year WHERE year = %(year)s GROUP BY 2
UNION ALL
SELECT 'Ember (bauran per sumber)', quality_status, count(*)
FROM mart.v_generation_mix WHERE year = %(year)s GROUP BY 2
ORDER BY 1, 2
""".strip()

# Alasan status "indikator kosong": kolom mana yang kosong (dari nilainya, bukan dari label status).
K_STATUS_REASON_SQL = """
SELECT 'Renewable (fakta energi)' AS sumber,
       count(*) FILTER (WHERE has_energy_fact AND renewables_share_energy IS NOT NULL AND renewables_share_elec IS NOT NULL) AS lengkap,
       count(*) FILTER (WHERE has_energy_fact AND renewables_share_energy IS NULL AND renewables_share_elec IS NOT NULL)     AS kolom1_kosong,
       count(*) FILTER (WHERE has_energy_fact AND renewables_share_energy IS NOT NULL AND renewables_share_elec IS NULL)     AS kolom2_kosong,
       count(*) FILTER (WHERE has_energy_fact AND renewables_share_energy IS NULL AND renewables_share_elec IS NULL)         AS keduanya_kosong,
       'pangsa energi primer' AS nama_kolom1, 'pangsa listrik' AS nama_kolom2
FROM mart.v_country_year WHERE year = %(year)s
UNION ALL
SELECT 'Ember (fakta emisi)',
       count(*) FILTER (WHERE has_emissions_fact AND emissions_intensity_gco2e_kwh IS NOT NULL AND ember_renewables_share_pct IS NOT NULL),
       count(*) FILTER (WHERE has_emissions_fact AND emissions_intensity_gco2e_kwh IS NULL AND ember_renewables_share_pct IS NOT NULL),
       count(*) FILTER (WHERE has_emissions_fact AND emissions_intensity_gco2e_kwh IS NOT NULL AND ember_renewables_share_pct IS NULL),
       count(*) FILTER (WHERE has_emissions_fact AND emissions_intensity_gco2e_kwh IS NULL AND ember_renewables_share_pct IS NULL),
       'intensitas emisi', 'pangsa terbarukan'
FROM mart.v_country_year WHERE year = %(year)s
""".strip()

# Nilai kosong penting per negara dan kelompok indikator, dengan alasan yang dapat dibuktikan dari data mart.
K_MISSING_SQL = """
WITH x AS (
    SELECT iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua, year,
           'Ember (pangsa terbarukan dan intensitas)' AS kelompok,
           CASE WHEN NOT has_emissions_fact THEN 'Tidak ada baris Ember untuk negara-tahun ini'
                WHEN total_generation_twh = 0 THEN 'Pembangkitan 0 TWh, sehingga pangsa dan intensitas tidak terdefinisi'
                WHEN total_generation_twh IS NULL THEN 'Baris Ember ada, tetapi nilai pembangkitan juga kosong'
                ELSE 'Pangsa atau intensitas kosong walaupun pembangkitan terisi' END AS alasan
    FROM mart.v_country_year
    WHERE ember_renewables_share_pct IS NULL OR emissions_intensity_gco2e_kwh IS NULL
    UNION ALL
    SELECT iso3_code, country_name, COALESCE(continent, 'Tidak diketahui'), year,
           'Renewable (pangsa listrik terbarukan)',
           CASE WHEN NOT has_energy_fact THEN 'Tidak ada baris Renewable untuk negara-tahun ini'
                WHEN electricity_generation_twh = 0 THEN 'Pembangkitan 0 TWh, sehingga pangsa tidak terdefinisi'
                WHEN electricity_generation_twh IS NULL THEN 'Baris Renewable ada, tetapi nilai pembangkitan juga kosong'
                ELSE 'Pangsa kosong walaupun pembangkitan terisi' END
    FROM mart.v_country_year
    WHERE renewables_share_elec IS NULL)
SELECT kelompok, iso3_code, country_name, benua, alasan, count(*) AS jumlah_tahun,
       string_agg(year::text, ', ' ORDER BY year) AS tahun
FROM x GROUP BY kelompok, iso3_code, country_name, benua, alasan
ORDER BY kelompok, alasan, country_name
""".strip()

K_NOCONT_SQL = """
SELECT count(*) AS negara_tanpa_benua, count(*) FILTER (WHERE tanpa_ember) AS tanpa_ember_semua_tahun
FROM (SELECT iso3_code, bool_and(NOT has_emissions_fact) AS tanpa_ember
      FROM mart.v_country_year GROUP BY iso3_code HAVING bool_or(continent IS NULL)) t
""".strip()

# Ember vs Renewable: cakupan negara per tahun.
K_SRC_COVER_SQL = """
SELECT year, count(*) AS negara_master,
       count(*) FILTER (WHERE has_energy_fact AND has_emissions_fact)     AS kedua_sumber,
       count(*) FILTER (WHERE has_energy_fact AND NOT has_emissions_fact) AS hanya_renewable,
       count(*) FILTER (WHERE has_emissions_fact AND NOT has_energy_fact) AS hanya_ember,
       count(*) FILTER (WHERE NOT has_energy_fact AND NOT has_emissions_fact) AS tanpa_keduanya
FROM mart.v_country_year GROUP BY year ORDER BY year
""".strip()

# Ember vs Renewable: perbedaan nilai pada negara-tahun yang ada di kedua sumber (mart.v_source_comparison).
# Selisih pangsa dihitung dari angka yang tampil (dibulatkan 1 desimal); selisih pembangkitan memakai kolom view.
K_SRC_DIFF_SQL = """
SELECT year, count(*) AS n_pasang,
       count(*) FILTER (WHERE selisih_persen IS NOT NULL) AS n_gen_dibanding,
       count(*) FILTER (WHERE abs(selisih_persen) > %(gen_pct)s) AS n_gen_besar,
       count(*) FILTER (WHERE ember_renewables_share_pct IS NOT NULL AND renewable_renewables_share_pct IS NOT NULL)
           AS n_pangsa_dibanding,
       count(*) FILTER (WHERE abs(round(ember_renewables_share_pct::numeric, 1) - round(renewable_renewables_share_pct::numeric, 1))
                              > %(pts)s) AS n_pangsa_besar
FROM mart.v_source_comparison GROUP BY year ORDER BY year
""".strip()

K_SRC_TOP_SQL = """
SELECT iso3_code, country_name,
       round(ember_renewables_share_pct::numeric, 1)::float8 AS pangsa_ember,
       round(renewable_renewables_share_pct::numeric, 1)::float8 AS pangsa_renewable,
       (round(ember_renewables_share_pct::numeric, 1) - round(renewable_renewables_share_pct::numeric, 1))::float8 AS selisih_poin,
       round(ember_generation_twh::numeric, 1)::float8 AS pembangkitan_ember,
       round(renewable_generation_twh::numeric, 1)::float8 AS pembangkitan_renewable,
       round(selisih_persen::numeric, 1)::float8 AS selisih_gen_persen
FROM mart.v_source_comparison
WHERE year = %(year)s AND ember_renewables_share_pct IS NOT NULL AND renewable_renewables_share_pct IS NOT NULL
ORDER BY abs(round(ember_renewables_share_pct::numeric, 1) - round(renewable_renewables_share_pct::numeric, 1)) DESC,
         country_name
LIMIT %(lim)s
""".strip()

K_SRC_SCATTER_SQL = """
SELECT iso3_code, country_name, COALESCE(continent, 'Tidak diketahui') AS benua,
       renewables_share_elec::float8 AS pangsa_renewable, ember_renewables_share_pct::float8 AS pangsa_ember,
       round(renewables_share_elec::numeric, 1)::float8 AS pangsa_renewable_bulat,
       round(ember_renewables_share_pct::numeric, 1)::float8 AS pangsa_ember_bulat
FROM mart.v_country_year
WHERE year = %(year)s AND renewables_share_elec IS NOT NULL AND ember_renewables_share_pct IS NOT NULL
ORDER BY country_name
""".strip()

# Rata-rata sederhana (tiap negara bobot sama) vs tertimbang pembangkitan, per tahun, SEMUA negara.
# Pangsa: bobot = pembangkitan listrik Renewable (sama dengan KPI halaman lain); bobot alternatif = pembangkitan Ember.
K_MEAN_SQL = f"""
WITH w AS (
    SELECT year, renewables_share_elec AS s, electricity_generation_twh AS g_ren, total_generation_twh AS g_emb,
           emissions_intensity_gco2e_kwh AS inten
    FROM mart.v_country_year)
SELECT year,
       count(s) AS n_pangsa,
       count(*) FILTER (WHERE s IS NOT NULL AND g_ren > 0) AS n_pangsa_berbobot,
       round(avg(s)::numeric, 1)::float8 AS pangsa_sederhana,
       round(({_weighted('s', 'g_ren')})::numeric, 1)::float8 AS pangsa_tertimbang,
       round(({_weighted('s', 'g_ren')})::numeric, 2)::float8 AS pangsa_tertimbang_2,
       round(({_weighted('s', 'g_emb')})::numeric, 2)::float8 AS pangsa_bobot_ember_2,
       count(inten) AS n_intensitas,
       count(*) FILTER (WHERE inten IS NOT NULL AND g_emb > 0) AS n_intensitas_berbobot,
       round(avg(inten)::numeric, 0)::float8 AS intensitas_sederhana,
       round(({_weighted('inten', 'g_emb')})::numeric, 0)::float8 AS intensitas_tertimbang
FROM w GROUP BY year ORDER BY year
""".strip()

# Konsistensi antar-view mart (pemeriksaan yang dapat dilakukan akun dashboard; DW -> Mart ada di sql/100).
K_RECON_SQL = """
SELECT c.year, c.n_cy, c.n_cy_iso, c.n_energy, c.n_ember, c.n_both,
       (SELECT count(*) FROM mart.v_source_comparison s WHERE s.year = c.year) AS n_cmp,
       (SELECT count(*) FROM mart.v_generation_mix g WHERE g.year = c.year) AS baris_mix,
       (SELECT count(DISTINCT g.iso3_code) FROM mart.v_generation_mix g WHERE g.year = c.year) AS negara_mix
FROM (SELECT year, count(*) AS n_cy, count(DISTINCT iso3_code) AS n_cy_iso,
             count(*) FILTER (WHERE has_energy_fact) AS n_energy, count(*) FILTER (WHERE has_emissions_fact) AS n_ember,
             count(*) FILTER (WHERE has_energy_fact AND has_emissions_fact) AS n_both
      FROM mart.v_country_year GROUP BY year) c
ORDER BY c.year
""".strip()

K_RECON_GEN_SQL = """
WITH m AS (SELECT iso3_code, year, sum(generation_twh) AS s FROM mart.v_generation_mix GROUP BY iso3_code, year)
SELECT m.year, count(*) AS pasang, max(abs(m.s - c.total_generation_twh))::float8 AS selisih_maks,
       round(sum(m.s)::numeric, 1)::float8 AS total_bauran, round(sum(c.total_generation_twh)::numeric, 1)::float8 AS total_negara
FROM m JOIN mart.v_country_year c ON c.iso3_code = m.iso3_code AND c.year = m.year
GROUP BY m.year ORDER BY m.year
""".strip()

K_YEARS_SQL = "SELECT min(year) AS tahun_awal, max(year) AS tahun_akhir, count(DISTINCT year) AS jumlah_tahun FROM mart.v_country_year"


def k_cover():
    return run_query(K_COVER_SQL)


def k_primary(year):
    return run_query(K_PRIMARY_SQL, {"year": int(year)})


def k_status(year):
    return run_query(K_STATUS_SQL, {"year": int(year)})


def k_status_reason(year):
    return run_query(K_STATUS_REASON_SQL, {"year": int(year)})


def k_missing():
    return run_query(K_MISSING_SQL)


def k_nocont():
    return run_query(K_NOCONT_SQL)


def k_src_cover():
    return run_query(K_SRC_COVER_SQL)


def k_src_diff():
    return run_query(K_SRC_DIFF_SQL, {"gen_pct": float(K_GEN_PCT), "pts": float(K_SHARE_PTS)})


def k_src_top(year):
    return run_query(K_SRC_TOP_SQL, {"year": int(year), "lim": int(K_TOP_N)})


def k_src_scatter(year):
    return run_query(K_SRC_SCATTER_SQL, {"year": int(year)})


def k_mean():
    return run_query(K_MEAN_SQL)


def k_recon():
    return run_query(K_RECON_SQL)


def k_recon_gen():
    return run_query(K_RECON_GEN_SQL)


def k_years():
    return run_query(K_YEARS_SQL)
