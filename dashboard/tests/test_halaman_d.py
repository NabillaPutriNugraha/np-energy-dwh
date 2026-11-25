"""Uji otomatis Halaman D (Pangsa Terbarukan vs Intensitas Emisi) dengan AppTest.
Jalankan dari folder proyek:  python dashboard/tests/test_halaman_d.py
Angka dan grafik di halaman dibandingkan dengan perhitungan INDEPENDEN di pandas/numpy dari baris mentah
mart.v_country_year dan mart.v_generation_mix. Grafik dibaca dari spesifikasi Plotly yang benar-benar dikirim halaman.
Tidak membuktikan tampilan visual; itu diperiksa manual di browser."""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np             # noqa: E402
import pandas as pd            # noqa: E402

import smoke_test as S         # noqa: E402
from smoke_test import check, r1, tanpa_error  # noqa: E402
import charts                  # noqa: E402
import db                      # noqa: E402
import queries                 # noqa: E402
import theme                   # noqa: E402

UNK = "Tidak diketahui"
HAL = "halaman/d_pangsa_intensitas.py"
SUMBER = Path(__file__).resolve().parents[1] / "halaman" / "d_pangsa_intensitas.py"
MIN_TWH, MIN_N = 10, 10


def halaman(at=None):
    at = at or S.baru()
    at.switch_page(HAL).run()
    return at


def kartu(at):
    return {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}


def df_dengan(at, kolom):
    for d in at.dataframe:
        if kolom in d.value.columns:
            return d.value
    return None


def figs(at):
    return [json.loads(e.proto.spec) for e in at.get("plotly_chart")]


def teks_halaman(at):
    return " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [t.value for t in at.title]
                    + [i.value for i in at.info] + [w.value for w in at.warning] + [s.value for s in at.subheader])


def valid(v, tahun, benua=None, grup=None):
    d = v[(v["year"] == tahun) & v["ember_renewables_share_pct"].notna() & v["emissions_intensity_gco2e_kwh"].notna()
          & (v["total_generation_twh"] > 0)]
    if benua is not None:
        d = d[d["continent"].fillna(UNK).isin(benua)]
    if grup is not None:
        d = d[d["group_label"].isin(grup)]
    return d


def statistik(d):
    x, y = d["ember_renewables_share_pct"].astype(float), d["emissions_intensity_gco2e_kwh"].astype(float)
    b, a = np.polyfit(x, y, 1)
    p = float(x.corr(y))
    return dict(n=len(d), pearson=p, spearman=float(x.corr(y, method="spearman")), lereng=float(b), intersep=float(a), r2=p * p)


def harapan_kartu(v, tahun, benua=None, grup=None, base=2019):
    s = statistik(valid(v, tahun, benua, grup))
    d = v[(v["year"] == tahun) & v["has_emissions_fact"]]
    if benua is not None:
        d = d[d["continent"].fillna(UNK).isin(benua)]
    if grup is not None:
        d = d[d["group_label"].isin(grup)]
    out = {"Korelasi Pearson (r)": r1(s["pearson"], 2), "Korelasi Spearman": r1(s["spearman"], 2),
           "Lereng garis regresi": r1(s["lereng"], 1)}
    hasil = {k: (theme.fmt_num(val, 2 if k != "Lereng garis regresi" else 1), None) for k, val in out.items()}
    if tahun != base:
        sb = statistik(valid(v, base, benua, grup))
        awal = {"Korelasi Pearson (r)": (r1(sb["pearson"], 2), 2), "Korelasi Spearman": (r1(sb["spearman"], 2), 2),
                "Lereng garis regresi": (r1(sb["lereng"], 1), 1)}
        for k in out:
            hasil[k] = (hasil[k][0], theme.fmt_delta(out[k] - awal[k][0], awal[k][1]))
    hasil["Negara dalam analisis"] = (f"{theme.fmt_num(s['n'], 0)} dari {theme.fmt_num(len(d), 0)}", None)
    return hasil, s


