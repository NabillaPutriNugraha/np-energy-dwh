"""Uji otomatis Halaman A (Perkembangan Terbarukan) dengan AppTest.
Jalankan dari folder proyek:  python dashboard/tests/test_halaman_a.py
Angka di halaman dibandingkan dengan perhitungan INDEPENDEN di pandas dari mart.v_country_year.
Tidak membuktikan tampilan visual; itu diperiksa manual di browser."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd            # noqa: E402

import smoke_test as S         # noqa: E402  (menyediakan check, baru, wavg, r1, harapan_kpi; juga mengatur sys.path)
from smoke_test import check, r1, tanpa_error, wavg  # noqa: E402
import db                      # noqa: E402
import queries                 # noqa: E402
import theme                   # noqa: E402

UNK = "Tidak diketahui"
HAL = "halaman/a_terbarukan.py"


def halaman(at=None):
    at = at or S.baru()
    at.switch_page(HAL).run()
    return at


def stat_pandas(df, tahun, benua=None):
    d = df[df["year"] == tahun]
    if benua is not None:
        d = d[d["continent"].fillna(UNK).isin(benua)]
    s = d["renewables_share_elec"].dropna()
    return {"median": r1(float(s.median()), 1) if len(s) else float("nan"),
            "n_ge50": int(sum(r1(x, 1) >= 50 for x in s)),
            "n_100": int(sum(r1(x, 1) >= 100 for x in s)), "n_nol": int(sum(r1(x, 1) == 0 for x in s))}


def tampil_kartu(df, tahun, benua=None, base=2019):
    h, a, b = S.harapan_kpi(df, tahun, benua), stat_pandas(df, tahun, benua), stat_pandas(df, base, benua)
    d = tahun != base
    return {
        "Pangsa listrik terbarukan": (theme.fmt_pct(h["terbarukan"]),
                                      theme.fmt_delta(h["terbarukan_delta"], 1, " poin") if d else None),
        "Median antarnegara": (theme.fmt_pct(a["median"]),
                               theme.fmt_delta(round(a["median"] - b["median"], 1), 1, " poin") if d else None),
        "Negara berpangsa 50% atau lebih": (f"{a['n_ge50']} negara", f"{a['n_ge50'] - b['n_ge50']:+d} negara" if d else None),
        "Cakupan negara": (f"{h['cakupan']} dari {h['total']}", None)}


def kartu(at):
    return {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}


def peringkat_pandas(df, tahun, ambang, arah, benua=None):
    d = df[(df["year"] == tahun) & df["renewables_share_elec"].notna() & (df["electricity_generation_twh"] >= ambang)].copy()
    if benua is not None:
        d = d[d["continent"].fillna(UNK).isin(benua)]
    d["p"] = [r1(x, 1) for x in d["renewables_share_elec"]]
    d = d.sort_values(["p", "electricity_generation_twh", "country_name"],
                      ascending=[arah == "bawah", False, True]).head(10)
    return list(zip(d["country_name"], d["p"]))


def main():
    df = db.run_query("SELECT * FROM mart.v_country_year")
    semua_benua = sorted(df["continent"].fillna(UNK).unique())
    print(f"Data dasar: {len(df)} baris\n== Halaman A")

    # ---------------------------------------------------------------- 1. kartu KPI
    at = halaman()
    tanpa_error(at, "A: halaman tampil tanpa error")
    check("A: 4 kartu KPI (2023 vs 2019, semua negara) = pandas", kartu(at) == tampil_kartu(df, 2023),
          f"{kartu(at)}")
    check("A: nilai acuan proyek (30,4% / 26,6% / 65 negara / 210 dari 221)",
          kartu(at)["Pangsa listrik terbarukan"][0] == "30,4%" and kartu(at)["Median antarnegara"][0] == "26,6%"
          and kartu(at)["Negara berpangsa 50% atau lebih"][0] == "65 negara"
          and kartu(at)["Cakupan negara"][0] == "210 dari 221")
    check("A: tingkat tampilan awal = Dunia", at.radio(key="a_level").value == "Dunia")

    # ---------------------------------------------------------------- 2. filter
    at.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    tanpa_error(at, "A: filter benua Asia berjalan")
    check("A: kartu KPI Asia = pandas", kartu(at) == tampil_kartu(df, 2023, ["Asia"]))
    at.sidebar.selectbox(key="f_year").select(2021).run()
    check("A: kartu KPI Asia 2021 = pandas", kartu(at) == tampil_kartu(df, 2021, ["Asia"]))
    at.sidebar.selectbox(key="f_year").select(2019).run()
    tanpa_error(at, "A: tahun 2019 tanpa error")
    check("A: tahun 2019 tanpa selisih dan ada petunjuk",
          all(d is None for _, d in kartu(at).values()) and any("pilih tahun setelah 2019" in c.value for c in at.caption))
    at.sidebar.selectbox(key="f_year").select(2023).run()
    at.sidebar.multiselect(key="f_continents").set_value(semua_benua).run()

    # ---------------------------------------------------------------- 3. drill-down Benua
    at = halaman()
    at.radio(key="a_level").set_value("Benua").run()
    tanpa_error(at, "A: tingkat Benua tanpa error")
    cont = queries.continent_series(tuple(semua_benua), tuple(sorted(df["group_label"].unique())))
    ok = True
    for (benua, thn), g in cont.groupby(["benua", "year"]):
        d = df[(df["year"] == thn) & (df["continent"].fillna(UNK) == benua)]
        harap = wavg(d, "renewables_share_elec", "electricity_generation_twh")
        ok &= (math.isnan(harap) and pd.isna(g["terbarukan"].iloc[0])) or abs(g["terbarukan"].iloc[0] - harap) < 1e-9 * max(1, abs(harap))
    check("A: pangsa tertimbang per benua per tahun = pandas (semua benua dan tahun)", ok)
    unk = cont[(cont["benua"] == UNK) & (cont["year"] == 2023)].iloc[0]
    check("A: 'Tidak diketahui' = 12 negara, 4 berdata pangsa (acuan proyek)", int(unk["negara"]) == 12 and int(unk["negara_pangsa"]) == 4,
          f"{int(unk['negara'])} / {int(unk['negara_pangsa'])}")
    tbl = at.dataframe[0].value
    check("A: tabel benua: 'Tidak diketahui' di baris terakhir dan benua lain urut abjad",
          list(tbl["Benua"]) == sorted(b for b in semua_benua if b != UNK) + [UNK], str(list(tbl["Benua"])))
    asia = tbl[tbl["Benua"] == "Asia"].iloc[0]
    d19, d23 = df[(df["year"] == 2019) & (df["continent"] == "Asia")], df[(df["year"] == 2023) & (df["continent"] == "Asia")]
    p19, p23 = wavg(d19, "renewables_share_elec", "electricity_generation_twh"), wavg(d23, "renewables_share_elec", "electricity_generation_twh")
    check("A: tabel benua: Asia (pangsa 2023, perubahan dari angka dibulatkan) = pandas",
          abs(asia["Pangsa 2023 (%)"] - p23) < 1e-9 and abs(asia["Perubahan (poin)"] - (r1(p23, 1) - r1(p19, 1))) < 1e-9,
          f"{asia['Pangsa 2023 (%)']:.2f} / {asia['Perubahan (poin)']}")
    check("A: keterangan menyatakan 'Tidak diketahui' bukan pembanding antar-benua",
          any("tidak dipakai sebagai pembanding antar-benua" in c.value for c in at.caption))
    at.sidebar.multiselect(key="f_continents").set_value(["Asia", "Europe"]).run()
    tanpa_error(at, "A: Benua dengan filter 2 benua tanpa error")
    check("A: filter 2 benua: tabel hanya 2 baris", len(at.dataframe[0].value) == 2)
    at.sidebar.multiselect(key="f_continents").set_value(semua_benua).run()

    # ---------------------------------------------------------------- 4. drill-down Negara
    at = halaman()
    at.radio(key="a_level").set_value("Negara").run()
    tanpa_error(at, "A: tingkat Negara tanpa error")
    top5 = df[df["year"] == 2023].sort_values(["electricity_generation_twh", "country_name"], ascending=[False, True]).head(5)["iso3_code"].tolist()
    harap_awal = list(dict.fromkeys(["IDN"] + top5))[:8]
    check("A: pilihan negara awal = sorotan + 5 pembangkit terbesar", at.multiselect(key="a_countries").value == harap_awal,
          str(at.multiselect(key="a_countries").value))
    at.multiselect(key="a_countries").set_value(["IDN", "DEU", "UKR"]).run()
    tanpa_error(at, "A: memilih 3 negara tanpa error")
    cs = queries.countries_series(["IDN", "DEU", "UKR"])
    ok = True
    for (iso, thn), g in cs.groupby(["iso3_code", "year"]):
        v = df[(df["iso3_code"] == iso) & (df["year"] == thn)]["renewables_share_elec"].iloc[0]
        x = g["pangsa"].iloc[0]
        ok &= (pd.isna(v) and pd.isna(x)) or abs(v - x) < 1e-9
    check("A: deret per negara = pandas", ok)
    ukr23 = cs[(cs["iso3_code"] == "UKR") & (cs["year"] == 2023)]["pangsa"].iloc[0]
    check("A: nilai kosong Ukraina 2023 tetap kosong (tidak diisi perkiraan)", pd.isna(ukr23))
    at.multiselect(key="a_countries").set_value([]).run()
    check("A: tanpa pilihan negara tampil petunjuk, tanpa error", not at.exception and any("Pilih minimal satu negara" in i.value for i in at.info))

    # ---------------------------------------------------------------- 5. peringkat
    at = halaman()
    for ambang in (10, 50):
        at.select_slider(key="a_min_twh").set_value(ambang).run()
        tanpa_error(at, f"A: peringkat ambang {ambang} TWh tanpa error")
        for arah, nama in (("atas", "tertinggi"), ("bawah", "terendah")):
            r = queries.ranking(2023, tuple(semua_benua), tuple(sorted(df["group_label"].unique())), ambang, arah)
            check(f"A: peringkat {nama} ({ambang} TWh): urutan, nilai, dan pemecah seri = pandas",
                  list(zip(r["country_name"], r["pangsa"])) == peringkat_pandas(df, 2023, ambang, arah),
                  str(list(r["country_name"])[:4]))
        t = queries.ranking_ties(2023, tuple(semua_benua), tuple(sorted(df["group_label"].unique())), ambang).iloc[0]
        pool = df[(df["year"] == 2023) & df["renewables_share_elec"].notna() & (df["electricity_generation_twh"] >= ambang)]
        p = [r1(x, 1) for x in pool["renewables_share_elec"]]
        check(f"A: jumlah negara seri ({ambang} TWh) = pandas",
              int(t["n_pool"]) == len(p) and int(t["n_tertinggi"]) == p.count(max(p)) and int(t["n_terendah"]) == p.count(min(p)),
              f"pool={int(t['n_pool'])}, di {t['nilai_tertinggi']:.1f}%: {int(t['n_tertinggi'])}, di {t['nilai_terendah']:.1f}%: {int(t['n_terendah'])}")
    at.select_slider(key="a_min_twh").set_value(10).run()
    teks = " ".join(c.value for c in at.caption)
    check("A: keterangan ambang = keputusan desain, bukan standar atau batas ilmiah",
          "keputusan desain" in teks and "bukan standar atau batas ilmiah" in teks)
    check("A: keterangan menyebut pemecah seri menurut pembangkitan", "diurutkan menurut pembangkitan terbesar" in teks)

    # ---------------------------------------------------------------- 6. tabel detail
    tb = at.dataframe[0].value
    d23 = df[df["year"] == 2023]
    check("A: tabel detail memuat semua negara pada filter (221 baris)", len(tb) == len(d23) == 221, str(len(tb)))
    check("A: tabel detail: jumlah negara bernilai = 210 dan sisanya kosong (bukan 0)",
          int(tb["Pangsa 2023 (%)"].notna().sum()) == 210 and int(tb["Pangsa 2023 (%)"].isna().sum()) == 11)
    ok = True
    for r in tb.itertuples(index=False):
        iso_row = d23[d23["country_name"] == r[0]].iloc[0]
        a = df[(df["year"] == 2019) & (df["iso3_code"] == iso_row["iso3_code"])]["renewables_share_elec"].iloc[0]
        b = iso_row["renewables_share_elec"]
        harap = None if (pd.isna(a) or pd.isna(b)) else r1(b, 1) - r1(a, 1)
        got = r[5]
        ok &= (harap is None and pd.isna(got)) or (harap is not None and not pd.isna(got) and abs(got - harap) < 1e-6)
    check("A: tabel detail: kolom Perubahan (dari angka dibulatkan) = pandas untuk semua negara", ok)
    lso = tb[tb["Negara"] == "Lesotho"].iloc[0]
    check("A: Lesotho 2023: pangsa kosong dan pembangkitan 0 tampil apa adanya",
          pd.isna(lso["Pangsa 2023 (%)"]) and lso["Pembangkitan 2023 (TWh)"] == 0)

    # ---------------------------------------------------------------- 7. kondisi khusus dan teks
    at = halaman()
    at.sidebar.multiselect(key="f_continents").set_value([]).run()
    check("A: filter kosong: pesan jelas, tanpa error", not at.exception and any("Tidak ada negara" in i.value for i in at.info))
    at = halaman()
    teks_halaman = " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [t.value for t in at.title])
    check("A: tidak ada catatan pengembang ('Tahap 4', 'placeholder', 'dalam pengembangan')",
          not any(k in teks_halaman.lower() for k in ("tahap 4", "placeholder", "dalam pengembangan")))

    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN HALAMAN A: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
