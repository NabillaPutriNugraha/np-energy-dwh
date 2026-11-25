"""Uji otomatis Halaman B (Ketergantungan pada Fosil) dengan AppTest.
Jalankan dari folder proyek:  python dashboard/tests/test_halaman_b.py
Angka di halaman dibandingkan dengan perhitungan INDEPENDEN di pandas dari mart.v_country_year.
Tidak membuktikan tampilan visual; itu diperiksa manual di browser."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd            # noqa: E402

import smoke_test as S         # noqa: E402
from smoke_test import check, r1, tanpa_error  # noqa: E402
import db                      # noqa: E402
import queries                 # noqa: E402
import theme                   # noqa: E402

UNK = "Tidak diketahui"
HAL = "halaman/b_fosil.py"
SUMBER = Path(__file__).resolve().parents[1] / "halaman" / "b_fosil.py"


def halaman(at=None):
    at = at or S.baru()
    at.switch_page(HAL).run()
    return at


def lingkup(df, tahun, benua=None):
    d = df[df["year"] == tahun]
    return d if benua is None else d[d["continent"].fillna(UNK).isin(benua)]


def kpi_pandas(df, tahun, benua=None):
    d = lingkup(df, tahun, benua)
    s = d[d["fossil_share_elec"].notna() & d["renewables_share_elec"].notna() & (d["electricity_generation_twh"] > 0)]
    w = s["electricity_generation_twh"]
    f, t = (s["fossil_share_elec"] * w).sum() / w.sum(), (s["renewables_share_elec"] * w).sum() / w.sum()
    sisa_benar = ((100 - s["fossil_share_elec"] - s["renewables_share_elec"]) * w).sum() / w.sum()
    return {"n": len(s), "total": len(d), "f": r1(f, 1), "t": r1(t, 1), "f_raw": f, "t_raw": t,
            "sisa": round(100 - r1(f, 1) - r1(t, 1), 1), "sisa_benar": sisa_benar}


def kartu_harapan(df, tahun, benua=None, base=2019):
    a, b = kpi_pandas(df, tahun, benua), kpi_pandas(df, base, benua)
    d = tahun != base
    dp = lambda x, y: theme.fmt_delta(x - y, 1, " poin") if d else None  # noqa: E731
    return {"Pangsa listrik fosil": (theme.fmt_pct(a["f"]), dp(a["f"], b["f"])),
            "Pangsa listrik terbarukan": (theme.fmt_pct(a["t"]), dp(a["t"], b["t"])),
            "Nuklir dan lainnya (sisa)": (theme.fmt_pct(a["sisa"]), dp(a["sisa"], b["sisa"])),
            "Negara dalam perhitungan": (f"{a['n']} dari {a['total']}", None)}


def kartu(at):
    return {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}


def tabel_pasangan(at):
    for d in at.dataframe:
        if "Selisih listrik - energi primer (poin)" in d.value.columns:
            return d.value
    return None


def main():
    df = db.run_query("SELECT * FROM mart.v_country_year")
    mix = db.run_query("SELECT * FROM mart.v_generation_mix")
    benua_semua = sorted(df["continent"].fillna(UNK).unique())
    grup_semua = tuple(sorted(df["group_label"].unique()))
    print(f"Data dasar: {len(df)} baris\n== Halaman B")

    # ------------------------------------------------ 1 dan 10. render, tanpa placeholder
    at = halaman()
    tanpa_error(at, "B1: halaman tampil tanpa error")
    teks = " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [t.value for t in at.title]
                    + [i.value for i in at.info])
    check("B10: tidak ada catatan pengembang ('Tahap 4', 'placeholder', 'dalam pengembangan')",
          not any(k in teks.lower() for k in ("tahap 4", "placeholder", "dalam pengembangan")))

    # ------------------------------------------------ 2. kartu KPI
    check("B2: tiga kartu KPI + cakupan (2023 vs 2019) = pandas", kartu(at) == kartu_harapan(df, 2023), str(kartu(at)))
    k = kartu(at)
    check("B2: nilai acuan proyek (60,7% -3,0 / 30,4% +4,3 / 8,9% -1,3 / 210 dari 221)",
          k["Pangsa listrik fosil"] == ("60,7%", "-3,0 poin") and k["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin")
          and k["Nuklir dan lainnya (sisa)"] == ("8,9%", "-1,3 poin") and k["Negara dalam perhitungan"][0] == "210 dari 221")
    check("B2: label kartu sisa persis 'Nuklir dan lainnya (sisa)'", "Nuklir dan lainnya (sisa)" in k)

    # ------------------------------------------------ 3. nilai 2019-2023 dan konsistensi dengan Ringkasan
    b = queries.b_kpi(tuple(benua_semua), grup_semua)
    ring = queries.kpi_by_year(tuple(benua_semua), grup_semua).set_index("year")
    ok_nilai = ok_ring = True
    for r in b.itertuples():
        p = kpi_pandas(df, r.year)
        ok_nilai &= (abs(r.fosil_bulat - p["f"]) < 1e-9 and abs(r.terbarukan_bulat - p["t"]) < 1e-9
                    and abs(r.sisa_tampil - p["sisa"]) < 1e-9 and int(r.negara_berbobot) == p["n"]
                    and abs(r.fosil - p["f_raw"]) < 1e-9 * 100 and abs(r.terbarukan - p["t_raw"]) < 1e-9 * 100)
        ok_ring &= (abs(r.fosil_bulat - r1(ring.loc[r.year, "fosil"], 1)) < 1e-9
                    and abs(r.terbarukan_bulat - r1(ring.loc[r.year, "terbarukan"], 1)) < 1e-9)
    check("B3: fosil, terbarukan, sisa, dan jumlah negara untuk 2019-2023 = pandas", ok_nilai and len(b) == 5)
    check("B3: fosil dan terbarukan halaman B = KPI Ringkasan untuk semua tahun (himpunan negara sama)", ok_ring)

    # ------------------------------------------------ 4. fosil + terbarukan + sisa = 100
    ok_kartu = ok_mentah = ok_batas = True
    for nama, cont in [("Dunia", None)] + [(x, [x]) for x in benua_semua]:
        bb = queries.b_kpi(tuple(cont or benua_semua), grup_semua)
        for r in bb.itertuples():
            if pd.isna(r.fosil_bulat):
                continue
            ok_kartu &= abs(r.fosil_bulat + r.terbarukan_bulat + r.sisa_tampil - 100) < 1e-9
            ok_mentah &= abs(r.fosil + r.terbarukan + r.sisa_tertimbang - 100) < 1e-9
            ok_batas &= abs(r.sisa_tampil - r.sisa_tertimbang) <= 0.1 + 1e-9
    check("B4: angka kartu (fosil + terbarukan + sisa) = 100,0 untuk semua tahun dan semua cakupan", ok_kartu)
    check("B4: nilai tertimbang tanpa pembulatan berjumlah 100 untuk semua tahun dan cakupan", ok_mentah)
    check("B4: sisa yang tampil berbeda <= 0,1 poin dari sisa tertimbang tanpa pembulatan", ok_batas)
    lengkap = df.dropna(subset=["fossil_share_elec", "low_carbon_share_elec", "renewables_share_elec"])
    # Sumber menyimpan 3 desimal, jadi jumlah dua pangsa bisa menyimpang 0,001 poin (mis. 76,654 + 23,345 = 99,999).
    # Batas 0,0011 memberi ruang bagi galat floating-point; selisih nyata terbesar yang diamati = 0,001 pada 2 dari 1.058 baris.
    dev = (lengkap["fossil_share_elec"] + lengkap["low_carbon_share_elec"] - 100).abs()
    check(f"B4: per negara-tahun ({len(lengkap)}): fosil + low-carbon = 100 sampai presisi sumber 3 desimal (selisih <= 0,001 poin)",
          float(dev.max()) <= 0.0011 and int((dev > 0.01).sum()) == 0, f"maks {dev.max():.4f}; baris > 0,0005: {int((dev > 0.0005).sum())}")
    check("B4: per negara-tahun: low-carbon tidak lebih kecil dari terbarukan (sisa tidak negatif)",
          float((lengkap["low_carbon_share_elec"] - lengkap["renewables_share_elec"]).min()) >= -0.001)
    ok_ember = True
    for thn in (2019, 2023):
        m = mix[mix["year"] == thn]
        nuk = 100 * m.loc[m["source_category"] == "Nuklir", "generation_twh"].sum() / m["generation_twh"].sum()
        ok_ember &= abs(float(b.loc[b["year"] == thn, "sisa_tampil"].iloc[0]) - nuk) <= 0.2
    check("B4: sisa (Renewable) dekat dengan pangsa nuklir Ember (sumber lain), selisih <= 0,2 poin pada 2019 dan 2023", ok_ember)

    # ------------------------------------------------ 5. filter benua dan tahun
    at.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    tanpa_error(at, "B5: filter benua Asia berjalan")
    check("B5: kartu Asia = pandas", kartu(at) == kartu_harapan(df, 2023, ["Asia"]), str(kartu(at)))
    at.sidebar.multiselect(key="f_continents").set_value(["Europe"]).run()
    check("B5: kartu Europe = pandas", kartu(at) == kartu_harapan(df, 2023, ["Europe"]))
    at.sidebar.selectbox(key="f_year").select(2021).run()
    check("B5: kartu Europe 2021 = pandas", kartu(at) == kartu_harapan(df, 2021, ["Europe"]))
    at.sidebar.selectbox(key="f_year").select(2019).run()
    tanpa_error(at, "B5: tahun 2019 tanpa error")
    check("B5: tahun 2019 tanpa selisih, dumbbell fosil diganti petunjuk",
          all(d is None for _, d in kartu(at).values()) and any("Pilih tahun setelah 2019" in i.value for i in at.info))
    at.sidebar.selectbox(key="f_year").select(2023).run()
    at.sidebar.multiselect(key="f_continents").set_value([]).run()
    check("B5: filter kosong: pesan jelas, tanpa error", not at.exception and any("Tidak ada negara" in i.value for i in at.info))
    at.sidebar.multiselect(key="f_continents").set_value(benua_semua).run()

    # ------------------------------------------------ 6 dan 7. dumbbell Top N menurut PEMBANGKITAN
    d23, d19 = df[df["year"] == 2023], df[df["year"] == 2019].set_index("iso3_code")
    urut_gen = d23[d23["electricity_generation_twh"].notna()].sort_values(["electricity_generation_twh", "country_name"], ascending=[False, True])
    for n in (5, 10, 15):
        t = queries.b_topn(2023, tuple(benua_semua), grup_semua, n)
        harap = urut_gen.head(n)
        ok_urut = list(t["iso3_code"]) == list(harap["iso3_code"])
        ok_nilai = True
        for r in t.itertuples():
            a, bb = d19.loc[r.iso3_code, "fossil_share_elec"], d23.set_index("iso3_code").loc[r.iso3_code, "fossil_share_elec"]
            ok_nilai &= abs(r.fosil_awal - r1(a, 1)) < 1e-9 and abs(r.fosil_tahun - r1(bb, 1)) < 1e-9 \
                and abs(r.perubahan - (r1(bb, 1) - r1(a, 1))) < 1e-9
        check(f"B6: dumbbell Top {n}: negara, urutan (menurut pembangkitan), dan nilai fosil 2019/2023 = pandas", ok_urut and ok_nilai,
              str(list(t['country_name'])[:3]))
        at.radio(key="b_topn").set_value(n).run()
        tanpa_error(at, f"B6: halaman dengan Top {n} tanpa error")
    t10 = queries.b_topn(2023, tuple(benua_semua), grup_semua, 10)
    gen = list(t10["pembangkitan_twh"])
    check("B7: urutan Top 10 menurun menurut pembangkitan listrik", all(x >= y for x, y in zip(gen, gen[1:])))
    check("B7: urutan Top 10 bukan urutan pangsa fosil (peringkat tidak berdasarkan pangsa fosil)",
          list(t10["iso3_code"]) != list(t10.sort_values("fosil_tahun", ascending=False)["iso3_code"]))
    check("B7: Top 10 = 10 pembangkit terbesar, termasuk negara berpangsa fosil rendah (Brazil, France)",
          {"BRA", "FRA"} <= set(t10["iso3_code"]))
    at = halaman()
    at.radio(key="b_topn").set_value(10).run()
    teks = " ".join(c.value for c in at.caption)
    ok = t10.dropna(subset=["fosil_awal", "fosil_tahun"])
    esp = (f"Dari {len(t10)} negara: {int((ok['perubahan'] < 0).sum())} berpangsa fosil lebih rendah daripada 2019, "
           f"{int((ok['perubahan'] > 0).sum())} lebih tinggi, {int((ok['perubahan'] == 0).sum())} sama")
    check("B6: keterangan dumbbell (jumlah lebih rendah/tinggi/sama) dihitung dari data dan = pandas", esp in teks, esp)
    check("B7: keterangan menyebut urutan menurut pembangkitan, bukan pangsa fosil",
          "menurut pembangkitan listrik 2023 dari yang terbesar, bukan menurut pangsa fosil" in teks)

    # ------------------------------------------------ 8. cakupan energi primer
    ok_cov = True
    for thn in range(2019, 2024):
        c = queries.b_coverage(thn)
        d = df[df["year"] == thn]
        ok_cov &= (int(c["berdata_primer"].sum()) == int(d["renewables_share_energy"].notna().sum())
                   and int(c["pasangan_valid"].sum()) == int((d["renewables_share_energy"].notna() & d["renewables_share_elec"].notna()).sum()))
    c23 = queries.b_coverage(2023).set_index("benua")
    check("B8: cakupan energi primer dan pasangan valid per tahun = pandas", ok_cov)
    check("B8: acuan proyek 2023: 79 negara berdata primer, 78 pasangan valid",
          int(c23["berdata_primer"].sum()) == 79 and int(c23["pasangan_valid"].sum()) == 78)
    check("B8: sebaran per benua 2023 (Europe 34/42, Asia 28/49, Africa 4/55, North America 4/33, Tidak diketahui 0/12)",
          all(int(c23.loc[b_, "berdata_primer"]) == p and int(c23.loc[b_, "negara"]) == n for b_, p, n in
              [("Europe", 34, 42), ("Asia", 28, 49), ("Africa", 4, 55), ("North America", 4, 33), (UNK, 0, 12)]))
    at = halaman()
    teks = " ".join([c.value for c in at.info] + [c.value for c in at.caption])
    check("B8: banner cakupan menyebut '79 negara' dan '78 di antaranya' (dihitung dari data)",
          "Cakupan energi primer: 79 negara pada 2023" in teks and "Sebanyak 78 di antaranya" in teks)
    check("B8: banner menyatakan tidak ada agregat dunia/benua untuk energi primer", "tidak ada angka agregat dunia atau benua" in teks)
    pas = tabel_pasangan(at)
    p23 = d23[d23["renewables_share_energy"].notna()]
    check("B8: tabel pasangan memuat semua 79 negara berdata energi primer", pas is not None and len(pas) == len(p23) == 79, str(None if pas is None else len(pas)))
    v = p23[p23["renewables_share_elec"].notna()]
    rend = sum(r1(a, 1) > r1(e, 1) for a, e in zip(v["renewables_share_elec"], v["renewables_share_energy"]))
    sama = sum(r1(a, 1) == r1(e, 1) for a, e in zip(v["renewables_share_elec"], v["renewables_share_energy"]))
    tinggi = len(v) - rend - sama
    esp = f"Dari {len(v)} negara berpasangan data pada filter ini: {rend} berpangsa energi primer lebih rendah daripada pangsa listrik, {sama} sama (pada 1 desimal), {tinggi} lebih tinggi"
    check("B8: hitungan lebih rendah/sama/lebih tinggi (aturan 1 desimal) = pandas", esp in " ".join(c.value for c in at.caption), esp)
    check("B8: negara dengan nilai sama (1 desimal) dipertahankan: baris 'Sama' di tabel = pandas",
          int((pas["Keterangan"] == "Sama").sum()) == sama, f"{int((pas['Keterangan'] == 'Sama').sum())} baris")
    at.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    pas = tabel_pasangan(at)
    asia = p23[p23["continent"] == "Asia"]
    check("B8: filter Asia: tabel pasangan = 28 negara Asia berdata primer; banner cakupan tetap 79 (tidak dipengaruhi filter)",
          pas is not None and len(pas) == len(asia) == 28 and "Cakupan energi primer: 79 negara" in " ".join(c.value for c in at.info))
    at.sidebar.multiselect(key="f_continents").set_value(benua_semua).run()

    # ------------------------------------------------ 9. NULL tidak menjadi 0
    at = halaman()
    pas = tabel_pasangan(at)
    ukr = pas[pas["Negara"] == "Ukraine"].iloc[0]
    col_l, col_p = "Terbarukan pada listrik 2023 (%)", "Terbarukan pada energi primer 2023 (%)"
    check("B9: Ukraina 2023: pangsa listrik kosong (bukan 0), energi primer terisi, keterangan 'Pangsa listrik kosong'",
          pd.isna(ukr[col_l]) and pd.notna(ukr[col_p]) and ukr["Keterangan"] == "Pangsa listrik kosong")
    check("B9: jumlah nilai 0 pada tabel = jumlah nilai 0 pada data (tidak ada NULL yang menjadi 0)",
          int((pas[col_l] == 0).sum()) == sum(r1(x, 1) == 0 for x in p23["renewables_share_elec"].dropna()))
    check("B9: jumlah sel kosong pada tabel = jumlah NULL pada data",
          int(pas[col_l].isna().sum()) == int(p23["renewables_share_elec"].isna().sum()) and int(pas[col_p].isna().sum()) == 0)
    check("B9: keterangan menyebut Ukraine tanpa pangsa listrik dan tidak diisi 0", "Tanpa pangsa listrik pada 2023" in " ".join(c.value for c in at.caption)
          and "Ukraine" in " ".join(c.value for c in at.caption))
    lso = df[(df["year"] == 2023) & (df["iso3_code"] == "LSO")].iloc[0]
    check("B9: Lesotho 2023 (pembangkitan 0, pangsa kosong) tidak masuk perhitungan KPI (n = 210, bukan 211)",
          pd.isna(lso["renewables_share_elec"]) and kpi_pandas(df, 2023)["n"] == 210)

    # ------------------------------------------------ 11. tidak ada klaim hard-coded
    kode = SUMBER.read_text(encoding="utf-8")
    terlarang = ["79 negara", "78 negara", "60,7", "30,4", "8,9", "10,2", "26,1", "63,7", "76 berpangsa"]
    check("B11: kode halaman tidak memuat angka data yang ditulis manual", not any(t in kode for t in terlarang)
          and not re.search(r"(?<![{\w])\d+ negara", kode), "")
    kata_kausal = ["menyebabkan", "akibat dari", "karena kebijakan", "berkat "]
    check("B11: teks halaman tidak memuat klaim sebab-akibat", not any(k in kode.lower() for k in kata_kausal))

    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN HALAMAN B: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