def dec(x):
    return Decimal(repr(float(x))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def median_dec(vals):
    v = sorted(vals)
    n = len(v)
    m = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    return float(Decimal(m).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def ref_perubahan(v, tahun, benua=None, grup=None, base=2019):
    d = v[v["year"].isin([base, tahun]) & v["has_emissions_fact"]]
    if benua is not None:
        d = d[d["continent"].fillna(UNK).isin(benua)]
    if grup is not None:
        d = d[d["group_label"].isin(grup)]
    baris = {}
    for iso, g in d.groupby("iso3_code"):
        def ambil(th, kol):
            r = g[(g["year"] == th) & (g["total_generation_twh"] > 0)]
            return float(r[kol].iloc[0]) if len(r) and pd.notna(r[kol].iloc[0]) else None
        gen = g[g["year"] == tahun]["total_generation_twh"]
        baris[iso] = dict(nama=g["country_name"].iloc[0], benua=g["continent"].fillna(UNK).iloc[0],
                          x0=ambil(base, "ember_renewables_share_pct"), x1=ambil(tahun, "ember_renewables_share_pct"),
                          y0=ambil(base, "emissions_intensity_gco2e_kwh"), y1=ambil(tahun, "emissions_intensity_gco2e_kwh"),
                          g1=(float(gen.iloc[0]) if len(gen) and pd.notna(gen.iloc[0]) else None))
    for r in baris.values():
        r["lengkap"] = all(r[k] is not None for k in ("x0", "x1", "y0", "y1"))
        if r["lengkap"]:
            r["dx"] = dec(r["x1"]) - dec(r["x0"])
            r["dy"] = dec(r["y1"]) - dec(r["y0"])
    return baris


def ref_pencilan(v, tahun, benua=None, grup=None):
    d = valid(v, tahun, benua, grup)
    s = statistik(d)
    out = []
    for r in d[d["total_generation_twh"] >= MIN_TWH].itertuples():
        yb = dec(r.emissions_intensity_gco2e_kwh)
        pb = dec(s["intersep"] + s["lereng"] * float(r.ember_renewables_share_pct))
        out.append((abs(yb - pb), -float(r.total_generation_twh), r.country_name, r.iso3_code, float(yb - pb), float(pb)))
    out.sort(key=lambda t: (-t[0], t[1], t[2]))
    return out


def main():
    v = db.run_query("SELECT * FROM mart.v_country_year")
    mix = db.run_query("SELECT * FROM mart.v_generation_mix")
    cont_semua = tuple(sorted(v["continent"].fillna(UNK).unique()))
    grup_all = tuple(sorted(v["group_label"].unique()))
    kode = SUMBER.read_text(encoding="utf-8")
    print(f"Data dasar: {len(v)} baris v_country_year\n== Halaman D")

    # ------------------------------------------------ 1. render dan teks tetap
    try:
        compile(kode, str(SUMBER), "exec")
        ok_compile = True
    except SyntaxError:
        ok_compile = False
    check("D1: kode halaman D valid (dapat dikompilasi)", ok_compile)
    at = halaman()
    tanpa_error(at, "D1: halaman D dirender tanpa error")
    check("D1: judul halaman 'D. Pangsa Terbarukan vs Intensitas Emisi'",
          [t.value for t in at.title] == ["D. Pangsa Terbarukan vs Intensitas Emisi"])
    check("D1: banner permanen: observasional dan bukan bukti hubungan sebab-akibat",
          any("observasional" in w.value and "bukan bukti hubungan sebab-akibat" in w.value for w in at.warning))
    check("D1: empat tab (sebaran, per benua, perubahan, pencilan)",
          [t.label for t in at.tabs] == ["Sebaran dan garis regresi", "Korelasi per benua", "Perubahan 2019 ke 2023", "Negara pencilan"],
          str([t.label for t in at.tabs]))

    # ------------------------------------------------ 2. KPI = pandas (semua tahun, dunia)
    for th in (2019, 2020, 2021, 2022, 2023):
        a = halaman()
        if th != 2023:
            a.sidebar.selectbox(key="f_year").set_value(th).run()
        harap, s = harapan_kartu(v, th)
        k = kartu(a)
        cocok = all(k.get(label) == nilai for label, nilai in harap.items())
        check(f"D2: KPI dunia {th} = pandas (r={s['pearson']:.3f}, rho={s['spearman']:.3f}, lereng={s['lereng']:.2f}, n={s['n']})",
              not a.exception and cocok, "" if cocok else f"halaman={ {l: k.get(l) for l in harap} } harap={harap}")
    st_sql = queries.d_stats(cont_semua, grup_all).set_index("year")
    pj = harapan_kartu(v, 2023)[1]
    check("D2: nilai tak dibulatkan dari SQL = pandas/numpy (Pearson, Spearman, lereng, intersep, R2; toleransi 1e-9)",
          abs(st_sql.loc[2023, "pearson"] - pj["pearson"]) < 1e-9 and abs(st_sql.loc[2023, "spearman"] - pj["spearman"]) < 1e-9
          and abs(st_sql.loc[2023, "lereng"] - pj["lereng"]) < 1e-7 and abs(st_sql.loc[2023, "intersep"] - pj["intersep"]) < 1e-6
          and abs(st_sql.loc[2023, "r2"] - pj["r2"]) < 1e-9, f"n={int(st_sql.loc[2023, 'n'])}")
    sf = valid(v, 2023)
    check("D2: Spearman memakai peringkat rata-rata untuk nilai seri (ada banyak negara berpangsa 0%)",
          (sf["ember_renewables_share_pct"] == 0).sum() > 1, f"{int((sf['ember_renewables_share_pct'] == 0).sum())} negara berpangsa 0")
    check("D2: 2023 dunia: n=207 (dari 208 berdata Ember), Pearson -0,88, Spearman -0,90, lereng -6,6 (acuan)",
          kartu(halaman())["Negara dalam analisis"][0] == "207 dari 208" and kartu(halaman())["Korelasi Pearson (r)"][0] == "-0,88"
          and kartu(halaman())["Korelasi Spearman"][0] == "-0,90" and kartu(halaman())["Lereng garis regresi"][0] == "-6,6")

    # ------------------------------------------------ 3. KPI dengan filter
    skenario = {"Asia+Eropa": ((("Asia", "Europe")), None), "Oceania": ((("Oceania",)), None)}
    for nama, (ben, gr) in skenario.items():
        a = halaman()
        a.sidebar.multiselect(key="f_continents").set_value(list(ben)).run()
        harap, s = harapan_kartu(v, 2023, ben, gr)
        k = kartu(a)
        check(f"D3: KPI filter {nama} = pandas (n={s['n']}, r={s['pearson']:.3f})",
              not a.exception and all(k.get(l) == nl for l, nl in harap.items()), str({l: k.get(l) for l in harap}))
    g7 = [g for g in grup_all if "G7" in g]
    a = halaman()
    a.sidebar.multiselect(key="f_groups").set_value(g7).run()
    s7 = statistik(valid(v, 2023, None, g7))
    check(f"D3: filter G7 (n={s7['n']} < {MIN_N}): peringatan jumlah negara sedikit, tanpa error",
          not a.exception and s7["n"] < MIN_N and any("tidak stabil" in w.value for w in a.warning))
    a.sidebar.multiselect(key="f_groups").set_value(["ASEAN"]).run()
    sa = valid(v, 2023, None, ["ASEAN"])
    check(f"D3: filter ASEAN saja (n={len(sa)}): halaman tetap berjalan sesuai jumlah negara",
          not a.exception and (len(sa) < queries.D_MIN_N_KPI and any("Data tidak cukup" in i.value for i in a.info)
                               or len(sa) >= queries.D_MIN_N_KPI and kartu(a)["Negara dalam analisis"][0].startswith(str(len(sa)))),
          f"n={len(sa)}")
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value([]).run()
    check("D3: filter benua kosong: pesan 'Data tidak cukup' (bukan error) dan tidak ada angka dibuat",
          not a.exception and any("Data tidak cukup" in i.value for i in a.info) and len(a.metric) == 0)
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Oceania"]).run()
    a.sidebar.multiselect(key="f_groups").set_value(["EU"]).run()
    check("D3: kombinasi filter tanpa negara (Oceania + EU): pesan 'Data tidak cukup', tanpa error",
          not a.exception and any("Data tidak cukup" in i.value for i in a.info))

    # ------------------------------------------------ 4. grafik sebaran (spesifikasi nyata dari halaman)
    at = halaman()
    f0 = figs(at)[0]
    trace_b = [t for t in f0["data"] if t.get("mode") == "markers" and t["name"] in cont_semua]
    x_all = sorted(x for t in trace_b for x in t["x"])
    y_all = sorted(y for t in trace_b for y in t["y"])
    d23 = valid(v, 2023)
    check(f"D4: jumlah titik = jumlah negara valid ({len(d23)}); tidak ada titik kosong",
          len(x_all) == len(d23) and None not in x_all and None not in y_all, str(len(x_all)))
    check("D4: posisi x (pangsa Ember) dan y (intensitas) semua titik = pandas",
          np.allclose(x_all, sorted(d23["ember_renewables_share_pct"].astype(float))) and
          np.allclose(y_all, sorted(d23["emissions_intensity_gco2e_kwh"].astype(float))))
    ukuran = sorted(s_ for t in trace_b for s_ in t["marker"]["size"])
    check("D4: ukuran titik = total pembangkitan (TWh) dan skala berbasis luas",
          np.allclose(ukuran, sorted(d23["total_generation_twh"].astype(float))) and all(t["marker"]["sizemode"] == "area" for t in trace_b))
    nama_titik = sorted(re.match(r"<b>(.+?)</b>", h).group(1) for t in trace_b for h in t["hovertext"])
    check("D4: negara yang digambar = negara valid; Lesotho (pembangkitan 0) dan Ukraina (tanpa nilai 2023) tidak digambar",
          nama_titik == sorted(d23["country_name"]) and "Lesotho" not in nama_titik and "Ukraine" not in nama_titik)
    check("D4: warna titik = warna benua pada charts.CONTINENT_COLORS, satu seri per benua",
          all(t["marker"]["color"] == charts.CONTINENT_COLORS[t["name"]] for t in trace_b) and len(trace_b) == 6)
    garis = [t for t in f0["data"] if t["name"] == "Garis regresi sederhana"][0]
    b_np, a_np = np.polyfit(d23["ember_renewables_share_pct"].astype(float), d23["emissions_intensity_gco2e_kwh"].astype(float), 1)
    check("D4: garis regresi = polyfit independen (ujung kiri dan kanan di rentang x data)",
          np.allclose(garis["y"], [a_np + b_np * x for x in garis["x"]], atol=1e-6)
          and abs(garis["x"][0] - d23["ember_renewables_share_pct"].min()) < 1e-9 and abs(garis["x"][1] - d23["ember_renewables_share_pct"].max()) < 1e-9)
    idn = d23[d23["iso3_code"] == "IDN"].iloc[0]
    hv = [h for t in trace_b for h in t["hovertext"] if h.startswith("<b>Indonesia</b>")][0]
    check("D4: tooltip menyebut negara, benua, tahun, pangsa, intensitas, dan pembangkitan (nilai dibulatkan 1 desimal)",
          "(Asia), 2023" in hv and f"Pangsa listrik terbarukan (Ember): {theme.fmt_pct(r1(idn.ember_renewables_share_pct, 1), 1)}" in hv
          and f"Intensitas emisi: {theme.fmt_num(r1(idn.emissions_intensity_gco2e_kwh, 1), 1)} gCO₂e/kWh" in hv
          and f"Pembangkitan: {theme.fmt_num(r1(idn.total_generation_twh, 1), 1)} TWh" in hv, hv.replace("<br>", " | "))
    check("D4: sumbu: x = Pangsa listrik terbarukan, Ember (%); y = Intensitas emisi (gCO₂e/kWh)",
          f0["layout"]["xaxis"]["title"]["text"] == charts.D_X_TITLE and f0["layout"]["yaxis"]["title"]["text"] == charts.D_Y_TITLE
          and "Ember" in charts.D_X_TITLE and "gCO₂e/kWh" in charts.D_Y_TITLE)
    sorot = [t for t in f0["data"] if t["name"].startswith("Sorotan")]
    check("D4: negara sorotan bawaan Indonesia digambar sebagai lingkaran terpisah",
          len(sorot) == 1 and sorot[0]["name"] == "Sorotan: Indonesia" and abs(sorot[0]["x"][0] - idn.ember_renewables_share_pct) < 1e-9)
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Europe"]).run()
    fe = figs(a)[0]
    check("D4: filter Eropa: titik = negara Eropa valid; sorotan Indonesia tetap tergambar (tidak dipengaruhi filter)",
          sum(len(t["x"]) for t in fe["data"] if t["name"] in cont_semua) == len(valid(v, 2023, ["Europe"]))
          and any(t["name"] == "Sorotan: Indonesia" for t in fe["data"]))
    iso_tanpa = v[v["continent"].isna()]["iso3_code"].iloc[0]
    a = halaman()
    a.sidebar.selectbox(key="f_country").select(iso_tanpa).run()
    check(f"D4: negara sorotan tanpa data Ember ({iso_tanpa}): tidak digambar, ada keterangan, tanpa error",
          not a.exception and not any(t["name"].startswith("Sorotan") for t in figs(a)[0]["data"])
          and any("tidak memiliki pangsa terbarukan dan intensitas emisi Ember" in c.value for c in a.caption))
    a = halaman()
    a.sidebar.selectbox(key="f_country").select("UKR").run()
    check("D4: Ukraina sebagai sorotan (tanpa nilai 2023): tidak digambar dan tanpa error",
          not a.exception and not any(t["name"].startswith("Sorotan") for t in figs(a)[0]["data"]))

    # ------------------------------------------------ 5. korelasi per benua
    at = halaman()
    tb = df_dengan(at, "Jumlah negara")
    ok_b = tb is not None and len(tb) == 6
    if ok_b:
        for r in tb.itertuples(index=False):
            d = valid(v, 2023, [r[0]])
            s = statistik(d)
            ok_b &= (r[1] == len(d) and abs(r[2] - r1(s["pearson"], 2)) < 1e-9 and abs(r[3] - r1(s["spearman"], 2)) < 1e-9
                     and abs(r[4] - r1(s["lereng"], 1)) < 1e-9)
    check("D5: tabel per benua (2023, dunia): n, Pearson, Spearman, lereng setiap benua = pandas", ok_b,
          "" if tb is None else str(tb.iloc[:, :3].values.tolist()))
    check("D5: urutan nilai Eropa paling lemah (-0,67) dan Amerika Selatan paling kuat (-0,99) = pandas",
          tb is not None and dict(zip(tb["Benua"], tb["Pearson (r)"]))["Europe"] == r1(statistik(valid(v, 2023, ["Europe"]))["pearson"], 2)
          and dict(zip(tb["Benua"], tb["Pearson (r)"]))["South America"] == r1(statistik(valid(v, 2023, ["South America"]))["pearson"], 2))
    fb = [f_ for f_ in figs(at) if f_["data"][0].get("orientation") == "h" and any("r = " in t for t in f_["data"][0].get("text", []))]
    check("D5: grafik batang korelasi per benua memuat n pada label, enam benua", len(fb) == 1 and len(fb[0]["data"][0]["y"]) == 6
          and all("n = " in t for t in fb[0]["data"][0]["text"]))
    # ambang n >= 10 (dan semantik >=) langsung pada SQL
    base_par = {"continents": list(cont_semua), "groups": list(grup_all), "year": 2023}
    n_afr = len(valid(v, 2023, ["Africa"]))
    r_pas = db.run_query(queries.D_CONTINENT_SQL, {**base_par, "min_n": n_afr}).set_index("benua")
    r_atas = db.run_query(queries.D_CONTINENT_SQL, {**base_par, "min_n": n_afr + 1}).set_index("benua")
    check(f"D5: ambang memakai '>=': benua dengan n = ambang ({n_afr}) dihitung; ambang n+1 tidak dihitung",
          pd.notna(r_pas.loc["Africa", "pearson_bulat"]) and pd.isna(r_atas.loc["Africa", "pearson_bulat"]))
    check("D5: ambang bawaan halaman = 10 negara (queries.D_MIN_N)", queries.D_MIN_N == MIN_N)
    a = halaman()
    a.sidebar.multiselect(key="f_groups").set_value(g7).run()
    t7 = df_dengan(a, "Jumlah negara")
    n7 = {b: len(valid(v, 2023, [b], g7)) for b in valid(v, 2023, None, g7)["continent"].fillna(UNK).unique()}
    check(f"D5: filter G7 (benua berjumlah {sorted(n7.values())} negara, semua < {MIN_N}): korelasi benua KOSONG dan diberi keterangan",
          t7 is not None and t7["Pearson (r)"].isna().all() and t7["Spearman"].isna().all() and t7["Lereng (gCO₂e/kWh per poin)"].isna().all()
          and all("Tidak dihitung" in k for k in t7["Keterangan"]) and any("Tidak ada benua dengan minimal" in i.value for i in a.info)
          and dict(zip(t7["Benua"], t7["Jumlah negara"])) == n7, str(n7))
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Oceania", "Europe"]).run()
    t2 = df_dengan(a, "Jumlah negara")
    check("D5: campuran: Oceania (15) dan Eropa (41) dihitung; hanya benua terpilih tampil",
          set(t2["Benua"]) == {"Oceania", "Europe"} and t2["Pearson (r)"].notna().all())

    # ------------------------------------------------ 6. perubahan 2019 -> tahun terpilih
    at = halaman()
    ref = ref_perubahan(v, 2023)
    lengkap = {k: r for k, r in ref.items() if r["lengkap"]}
    k = kartu(at)
    dx_med = median_dec([r["dx"] for r in lengkap.values()])
    dy_med = median_dec([r["dy"] for r in lengkap.values()])
    g10 = [r for r in lengkap.values() if r["g1"] is not None and r["g1"] >= MIN_TWH]
    kor = r1(float(pd.Series([float(r["x1"] - r["x0"]) for r in g10]).corr(pd.Series([float(r["y1"] - r["y0"]) for r in g10]))), 2)
    check(f"D6: kartu perubahan = pandas (lengkap {len(lengkap)} dari {len(ref)}, median {dx_med:+.1f} poin / {dy_med:+.1f} gCO2e/kWh, r={kor}, n={len(g10)})",
          k["Negara berdata lengkap"][0] == f"{len(lengkap)} dari {len(ref)}"
          and k["Median perubahan pangsa"][0] == theme.fmt_delta(dx_med, 1, " poin")
          and k["Median perubahan intensitas"][0] == theme.fmt_delta(dy_med, 1, " gCO₂e/kWh")
          and k["Korelasi antar-perubahan"][0] == theme.fmt_num(kor, 2), str({x: k[x] for x in list(k)[4:]}))
    check("D6: acuan: 207 dari 209 negara lengkap, korelasi antar-perubahan -0,84 dari 108 negara berpembangkitan >= 10 TWh",
          len(lengkap) == 207 and len(ref) == 209 and len(g10) == 108 and kor == -0.84, f"{len(lengkap)}/{len(ref)}/{len(g10)}/{kor}")
    tp = df_dengan(at, "Perubahan pangsa (poin)")
    check("D6: tabel perubahan memuat semua negara berdata Ember (209), termasuk yang bernilai kosong", tp is not None and len(tp) == len(ref))
    ok_nilai = True
    for r in tp.itertuples(index=False):
        iso = [i for i, x in ref.items() if x["nama"] == r[0]][0]
        x = ref[iso]
        if x["lengkap"]:
            ok_nilai &= (abs(r[2] - float(dec(x["x0"]))) < 1e-9 and abs(r[3] - float(dec(x["x1"]))) < 1e-9
                         and abs(r[4] - float(x["dx"])) < 1e-9 and abs(r[7] - float(x["dy"])) < 1e-9
                         and abs((r[3] - r[2]) - r[4]) < 1e-9)   # selisih = angka yang tampil
        else:
            ok_nilai &= pd.isna(r[4]) and pd.isna(r[7])
    check("D6: untuk setiap negara, nilai awal/akhir dan selisih = pandas; selisih = akhir dikurangi awal (angka tampil); tidak lengkap -> kosong",
          ok_nilai)
    n_kosong_tab = int(tp["Perubahan pangsa (poin)"].isna().sum())
    check(f"D6: NULL tetap NULL: {len(ref) - len(lengkap)} negara bernilai kosong punya selisih kosong (bukan 0)",
          n_kosong_tab == len(ref) - len(lengkap) and int((tp["Perubahan pangsa (poin)"] == 0).sum()) == sum(1 for r in lengkap.values() if r["dx"] == 0))
    ukr = tp[tp["Negara"] == "Ukraine"].iloc[0]
    lso = tp[tp["Negara"] == "Lesotho"].iloc[0]
    check("D6: Ukraina: nilai 2019 ada, nilai 2023 kosong (pembangkitan kosong); Lesotho: pangsa 2023 kosong dan pembangkitan 2023 = 0,0 (bukan kosong)",
          pd.notna(ukr["Pangsa 2019 (%)"]) and pd.isna(ukr["Pangsa 2023 (%)"]) and pd.isna(ukr["Pembangkitan 2023 (TWh)"])
          and pd.isna(lso["Pangsa 2023 (%)"]) and lso["Pembangkitan 2023 (TWh)"] == 0.0)
    fc = [f_ for f_ in figs(at) if "Perubahan pangsa terbarukan 2019 ke 2023" in json.dumps(f_["layout"], ensure_ascii=False)]
    titik_c = [(x, y) for f_ in fc for t in f_["data"] for x, y in zip(t["x"], t["y"])]
    check(f"D6: grafik perubahan: hanya {len(lengkap)} negara berdata lengkap; tidak ada titik kosong",
          len(fc) == 1 and len(titik_c) == len(lengkap) and all(x is not None and y is not None for x, y in titik_c))
    check("D6: tombol unduh CSV tabel perubahan tersedia", len(at.get("download_button")) >= 1)
    a = halaman()
    a.sidebar.selectbox(key="f_year").set_value(2019).run()
    check("D6: tahun 2019 (= tahun pembanding): pesan jelas, tanpa tabel perubahan, tanpa error",
          not a.exception and any("sama dengan tahun pembanding" in i.value for i in a.info) and df_dengan(a, "Perubahan pangsa (poin)") is None)
    a = halaman()
    a.sidebar.selectbox(key="f_year").set_value(2021).run()
    r21 = ref_perubahan(v, 2021)
    l21 = {k_: r for k_, r in r21.items() if r["lengkap"]}
    k21 = kartu(a)
    check(f"D6: tahun 2021: lengkap {len(l21)} dari {len(r21)} dan median = pandas",
          k21["Negara berdata lengkap"][0] == f"{len(l21)} dari {len(r21)}"
          and k21["Median perubahan pangsa"][0] == theme.fmt_delta(median_dec([r['dx'] for r in l21.values()]), 1, " poin")
          and [t.label for t in a.tabs][2] == "Perubahan 2019 ke 2021")
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Asia", "Oceania"]).run()
    rs = ref_perubahan(v, 2023, ["Asia", "Oceania"])
    ls = {k_: r for k_, r in rs.items() if r["lengkap"]}
    ks = kartu(a)
    check(f"D6: filter Asia+Oceania: lengkap {len(ls)} dari {len(rs)} dan median (n genap/ganjil, setengah ke atas) = pandas",
          ks["Negara berdata lengkap"][0] == f"{len(ls)} dari {len(rs)}"
          and ks["Median perubahan pangsa"][0] == theme.fmt_delta(median_dec([r['dx'] for r in ls.values()]), 1, " poin")
          and ks["Median perubahan intensitas"][0] == theme.fmt_delta(median_dec([r['dy'] for r in ls.values()]), 1, " gCO₂e/kWh"))

    # ------------------------------------------------ 7. pencilan
    at = halaman()
    rp = ref_pencilan(v, 2023)
    to = df_dengan(at, "Selisih (aktual - garis)")
    top10 = rp[:10]
    check(f"D7: kumpulan pencilan = negara >= {MIN_TWH} TWh; jumlah = {len(rp)} (acuan 108)",
          len(rp) == 108 and any(f"dari {len(rp)} negara berpembangkitan minimal {MIN_TWH} TWh" in c.value for c in at.caption))
    check("D7: 10 negara pencilan, urutan, selisih, dan intensitas menurut garis = pandas (residual terbesar dari garis sederhana)",
          to is not None and len(to) == 10 and list(to["Negara"]) == [t[2] for t in top10]
          and np.allclose(to["Selisih (aktual - garis)"], [t[4] for t in top10]) and np.allclose(to["Intensitas menurut garis"], [t[5] for t in top10]),
          "" if to is None else str(list(to["Negara"])))
    check("D7: selisih = intensitas aktual - intensitas menurut garis (dari angka yang tampil)",
          np.allclose(to["Selisih (aktual - garis)"], to["Intensitas aktual"] - to["Intensitas menurut garis"], atol=1e-9))
    check("D7: kolom Posisi sesuai tanda selisih",
          all((p == "Di atas garis") == (s_ > 0) for p, s_ in zip(to["Posisi"], to["Selisih (aktual - garis)"])))
    check(f"D7: semua negara pencilan berpembangkitan >= {MIN_TWH} TWh (ambang = keputusan desain, dinyatakan di keterangan)",
          (to["Pembangkitan (TWh)"] >= MIN_TWH).all() and any("keputusan desain, bukan standar pencilan universal" in c.value for c in at.caption))
    check("D7: acuan: Turkmenistan dan Uzbekistan di atas garis; France, Slovakia, Belgium, Hungary di bawah garis (hasil data, bukan penjelasan)",
          {n_: s_ for n_, s_ in zip(to["Negara"], to["Posisi"])}.get("Turkmenistan") == "Di atas garis"
          and {n_: s_ for n_, s_ in zip(to["Negara"], to["Posisi"])}.get("Uzbekistan") == "Di atas garis"
          and all({n_: s_ for n_, s_ in zip(to["Negara"], to["Posisi"])}.get(n_) == "Di bawah garis" for n_ in ("France", "Slovakia", "Belgium", "Hungary")))
    m23 = mix[(mix["year"] == 2023) & (mix["source_category"] == queries.NUCLEAR_CATEGORY)].groupby("country_name")["share_of_generation_pct"].sum()
    ok_n = True
    for r in to.itertuples(index=False):
        ok_n &= (pd.isna(r[4]) if r[1] not in m23.index else abs(r[4] - r1(m23[r[1]], 1)) < 1e-9)
    check("D7: pangsa nuklir tiap negara pencilan = v_generation_mix (Ember); negara tanpa baris nuklir kosong, bukan 0", ok_n,
          str(dict(zip(to['Negara'], to['Pangsa nuklir (%)']))))
    check("D7: kategori nuklir yang dipakai query ada di data (queries.NUCLEAR_CATEGORY)", queries.NUCLEAR_CATEGORY in set(mix["source_category"]))
    fr = [f_ for f_ in figs(at) if f_["data"][0].get("orientation") == "h" and "selisih" in json.dumps(f_["layout"], ensure_ascii=False).lower()]
    check("D7: grafik selisih memuat 10 negara", len(fr) == 1 and len(fr[0]["data"][0]["y"]) == 10)
    rk = [i for i, t in enumerate(rp) if t[3] == "IDN"][0] + 1
    check(f"D7: keterangan negara sorotan Indonesia: peringkat {rk} dari {len(rp)} (jika masuk daftar)",
          any(f"Negara sorotan Indonesia: peringkat {rk} dari {len(rp)}" in c.value for c in at.caption))
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    ra = ref_pencilan(v, 2023, ["Asia"])
    ta = df_dengan(a, "Selisih (aktual - garis)")
    check("D7: filter Asia: garis regresi dihitung ulang dari negara Asia dan 10 pencilan = pandas",
          list(ta["Negara"]) == [t[2] for t in ra[:10]] and np.allclose(ta["Selisih (aktual - garis)"], [t[4] for t in ra[:10]]),
          str(list(ta["Negara"])[:4]))
    a = halaman()
    a.sidebar.multiselect(key="f_groups").set_value(["ASEAN"]).run()
    check("D7: filter tanpa negara >= 10 TWh atau tanpa data: pesan jelas atau daftar sesuai pandas, tanpa error", not a.exception)

    # ------------------------------------------------ 8. tidak ada data buatan, satu sumber, tanpa GDP/populasi
    d_sql = {n: getattr(queries, n) for n in dir(queries) if n.startswith("D_") and n.endswith("SQL")}
    gabung_sql = " ".join(d_sql.values()).lower()
    check("D8: semua query D hanya memakai kolom Ember (tanpa renewables_share_elec/Renewable Energy Share)",
          "renewables_share_elec" not in gabung_sql and "ember_renewables_share_pct" in gabung_sql and "emissions_intensity_gco2e_kwh" in gabung_sql)
    baris_gdp = [b for b in kode.lower().splitlines() if "gdp" in b or "population" in b or "populasi" in b]
    check("D8: GDP dan populasi tidak dipakai (tidak ada di query; di kode halaman hanya kalimat penjelasan 'tidak dipakai')",
          not any(k in gabung_sql for k in ("gdp", "population")) and len(baris_gdp) == 1 and "tidak dipakai" in baris_gdp[0])
    check(f"D8: {len(d_sql)} query halaman D hanya SELECT (tanpa INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/TRUNCATE/GRANT)",
          len(d_sql) >= 7 and all(re.match(r"\s*(WITH|SELECT)\b", q_, re.I) for q_ in d_sql.values())
          and not any(re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|GRANT)\b", q_, re.I) for q_ in d_sql.values()))
    check("D8: kode halaman tidak memuat angka data yang ditulis manual (tanpa angka desimal, nilai acuan, atau nama negara)",
          not re.search(r"\b\d+,\d+\b", kode) and not any(s_ in kode for s_ in ("207", "108", "209", "0,88", "6,6", "Indonesia", "France", "Turkmenistan")))
    teks = teks_halaman(at)
    check("D8: tidak ada catatan pengembang ('Tahap 4', 'placeholder', 'dalam pengembangan')",
          not any(k_ in (teks + kode).lower() for k_ in ("tahap 4", "placeholder", "dalam pengembangan")))
    kausal = ["menyebabkan", "akibat dari", "disebabkan", "karena kebijakan", "berkat ", "berhasil menurunkan", "gagal menurunkan",
              "mengakibatkan", "berdampak", "efek dari", "membuktikan"]
    check("D8: teks dan kode halaman tidak memuat klaim sebab-akibat",
          not any(k_ in (teks + " " + kode).lower() for k_ in kausal))
    check("D8: catatan sumber: pangsa dari Ember dan dapat berbeda dari halaman lain (Renewable Energy Share)",
          any("dari Ember" in c.value and "berbeda" in c.value and "Renewable Energy Share" in c.value for c in at.caption))
    sem = True
    for th, benua in ((2023, None), (2020, ["Asia"])):
        a = halaman()
        a.sidebar.selectbox(key="f_year").set_value(th).run()
        if benua:
            a.sidebar.multiselect(key="f_continents").set_value(benua).run()
        sem &= any("bukan bukti hubungan sebab-akibat" in w.value for w in a.warning) and not a.exception
    check("D8: banner observasional/bukan sebab-akibat muncul di semua skenario (tahun dan filter berbeda)", sem)

    # ------------------------------------------------ 9. fungsi grafik dengan data sintetis (NULL tetap)
    ke = pd.DataFrame({"benua": ["A", "B", "C"], "n": [12, 30, 11], "pearson_bulat": [-0.5, -0.9, 0.1]})
    fc_ = charts.corr_bar(ke)
    check("D9: corr_bar menggambar 3 batang dengan korelasi apa adanya (positif tetap positif)",
          list(fc_.data[0].x) == [0.1, -0.9, -0.5] or sorted(fc_.data[0].x) == [-0.9, -0.5, 0.1])
    sint = pd.DataFrame({"country_name": ["X", "Y"], "benua": ["Asia", "Asia"], "pangsa": [10.0, 60.0], "intensitas": [500.0, 100.0],
                         "pembangkitan_twh": [1.0, 100.0], "pangsa_bulat": [10.0, 60.0], "intensitas_bulat": [500.0, 100.0],
                         "pembangkitan_bulat": [1.0, 100.0]})
    fs = charts.scatter_regression(sint, 600.0, -8.0, 10.0, 60.0, 2023)
    check("D9: scatter_regression sintetis: 1 seri benua + 1 garis, tanpa sorotan", len(fs.data) == 2 and fs.data[1].name == "Garis regresi sederhana")
    d_kosong = pd.DataFrame({"selisih": [5.0, -3.0], "country_name": ["P", "Q"], "benua": ["Asia", "Europe"], "intensitas": [1.0, 2.0],
                             "intensitas_garis": [1.0, 2.0]})
    fr_ = charts.residual_bar(d_kosong)
    check("D9: residual_bar: tanda selisih menentukan warna (dua warna berbeda)", len(set(fr_.data[0].marker.color)) == 2)

    # ------------------------------------------------ 10. regresi A, B, C, Ringkasan
    def kartu_hal(h):
        a_ = S.baru()
        a_.switch_page(f"halaman/{h}.py").run()
        return a_, kartu(a_)
    a_, ka = kartu_hal("a_terbarukan")
    check("D10: halaman A tidak rusak (30,4% +4,3 poin / 26,6% / 65 negara / 210 dari 221)",
          not a_.exception and ka["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin") and ka["Median antarnegara"][0] == "26,6%"
          and ka["Negara berpangsa 50% atau lebih"][0] == "65 negara" and ka["Cakupan negara"][0] == "210 dari 221", str(ka))
    b_, kb = kartu_hal("b_fosil")
    check("D10: halaman B tidak rusak (60,7% -3,0 / 30,4% +4,3 / 8,9% -1,3 / 210 dari 221)",
          not b_.exception and kb["Pangsa listrik fosil"] == ("60,7%", "-3,0 poin") and kb["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin")
          and kb["Nuklir dan lainnya (sisa)"] == ("8,9%", "-1,3 poin") and kb["Negara dalam perhitungan"][0] == "210 dari 221", str(kb))
    c_, kc = kartu_hal("c_bauran")
    check("D10: halaman C tidak rusak (29.683 TWh +2.782 / fosil 61,0% -2,8 / nuklir 8,9% -1,3 / terbarukan 30,1% +4,1)",
          not c_.exception and kc["Total pembangkitan"] == ("29.683 TWh", "+2.782 TWh") and kc["Pangsa fosil"] == ("61,0%", "-2,8 poin")
          and kc["Pangsa nuklir"] == ("8,9%", "-1,3 poin") and kc["Pangsa terbarukan"] == ("30,1%", "+4,1 poin"), str(kc))
    r_, kr = kartu_hal("ringkasan")
    check("D10: Ringkasan tidak rusak (30,4% / 60,7% / 486 / 210 dari 221)",
          not r_.exception and kr["Pangsa listrik terbarukan"][0] == "30,4%" and kr["Pangsa listrik fosil"][0] == "60,7%"
          and kr["Intensitas emisi (gCO₂e/kWh)"][0] == "486" and kr["Cakupan negara"][0] == "210 dari 221", str(kr))
    k_hal = S.baru()
    k_hal.switch_page("halaman/kualitas.py").run()
    check("D10: halaman Kualitas (masih placeholder 4-3e) tetap tampil tanpa error", not k_hal.exception)

    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN HALAMAN D: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
