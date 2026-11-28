"""Halaman Kualitas Data (lapisan transparansi kualitas data).
Pertanyaan bisnis: seberapa lengkap data yang ditampilkan dashboard, di mana nilai kosongnya, dan seberapa jauh dua
sumber data (Ember dan Renewable) serta dua cara merata-ratakan (sederhana dan tertimbang) memberi hasil yang berbeda?
Sumber: HANYA view mart (akun dashboard tidak punya akses ke dw/stg). Halaman ini memakai seluruh data; hanya tahun
terpilih yang dipakai pada bagian per tahun. Tidak ada nilai yang diisi (NULL tetap kosong) dan tidak ada angka manual."""
import pandas as pd
import streamlit as st

import charts
import components
import db
import queries
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
GEN_PCT, SHARE_PTS, TOL = queries.K_GEN_PCT, queries.K_SHARE_PTS, queries.K_TOL_TWH


def n_(x) -> str:
    return theme.fmt_num(x, 0)


chips = components.active_filter_chips(
    year, f["continents"], f["continents"], f["groups"], f["groups"], ignore_region=True
)
components.hero_banner(
    "Kualitas Data",
    "Transparansi kelengkapan data, nilai kosong, perbandingan dua sumber, metode pembobotan, dan status ETL.",
    chips=chips,
    variant="quality",
)
st.title("Kualitas Data")
st.caption("Seberapa lengkap data yang dipakai dashboard, di mana nilainya kosong, dan bagaimana sumber serta cara "
           "menghitung memengaruhi angka. Halaman ini menampilkan seluruh data dan tidak dipengaruhi filter benua dan "
           "kelompok negara; hanya tahun terpilih yang dipakai pada bagian per tahun. Nilai kosong tidak pernah diisi "
           "dengan perkiraan.")

cover = db.safe(queries.k_cover)
if cover.empty or year not in set(cover["year"]):
    components.empty_state("Data kualitas belum tersedia. Pastikan ETL sudah dijalankan dan view mart sudah dibuat.")
    st.stop()
cy = cover[cover["year"] == year].set_index("kode")
master = int(cy["negara_master"].iloc[0])

# Data ringkas untuk 3 kartu status visual di bagian atas (menjawab R09)
rec = db.safe(queries.k_recon).set_index("year")
gen = db.safe(queries.k_recon_gen).set_index("year")
etl = db.safe(queries.etl_status)
cek_awal = [
    ("Tidak ada negara-tahun ganda pada v_country_year (baris = negara unik)", (rec["n_cy"] == rec["n_cy_iso"]).tolist()),
    ("Jumlah negara master sama di semua tahun", [rec["n_cy"].nunique() == 1] * len(rec)),
    ("Baris v_source_comparison = negara yang ada di kedua sumber", (rec["n_cmp"] == rec["n_both"]).tolist()),
    ("Negara pada bauran pembangkitan = negara yang punya baris Ember", (rec["negara_mix"] == rec["n_ember"]).tolist()),
    (f"Jumlah semua sumber = total pembangkitan Ember per negara (selisih maksimum {theme.fmt_num(TOL, 2)} TWh)",
     [bool(gen.loc[y, "selisih_maks"] <= TOL) if (y in gen.index and pd.notna(gen.loc[y, "selisih_maks"])) else False for y in rec.index]),
]
n_ok_awal = sum(1 for _, hasil in cek_awal if all(hasil))
cov_ren = float(cy.loc["pangsa_listrik_ren", "coverage"]) if "pangsa_listrik_ren" in cy.index else None
etl_val = f"Run #{int(etl.iloc[0]['run_id'])}" if not etl.empty else "Belum tersedia"
etl_note = (etl.iloc[0]["finished_at"].to_pydatetime().astimezone().strftime("%d-%m-%Y %H:%M")
            if not etl.empty else "Jalankan proses ETL untuk memuat data.")

