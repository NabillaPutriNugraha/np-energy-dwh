"""Uji otomatis halaman Kualitas Data (Fase 4-3e) dengan AppTest.
Jalankan dari folder proyek:  python dashboard/tests/test_halaman_kualitas.py
Angka di halaman dibandingkan dengan perhitungan INDEPENDEN di pandas dari baris mentah mart.v_country_year,
mart.v_generation_mix, dan mart.v_source_comparison. Asal nilai kosong (sumber atau ETL) ditelusuri ke berkas mentah
data/raw bila berkas itu ada. Bagian 'tidak hardcode' mengubah hasil query (patch) dan memastikan halaman ikut berubah.
Tidak membuktikan tampilan visual; itu diperiksa manual di browser.
Catatan: rekonsiliasi DW -> Mart (butuh akses schema dw) ada di sql/100_validate_quality.sql, bukan di sini."""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np             # noqa: E402
import pandas as pd            # noqa: E402

import smoke_test as S         # noqa: E402
from smoke_test import check, r1, tanpa_error, wavg  # noqa: E402
import charts                  # noqa: E402
import db                      # noqa: E402
import queries                 # noqa: E402
import theme                   # noqa: E402

HAL = "halaman/kualitas.py"
ROOT = Path(__file__).resolve().parents[2]
SUMBER = ROOT / "dashboard" / "halaman" / "kualitas.py"
RAW_EMBER = ROOT / "data" / "raw" / "release_generation_yearly_global.csv"
RAW_REN = ROOT / "data" / "raw" / "renewable_energy_share_2000_2025.csv"
TAHUN = [2019, 2020, 2021, 2022, 2023]


def halaman(at=None):
    at = at or S.baru()
    at.switch_page(HAL).run()
    return at


def kartu(at):
    return {m.label: (m.value, m.delta if m.delta else None) for m in at.metric}


def df_dengan(at, *kolom):
    for d in at.dataframe:
        if set(kolom) <= set(d.value.columns):
            return d.value
    return None


def semua_df(at, kolom):
    return [d.value for d in at.dataframe if kolom in d.value.columns]


def figs(at):
    return [json.loads(e.proto.spec) for e in at.get("plotly_chart")]


def teks_halaman(at):
    return " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [t.value for t in at.title]
                    + [i.value for i in at.info] + [w.value for w in at.warning] + [s.value for s in at.subheader])


def skip(nama, alasan):
    print(f"[SKIP] {nama}  ({alasan})")


