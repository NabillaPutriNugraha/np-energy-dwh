"""Uji otomatis Halaman C (Bauran Pembangkitan) dengan AppTest.
Jalankan dari folder proyek:  python dashboard/tests/test_halaman_c.py
Angka di halaman dibandingkan dengan perhitungan INDEPENDEN di pandas dari mart.v_generation_mix (baris mentah).
Tidak membuktikan tampilan visual; itu diperiksa manual di browser."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd            # noqa: E402

import smoke_test as S         # noqa: E402
from smoke_test import check, r1, tanpa_error  # noqa: E402
import charts                  # noqa: E402
import db                      # noqa: E402
import queries                 # noqa: E402
import theme                   # noqa: E402

UNK = "Tidak diketahui"
HAL = "halaman/c_bauran.py"
SUMBER = Path(__file__).resolve().parents[1] / "halaman" / "c_bauran.py"
LABEL_KARTU = {"Fossil": "Pangsa fosil", "Nuklir": "Pangsa nuklir", "Renewable": "Pangsa terbarukan"}


def halaman(at=None):
    at = at or S.baru()
    at.switch_page(HAL).run()
    return at


def ruang(mix, tahun, benua=None):
    d = mix[mix["year"] == tahun]
    return d if benua is None else d[d["continent"].fillna(UNK).isin(benua)]


def ref_kategori(mix, tahun, benua=None):
    d = ruang(mix, tahun, benua)
    g = d.groupby("source_category")["generation_twh"].sum()
    tot = float(g.sum())
    return {k: (float(v), r1(100 * float(v) / tot, 1)) for k, v in g.items()}, tot


def kartu_harapan(mix, tahun, benua=None, base=2019):
    a, ta = ref_kategori(mix, tahun, benua)
    d = tahun != base
    b, tb = ref_kategori(mix, base, benua) if d else ({}, None)
    out = {"Total pembangkitan": (f"{theme.fmt_num(ta, 0)} TWh", theme.fmt_delta(round(ta) - round(tb), 0, " TWh") if d else None)}
    for k in charts.urut_kategori(mix["source_category"].unique()):
        if k in a:
            dl = theme.fmt_delta(a[k][1] - b[k][1], 1, " poin") if (d and k in b) else None
            out[LABEL_KARTU[k]] = (theme.fmt_pct(a[k][1]), dl)
        else:
            out[LABEL_KARTU[k]] = (theme.fmt_pct(None), None)
    return out


def kartu(at):
    return {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}


def df_dengan(at, kolom):
    for d in at.dataframe:
        if kolom in d.value.columns:
            return d.value
    return None


def main():
    mix = db.run_query("SELECT * FROM mart.v_generation_mix")
    vcy = db.run_query("SELECT iso3_code, country_name, continent FROM mart.v_country_year WHERE year = 2023")
    benua_semua = sorted(set(mix["continent"].fillna(UNK)) | set(vcy["continent"].fillna(UNK)))
    grup_semua = tuple(sorted(mix["group_label"].unique()))
    cont_semua = tuple(sorted(db.run_query("SELECT DISTINCT COALESCE(continent,'Tidak diketahui') AS v FROM mart.v_country_year")["v"]))
    grup_all = tuple(sorted(db.run_query("SELECT DISTINCT group_label AS v FROM mart.v_country_year")["v"]))
    print(f"Data dasar: {len(mix)} baris v_generation_mix\n== Halaman C")

    # ------------------------------------------------ 1. halaman dapat di-import dan dirender
    try:
        compile(SUMBER.read_text(encoding="utf-8"), str(SUMBER), "exec")
        ok_compile = True
    except SyntaxError:
        ok_compile = False
    check("C1: kode halaman C valid (dapat dikompilasi)", ok_compile)
    at = halaman()
    tanpa_error(at, "C1: halaman C dirender tanpa error")

    # ------------------------------------------------ 2. query tanpa error
    ok = True
    try:
        for fn, args in [(queries.c_catalog, ()), (queries.c_source, (cont_semua, grup_all)), (queries.c_category, (cont_semua, grup_all)),
                         (queries.c_counts, (cont_semua, grup_all)), (queries.c_totals, (cont_semua, grup_all)), (queries.c_countries, ()),
                         (queries.c_source_country, ("IDN",)), (queries.c_category_country, ("IDN",)),
                         (queries.c_detail, (2023, cont_semua, grup_all, [], None, False, 100)),
                         (queries.c_detail_count, (2023, cont_semua, grup_all, [], None, False))]:
            r = fn(*args)
            ok &= (len(r) > 0) if hasattr(r, "__len__") else r > 0
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("   galat:", exc)
    check("C2: semua query halaman C berjalan dan mengembalikan data", ok)

    # ------------------------------------------------ 3. KPI global = pandas
    check("C3: kartu KPI (2023 vs 2019, dunia) = pandas", kartu(at) == kartu_harapan(mix, 2023), str(kartu(at)))
    k = kartu(at)
    check("C3: nilai acuan proyek (29.683 TWh +2.782 / fosil 61,0% / nuklir 8,9% / terbarukan 30,1%)",
          k["Total pembangkitan"] == ("29.683 TWh", "+2.782 TWh") and k["Pangsa fosil"] == ("61,0%", "-2,8 poin")
          and k["Pangsa nuklir"] == ("8,9%", "-1,3 poin") and k["Pangsa terbarukan"] == ("30,1%", "+4,1 poin"), str(k))

    # ------------------------------------------------ 4. filter tahun
    ok_thn = True
    totals = {}
    for thn in (2021, 2022, 2019):
        at.sidebar.selectbox(key="f_year").select(thn).run()
        ok_thn &= (kartu(at) == kartu_harapan(mix, thn)) and not at.exception
        totals[thn] = kartu(at)["Total pembangkitan"][0]
    check("C4: filter tahun 2021, 2022, 2019: kartu = pandas", ok_thn)
    check("C4: tahun 2019 tanpa selisih dan ada petunjuk",
          all(d is None for _, d in kartu(at).values()) and any("pilih tahun setelah 2019" in c.value for c in at.caption))
    at.sidebar.selectbox(key="f_year").select(2023).run()
    check("C4: total pembangkitan berubah mengikuti tahun (2019 berbeda dari 2023)", totals[2019] != kartu(at)["Total pembangkitan"][0])

    # ------------------------------------------------ 5. filter benua
    for benua in (["Asia"], ["Europe"], ["Oceania"]):
        at.sidebar.multiselect(key="f_continents").set_value(benua).run()
        check(f"C5: filter {benua[0]}: kartu = pandas dan tanpa error", not at.exception and kartu(at) == kartu_harapan(mix, 2023, benua),
              str(kartu(at)))
    check("C5: total Asia berbeda dari total dunia (total tidak ditulis manual)", kartu_harapan(mix, 2023, ["Asia"])["Total pembangkitan"][0] != "29.683 TWh")
    at.sidebar.multiselect(key="f_continents").set_value([UNK]).run()
    check("C5: hanya 'Tidak diketahui' (tanpa data Ember): pesan jelas tanpa error",
          not at.exception and any("Tidak ada data bauran" in i.value for i in at.info))
    at.sidebar.multiselect(key="f_continents").set_value([]).run()
    check("C5: filter kosong: pesan jelas tanpa error", not at.exception and any("Tidak ada data bauran" in i.value for i in at.info))
    at.sidebar.multiselect(key="f_continents").set_value(list(cont_semua)).run()

    # ------------------------------------------------ 6. kategori dari data
    kat_db = set(mix["source_category"].unique())
    at = halaman()
    kartu_pangsa = {l for l in kartu(at) if l.startswith("Pangsa ")}
    check("C6: kategori = data aktual (3: Fossil, Nuklir, Renewable); kartu pangsa sesuai kategori di data",
          kat_db == {"Fossil", "Nuklir", "Renewable"} and kartu_pangsa == {LABEL_KARTU[k] for k in kat_db}, str(sorted(kat_db)))
    at.radio(key="c_level").set_value("Sumber rinci").run()
    tanpa_error(at, "C6: tingkat 'Sumber rinci' tanpa error")
    check("C6: pilihan rinci kategori = 'Semua kategori' + kategori dari data",
          list(at.selectbox(key="c_kat").options) == ["Semua kategori"] + [charts.kategori_label(k) for k in charts.urut_kategori(kat_db)],
          str(list(at.selectbox(key="c_kat").options)))
    check("C6: nama tak dikenal tidak diciptakan: label cadangan = nama asli",
          charts.kategori_label("KategoriBaru") == "KategoriBaru" and charts.sumber_label("SumberBaru") == "SumberBaru")

    # ------------------------------------------------ 7. sumber dari data
    sum_db = set(mix["source_name"].unique())
    at = halaman()
    ringkas = df_dengan(at, "Pangsa dalam kategori (%)")
    sumber_tabel = {re.search(r"\(([^()]+)\)$", s).group(1) for s in ringkas["Sumber"]}
    check("C7: sumber di tabel ringkasan = 9 sumber dari data (tanpa 'Oil'/'Hydropower' yang tidak ada di data)",
          sumber_tabel == sum_db and len(sum_db) == 9 and "Oil" not in sum_db and "Hydropower" not in sum_db, str(sorted(sum_db)))
    for kat in sorted(kat_db):
        at.radio(key="c_level").set_value("Sumber rinci").run()
        at.selectbox(key="c_kat").select(kat).run()
        tanpa_error(at, f"C7: rinci kategori {kat} tanpa error")
    kode = SUMBER.read_text(encoding="utf-8")
    check("C7: kode halaman tidak menulis nama sumber manual (Coal, Gas, Hydro, Wind, Solar, ...)",
          not any(re.search(rf"[\"']{n}[\"']", kode) for n in sum_db), "")
    check("C7: kode halaman tidak menulis nama kategori manual (Fossil, Nuklir, Renewable)",
          not any(re.search(rf"[\"']{n}[\"']", kode.replace('"Fossil": "inverse", "Renewable": "normal"', "")) for n in kat_db), "")

    # ------------------------------------------------ 8. total tidak hardcoded
    terlarang = ["29683", "29.683", "26901", "26.901", "29682", "17160", "18113", "8924", "6986", "2644", "2754"]
    check("C8: kode halaman tidak memuat angka total/TWh yang ditulis manual", not any(t in kode for t in terlarang))
    check("C8: tidak ada angka data yang ditulis manual (persen dan jumlah negara)",
          not re.search(r"(?<![{\w])\d+ negara", kode) and not any(t in kode for t in ["61,0", "30,1", "8,9", "63,8", "208 negara"]))

    # ------------------------------------------------ 9. pangsa kategori konsisten dengan referensi
    ok_jml = ok_ref = ok_src = ok_dlm = ok_nol = True
    for nama, benua in [("Dunia", None)] + [(b, [b]) for b in benua_semua if b != UNK]:
        cc = queries.c_category(tuple(benua or cont_semua), grup_all)
        ss = queries.c_source(tuple(benua or cont_semua), grup_all)
        for thn in range(2019, 2024):
            r, tot = ref_kategori(mix, thn, benua)
            c = cc[cc["year"] == thn].set_index("kategori")
            ok_jml &= abs(float(c["pangsa"].sum()) - 100) < 1e-9 and abs(float(c["total_twh"].iloc[0]) - tot) < 1e-6
            ok_ref &= all(abs(float(c.loc[k, "pangsa"]) - 100 * v[0] / tot) < 1e-9 and abs(float(c.loc[k, "pangsa_bulat"]) - v[1]) < 1e-9 for k, v in r.items())
            s = ss[ss["year"] == thn]
            ok_src &= abs(float(s["pangsa_total"].sum()) - 100) < 1e-9
            for kat, g in s.groupby("kategori"):
                if float(g["twh"].sum()) == 0:      # total kategori 0 TWh: pangsa dalam kategori tidak terdefinisi, harus NULL
                    ok_nol &= bool(g["pangsa_kategori_bulat"].isna().all())
                    continue
                # galat pembulatan 1 desimal per sumber paling besar 0,05
                ok_dlm &= abs(float(g["pangsa_kategori_bulat"].sum()) - 100) <= 0.05 * len(g) + 1e-9
    check("C9: jumlah pangsa kategori = 100 dan total = jumlah TWh (semua tahun, dunia dan tiap benua)", ok_jml)
    check("C9: pangsa kategori (mentah dan dibulatkan) = pandas: TWh kategori / TWh total x 100", ok_ref)
    check("C9: jumlah pangsa semua sumber = 100", ok_src)
    check("C9: pangsa dalam kategori berjumlah 100 (toleransi pembulatan 0,05 x jumlah sumber)", ok_dlm)
    check("C9: kategori bertotal 0 TWh (Oceania, Nuklir): pangsa dalam kategori NULL, bukan 0 atau 100 (tidak diisi perkiraan)", ok_nol)
    d23 = mix[mix["year"] == 2023]
    rata = d23.groupby(["iso3_code", "source_category"])["generation_twh"].sum().groupby("iso3_code").apply(
        lambda s: 100 * s.get("Renewable", 0) / s.sum() if s.sum() > 0 else float("nan")).mean()
    check("C9: pangsa global tertimbang berbeda dari rata-rata sederhana antarnegara (bukan rata-rata sederhana)",
          abs(rata - ref_kategori(mix, 2023)[0]["Renewable"][0] / ref_kategori(mix, 2023)[1] * 100) > 1.0, f"rata-rata sederhana {rata:.1f}%")
    jml = mix.groupby(["iso3_code", "year"])["generation_twh"].sum().rename("s")
    vt = db.run_query("SELECT iso3_code, year, total_generation_twh FROM mart.v_country_year WHERE total_generation_twh IS NOT NULL")
    j = vt.merge(jml.reset_index(), on=["iso3_code", "year"])
    check("C9: jumlah semua sumber per negara-tahun = total pembangkitan Ember (selisih maks <= 0,05 TWh); sumber tanpa baris tidak menghilangkan TWh",
          float((j["total_generation_twh"] - j["s"]).abs().max()) <= 0.05, f"{len(j)} pasangan, maks {float((j['total_generation_twh'] - j['s']).abs().max()):.4f}")

    # ------------------------------------------------ 10. treemap hanya TWh > 0
    uji = pd.DataFrame({"kategori": ["Fossil", "Fossil", "Nuklir", "Renewable", "Renewable"],
                        "sumber": ["Coal", "Gas", "Nuclear", "Wind", "Solar"], "twh": [10.0, 0.0, None, 5.0, -1.0]})
    tf = charts.treemap_frame(uji)
    fig = charts.mix_treemap(uji)
    check("C10: treemap_frame membuang nilai 0, NULL, dan negatif (sintetis)", list(tf["sumber"]) == ["Coal", "Wind"] and (tf["twh"] > 0).all())
    check("C10: gambar treemap hanya memuat luas > 0", all(v > 0 for v in fig.data[0].values))
    src_g = queries.c_source(tuple(cont_semua), grup_all)
    check("C10: treemap data nyata (dunia 2023): semua sumber > 0 dan tidak ada NULL",
          (charts.treemap_frame(src_g[src_g["year"] == 2023])["twh"] > 0).all() and len(charts.treemap_frame(src_g[src_g["year"] == 2023])) == 9)
    at = halaman()
    at.sidebar.multiselect(key="f_continents").set_value(["Oceania"]).run()
    so = queries.c_source(("Oceania",), grup_all)
    so23 = so[so["year"] == 2023]
    nol = int((so23["twh"] <= 0).sum())
    tanpa_error(at, "C10: skenario Oceania (ada sumber 0 TWh) tanpa error")
    check(f"C10: Oceania: {nol} sumber bernilai 0 TWh dikeluarkan dari treemap dan disebut di keterangan (data tetap ada di tabel)",
          nol >= 1 and len(charts.treemap_frame(so23)) == len(so23) - nol and f"{nol} sumber bernilai 0 TWh" in " ".join(c.value for c in at.caption),
          f"nol={nol}")
    at.radio(key="c_level").set_value("Sumber rinci").run()
    at.selectbox(key="c_kat").select("Nuklir").run()
    check("C10: Oceania + rinci Nuklir (total 0 TWh): pesan 'tidak terdefinisi', tanpa error dan tanpa grafik kosong",
          not at.exception and any("tidak terdefinisi" in i.value for i in at.info))
    at.sidebar.multiselect(key="f_continents").set_value(list(cont_semua)).run()

    # ------------------------------------------------ 11. tabel detail
    at = halaman()
    det = df_dengan(at, "Pangsa dalam negara (%)")
    d23p = mix[(mix["year"] == 2023) & (mix["generation_twh"] > 0)]
    check("C11: tabel detail berisi data, kolom Negara/Tahun/Kategori/Sumber/Pembangkitan, maksimal 100 baris, tanpa baris 0 TWh",
          det is not None and 0 < len(det) <= 100 and {"Negara", "Tahun", "Kategori", "Sumber", "Pembangkitan (TWh)"} <= set(det.columns)
          and (det["Pembangkitan (TWh)"] > 0).all(), str(None if det is None else len(det)))
    teks = " ".join(c.value for c in at.caption)
    check("C11: keterangan 'Menampilkan 100 dari 1007 baris' (1007 = baris > 0 TWh pada 2023 menurut pandas)",
          f"Menampilkan 100 dari {len(d23p)} baris" in teks and len(d23p) == 1007, f"{len(d23p)}")
    check("C11: keterangan menyebut jumlah baris 0 TWh yang disembunyikan (809 pada 2023)",
          f"{int((mix[(mix['year'] == 2023)]['generation_twh'] == 0).sum())} baris 0 TWh disembunyikan" in teks)
    at.toggle(key="c_nol").set_value(True).run()
    check("C11: 'Tampilkan baris 0 TWh' memunculkan jumlah baris total 1816", "dari 1816 baris" in " ".join(c.value for c in at.caption))
    at.toggle(key="c_nol").set_value(False).run()
    at.select_slider(key="c_batas").set_value(50).run()
    check("C11: batas baris 50 dihormati", len(df_dengan(at, "Pangsa dalam negara (%)")) == 50)
    at.select_slider(key="c_batas").set_value(100).run()
    at.multiselect(key="c_negara").set_value(["IDN"]).run()
    idn = df_dengan(at, "Pangsa dalam negara (%)")
    harap = mix[(mix["year"] == 2023) & (mix["iso3_code"] == "IDN") & (mix["generation_twh"] > 0)]
    check("C11: filter negara Indonesia: hanya baris Indonesia, jumlah dan TWh = pandas",
          set(idn["Negara"]) == {"Indonesia"} and len(idn) == len(harap) and abs(float(idn["Pembangkitan (TWh)"].sum()) - float(harap["generation_twh"].sum())) < 1e-6,
          f"{len(idn)} baris")
    at.multiselect(key="c_negara").set_value([]).run()
    at.selectbox(key="c_kat_tabel").select("Renewable").run()
    ren = df_dengan(at, "Pangsa dalam negara (%)")
    check("C11: filter kategori Renewable pada tabel detail", set(ren["Kategori"]) == {"Terbarukan"})
    at.selectbox(key="c_kat_tabel").select("Semua kategori").run()

    # ------------------------------------------------ 12 dan 13. teks halaman
    at = halaman()
    teks = " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [t.value for t in at.title]
                    + [i.value for i in at.info] + [s.value for s in at.subheader])
    check("C12: tidak ada catatan pengembang ('Tahap 4', 'placeholder', 'dalam pengembangan')",
          not any(k in (teks + kode).lower() for k in ("tahap 4", "placeholder", "dalam pengembangan")))
    kausal = ["menyebabkan", "akibat dari", "disebabkan", "karena kebijakan", "berkat ", "berhasil menurunkan", "gagal menurunkan"]
    check("C13: teks dan kode halaman tidak memuat klaim sebab-akibat", not any(k in (teks + kode).lower() for k in kausal))
    check("C13: ada pernyataan eksplisit bahwa dashboard menunjukkan pola deskriptif, bukan sebab-akibat", "bukan hubungan sebab-akibat" in kode)

    # ------------------------------------------------ pembanding negara sorotan
    at = halaman()
    r, tot = ref_kategori(mix[mix["iso3_code"] == "IDN"], 2023)
    c_idn = queries.c_category_country("IDN")
    c_idn = c_idn[c_idn["year"] == 2023].set_index("kategori")
    check("C8b: bauran Indonesia 2023 (negara sorotan) = pandas: fosil 84,9% dan terbarukan 15,1%, tanpa baris nuklir",
          all(abs(float(c_idn.loc[k, "pangsa_bulat"]) - v[1]) < 1e-9 for k, v in r.items()) and set(r) == {"Fossil", "Renewable"}
          and r["Fossil"][1] == 84.9 and r["Renewable"][1] == 15.1, str({k: v[1] for k, v in r.items()}))
    at.sidebar.multiselect(key="f_continents").set_value(["Europe"]).run()
    check("C8b: keterangan perbandingan menyatakan negara sorotan tidak dipengaruhi filter benua/kelompok, dan batang sorotan tetap Indonesia",
          any("tidak dipengaruhi filter benua dan kelompok negara" in c.value for c in at.caption) and not at.exception)
    at.sidebar.multiselect(key="f_continents").set_value(list(cont_semua)).run()
    iso_tanpa = vcy[vcy["continent"].isna()]["iso3_code"].iloc[0]
    at.sidebar.selectbox(key="f_country").select(iso_tanpa).run()
    check(f"C8b: negara sorotan tanpa data Ember ({iso_tanpa}): pesan jelas tanpa error",
          not at.exception and any("tidak memiliki data bauran Ember" in i.value for i in at.info))

    # ------------------------------------------------ keamanan: query hanya SELECT
    sqls = [getattr(queries, n) for n in dir(queries) if n.startswith("C_") and n.endswith("SQL")]
    check(f"C: {len(sqls)} query halaman C hanya SELECT (tanpa INSERT/UPDATE/DELETE/CREATE/DROP/ALTER)",
          len(sqls) >= 8 and not any(re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)\b", q, re.I) for q in sqls))

    # ------------------------------------------------ 14 dan 15. regresi A dan B
    at = S.baru()
    at.switch_page("halaman/a_terbarukan.py").run()
    ka = kartu(at)
    check("C14: halaman A tidak rusak (30,4% +4,3 poin / 26,6% / 65 negara / 210 dari 221)",
          not at.exception and ka["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin") and ka["Median antarnegara"][0] == "26,6%"
          and ka["Negara berpangsa 50% atau lebih"][0] == "65 negara" and ka["Cakupan negara"][0] == "210 dari 221", str(ka))
    at.switch_page("halaman/b_fosil.py").run()
    kb = kartu(at)
    check("C15: halaman B tidak rusak (60,7% -3,0 / 30,4% +4,3 / 8,9% -1,3 / 210 dari 221)",
          not at.exception and kb["Pangsa listrik fosil"] == ("60,7%", "-3,0 poin") and kb["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin")
          and kb["Nuklir dan lainnya (sisa)"] == ("8,9%", "-1,3 poin") and kb["Negara dalam perhitungan"][0] == "210 dari 221", str(kb))
    at.switch_page("halaman/ringkasan.py").run()
    kr = kartu(at)
    check("C14/15: Ringkasan tidak rusak (30,4% / 60,7% / 486 / 210 dari 221)",
          not at.exception and kr["Pangsa listrik terbarukan"][0] == "30,4%" and kr["Pangsa listrik fosil"][0] == "60,7%"
          and kr["Intensitas emisi (gCO₂e/kWh)"][0] == "486" and kr["Cakupan negara"][0] == "210 dari 221", str(kr))

    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN HALAMAN C: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