components.status_cards([
    {
        "eyebrow": f"Kelengkapan indikator utama ({year})",
        "value": theme.fmt_pct(cov_ren) if cov_ren is not None else "tidak ada data",
        "note": "Cakupan pangsa listrik terbarukan (Renewable) terhadap seluruh negara master.",
    },
    {
        "eyebrow": "Konsistensi antar-view mart",
        "value": f"{n_ok_awal} dari {len(cek_awal)} lulus",
        "note": "Memeriksa keunikan baris, kesesuaian cakupan sumber, dan penjumlahan bauran.",
        "warn": n_ok_awal < len(cek_awal),
    },
    {
        "eyebrow": "Sinkronisasi ETL terakhir",
        "value": etl_val,
        "note": f"Selesai: {etl_note}",
        "warn": etl.empty,
    },
])

components.glossary_box(
    "Kamus Istilah Singkat (Panduan Pembaca)",
    [
        (
            "Negara Master",
            "Daftar seluruh negara yang tercatat pada data warehouse per tahun, termasuk negara yang sebagian indikatornya kosong di salah satu sumber.",
        ),
        (
            "Rata-rata Tertimbang",
            "Perhitungan yang memberi bobot sesuai besar pembangkitan listrik tiap negara, sehingga mencerminkan total listrik gabungan, bukan rata-rata per negara.",
        ),
        (
            "Ember vs Renewable",
            "Dua himpunan data terpisah yang dipakai sesuai cakupan indikatornya; keduanya tidak dicampur dalam satu rumus agar setiap angka tetap konsisten.",
        ),
    ],
)

# ------------------------------------------------------------------ kartu ringkas (tahun terpilih)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Negara dalam master", n_(master),
          help="Seluruh negara pada data warehouse untuk tahun ini, termasuk yang tidak punya data indikator tertentu. "
               "Jumlah ini berbeda dari jumlah negara yang memiliki nilai.")


def kartu(kolom, kode, label, bantuan):
    r = cy.loc[kode]
    kolom.metric(label, f"{n_(r['tersedia'])} dari {n_(r['negara_master'])}", help=bantuan)


kartu(k2, "pangsa_listrik_ren", "Pangsa listrik terbarukan (Renewable)",
      "Negara yang memiliki nilai pangsa listrik terbarukan dari sumber Renewable Energy Share.")
kartu(k3, "intensitas_emb", "Intensitas emisi (Ember)",
      "Negara yang memiliki nilai intensitas emisi dari sumber Ember.")
kartu(k4, "pangsa_primer_ren", "Energi primer (Renewable)",
      "Negara yang memiliki pangsa terbarukan pada energi primer. Cakupannya jauh lebih terbatas daripada data listrik, "
      "sehingga tidak dibuat angka global untuk energi primer.")
st.caption(f"Tahun {year}. Coverage = negara yang memiliki nilai dibagi negara master, dikali 100. Rincian per indikator "
           f"dan per tahun ada di tab Cakupan.")

tab_c, tab_m, tab_s, tab_r, tab_k = st.tabs(["Cakupan", "Nilai kosong", "Ember vs Renewable",
                                              "Rata-rata sederhana vs tertimbang", "Konsistensi dan ETL"])

