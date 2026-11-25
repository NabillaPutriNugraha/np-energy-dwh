"""Uji otomatis dashboard (tanpa browser) memakai AppTest bawaan Streamlit.
Jalankan dari folder proyek:  python dashboard/tests/smoke_test.py
Syarat: PostgreSQL berjalan, ETL sudah dijalankan, dan .env berisi akun np_dashboard.

Yang DIBUKTIKAN uji ini: skrip aplikasi berjalan tanpa error, angka di kartu KPI dan peringkat sama dengan
perhitungan independen di pandas dari view mart, penanganan error berfungsi, dan akun dashboard benar-benar baca-saja.
Yang TIDAK dibuktikan: tampilan visual. Itu harus Anda periksa langsung di browser."""
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DASH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASH))

import pandas as pd          # noqa: E402
import psycopg               # noqa: E402
import streamlit as st       # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import charts                # noqa: E402
import db                    # noqa: E402
import settings              # noqa: E402
import theme                 # noqa: E402

APP = str(DASH / "app.py")
HASIL = []


def check(nama: str, kondisi: bool, rincian: str = ""):
    HASIL.append(bool(kondisi))
    print(f"[{'PASS' if kondisi else 'FAIL'}] {nama}" + (f"  ({rincian})" if rincian else ""))


def baru() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def tanpa_error(at: AppTest, nama: str):
    check(nama, not at.exception, "; ".join(str(e.value)[:150] for e in at.exception))


# ---------------------------------------------------------------- perhitungan independen (pandas)
def wavg(df: pd.DataFrame, v: str, w: str) -> float:
    d = df[df[v].notna() & (df[w] > 0)]
    return float((d[v] * d[w]).sum() / d[w].sum()) if len(d) else float("nan")


def r1(x: float, dec: int) -> float:
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP))


def harapan_kpi(df, tahun, benua=None, base=2019):
    def sub(y):
        d = df[df["year"] == y]
        if benua is not None:
            d = d[d["continent"].fillna("Tidak diketahui").isin(benua)]
        return d
    c, b = sub(tahun), sub(base)
    out = {"total": len(c), "cakupan": int(c["renewables_share_elec"].notna().sum())}
    for kol, v, w, dec in [("terbarukan", "renewables_share_elec", "electricity_generation_twh", 1),
                           ("fosil", "fossil_share_elec", "electricity_generation_twh", 1),
                           ("intensitas", "emissions_intensity_gco2e_kwh", "total_generation_twh", 0)]:
        a, o = r1(wavg(c, v, w), dec), r1(wavg(b, v, w), dec)
        out[kol] = a
        out[kol + "_delta"] = round(a - o, dec)
    return out


def tampil(harapan, tahun, base=2019):
    """Mengubah angka harapan menjadi teks seperti yang ditampilkan di kartu."""
    d = tahun != base
    return {
        "Pangsa listrik terbarukan": (theme.fmt_pct(harapan["terbarukan"]), theme.fmt_delta(harapan["terbarukan_delta"], 1, " poin") if d else None),
        "Pangsa listrik fosil": (theme.fmt_pct(harapan["fosil"]), theme.fmt_delta(harapan["fosil_delta"], 1, " poin") if d else None),
        "Intensitas emisi (gCO₂e/kWh)": (theme.fmt_num(harapan["intensitas"]), theme.fmt_delta(harapan["intensitas_delta"], 0, "") if d else None),
        "Cakupan negara": (f"{harapan['cakupan']} dari {harapan['total']}", None),
    }


def bandingkan_kartu(at, harapan, tahun, nama):
    ada = {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}
    sama = ada == tampil(harapan, tahun)
    check(nama, sama, "" if sama else f"tampil={ada} harapan={tampil(harapan, tahun)}")