def dec1(x):
    return Decimal(repr(float(x))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def ganti(modul, nama, fungsi):
    """Mengganti fungsi query sementara (untuk uji 'tidak hardcode' dan ketahanan); mengembalikan fungsi asli."""
    asli = getattr(modul, nama)
    setattr(modul, nama, fungsi)
    return asli


def main():
    v = db.run_query("SELECT * FROM mart.v_country_year")
    mix = db.run_query("SELECT * FROM mart.v_generation_mix")
    cmp_ = db.run_query("SELECT * FROM mart.v_source_comparison")
    kode = SUMBER.read_text(encoding="utf-8")
    print(f"Data dasar: {len(v)} baris v_country_year, {len(mix)} v_generation_mix, {len(cmp_)} v_source_comparison\n== Halaman Kualitas")

    # ------------------------------------------------ 1. render
    try:
        compile(kode, str(SUMBER), "exec")
        ok_compile = True
    except SyntaxError:
        ok_compile = False
    check("K1: kode halaman Kualitas valid (dapat dikompilasi)", ok_compile)
    at = halaman()
    tanpa_error(at, "K1: halaman Kualitas dirender tanpa error")
    check("K1: judul 'Kualitas Data' dan lima tab",
          [t.value for t in at.title] == ["Kualitas Data"]
          and [t.label for t in at.tabs] == ["Cakupan", "Nilai kosong", "Ember vs Renewable",
                                             "Rata-rata sederhana vs tertimbang", "Konsistensi dan ETL"], str([t.label for t in at.tabs]))
    teks = teks_halaman(at)
    check("K1: tidak ada placeholder atau catatan pengembang ('dalam pengembangan', 'placeholder', 'Tahap 4')",
          not any(k in (teks + kode).lower() for k in ("dalam pengembangan", "placeholder", "tahap 4")) and "theme.placeholder" not in kode)

    # ------------------------------------------------ 2. query berjalan, hanya SELECT, hanya view mart
    fungsi = [queries.k_cover, queries.k_missing, queries.k_nocont, queries.k_src_cover, queries.k_src_diff, queries.k_mean,
              queries.k_recon, queries.k_recon_gen, queries.k_years]
    fungsi_tahun = [queries.k_primary, queries.k_status, queries.k_status_reason, queries.k_src_top, queries.k_src_scatter]
    hasil = [fn() for fn in fungsi] + [fn(2023) for fn in fungsi_tahun]
    check(f"K2: {len(hasil)} query Kualitas berjalan dan mengembalikan data", all(len(h) > 0 for h in hasil))
    k_sql = {n: getattr(queries, n) for n in dir(queries) if n.startswith("K_") and n.endswith("SQL")}
    check(f"K2: {len(k_sql)} query Kualitas hanya SELECT (tanpa INSERT/UPDATE/DELETE/CREATE/DROP/ALTER/TRUNCATE/GRANT)",
          len(k_sql) >= 14 and all(re.match(r"\s*(WITH|SELECT)\b", q, re.I) for q in k_sql.values())
          and not any(re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|GRANT)\b", q, re.I) for q in k_sql.values()))
    skema = {m.lower() for q in k_sql.values() for m in re.findall(r"\b(?:from|join)\s+(\w+)\.\w+", q, re.I)}
    check("K2: semua query membaca hanya schema mart (tidak menyentuh dw, stg, atau ops)", skema == {"mart"}, str(skema))

    # ------------------------------------------------ 3. cakupan per tahun dan indikator
    cov = queries.k_cover()
    ok_cov, n_baris = True, 0
    for th in TAHUN:
        d = v[v["year"] == th]
        for kd, _ind, _src, kol, ada in queries.K_INDICATORS:
            r = cov[(cov["year"] == th) & (cov["kode"] == kd)].iloc[0]
            ok_cov &= (int(r["negara_master"]) == len(d) and int(r["punya_baris"]) == int(d[ada].sum())
                       and int(r["tersedia"]) == int(d[kol].notna().sum())
                       and abs(float(r["coverage"]) - r1(100 * d[kol].notna().sum() / len(d), 1)) < 1e-9)
            n_baris += 1
        m = mix[mix["year"] == th]
        r = cov[(cov["year"] == th) & (cov["kode"] == queries.K_MIX_CODE)].iloc[0]
        ok_cov &= (int(r["negara_master"]) == len(d) and int(r["punya_baris"]) == m["iso3_code"].nunique()
                   and int(r["tersedia"]) == m[m["generation_twh"].notna()]["iso3_code"].nunique())
        n_baris += 1
    check(f"K3: coverage {n_baris} kombinasi tahun x indikator (master, punya baris, tersedia, %) = pandas", ok_cov and len(cov) == n_baris)
    d23 = v[v["year"] == 2023]
    r_ren = cov[(cov["year"] == 2023) & (cov["kode"] == "pangsa_listrik_ren")].iloc[0]
    check("K3: negara master (dari data) dibedakan dari negara yang punya nilai: master = negara unik, tersedia lebih kecil",
          int(r_ren["negara_master"]) == v["iso3_code"].nunique() and int(r_ren["tersedia"]) < int(r_ren["negara_master"]),
          f"{int(r_ren['tersedia'])} dari {int(r_ren['negara_master'])}")
    r_emb = cov[(cov["year"] == 2023) & (cov["kode"] == "pangsa_listrik_emb")].iloc[0]
    check("K3: 'punya baris di sumber' dibedakan dari 'nilai tersedia' (Ember 2023: ada baris tetapi pangsa kosong untuk sebagian negara)",
          int(r_emb["punya_baris"]) > int(r_emb["tersedia"]), f"{int(r_emb['punya_baris'])} vs {int(r_emb['tersedia'])}")
    tc = df_dengan(at, "Coverage (%)", "Punya baris di sumber")
    harap_tc = [(int(r.year), r.indikator, r.sumber, int(r.negara_master), int(r.punya_baris), int(r.tersedia), float(r.coverage)) for r in cov.itertuples()]
    check("K3: tabel cakupan di halaman = hasil query (35 baris: 5 tahun x 7 indikator, semua kolom)",
          tc is not None and len(tc) == len(harap_tc)
          and [(int(r[0]), r[1], r[2], int(r[3]), int(r[4]), int(r[5]), float(r[6])) for r in tc.itertuples(index=False)] == harap_tc)
    for th in TAHUN:
        a = halaman()
        if th != 2023:
            a.sidebar.selectbox(key="f_year").set_value(th).run()
        d = v[v["year"] == th]
        k = kartu(a)
        harap = {"Negara dalam master": (theme.fmt_num(len(d), 0), None),
                 "Pangsa listrik terbarukan (Renewable)": (f"{int(d['renewables_share_elec'].notna().sum())} dari {len(d)}", None),
                 "Intensitas emisi (Ember)": (f"{int(d['emissions_intensity_gco2e_kwh'].notna().sum())} dari {len(d)}", None),
                 "Energi primer (Renewable)": (f"{int(d['renewables_share_energy'].notna().sum())} dari {len(d)}", None)}
        fc = [f_ for f_ in figs(a) if f_["data"][0].get("orientation") == "h" and "Coverage" in json.dumps(f_["layout"], ensure_ascii=False)]
        cov_th = cov[cov["year"] == th]
        ok_fig = len(fc) == 1 and sorted(fc[0]["data"][0]["x"]) == sorted(float(x) for x in cov_th["coverage"])
        check(f"K3: kartu dan grafik cakupan {th} = pandas", not a.exception and all(k.get(l) == nl for l, nl in harap.items()) and ok_fig,
              str({l: k.get(l) for l in harap}))

    # ------------------------------------------------ 4. energi primer: cakupan terbatas, tanpa agregat global
    prim = queries.k_primary(2023)
    harap_p = d23.assign(benua=d23["continent"].fillna("Tidak diketahui")).groupby("benua").agg(
        master=("iso3_code", "count"), tersedia=("renewables_share_energy", "count"))
    check("K4: cakupan energi primer per benua (2023) = pandas, dan jumlahnya = cakupan indikator primer",
          dict(zip(prim["benua"], zip(prim["negara_master"], prim["tersedia"]))) == {k: (int(r.master), int(r.tersedia)) for k, r in harap_p.iterrows()}
          and int(prim["tersedia"].sum()) == int(d23["renewables_share_energy"].notna().sum()))
    tp = df_dengan(halaman(), "Punya pangsa energi primer")
    check("K4: tabel energi primer menunjukkan cakupan tidak merata antarbenua (coverage tertinggi dan terendah berbeda jauh)",
          tp is not None and tp["Coverage (%)"].max() - tp["Coverage (%)"].min() > 20, "" if tp is None else f"{tp['Coverage (%)'].min()}-{tp['Coverage (%)'].max()}")
    check("K4: tidak ada agregat global energi primer (tidak ada avg/sum/percentile atas renewables_share_energy di query maupun kode)",
          not any(re.search(r"(avg|sum|percentile\w*|_weighted)\s*\(\s*'?[^)]*renewables_share_energy", q, re.I) for q in k_sql.values())
          and "renewables_share_energy" not in kode)
    check("K4: keterangan menyatakan dashboard tidak membuat agregat global energi primer",
          any("tidak membuat agregat global energi primer" in c.value for c in at.caption))

    # ------------------------------------------------ 5. status kelengkapan
    st23 = queries.k_status(2023)
    ada_e = d23[d23["has_energy_fact"]]
    ada_m = d23[d23["has_emissions_fact"]]
    harap_st = {("Renewable (fakta energi)", s_): int(c) for s_, c in d23["energy_quality_status"].fillna("Tidak ada baris").value_counts().items()}
    harap_st.update({("Ember (fakta emisi)", s_): int(c) for s_, c in d23["emissions_quality_status"].fillna("Tidak ada baris").value_counts().items()})
    harap_st.update({("Ember (bauran per sumber)", s_): int(c) for s_, c in mix[mix["year"] == 2023]["quality_status"].value_counts().items()})
    check("K5: sebaran status kelengkapan 2023 (3 sumber) = pandas",
          {(r.sumber, r.status): int(r.jumlah) for r in st23.itertuples()} == harap_st)
    lengkap_ren = int((ada_e["renewables_share_energy"].notna() & ada_e["renewables_share_elec"].notna()).sum())
    lengkap_emb = int((ada_m["emissions_intensity_gco2e_kwh"].notna() & ada_m["ember_renewables_share_pct"].notna()).sum())
    check("K5: label 'Valid lengkap' = kedua kolom indikator terisi, 'Valid dengan indikator kosong' = salah satu kosong (kalimat D4 terbukti dari data)",
          harap_st[("Renewable (fakta energi)", "Valid lengkap")] == lengkap_ren and harap_st[("Ember (fakta emisi)", "Valid lengkap")] == lengkap_emb
          and harap_st[("Renewable (fakta energi)", "Valid dengan indikator kosong")] == len(ada_e) - lengkap_ren
          and harap_st[("Ember (fakta emisi)", "Valid dengan indikator kosong")] == len(ada_m) - lengkap_emb)
    sr = queries.k_status_reason(2023).set_index("sumber")
    ren_r, emb_r = sr.loc["Renewable (fakta energi)"], sr.loc["Ember (fakta emisi)"]
    check("K5: alasan status: kolom mana yang kosong (energi primer, listrik, keduanya) = pandas, dan jumlahnya = baris yang ada",
          int(ren_r["kolom1_kosong"]) == int((ada_e["renewables_share_energy"].isna() & ada_e["renewables_share_elec"].notna()).sum())
          and int(ren_r["kolom2_kosong"]) == int((ada_e["renewables_share_energy"].notna() & ada_e["renewables_share_elec"].isna()).sum())
          and int(ren_r["keduanya_kosong"]) == int((ada_e["renewables_share_energy"].isna() & ada_e["renewables_share_elec"].isna()).sum())
          and int(ren_r[["lengkap", "kolom1_kosong", "kolom2_kosong", "keduanya_kosong"]].sum()) == len(ada_e)
          and int(emb_r[["lengkap", "kolom1_kosong", "kolom2_kosong", "keduanya_kosong"]].sum()) == len(ada_m))
    check("K5: halaman menjelaskan bahwa status bukan penilaian seluruh baris",
          any("bukan penilaian mutu seluruh baris" in c.value for c in at.caption))
    ts = df_dengan(at, "Status", "Jumlah baris")
    check("K5: tabel status di halaman memuat semua baris status 2023 (sesuai query)", ts is not None and len(ts) == len(st23))

    # ------------------------------------------------ 6. nilai kosong dan alasannya
    miss = queries.k_missing()
    ref = {}
    for r in v.itertuples():
        if pd.isna(r.ember_renewables_share_pct) or pd.isna(r.emissions_intensity_gco2e_kwh):
            if not r.has_emissions_fact:
                al = "Tidak ada baris Ember"
            elif r.total_generation_twh == 0:
                al = "Pembangkitan 0 TWh"
            elif pd.isna(r.total_generation_twh):
                al = "nilai pembangkitan juga kosong"
            else:
                al = "walaupun pembangkitan terisi"
            ref.setdefault(("Ember", r.iso3_code, al), []).append(int(r.year))
        if pd.isna(r.renewables_share_elec):
            if not r.has_energy_fact:
                al = "Tidak ada baris Renewable"
            elif r.electricity_generation_twh == 0:
                al = "Pembangkitan 0 TWh"
            elif pd.isna(r.electricity_generation_twh):
                al = "nilai pembangkitan juga kosong"
            else:
                al = "walaupun pembangkitan terisi"
            ref.setdefault(("Renewable", r.iso3_code, al), []).append(int(r.year))
    got = {}
    for r in miss.itertuples():
        kunci = [al for al in ("Tidak ada baris Ember", "Tidak ada baris Renewable", "Pembangkitan 0 TWh", "nilai pembangkitan juga kosong",
                               "walaupun pembangkitan terisi") if al in r.alasan][0]
        got[(r.kelompok.split(" ")[0], r.iso3_code, kunci)] = [int(x) for x in r.tahun.split(", ")]
    check(f"K6: daftar nilai kosong ({len(miss)} baris negara x alasan) = replika pandas (negara, kelompok, alasan, tahun)",
          got == {k: sorted(x) for k, x in ref.items()}, f"{len(got)} vs {len(ref)}")
    n_null_ember = int((v["ember_renewables_share_pct"].isna() | v["emissions_intensity_gco2e_kwh"].isna()).sum())
    check("K6: setiap negara-tahun kosong di mart tercakup tepat sekali di daftar (tidak ada yang hilang atau dobel)",
          int(miss[miss["kelompok"].str.startswith("Ember")]["jumlah_tahun"].sum()) == n_null_ember
          and int(miss[miss["kelompok"].str.startswith("Renewable")]["jumlah_tahun"].sum()) == int(v["renewables_share_elec"].isna().sum()))
    lso_e = d23[d23["iso3_code"] == "LSO"].iloc[0]
    check("K6: Lesotho 2023: pembangkitan 0, pangsa dan intensitas tetap NULL (bukan 0, tidak diimputasi)",
          lso_e["total_generation_twh"] == 0 and pd.isna(lso_e["ember_renewables_share_pct"]) and pd.isna(lso_e["emissions_intensity_gco2e_kwh"])
          and pd.isna(lso_e["renewables_share_elec"]))
    lso = miss[miss["iso3_code"] == "LSO"]
    check("K6: alasan Lesotho (Ember dan Renewable, 2023) = pembangkitan 0 sehingga pangsa tidak terdefinisi",
          len(lso) == 2 and all("Pembangkitan 0 TWh" in a for a in lso["alasan"]) and all(t == "2023" for t in lso["tahun"]))
    ukr = miss[miss["iso3_code"] == "UKR"]
    ukr_e = d23[d23["iso3_code"] == "UKR"].iloc[0]
    check("K6: Ukraina 2023: tidak ada baris Ember; Renewable: baris ada tetapi pembangkitan dan pangsa listrik kosong; pangsa energi primer tetap ada (tidak dihapus)",
          any("Tidak ada baris Ember" in a for a in ukr["alasan"]) and any("nilai pembangkitan juga kosong" in a for a in ukr["alasan"])
          and pd.notna(ukr_e["renewables_share_energy"]) and pd.isna(ukr_e["renewables_share_elec"]))
    notes = df_dengan(at, "Alasan (dari data)")
    tabel_hal = pd.concat(semua_df(at, "Alasan (dari data)"))
    check("K6: tabel nilai kosong di halaman = hasil query (jumlah baris, negara, alasan)",
          len(tabel_hal) == len(miss) and sorted(tabel_hal["Negara"]) == sorted(miss["country_name"])
          and sorted(tabel_hal["Alasan (dari data)"]) == sorted(miss["alasan"]))
    nc = queries.k_nocont().iloc[0]
    n_nobenua = d23[d23["continent"].isna()]["iso3_code"].nunique()
    check("K6: negara tanpa atribut benua dan tanpa baris Ember pada semua tahun = pandas",
          int(nc["negara_tanpa_benua"]) == n_nobenua and int(nc["tanpa_ember_semua_tahun"]) == int(
              v[v["continent"].isna()].groupby("iso3_code")["has_emissions_fact"].apply(lambda s_: not s_.any()).sum()))
    kata_etl = ["kesalahan etl", "error etl", "gagal etl", "bug etl", "etl gagal", "etl salah"]
    check("K6: halaman tidak menyebut kekosongan sebagai error ETL; pemeriksaan asal (sumber vs ETL) dirujuk ke sql/100 dan test ini",
          not any(k in (teks + kode).lower() for k in kata_etl) and "sql/100_validate_quality.sql" in kode)
    check("K6: keterangan menyatakan alasan hanya yang dapat dibuktikan dan penyebab di sumber tidak ditebak",
          any("tidak diketahui dan tidak ditebak" in c.value for c in at.caption))

    # ---- penelusuran asal: berkas mentah data/raw (sumber vs ETL)
    if RAW_EMBER.exists() and RAW_REN.exists():
        em = pd.read_csv(RAW_EMBER, low_memory=False)
        em = em[em["Electricity source"] == "Total generation"]
        em["Year"] = em["Year"].astype(int)
        em_key = set(zip(em["ISO 3 code"], em["Year"]))
        rn = pd.read_csv(RAW_REN)
        rn_idx = rn.set_index(["iso_code", "year"])
        tanpa = [(r.iso3_code, int(r.year)) for r in v.itertuples() if not r.has_emissions_fact]
        check(f"K6: asal kosong (Ember): {len(tanpa)} negara-tahun 'tanpa baris Ember' juga TIDAK ADA di berkas mentah Ember (hilangnya di sumber, bukan oleh ETL)",
              len(tanpa) > 0 and not any(k_ in em_key for k_ in tanpa), f"{len(tanpa)} negara-tahun")
        pembangkitan_0 = [(r.iso3_code, int(r.year)) for r in v.itertuples() if r.has_emissions_fact and r.total_generation_twh == 0]
        raw0 = em.set_index(["ISO 3 code", "Year"])
        check(f"K6: Lesotho (dan sejenisnya, {len(pembangkitan_0)} negara-tahun): berkas mentah Ember mencatat Total generation 0 dan pangsa kosong",
              all(k_ in raw0.index and bool(raw0.loc[[k_], "Generation (TWh)"].astype(float).eq(0).all()) for k_ in pembangkitan_0))
        tanpa_ren = [(r.iso3_code, int(r.year)) for r in v.itertuples() if not r.has_energy_fact]
        check(f"K6: asal kosong (Renewable): {len(tanpa_ren)} negara-tahun 'tanpa baris Renewable' tidak ada di berkas mentah Renewable",
              len(tanpa_ren) > 0 and not any(k_ in rn_idx.index for k_ in tanpa_ren))
        ren_kosong = [(r.iso3_code, int(r.year)) for r in v.itertuples()
                      if r.has_energy_fact and pd.isna(r.renewables_share_elec)]
        check(f"K6: {len(ren_kosong)} nilai pangsa listrik Renewable yang kosong di mart juga kosong di berkas mentah (tidak dihapus oleh ETL)",
              len(ren_kosong) > 0 and all(bool(rn_idx.loc[[k_], "renewables_share_elec"].isna().all()) for k_ in ren_kosong if k_ in rn_idx.index))
    else:
        skip("K6: penelusuran asal kosong ke berkas mentah", "data/raw tidak ditemukan; lihat sql/100 blok Q7 untuk staging")

    # ------------------------------------------------ 7. Ember vs Renewable
    sc = queries.k_src_cover().set_index("year")
    ok_sc = True
    for th in TAHUN:
        d = v[v["year"] == th]
        r = sc.loc[th]
        ok_sc &= (int(r["kedua_sumber"]) == int((d["has_energy_fact"] & d["has_emissions_fact"]).sum())
                  and int(r["hanya_renewable"]) == int((d["has_energy_fact"] & ~d["has_emissions_fact"]).sum())
                  and int(r["hanya_ember"]) == int((~d["has_energy_fact"] & d["has_emissions_fact"]).sum())
                  and int(r["tanpa_keduanya"]) == int((~d["has_energy_fact"] & ~d["has_emissions_fact"]).sum())
                  and int(r["kedua_sumber"] + r["hanya_renewable"] + r["hanya_ember"] + r["tanpa_keduanya"]) == len(d))
    check("K7: cakupan negara menurut sumber (kedua, hanya Renewable, hanya Ember, tanpa keduanya) per tahun = pandas dan menjumlah ke master", ok_sc)
    sd = queries.k_src_diff().set_index("year")
    ok_sd, ref_d = True, {}
    for th in TAHUN:
        d = v[(v["year"] == th) & v["has_energy_fact"] & v["has_emissions_fact"]]
        gen_pct = [round(100 * (e / r_ - 1), 2) for e, r_ in zip(d["total_generation_twh"], d["electricity_generation_twh"])
                   if pd.notna(e) and pd.notna(r_) and r_ != 0]
        both = d[d["renewables_share_elec"].notna() & d["ember_renewables_share_pct"].notna()]
        besar = [abs(dec1(a) - dec1(b)) > queries.K_SHARE_PTS for a, b in zip(both["ember_renewables_share_pct"], both["renewables_share_elec"])]
        ref_d[th] = (len(d), len(gen_pct), sum(abs(x) > queries.K_GEN_PCT for x in gen_pct), len(both), sum(besar))
        r = sd.loc[th]
        ok_sd &= (int(r["n_pasang"]), int(r["n_gen_dibanding"]), int(r["n_gen_besar"]), int(r["n_pangsa_dibanding"]), int(r["n_pangsa_besar"])) == ref_d[th]
    check("K7: jumlah negara berselisih besar (pembangkitan > 5%, pangsa > 2 poin) per tahun = replika pandas dari v_country_year", ok_sd, str(ref_d))
    check("K7: selisih pembangkitan besar bertambah dari awal ke akhir periode (hasil data: jumlahnya berbeda antartahun)",
          ref_d[2019][2] != ref_d[2023][2], f"{ref_d[2019][2]} pada 2019 dan {ref_d[2023][2]} pada 2023")
    # konsistensi v_source_comparison dengan v_country_year
    j = cmp_.merge(v[["iso3_code", "year", "ember_renewables_share_pct", "renewables_share_elec", "total_generation_twh", "electricity_generation_twh"]],
                   on=["iso3_code", "year"], suffixes=("", "_v"))
    check("K7: v_source_comparison konsisten dengan v_country_year (nilai pangsa dan pembangkitan kedua sumber sama untuk setiap negara-tahun)",
          len(j) == len(cmp_) and np.allclose(j["ember_renewables_share_pct"].fillna(-1), j["ember_renewables_share_pct_v"].fillna(-1))
          and np.allclose(j["renewable_renewables_share_pct"].fillna(-1), j["renewables_share_elec"].fillna(-1))
          and np.allclose(j["ember_generation_twh"].fillna(-1), j["total_generation_twh"].fillna(-1))
          and np.allclose(j["renewable_generation_twh"].fillna(-1), j["electricity_generation_twh"].fillna(-1)))
    a = halaman()
    tab_d = df_dengan(a, "Negara di kedua sumber")
    check("K7: tabel 'seberapa sering kedua sumber berbeda' di halaman = pandas (semua tahun)",
          tab_d is not None and [tuple(int(x) for x in (r[0], r[1], r[2], r[3])) for r in tab_d.itertuples(index=False)] ==
          [(th, ref_d[th][0], ref_d[th][2], ref_d[th][4]) for th in TAHUN])
    top = queries.k_src_top(2023)
    d = v[(v["year"] == 2023) & v["renewables_share_elec"].notna() & v["ember_renewables_share_pct"].notna()]
    urut = sorted(((abs(dec1(r.ember_renewables_share_pct) - dec1(r.renewables_share_elec)), r.country_name,
                    float(dec1(r.ember_renewables_share_pct) - dec1(r.renewables_share_elec))) for r in d.itertuples()), key=lambda t: (-t[0], t[1]))[:queries.K_TOP_N]
    tt = df_dengan(a, "Selisih (poin, Ember dikurangi Renewable)")
    check(f"K7: {queries.K_TOP_N} negara selisih pangsa terbesar (urutan dan selisih dari angka tampil) = pandas",
          tt is not None and list(tt["Negara"]) == [u[1] for u in urut] and np.allclose(tt["Selisih (poin, Ember dikurangi Renewable)"], [u[2] for u in urut])
          and list(top["country_name"]) == [u[1] for u in urut], str(list(tt["Negara"])[:4]) if tt is not None else "")
    check("K7: selisih = pangsa Ember dikurangi pangsa Renewable dari angka yang tampil",
          np.allclose(tt["Selisih (poin, Ember dikurangi Renewable)"], tt["Pangsa Ember (%)"] - tt["Pangsa Renewable (%)"], atol=1e-9))
    pas = [f_ for f_ in figs(a) if "Kedua sumber sama (y = x)" in json.dumps(f_["data"], ensure_ascii=False)]
    n_pts = sum(len(t["x"]) for f_ in pas for t in f_["data"] if t["name"] not in ("Kedua sumber sama (y = x)",))
    check("K7: sebaran Ember vs Renewable memuat semua negara yang kedua pangsanya ada (2023) dan garis y = x",
          len(pas) == 1 and n_pts == len(d), f"{n_pts} titik")
    check("K7: halaman menyatakan kedua sumber dapat berbeda, tidak menyebut salah satu lebih benar, dan penyebab tidak dipastikan",
          any("dapat memberi nilai berbeda" in c.value and "tidak menyatakan salah satunya lebih benar" in c.value for c in a.caption)
          and not any(k_ in (teks_halaman(a) + kode).lower() for k_ in ("lebih akurat", "paling benar", "sumber terbaik", "lebih andal", "paling akurat")))

    # ------------------------------------------------ 8. rata-rata sederhana vs tertimbang
    mean = queries.k_mean().set_index("year")
    ok_m, ref_m = True, {}
    for th in TAHUN:
        d = v[v["year"] == th]
        sed = r1(d["renewables_share_elec"].mean(), 1)
        tim = wavg(d, "renewables_share_elec", "electricity_generation_twh")
        tim_e = wavg(d, "renewables_share_elec", "total_generation_twh")
        is_ = r1(d["emissions_intensity_gco2e_kwh"].mean(), 0)
        it = wavg(d, "emissions_intensity_gco2e_kwh", "total_generation_twh")
        ref_m[th] = (sed, r1(tim, 1), r1(tim, 2), r1(tim_e, 2), is_, r1(it, 0))
        r = mean.loc[th]
        ok_m &= (abs(r["pangsa_sederhana"] - sed) < 1e-9 and abs(r["pangsa_tertimbang"] - r1(tim, 1)) < 1e-9
                 and abs(r["pangsa_tertimbang_2"] - r1(tim, 2)) < 1e-9 and abs(r["pangsa_bobot_ember_2"] - r1(tim_e, 2)) < 1e-9
                 and abs(r["intensitas_sederhana"] - is_) < 1e-9 and abs(r["intensitas_tertimbang"] - r1(it, 0)) < 1e-9
                 and int(r["n_pangsa"]) == int(d["renewables_share_elec"].notna().sum())
                 and int(r["n_intensitas"]) == int(d["emissions_intensity_gco2e_kwh"].notna().sum()))
    check("K8: rata-rata sederhana, tertimbang, bobot alternatif (pangsa) dan intensitas per tahun = pandas independen", ok_m, str(ref_m[2023]))
    kpi = queries.kpi_by_year(tuple(sorted(v["continent"].fillna("Tidak diketahui").unique())), tuple(sorted(v["group_label"].unique()))).set_index("year")
    check("K8: pangsa tertimbang dan intensitas tertimbang di sini = KPI Ringkasan/A/B (kpi_by_year) untuk semua tahun",
          all(abs(r1(kpi.loc[th, "terbarukan"], 1) - mean.loc[th, "pangsa_tertimbang"]) < 1e-9 and abs(r1(kpi.loc[th, "intensitas"], 0) - mean.loc[th, "intensitas_tertimbang"]) < 1e-9
              for th in TAHUN))
    check("K8: rata-rata sederhana berbeda jelas dari tertimbang (> 1 poin pangsa dan > 10 gCO2e/kWh pada 2019 dan 2023)",
          all(abs(ref_m[th][0] - ref_m[th][1]) > 1 and abs(ref_m[th][4] - ref_m[th][5]) > 10 for th in (2019, 2023)),
          f"2019: {ref_m[2019][0]} vs {ref_m[2019][1]}; 2023: {ref_m[2023][0]} vs {ref_m[2023][1]}")
    check("K8: pilihan bobot (Renewable vs Ember) memengaruhi pangsa global kurang dari 0,1 poin pada semua tahun",
          all(abs(ref_m[th][2] - ref_m[th][3]) < 0.1 for th in TAHUN), str([round(ref_m[th][2] - ref_m[th][3], 2) for th in TAHUN]))
    for th in (2019, 2023):
        a = halaman()
        if th != 2023:
            a.sidebar.selectbox(key="f_year").set_value(th).run()
        k = kartu(a)
        sed, tim = ref_m[th][0], ref_m[th][1]
        ok_k = (k["Rata-rata sederhana antarnegara"][0] == theme.fmt_pct(sed) and k["Tertimbang pembangkitan"][0] == theme.fmt_pct(tim)
                and k["Selisih (sederhana dikurangi tertimbang)"][0] == theme.fmt_delta(round(sed - tim, 1), 1, " poin"))
        ok_t = any(f"pada {th} selisihnya {theme.fmt_delta(round(sed - tim, 1), 1, ' poin')}" in c.value for c in a.caption)
        check(f"K8: kartu dan kalimat interpretasi {th} dihitung dari data (sederhana {theme.fmt_pct(sed)}, tertimbang {theme.fmt_pct(tim)})",
              not a.exception and ok_k and ok_t, str({x: k[x] for x in list(k)[4:7]}))
    a = halaman()
    tm = df_dengan(a, "Rata-rata sederhana (%)", "Tertimbang pembangkitan (%)")
    ti = df_dengan(a, "Rata-rata sederhana (gCO₂e/kWh)")
    tb = df_dengan(a, "Bobot pembangkitan Renewable (%)")
    check("K8: tabel pangsa, intensitas, dan dampak bobot di halaman = pandas (selisih dari angka tampil)",
          tm is not None and ti is not None and tb is not None
          and np.allclose(tm["Rata-rata sederhana (%)"], [ref_m[t][0] for t in TAHUN]) and np.allclose(tm["Tertimbang pembangkitan (%)"], [ref_m[t][1] for t in TAHUN])
          and np.allclose(tm["Selisih (poin)"], [round(ref_m[t][0] - ref_m[t][1], 1) for t in TAHUN])
          and np.allclose(ti["Rata-rata sederhana (gCO₂e/kWh)"], [ref_m[t][4] for t in TAHUN]) and np.allclose(ti["Tertimbang pembangkitan (gCO₂e/kWh)"], [ref_m[t][5] for t in TAHUN])
          and np.allclose(tb["Selisih (poin)"], [round(ref_m[t][2] - ref_m[t][3], 2) for t in TAHUN]))
    ft = [f_ for f_ in figs(a) if any(t_.get("name") == "Rata-rata sederhana" for t_ in f_["data"])]
    check("K8: grafik garis (sederhana vs tertimbang) memuat 5 tahun dan nilai = pandas",
          len(ft) == 1 and np.allclose(ft[0]["data"][0]["y"], [ref_m[t][0] for t in TAHUN]) and np.allclose(ft[0]["data"][1]["y"], [ref_m[t][1] for t in TAHUN]))

    # ------------------------------------------------ 9. konsistensi antar-view mart
    rec = queries.k_recon().set_index("year")
    ok_r = True
    for th in TAHUN:
        d = v[v["year"] == th]
        r = rec.loc[th]
        ok_r &= (int(r["n_cy"]) == len(d) and int(r["n_cy_iso"]) == d["iso3_code"].nunique() and int(r["n_energy"]) == int(d["has_energy_fact"].sum())
                 and int(r["n_ember"]) == int(d["has_emissions_fact"].sum()) and int(r["n_both"]) == int((d["has_energy_fact"] & d["has_emissions_fact"]).sum())
                 and int(r["n_cmp"]) == int((cmp_["year"] == th).sum()) and int(r["baris_mix"]) == int((mix["year"] == th).sum())
                 and int(r["negara_mix"]) == mix[mix["year"] == th]["iso3_code"].nunique())
    check("K9: angka konsistensi per tahun (baris, negara, penanda sumber, perbandingan, bauran) = pandas", ok_r)
    gen = queries.k_recon_gen().set_index("year")
    jml = mix.groupby(["iso3_code", "year"])["generation_twh"].sum().rename("s").reset_index().merge(
        v[["iso3_code", "year", "total_generation_twh"]], on=["iso3_code", "year"])
    jml["sel"] = (jml["s"] - jml["total_generation_twh"]).abs()
    check("K9: selisih maksimum jumlah semua sumber vs total pembangkitan Ember per tahun = pandas dan di bawah toleransi (0,05 TWh, keputusan desain)",
          all(abs(gen.loc[th, "selisih_maks"] - float(jml[jml["year"] == th]["sel"].max())) < 1e-9 for th in TAHUN)
          and float(gen["selisih_maks"].max()) <= queries.K_TOL_TWH)
    a = halaman()
    tk = df_dengan(a, "Pemeriksaan", "Status")
    k = kartu(a)
    check("K9: lima pemeriksaan konsistensi bernilai OK dan kartu 'Pemeriksaan konsistensi lulus' = 5 dari 5",
          tk is not None and len(tk) == 5 and list(tk["Status"]) == ["OK"] * 5 and k["Pemeriksaan konsistensi lulus"][0] == "5 dari 5")
    # status BEDA harus muncul bila data tidak konsisten (hasil query diubah sementara)
    asli = ganti(queries, "k_recon", lambda: rec.reset_index().assign(n_cmp=lambda x: x["n_cmp"] + 1))
    try:
        b = halaman()
        tb2 = df_dengan(b, "Pemeriksaan", "Status")
        bedanya = [] if tb2 is None else [p for p, s_ in zip(tb2["Pemeriksaan"], tb2["Status"]) if s_ == "BEDA"]
        check("K9: bila data tidak konsisten (jumlah baris perbandingan diubah +1), pemeriksaan terkait menjadi BEDA dan kartu turun menjadi 4 dari 5",
              not b.exception and len(bedanya) == 1 and "v_source_comparison" in bedanya[0] and kartu(b)["Pemeriksaan konsistensi lulus"][0] == "4 dari 5", str(bedanya))
    finally:
        queries.k_recon = asli
    asli = ganti(queries, "k_recon_gen", lambda: gen.reset_index().assign(selisih_maks=0.5))
    try:
        b = halaman()
        tb3 = df_dengan(b, "Pemeriksaan", "Status")
        check("K9: selisih penjumlahan bauran 0,5 TWh (> toleransi) menjadi BEDA",
              not b.exception and tb3 is not None and list(tb3["Status"]).count("BEDA") == 1)
    finally:
        queries.k_recon_gen = asli
    check("K9: halaman menyatakan rekonsiliasi DW -> Mart dijalankan di sql/100 (butuh akses dw) dan tidak membuat v_control_totals",
          any("sql/100_validate_quality.sql" in c.value and "akses ke schema dw" in c.value for c in a.caption)
          and "v_control_totals" not in kode and not any("v_control_totals" in q for q in k_sql.values()))

    # ------------------------------------------------ 10. ETL
    etl = db.run_query("SELECT run_id, finished_at, rows_loaded_dw FROM mart.v_etl_status")
    a = halaman()
    k = kartu(a)
    r = etl.iloc[0]
    waktu = r["finished_at"].to_pydatetime().astimezone().strftime("%d-%m-%Y %H:%M")
    check("K10: informasi ETL (run, waktu selesai, baris dimuat) = mart.v_etl_status; tidak ada timestamp buatan",
          k["Run ETL terakhir yang sukses"][0] == f"#{int(r['run_id'])}" and k["Selesai (waktu lokal komputer)"][0] == waktu
          and k["Baris dimuat ke DW"][0] == theme.fmt_num(r["rows_loaded_dw"], 0), str({x: k[x] for x in list(k)[-3:]}))
    asli = ganti(queries, "etl_status", lambda: pd.DataFrame(columns=["run_id", "started_at", "finished_at", "status", "rows_loaded_dw"]))
    try:
        b = halaman()
        check("K10: bila tidak ada run ETL: pesan 'Status ETL belum tersedia' (tanpa error, tanpa timestamp karangan)",
              not b.exception and any("Status ETL belum tersedia" in i.value for i in b.info) and "Run ETL terakhir yang sukses" not in kartu(b))
    finally:
        queries.etl_status = asli
    yrs = queries.k_years().iloc[0]
    check("K10: rentang tahun data = pandas", (int(yrs["tahun_awal"]), int(yrs["tahun_akhir"]), int(yrs["jumlah_tahun"])) == (int(v["year"].min()), int(v["year"].max()), v["year"].nunique()))

    # ------------------------------------------------ 11. tidak ada angka hardcode yang menggantikan hasil query
    nilai_acuan = ["221", "210", "207", "209", "208", "79", "36,7", "30,4", "26,1", "486", "433", "0,002", "Lesotho", "Ukraine", "Ukraina",
                   "Thailand", "Indonesia", "Pakistan", "Kosovo"]
    check("K11: kode halaman tidak memuat nilai data yang ditulis manual (jumlah negara, persentase, intensitas, nama negara)",
          not [x for x in nilai_acuan if x in kode] and not re.search(r"\b\d+,\d+\b", kode), str([x for x in nilai_acuan if x in kode]))
    asli = ganti(queries, "k_cover", lambda: cov.assign(tersedia=lambda x: x["tersedia"] + 1, negara_master=lambda x: x["negara_master"] + 5))
    try:
        b = halaman()
        kb = kartu(b)
        e0 = int(cov[(cov["year"] == 2023) & (cov["kode"] == "pangsa_listrik_ren")]["tersedia"].iloc[0])
        m0 = int(cov[(cov["year"] == 2023) & (cov["kode"] == "pangsa_listrik_ren")]["negara_master"].iloc[0])
        check("K11: kartu cakupan ikut berubah ketika hasil query diubah (angka berasal dari query, bukan teks tetap)",
              not b.exception and kb["Pangsa listrik terbarukan (Renewable)"][0] == f"{e0 + 1} dari {m0 + 5}" and kb["Negara dalam master"][0] == theme.fmt_num(m0 + 5, 0))
    finally:
        queries.k_cover = asli
    asli = ganti(queries, "k_mean", lambda: queries.run_query(queries.K_MEAN_SQL).assign(pangsa_sederhana=lambda x: x["pangsa_sederhana"] + 1.0))
    try:
        b = halaman()
        kb = kartu(b)
        check("K11: rata-rata sederhana dan kalimat interpretasi ikut berubah ketika hasil query diubah (+1,0 poin)",
              not b.exception and kb["Rata-rata sederhana antarnegara"][0] == theme.fmt_pct(ref_m[2023][0] + 1.0)
              and any(f"pada 2023 selisihnya {theme.fmt_delta(round(ref_m[2023][0] + 1.0 - ref_m[2023][1], 1), 1, ' poin')}" in c.value for c in b.caption))
    finally:
        queries.k_mean = asli
    asli = ganti(queries, "k_missing", lambda: queries.run_query(queries.K_MISSING_SQL).iloc[0:0])
    try:
        b = halaman()
        check("K11: tanpa data nilai kosong, halaman menampilkan pesan (tidak ada daftar karangan) dan tidak error",
              not b.exception and any("Tidak ada negara dengan nilai kosong" in i.value for i in b.info))
    finally:
        queries.k_missing = asli

    # ------------------------------------------------ 12. filter dan teks
    a = halaman()
    a.sidebar.multiselect(key="f_continents").set_value(["Asia"]).run()
    check("K12: halaman memakai seluruh data: filter benua tidak mengubah kartu cakupan (dan hal ini dijelaskan di keterangan)",
          not a.exception and kartu(a)["Negara dalam master"][0] == theme.fmt_num(len(d23), 0)
          and kartu(a)["Pangsa listrik terbarukan (Renewable)"][0] == f"{int(d23['renewables_share_elec'].notna().sum())} dari {len(d23)}"
          and any("tidak dipengaruhi filter benua dan kelompok negara" in c.value for c in a.caption))
    a = halaman()
    teks = teks_halaman(a)
    kausal = ["menyebabkan", "akibat dari", "disebabkan", "karena kebijakan", "berkat ", "berhasil menurunkan", "gagal menurunkan", "mengakibatkan", "membuktikan"]
    check("K12: teks dan kode halaman tidak memuat klaim sebab-akibat", not any(k_ in (teks + " " + kode).lower() for k_ in kausal))
    check("K12: ambang yang dipakai diberi label keputusan desain (bukan standar ilmiah)",
          any("keputusan desain, bukan standar ilmiah" in c.value for c in a.caption))
    ek = [e_ for e_ in a.expander]
    check("K12: ada penjelasan 'Definisi KPI dan alasan pembobotan' dan 'Sumber data dan query'",
          {e_.label for e_ in ek} >= {"Definisi KPI dan alasan pembobotan", "Sumber data dan query"})
    check("K12: tombol unduh CSV (cakupan dan nilai kosong) tersedia", len(a.get("download_button")) >= 2)

    # ------------------------------------------------ 13. regresi halaman lain
    def kartu_hal(h):
        a_ = S.baru()
        a_.switch_page(f"halaman/{h}.py").run()
        return a_, kartu(a_)
    a_, ka = kartu_hal("a_terbarukan")
    check("K13: halaman A tidak rusak (30,4% +4,3 poin / 26,6% / 65 negara / 210 dari 221)",
          not a_.exception and ka["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin") and ka["Median antarnegara"][0] == "26,6%"
          and ka["Negara berpangsa 50% atau lebih"][0] == "65 negara" and ka["Cakupan negara"][0] == "210 dari 221", str(ka))
    b_, kb = kartu_hal("b_fosil")
    check("K13: halaman B tidak rusak (60,7% -3,0 / 30,4% +4,3 / 8,9% -1,3 / 210 dari 221)",
          not b_.exception and kb["Pangsa listrik fosil"] == ("60,7%", "-3,0 poin") and kb["Pangsa listrik terbarukan"] == ("30,4%", "+4,3 poin")
          and kb["Nuklir dan lainnya (sisa)"] == ("8,9%", "-1,3 poin") and kb["Negara dalam perhitungan"][0] == "210 dari 221", str(kb))
    c_, kc = kartu_hal("c_bauran")
    check("K13: halaman C tidak rusak (29.683 TWh +2.782 / fosil 61,0% -2,8 / nuklir 8,9% -1,3 / terbarukan 30,1% +4,1)",
          not c_.exception and kc["Total pembangkitan"] == ("29.683 TWh", "+2.782 TWh") and kc["Pangsa fosil"] == ("61,0%", "-2,8 poin")
          and kc["Pangsa nuklir"] == ("8,9%", "-1,3 poin") and kc["Pangsa terbarukan"] == ("30,1%", "+4,1 poin"), str(kc))
    d_, kd = kartu_hal("d_pangsa_intensitas")
    check("K13: halaman D tidak rusak (Pearson -0,88 / Spearman -0,90 / lereng -6,6 / 207 dari 208)",
          not d_.exception and kd["Korelasi Pearson (r)"][0] == "-0,88" and kd["Korelasi Spearman"][0] == "-0,90"
          and kd["Lereng garis regresi"][0] == "-6,6" and kd["Negara dalam analisis"][0] == "207 dari 208", str(kd))
    r_, kr = kartu_hal("ringkasan")
    check("K13: Ringkasan tidak rusak (30,4% / 60,7% / 486 / 210 dari 221)",
          not r_.exception and kr["Pangsa listrik terbarukan"][0] == "30,4%" and kr["Pangsa listrik fosil"][0] == "60,7%"
          and kr["Intensitas emisi (gCO₂e/kWh)"][0] == "486" and kr["Cakupan negara"][0] == "210 dari 221", str(kr))

    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN HALAMAN KUALITAS: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