# ------------------------------------------------------------------ tab 1: cakupan
with tab_c:
    st.subheader(f"Cakupan negara per indikator, {year}")
    components.micro_guide(
        "Panjang batang menunjukkan persentase negara master yang memiliki nilai non-kosong untuk setiap indikator."
    )
    st.plotly_chart(charts.coverage_bar(cover[cover["year"] == year], year), width="stretch")
    st.caption("'Negara master' adalah seluruh negara pada data warehouse; 'tersedia' adalah negara yang punya nilai "
               "(bukan kosong) untuk indikator itu. Keduanya sengaja dipisahkan: negara bisa ada di master tetapi tidak "
               "punya baris di sebuah sumber, atau punya baris tetapi nilainya kosong.")
    tabel_c = pd.DataFrame({
        "Tahun": cover["year"].astype(int), "Indikator": cover["indikator"], "Sumber": cover["sumber"],
        "Negara master": cover["negara_master"].astype(int), "Punya baris di sumber": cover["punya_baris"].astype(int),
        "Nilai tersedia": cover["tersedia"].astype(int), "Coverage (%)": cover["coverage"]})
    st.dataframe(tabel_c, hide_index=True, width="stretch", column_config={
        "Coverage (%)": st.column_config.NumberColumn(format="%.1f"),
        "Tahun": st.column_config.NumberColumn(format="%d")})
    st.download_button("Unduh tabel cakupan (CSV)", tabel_c.to_csv(index=False).encode("utf-8-sig"),
                       file_name="cakupan_indikator_per_tahun.csv", mime="text/csv")
    st.caption("Untuk bauran pembangkitan, 'tersedia' = jumlah negara yang memiliki baris sumber pembangkitan pada tahun itu.")

    st.subheader(f"Energi primer: cakupan terbatas dan tidak merata, {year}")
    prim = db.safe(queries.k_primary, year)
    st.dataframe(pd.DataFrame({"Benua": prim["benua"], "Negara master": prim["negara_master"].astype(int),
                               "Punya pangsa energi primer": prim["tersedia"].astype(int), "Coverage (%)": prim["coverage"]}),
                 hide_index=True, width="stretch", column_config={"Coverage (%)": st.column_config.NumberColumn(format="%.1f")})
    n_prim, n_master = int(prim["tersedia"].sum()), int(prim["negara_master"].sum())
    st.caption(f"Hanya {n_(n_prim)} dari {n_(n_master)} negara master yang memiliki pangsa terbarukan energi primer, dengan "
               f"coverage yang berbeda jauh antarbenua. Karena itu dashboard tidak membuat agregat global energi primer "
               f"yang seolah-olah mewakili seluruh negara; pangsa terbarukan global pada halaman lain memakai data listrik.")

    st.subheader(f"Status kelengkapan data, {year}")
    status = db.safe(queries.k_status, year)
    alasan = db.safe(queries.k_status_reason, year)
    st.dataframe(pd.DataFrame({"Sumber": status["sumber"], "Status": status["status"], "Jumlah baris": status["jumlah"].astype(int)}),
                 hide_index=True, width="stretch")
    st.caption("Status adalah indikator kelengkapan pada kolom indikator tertentu saja (dua kolom pangsa untuk Renewable; "
               "pangsa terbarukan dan intensitas untuk Ember), bukan penilaian mutu seluruh baris. 'Valid dengan indikator "
               "kosong' berarti salah satu kolom itu kosong, bukan berarti baris tidak berisi data. 'Tidak ada baris' = "
               "negara master tanpa baris di sumber itu.")
    rinci = []
    for r in alasan.itertuples():
        rinci += [{"Sumber": r.sumber, "Keadaan kolom": "Kedua kolom terisi", "Jumlah baris": int(r.lengkap)},
                  {"Sumber": r.sumber, "Keadaan kolom": f"Hanya {r.nama_kolom1} kosong", "Jumlah baris": int(r.kolom1_kosong)},
                  {"Sumber": r.sumber, "Keadaan kolom": f"Hanya {r.nama_kolom2} kosong", "Jumlah baris": int(r.kolom2_kosong)},
                  {"Sumber": r.sumber, "Keadaan kolom": "Kedua kolom kosong", "Jumlah baris": int(r.keduanya_kosong)}]
    st.markdown("**Kolom mana yang kosong pada baris yang ada (dari nilai di data, bukan dari label status):**")
    st.dataframe(pd.DataFrame(rinci), hide_index=True, width="stretch")