# ================================================================== PENGUJIAN
def main():
    df = db.run_query("SELECT * FROM mart.v_country_year")
    print(f"Data dasar uji: {len(df)} baris dari mart.v_country_year\n")

    print("== 1. Keadaan awal (semua negara, 2023 dibanding 2019)")
    at = baru()
    tanpa_error(at, "aplikasi berjalan tanpa error")
    bandingkan_kartu(at, harapan_kpi(df, 2023), 2023, "kartu KPI = perhitungan independen pandas")
    acuan = {m.label: (m.value, m.delta) for m in at.metric}
    check("nilai acuan proyek (30,4% / 60,7% / 486 / 210 dari 221)",
          acuan.get("Pangsa listrik terbarukan") == ("30,4%", "+4,3 poin")
          and acuan.get("Pangsa listrik fosil") == ("60,7%", "-3,0 poin")
          and acuan.get("Intensitas emisi (gCO₂e/kWh)") == ("486", "-21")
          and acuan.get("Cakupan negara", ("",))[0] == "210 dari 221", str(acuan))
    check("negara sorotan bawaan = Indonesia", at.sidebar.selectbox(key="f_country").value == "IDN")
    check("sidebar memuat info ETL terakhir", any("ETL terakhir: run #" in c.value for c in at.sidebar.caption))
    check("keterangan ambang 10 TWh sebagai keputusan desain (bukan standar ilmiah)",
          any("keputusan desain" in c.value and "bukan standar atau batas ilmiah" in c.value for c in at.caption))

    print("\n== 2. Filter")
    at.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    tanpa_error(at, "filter benua Asia berjalan")
    bandingkan_kartu(at, harapan_kpi(df, 2023, ["Asia"]), 2023, "KPI Asia = pandas")
    at.sidebar.selectbox(key="f_year").select(2022).run()
    bandingkan_kartu(at, harapan_kpi(df, 2022, ["Asia"]), 2022, "KPI Asia 2022 = pandas")
    at.sidebar.multiselect(key="f_continents").set_value(sorted(df["continent"].fillna("Tidak diketahui").unique())).run()
    bandingkan_kartu(at, harapan_kpi(df, 2022), 2022, "semua benua 2022 = pandas")
    at.sidebar.selectbox(key="f_year").select(2019).run()
    tanpa_error(at, "tahun pembanding (2019) tanpa error")
    check("tahun 2019: tanpa selisih dan ada petunjuk", all(m.delta in (None, "") for m in at.metric)
          and any("Pilih tahun setelah 2019" in i.value for i in at.info))
    at.sidebar.selectbox(key="f_year").select(2023).run()
    at.sidebar.multiselect(key="f_continents").set_value([]).run()
    tanpa_error(at, "filter kosong tidak menimbulkan error")
    check("filter kosong menampilkan pesan 'Tidak ada negara'", any("Tidak ada negara" in i.value for i in at.info))
    at.sidebar.multiselect(key="f_continents").set_value(sorted(df["continent"].fillna("Tidak diketahui").unique())).run()

    print("\n== 3. Peringkat dan ambang pembangkitan")
    for ambang in (10, 50):
        at.select_slider(key="min_twh").set_value(ambang).run()
        a, b = df[df["year"] == 2019].set_index("iso3_code"), df[df["year"] == 2023].set_index("iso3_code")
        j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
        j = j[j["renewables_share_elec_a"].notna() & j["renewables_share_elec_b"].notna()
              & (j["electricity_generation_twh_b"] >= ambang)]
        keterangan = " ".join(c.value for c in at.caption)
        check(f"ambang {ambang} TWh: jumlah negara memenuhi ambang = pandas ({len(j)})",
              f"{len(j)} negara memenuhi" in keterangan)
    at.select_slider(key="min_twh").set_value(10).run()
    for nilai, nama in [(10, "ambang 10 TWh")]:
        j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
        j = j[j["renewables_share_elec_a"].notna() & j["renewables_share_elec_b"].notna()
              & (j["electricity_generation_twh_b"] >= nilai)].copy()
        j["d"] = [r1(x, 1) - r1(y, 1) for x, y in zip(j["renewables_share_elec_b"], j["renewables_share_elec_a"])]
        harap = j.sort_values("d", ascending=False).head(10)
        top = db.run_query(__import__("queries").MOVERS_SQL, {"continents": sorted(df["continent"].fillna("Tidak diketahui").unique()),
                           "groups": sorted(df["group_label"].unique()), "base": 2019, "year": 2023, "min_twh": 10.0})
        check(f"peringkat 10 teratas ({nama}): selisih nilai = pandas",
              sorted(round(x, 1) for x in top["perubahan"]) == sorted(round(x, 1) for x in harap["d"]),
              f"{top['country_name'].tolist()[:3]}")

    print("\n== 4. Semua halaman (tidak ada placeholder tersisa)")
    halaman_semua = ["ringkasan", "a_terbarukan", "b_fosil", "c_bauran", "d_pangsa_intensitas", "kualitas"]
    sisa = []
    for hal in halaman_semua:   # Fase 4-3e: halaman terakhir (kualitas) selesai; pemeriksaan placeholder diganti pemeriksaan ini
        at.switch_page(f"halaman/{hal}.py").run()
        teks = " ".join([i.value for i in at.info] + [w.value for w in at.warning] + [c.value for c in at.caption])
        if at.exception or "dalam pengembangan" in teks.lower() or "placeholder" in teks.lower():
            sisa.append(hal)
    check("semua 6 halaman tampil tanpa error dan tidak ada yang bertanda 'dalam pengembangan' (placeholder)", not sisa, str(sisa))

    print("\n== 5. Grafik (struktur data)")
    kpi = db.run_query(__import__("queries").KPI_SQL, {"continents": sorted(df["continent"].fillna("Tidak diketahui").unique()),
                       "groups": sorted(df["group_label"].unique())})
    fig = charts.trend_chart(kpi["year"].astype(int).tolist(), kpi["terbarukan"].tolist(), "Dunia",
                             [None, 1.0, None, 2.0, 3.0], "Negara X", "y", "#009E73")
    check("grafik tren: 2 garis, 5 titik, nilai kosong tidak diganti angka",
          len(fig.data) == 2 and len(fig.data[0].x) == 5 and fig.data[1].y[0] is None)
    peta = db.run_query(__import__("queries").MAP_SQL, {"continents": sorted(df["continent"].fillna("Tidak diketahui").unique()),
                        "groups": sorted(df["group_label"].unique()), "year": 2023})
    fm = charts.share_map(peta)
    check("peta: jumlah negara = cakupan pangsa 2023 (210)", len(fm.data[0].locations) == 210, str(len(fm.data[0].locations)))

    print("\n== 6. Ketahanan dan keamanan")
    pw_asli = os.environ.get("DASHBOARD_DB_PASSWORD")
    os.environ["DASHBOARD_DB_PASSWORD"] = "password_salah"
    st.cache_data.clear()
    at_err = AppTest.from_file(APP, default_timeout=60).run()
    check("password salah: pesan ramah, bukan jejak error",
          not at_err.exception and any("Tidak dapat terhubung" in e.value for e in at_err.error))
    del os.environ["DASHBOARD_DB_PASSWORD"]
    st.cache_data.clear()
    cfg_asli = settings.os.environ.pop("DASHBOARD_DB_USER", None)
    at_cfg = AppTest.from_file(APP, default_timeout=60).run()
    check("akun belum dikonfigurasi: pesan ramah",
          not at_cfg.exception and any("belum dikonfigurasi" in e.value for e in at_cfg.error))
    os.environ["DASHBOARD_DB_PASSWORD"] = pw_asli
    if cfg_asli:
        os.environ["DASHBOARD_DB_USER"] = cfg_asli
    st.cache_data.clear()

    with psycopg.connect(**settings.db_settings()) as conn:
        user, ro = conn.execute("SELECT current_user, current_setting('default_transaction_read_only')").fetchone()
        check("koneksi dashboard memakai akun np_dashboard dan transaksi baca-saja", user == "np_dashboard" and ro == "on", f"{user}, read_only={ro}")
        for sql, nama in [("SELECT count(*) FROM dw.dim_country", "membaca schema dw ditolak"),
                          ("SELECT count(*) FROM ops.etl_run", "membaca schema ops ditolak"),
                          ("CREATE TABLE mart.uji_tulis (a int)", "membuat tabel ditolak")]:
            try:
                conn.execute(sql)
                check(nama, False, "TIDAK ditolak")
            except psycopg.Error as exc:
                conn.rollback()
                check(nama, True, type(exc).__name__)

    total, lulus = len(HASIL), sum(HASIL)
    print(f"\nRINGKASAN: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