# ------------------------------------------------------------------ tab 2: nilai kosong
with tab_m:
    miss = db.safe(queries.k_missing)
    nocont = db.safe(queries.k_nocont).iloc[0]
    st.subheader("Negara dan tahun dengan nilai kosong penting")
    if miss.empty:
        st.info("Tidak ada negara dengan nilai kosong pada indikator listrik utama.")
    else:
        for kel in miss["kelompok"].unique():
            d = miss[miss["kelompok"] == kel]
            st.markdown(f"**{kel}**: {n_(d['iso3_code'].nunique())} negara, {n_(d['jumlah_tahun'].sum())} negara-tahun kosong")
            st.dataframe(pd.DataFrame({"Negara": d["country_name"], "Kode": d["iso3_code"], "Benua": d["benua"],
                                       "Tahun kosong": d["tahun"], "Jumlah tahun": d["jumlah_tahun"].astype(int),
                                       "Alasan (dari data)": d["alasan"]}), hide_index=True, width="stretch")
        st.download_button("Unduh daftar nilai kosong (CSV)", miss.to_csv(index=False).encode("utf-8-sig"),
                           file_name="nilai_kosong_per_negara.csv", mime="text/csv")
    st.caption("Alasan hanya memuat apa yang dapat dibuktikan dari data: ada atau tidaknya baris di sumber, dan "
               "pembangkitan yang 0 atau kosong (pangsa dari pembangkitan 0 tidak terdefinisi). Mengapa sumber tidak "
               "memuat sebuah baris tidak diketahui dan tidak ditebak. Nilai kosong tidak diisi, tidak dianggap 0, dan "
               "tidak ikut dihitung; jumlah negara yang dipakai selalu ditampilkan di halaman analisis.")
    st.caption(f"{n_(nocont['negara_tanpa_benua'])} negara tidak memiliki atribut benua di sumber; "
               f"{n_(nocont['tanpa_ember_semua_tahun'])} di antaranya tidak memiliki baris Ember pada semua tahun. Pada "
               f"filter benua mereka dikelompokkan sebagai 'Tidak diketahui' agar tidak hilang diam-diam.")
    st.info("Asal kekosongan (data sumber atau proses ETL) tidak dapat diperiksa dari dashboard, karena akun baca-saja "
            "tidak punya akses ke staging dan data warehouse. Pemeriksaan itu dilakukan di `sql/100_validate_quality.sql` "
            "dan `test_halaman_kualitas.py` terhadap staging dan berkas mentah.")

# ------------------------------------------------------------------ tab 3: Ember vs Renewable
with tab_s:
    sc = db.safe(queries.k_src_cover).set_index("year")
    sd = db.safe(queries.k_src_diff).set_index("year")
    st.subheader("Cakupan negara menurut sumber")
    st.dataframe(pd.DataFrame({"Tahun": sc.index.astype(int), "Negara master": sc["negara_master"].astype(int).values,
                               "Ada di kedua sumber": sc["kedua_sumber"].astype(int).values,
                               "Hanya Renewable": sc["hanya_renewable"].astype(int).values,
                               "Hanya Ember": sc["hanya_ember"].astype(int).values,
                               "Tanpa keduanya": sc["tanpa_keduanya"].astype(int).values}),
                 hide_index=True, width="stretch", column_config={"Tahun": st.column_config.NumberColumn(format="%d")})
    st.caption("'Ada di sumber' berarti negara punya baris di sumber itu (nilainya bisa saja ada yang kosong). Nilai "
               "dibandingkan hanya untuk negara yang ada di kedua sumber.")
    st.subheader("Seberapa sering kedua sumber berbeda")
    tabel_d = pd.DataFrame({
        "Tahun": sd.index.astype(int),
        "Negara di kedua sumber": sd["n_pasang"].astype(int).values,
        f"Selisih pembangkitan lebih dari {GEN_PCT}%": sd["n_gen_besar"].astype(int).values,
        f"Selisih pangsa lebih dari {SHARE_PTS} poin": sd["n_pangsa_besar"].astype(int).values})
    st.dataframe(tabel_d, hide_index=True, width="stretch", column_config={"Tahun": st.column_config.NumberColumn(format="%d")})
    if year in sd.index:
        r = sd.loc[year]
        st.caption(f"Pada {year}: dari {n_(r['n_gen_dibanding'])} negara yang pembangkitannya dapat dibandingkan, "
                   f"{n_(r['n_gen_besar'])} berselisih lebih dari {GEN_PCT}%; dari {n_(r['n_pangsa_dibanding'])} negara "
                   f"yang pangsanya dapat dibandingkan, {n_(r['n_pangsa_besar'])} berselisih lebih dari {SHARE_PTS} poin. "
                   f"Ambang {GEN_PCT}% dan {SHARE_PTS} poin adalah keputusan desain, bukan standar ilmiah.")
    st.subheader(f"Negara dengan selisih pangsa terbesar, {year}")
    top = db.safe(queries.k_src_top, year)
    if top.empty:
        st.info("Tidak ada negara yang pangsanya dapat dibandingkan pada tahun ini.")
    else:
        st.dataframe(pd.DataFrame({
            "Negara": top["country_name"], "Pangsa Ember (%)": top["pangsa_ember"], "Pangsa Renewable (%)": top["pangsa_renewable"],
            "Selisih (poin, Ember dikurangi Renewable)": top["selisih_poin"], "Pembangkitan Ember (TWh)": top["pembangkitan_ember"],
            "Pembangkitan Renewable (TWh)": top["pembangkitan_renewable"], "Selisih pembangkitan (%)": top["selisih_gen_persen"]}),
            hide_index=True, width="stretch", column_config={
                c: st.column_config.NumberColumn(format="%.1f") for c in
                ["Pangsa Ember (%)", "Pangsa Renewable (%)", "Selisih (poin, Ember dikurangi Renewable)",
                 "Pembangkitan Ember (TWh)", "Pembangkitan Renewable (TWh)", "Selisih pembangkitan (%)"]})
        st.caption(f"{queries.K_TOP_N} negara dengan selisih pangsa (dari angka yang tampil) terbesar; keputusan desain "
                   f"untuk jumlah baris. Selisih pembangkitan = pembangkitan Ember dibagi pembangkitan Renewable dikurangi 1, "
                   f"dihitung dari nilai sebelum dibulatkan.")
    scat = db.safe(queries.k_src_scatter, year)
    if not scat.empty:
        st.plotly_chart(charts.source_scatter(scat, year), width="stretch")
        st.caption(f"Setiap titik adalah satu negara pada {year}; titik di garis putus-putus berarti kedua sumber memberi "
                   f"pangsa yang sama.")
    st.caption("Ember dan Renewable Energy Share adalah dua sumber yang berbeda dan dapat memberi nilai berbeda untuk negara "
               "dan tahun yang sama. Halaman ini tidak menyatakan salah satunya lebih benar. Penyebab selisih (misalnya "
               "definisi, cakupan, atau waktu pembaruan) tidak dapat dipastikan dari data ini. Karena itu halaman A, B, dan "
               "Ringkasan memakai Renewable, sedangkan halaman C dan D memakai Ember, dan keduanya tidak dicampur dalam "
               "satu perhitungan.")

# ------------------------------------------------------------------ tab 4: sederhana vs tertimbang
with tab_r:
    mean = db.safe(queries.k_mean)
    tahun_list = [int(y) for y in mean["year"]]
    st.subheader("Pangsa listrik terbarukan: rata-rata negara vs tertimbang pembangkitan")
    sel_s = mean.loc[mean["year"] == year, "pangsa_tertimbang"]
    sed_s = mean.loc[mean["year"] == year, "pangsa_sederhana"]
    sel = float(sel_s.iloc[0]) if (len(sel_s) and pd.notna(sel_s.iloc[0])) else None
    sed = float(sed_s.iloc[0]) if (len(sed_s) and pd.notna(sed_s.iloc[0])) else None
    m1, m2, m3 = st.columns(3)
    m1.metric("Rata-rata sederhana antarnegara", theme.fmt_pct(sed), help="Setiap negara diberi bobot sama, berapa pun "
              "besar pembangkitannya.")
    m2.metric("Tertimbang pembangkitan", theme.fmt_pct(sel), help="Setiap negara diberi bobot sebesar pembangkitan listriknya "
              "(Renewable). Ini definisi KPI pada halaman Ringkasan, A, dan B.")
    selisih_m = round(sed - sel, 1) if (sed is not None and sel is not None) else None
    m3.metric("Selisih (sederhana dikurangi tertimbang)",
              theme.fmt_delta(selisih_m, 1, " poin") if selisih_m is not None else "tidak ada data",
              delta_color="off", help="Dihitung dari angka yang ditampilkan.")
    st.caption(f"Tahun {year}. Rata-rata sederhana menjawab 'berapa pangsa terbarukan rata-rata sebuah negara', sedangkan "
               f"rata-rata tertimbang menjawab 'berapa pangsa terbarukan dari seluruh listrik yang dihasilkan'. Keduanya "
               f"benar untuk pertanyaannya masing-masing dan tidak dapat saling menggantikan; pada {year} selisihnya "
               f"{theme.fmt_delta(selisih_m, 1, ' poin') if selisih_m is not None else 'tidak ada data'}.")
    tabel_m = pd.DataFrame({
        "Tahun": tahun_list, "Negara dalam perhitungan": mean["n_pangsa_berbobot"].astype(int),
        "Rata-rata sederhana (%)": mean["pangsa_sederhana"], "Tertimbang pembangkitan (%)": mean["pangsa_tertimbang"],
        "Selisih (poin)": [round(a - b, 1) if (pd.notna(a) and pd.notna(b)) else None
                           for a, b in zip(mean["pangsa_sederhana"], mean["pangsa_tertimbang"])]})
    ca, cb = st.columns([3, 2])
    with ca:
        st.dataframe(tabel_m, hide_index=True, width="stretch", column_config={
            "Tahun": st.column_config.NumberColumn(format="%d"),
            **{c: st.column_config.NumberColumn(format="%.1f") for c in
               ["Rata-rata sederhana (%)", "Tertimbang pembangkitan (%)", "Selisih (poin)"]}})
    with cb:
        st.plotly_chart(charts.multi_trend(tahun_list, [
            dict(name="Rata-rata sederhana", values=list(mean["pangsa_sederhana"]), color=theme.COLOR_HIGHLIGHT, width=2, dash="dash"),
            dict(name="Tertimbang pembangkitan", values=list(mean["pangsa_tertimbang"]), color=theme.COLOR_RENEWABLE, width=3)],
            "Pangsa terbarukan (%)", dec=1, suffix="%", height=300), width="stretch")
    st.subheader("Intensitas emisi: rata-rata negara vs tertimbang pembangkitan")
    tabel_i = pd.DataFrame({
        "Tahun": tahun_list, "Negara dalam perhitungan": mean["n_intensitas_berbobot"].astype(int),
        "Rata-rata sederhana (gCO₂e/kWh)": mean["intensitas_sederhana"],
        "Tertimbang pembangkitan (gCO₂e/kWh)": mean["intensitas_tertimbang"],
        "Selisih": [round(a - b, 0) if (pd.notna(a) and pd.notna(b)) else None
                    for a, b in zip(mean["intensitas_sederhana"], mean["intensitas_tertimbang"])]})
    st.dataframe(tabel_i, hide_index=True, width="stretch", column_config={
        "Tahun": st.column_config.NumberColumn(format="%d"),
        **{c: st.column_config.NumberColumn(format="%.0f") for c in
           ["Rata-rata sederhana (gCO₂e/kWh)", "Tertimbang pembangkitan (gCO₂e/kWh)", "Selisih"]}})
    st.caption("Intensitas memakai data Ember; bobot = total pembangkitan Ember. Rata-rata sederhana memberi bobot sama pada "
               "negara kecil dan besar, sehingga dapat berbeda jauh dari angka yang tertimbang pembangkitan.")
    st.subheader("Dampak pilihan bobot pada pangsa terbarukan global")
    tabel_b = pd.DataFrame({
        "Tahun": tahun_list, "Bobot pembangkitan Renewable (%)": mean["pangsa_tertimbang_2"],
        "Bobot pembangkitan Ember (%)": mean["pangsa_bobot_ember_2"],
        "Selisih (poin)": [round(a - b, 2) if (pd.notna(a) and pd.notna(b)) else None
                           for a, b in zip(mean["pangsa_tertimbang_2"], mean["pangsa_bobot_ember_2"])]})
    st.dataframe(tabel_b, hide_index=True, width="stretch", column_config={
        "Tahun": st.column_config.NumberColumn(format="%d"),
        **{c: st.column_config.NumberColumn(format="%.2f") for c in
           ["Bobot pembangkitan Renewable (%)", "Bobot pembangkitan Ember (%)", "Selisih (poin)"]}})
    selisih_valid = [abs(v) for v in tabel_b["Selisih (poin)"] if pd.notna(v)]
    maks = max(selisih_valid) if selisih_valid else 0.0
    st.caption(f"Pangsa Renewable yang sama dibobot dengan dua ukuran pembangkitan yang berbeda (Renewable dan Ember). "
               f"Selisih terbesar antartahun {theme.fmt_num(maks, 2)} poin; ditampilkan 2 desimal karena selisihnya kecil.")

# ------------------------------------------------------------------ tab 5: konsistensi dan ETL
with tab_k:
    tabel_k = pd.DataFrame({"Pemeriksaan": [c[0] for c in cek_awal], "Tahun lulus": [f"{sum(c[1])} dari {len(c[1])}" for c in cek_awal],
                            "Status": ["OK" if all(c[1]) else "BEDA" for c in cek_awal]})
    n_ok = int((tabel_k["Status"] == "OK").sum())
    st.subheader("Konsistensi antar-view mart")
    kk1, kk2 = st.columns(2)
    kk1.metric("Pemeriksaan konsistensi lulus", f"{n_ok} dari {len(tabel_k)}")
    maks_bauran = float(gen["selisih_maks"].max()) if (not gen.empty and gen["selisih_maks"].notna().any()) else None
    kk2.metric("Selisih maksimum penjumlahan bauran",
               f"{theme.fmt_num(maks_bauran, 3)} TWh" if maks_bauran is not None else "tidak ada data",
               help=f"Selisih terbesar antara jumlah semua sumber dan total pembangkitan Ember pada satu negara-tahun. "
                    f"Toleransi {theme.fmt_num(TOL, 2)} TWh adalah keputusan desain.")
    st.dataframe(tabel_k, hide_index=True, width="stretch")
    with st.expander("Angka per tahun yang dibandingkan"):
        st.dataframe(pd.DataFrame({
            "Tahun": rec.index.astype(int), "Baris v_country_year": rec["n_cy"].astype(int).values,
            "Negara unik": rec["n_cy_iso"].astype(int).values, "Punya baris Renewable": rec["n_energy"].astype(int).values,
            "Punya baris Ember": rec["n_ember"].astype(int).values, "Di kedua sumber": rec["n_both"].astype(int).values,
            "Baris v_source_comparison": rec["n_cmp"].astype(int).values, "Baris bauran": rec["baris_mix"].astype(int).values,
            "Negara pada bauran": rec["negara_mix"].astype(int).values,
            "Total bauran (TWh)": gen["total_bauran"].reindex(rec.index).values,
            "Total negara (TWh)": gen["total_negara"].reindex(rec.index).values}),
            hide_index=True, width="stretch", column_config={"Tahun": st.column_config.NumberColumn(format="%d")})
    st.caption("Pemeriksaan di atas membandingkan view mart satu sama lain. Rekonsiliasi Data Warehouse ke Data Mart "
               "(jumlah baris, jumlah negara, total pembangkitan, dan indikator utama) membutuhkan akses ke schema dw, yang "
               "tidak dimiliki akun dashboard, sehingga dijalankan sebagai query independen di `sql/100_validate_quality.sql` "
               "oleh pengguna `postgres`.")
    st.subheader("Proses ETL terakhir")
    yrs = db.safe(queries.k_years).iloc[0]
    if etl.empty:
        st.info("Status ETL belum tersedia.")
    else:
        r = etl.iloc[0]
        waktu = r["finished_at"].to_pydatetime().astimezone().strftime("%d-%m-%Y %H:%M")   # waktu lokal komputer
        e1, e2, e3 = st.columns(3)
        e1.metric("Run ETL terakhir yang sukses", f"#{int(r['run_id'])}")
        e2.metric("Selesai (waktu lokal komputer)", waktu)
        e3.metric("Baris dimuat ke DW", n_(r["rows_loaded_dw"]),
                  help="Jumlah baris yang dicatat langkah load_dw pada run itu (log ETL). Run '--staging-only' tidak dihitung.")
    st.caption(f"Data mencakup tahun {int(yrs['tahun_awal'])} sampai {int(yrs['tahun_akhir'])} ({n_(yrs['jumlah_tahun'])} "
               f"tahun). Kesegaran data mengikuti ETL terakhir; ETL dijalankan manual.")

with st.expander("Definisi KPI dan alasan pembobotan"):
    st.markdown(
        "- **Pangsa terbarukan dan fosil (kartu pada Ringkasan, A, dan B)** = jumlah (pangsa x pembangkitan listrik) dibagi "
        "jumlah pembangkitan, hanya untuk negara yang bernilai dan pembangkitannya lebih dari 0. Ini rata-rata tertimbang "
        "pembangkitan: negara dengan listrik lebih besar berpengaruh lebih besar, sehingga angkanya menggambarkan listrik "
        "dunia, bukan 'negara rata-rata'. Rata-rata sederhana hanya ditampilkan dengan label eksplisit.\n"
        "- **Intensitas emisi** = jumlah (intensitas x total pembangkitan Ember) dibagi jumlah total pembangkitan Ember, "
        "dengan syarat yang sama.\n"
        f"- **Tahun pembanding** tetap {base}; selisih dan perubahan dihitung dari angka yang ditampilkan (dibulatkan 1 "
        "desimal, setengah ke atas, di SQL).\n"
        "- **Dua sumber data:** halaman Ringkasan, A, dan B memakai Renewable Energy Share; halaman C dan D memakai Ember. "
        "Keduanya tidak dicampur dalam satu perhitungan.\n"
        "- **Nilai kosong (NULL)** tidak diisi dan tidak dihitung sebagai 0; jumlah negara yang dipakai selalu ditampilkan.\n"
        "- **Ambang yang merupakan keputusan desain, bukan standar ilmiah:** pembangkitan minimum pada peringkat dan "
        "pencilan, jumlah negara minimum per benua, ambang selisih Ember vs Renewable, dan toleransi penjumlahan bauran.\n"
        "- **Tidak dipakai:** GDP dan populasi (tidak memadai di data mart) serta agregat global energi primer (cakupan terbatas).\n"
        "- Dashboard menunjukkan pola deskriptif dan tidak menarik kesimpulan tentang penyebab.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka dibaca dari view `mart.v_country_year`, `mart.v_generation_mix`, `mart.v_source_comparison`, dan "
                "`mart.v_etl_status` memakai akun baca-saja `np_dashboard`. Parameter dikirim terpisah dari teks SQL.")
    st.markdown("**Cakupan per indikator dan tahun:**")
    st.code(queries.K_COVER_SQL, language="sql")
    st.markdown("**Nilai kosong beserta alasan:**")
    st.code(queries.K_MISSING_SQL, language="sql")
    st.markdown("**Rata-rata sederhana vs tertimbang:**")
    st.code(queries.K_MEAN_SQL, language="sql")
