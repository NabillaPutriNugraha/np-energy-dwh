"""Halaman D: Pangsa Terbarukan vs Intensitas Emisi.
Pertanyaan bisnis: bagaimana hubungan pangsa listrik terbarukan dengan intensitas emisi antarnegara?
Sumber: HANYA mart.v_country_year, kolom Ember (pangsa terbarukan, intensitas emisi, pembangkitan). Kedua indikator
berasal dari satu sumber (Ember). Hubungan bersifat observasional; halaman ini tidak menyimpulkan penyebab."""
import pandas as pd
import streamlit as st

import charts
import db
import queries
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
cont, grp, iso = f["continents"], f["groups"], f["country"]
opts = db.safe(queries.filter_options)
names = dict(opts["countries"])
semua = (len(cont) == len(opts["continents"])) and (len(grp) == len(opts["groups"]))
scope_label = "Dunia" if semua else "Negara terpilih"
MIN_TWH, MIN_N = queries.D_MIN_TWH, queries.D_MIN_N

st.title("D. Pangsa Terbarukan vs Intensitas Emisi")
st.caption("Bagaimana hubungan antara pangsa listrik terbarukan dan intensitas emisi listrik antarnegara. "
           "Sumber: Data Warehouse NP Energy Intelligence (Ember); kedua indikator berasal dari sumber yang sama.")
st.warning("**Catatan interpretasi (selalu berlaku):** hubungan yang ditampilkan di halaman ini bersifat observasional "
           "(korelasi antarnegara) dan **bukan bukti hubungan sebab-akibat**. Korelasi tidak menunjukkan arah maupun "
           "penyebab, dan negara dapat berbeda karena banyak hal lain yang tidak ada dalam data ini.")


def n_fmt(x) -> str:
    return theme.fmt_num(x, 0)


stats = db.safe(queries.d_stats, cont, grp)
cover = db.safe(queries.d_cover, cont, grp).set_index("year")
ada = (not stats.empty) and year in set(stats["year"])
cur = stats[stats["year"] == year].iloc[0] if ada else None
if cur is None or int(cur["n"]) < queries.D_MIN_N_KPI or pd.isna(cur["pearson_bulat"]):
    n_ada = int(cur["n"]) if cur is not None else 0
    st.info(f"Data tidak cukup untuk menghitung hubungan pada filter ini: hanya {n_ada} negara yang memiliki pangsa "
            f"terbarukan dan intensitas emisi pada {year} (minimal {queries.D_MIN_N_KPI} negara). Ubah filter di sidebar. "
            f"Nilai yang kosong di sumber tidak diisi dengan perkiraan.")
    st.stop()

ada_awal = year != base and base in set(stats["year"])
prev = stats[stats["year"] == base].iloc[0] if ada_awal else None
bandingkan = prev is not None and int(prev["n"]) >= queries.D_MIN_N_KPI and pd.notna(prev["pearson_bulat"])
n_cur = int(cur["n"])
n_ember = int(cover.loc[year, "negara_ember"]) if year in cover.index else n_cur


def delta(kolom, dec):
    """Selisih dari angka yang ditampilkan (sudah dibulatkan di SQL), sama dengan halaman lain."""
    return theme.fmt_delta(float(cur[kolom]) - float(prev[kolom]), dec) if bandingkan else None


# ------------------------------------------------------------------ kartu KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("Korelasi Pearson (r)", theme.fmt_num(cur["pearson_bulat"], 2), delta("pearson_bulat", 2), delta_color="off",
          help="Mengukur seberapa lurus hubungan pangsa terbarukan dan intensitas emisi antarnegara, dari -1 sampai 1. "
               "Negatif berarti negara berpangsa terbarukan lebih tinggi cenderung berintensitas lebih rendah. "
               "Setiap negara dihitung satu kali (tidak tertimbang pembangkitan).")
c2.metric("Korelasi Spearman", theme.fmt_num(cur["spearman_bulat"], 2), delta("spearman_bulat", 2), delta_color="off",
          help="Korelasi atas peringkat negara (bukan nilai asli), sehingga tidak banyak dipengaruhi nilai ekstrem. "
               "Nilai seri diberi peringkat rata-rata.")
c3.metric("Lereng garis regresi", theme.fmt_num(cur["lereng_bulat"], 1), delta("lereng_bulat", 1), delta_color="off",
          help="Perubahan intensitas emisi (gCO₂e/kWh) yang diperkirakan garis regresi sederhana untuk setiap "
               "kenaikan pangsa terbarukan 1 poin persentase. Ini ringkasan pola antarnegara pada data, "
               "bukan perkiraan untuk satu negara jika pangsanya berubah.")
c4.metric("Negara dalam analisis", f"{n_fmt(n_cur)} dari {n_fmt(n_ember)}",
          help="Negara yang pangsa terbarukan dan intensitas emisinya terisi dan pembangkitannya lebih dari 0. Negara "
               "tanpa nilai tidak ikut dihitung dan tidak diisi dengan perkiraan.")
st.caption(f"{scope_label}, tahun {year}" + (f" dibandingkan {base} (selisih dihitung dari angka yang tampil)." if bandingkan
           else f". Pilih tahun setelah {base} untuk melihat selisih terhadap {base}.") +
           f" Lereng dalam gCO₂e/kWh untuk setiap kenaikan pangsa 1 poin; R² garis regresi = "
           f"{theme.fmt_num(cur['r2_bulat'], 2)}. Pangsa terbarukan di halaman ini dari Ember, sehingga dapat berbeda "
           f"dari halaman lain yang memakai Renewable Energy Share. {n_fmt(n_ember)} negara berdata Ember pada filter; "
           f"{n_fmt(n_ember - n_cur)} di antaranya tidak memiliki kedua nilai pada {year} dan tidak ikut dihitung.")
if n_cur < MIN_N:
    st.warning(f"Hanya {n_cur} negara pada filter ini (kurang dari {MIN_N}). Korelasi dari jumlah negara sekecil ini "
               f"tidak stabil dan sebaiknya tidak ditafsirkan.")

tab_s, tab_b, tab_p, tab_o = st.tabs(["Sebaran dan garis regresi", "Korelasi per benua",
                                       f"Perubahan {base} ke {year}", "Negara pencilan"])

# ------------------------------------------------------------------ tab 1: sebaran
with tab_s:
    titik = db.safe(queries.d_points, year, cont, grp)
    sorot = db.safe(queries.d_point_country, year, iso)
    nama_sorot = names.get(iso, iso)
    st.plotly_chart(charts.scatter_regression(titik, cur["intersep"], cur["lereng"], cur["x_min"], cur["x_max"], year,
                                              sorot if len(sorot) else None, nama_sorot), width="stretch")
    st.caption(f"Setiap titik adalah satu negara pada {year}. Posisi mendatar = pangsa listrik terbarukan (Ember), posisi "
               f"tegak = intensitas emisi, ukuran = total pembangkitan listrik (TWh), warna = benua. Garis putus-putus = "
               f"garis regresi sederhana (intensitas terhadap pangsa) dari {n_fmt(n_cur)} negara pada grafik. Arahkan "
               f"kursor ke titik untuk melihat negara, tahun, dan nilainya.")
    if len(sorot):
        st.caption(f"Lingkaran biru = negara sorotan ({nama_sorot}); posisinya tidak dipengaruhi filter benua dan kelompok "
                   f"negara.")
    else:
        st.caption(f"Negara sorotan ({nama_sorot}) tidak memiliki pangsa terbarukan dan intensitas emisi Ember pada {year}, "
                   f"sehingga tidak digambar.")

# ------------------------------------------------------------------ tab 2: per benua
with tab_b:
    benua_df = db.safe(queries.d_continent, year, cont, grp)
    tampil = benua_df[benua_df["benua"] != queries.UNKNOWN_CONTINENT]
    tak_dikenal = benua_df[benua_df["benua"] == queries.UNKNOWN_CONTINENT]
    ok = tampil[tampil["pearson_bulat"].notna()]
    if not ok.empty:
        st.plotly_chart(charts.corr_bar(ok), width="stretch")
    else:
        st.info(f"Tidak ada benua dengan minimal {MIN_N} negara pada filter ini, sehingga tidak ada korelasi per benua "
                f"yang ditampilkan.")
    tabel_b = pd.DataFrame({
        "Benua": tampil["benua"], "Jumlah negara": tampil["n"].astype(int),
        "Pearson (r)": tampil["pearson_bulat"], "Spearman": tampil["spearman_bulat"],
        "Lereng (gCO₂e/kWh per poin)": tampil["lereng_bulat"],
        "Keterangan": ["" if pd.notna(p) else f"Tidak dihitung: kurang dari {MIN_N} negara" for p in tampil["pearson_bulat"]]})
    st.dataframe(tabel_b, hide_index=True, width="stretch", column_config={
        "Pearson (r)": st.column_config.NumberColumn(format="%.2f"),
        "Spearman": st.column_config.NumberColumn(format="%.2f"),
        "Lereng (gCO₂e/kWh per poin)": st.column_config.NumberColumn(format="%.1f")})
    st.caption(f"Korelasi per benua pada {year}, dihitung hanya dari negara pada benua itu. Benua dengan kurang dari "
               f"{MIN_N} negara tidak diberi nilai (sel kosong), karena korelasi dari jumlah sekecil itu tidak stabil; "
               f"{MIN_N} negara adalah keputusan desain, bukan standar ilmiah. Nilai pada tiap benua tidak bisa "
               f"dibandingkan begitu saja dengan nilai gabungan, karena rentang pangsa tiap benua berbeda.")
    if not tak_dikenal.empty:
        st.caption(f"{int(tak_dikenal['n'].iloc[0])} negara tanpa atribut benua tidak dimasukkan ke tabel ini.")

# ------------------------------------------------------------------ tab 3: perubahan
with tab_p:
    if year == base:
        st.info(f"Tahun terpilih sama dengan tahun pembanding ({base}). Pilih tahun setelah {base} di sidebar untuk "
                f"melihat perubahan.")
    else:
        ch = db.safe(queries.d_change, year, cont, grp)
        cs = db.safe(queries.d_change_stats, year, cont, grp).iloc[0]
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Negara berdata lengkap", f"{n_fmt(cs['n_lengkap'])} dari {n_fmt(cs['n_daftar'])}",
                  help=f"Negara yang pangsa terbarukan dan intensitas emisinya terisi pada {base} dan {year}. Negara "
                       f"dengan nilai kosong tetap ada di tabel, tetapi perubahannya kosong (tidak diisi).")
        p2.metric("Median perubahan pangsa", theme.fmt_delta(cs["median_d_pangsa"], 1, " poin") or "tidak ada data",
                  help="Median antarnegara (tidak tertimbang pembangkitan) dari selisih pangsa yang tampil.")
        p3.metric("Median perubahan intensitas",
                  theme.fmt_delta(cs["median_d_intensitas"], 1, " gCO₂e/kWh") or "tidak ada data",
                  help="Median antarnegara (tidak tertimbang pembangkitan) dari selisih intensitas yang tampil.")
        if int(cs["n_korelasi"]) >= MIN_N and pd.notna(cs["korelasi_perubahan"]):
            p4.metric("Korelasi antar-perubahan", theme.fmt_num(cs["korelasi_perubahan"], 2),
                      help=f"Korelasi Pearson antara perubahan pangsa dan perubahan intensitas, hanya untuk "
                           f"{n_fmt(cs['n_korelasi'])} negara berpembangkitan minimal {MIN_TWH} TWh pada {year} "
                           f"(keputusan desain agar negara sangat kecil tidak mendominasi).")
        else:
            p4.metric("Korelasi antar-perubahan", "tidak ada data",
                      help=f"Dihitung hanya jika minimal {MIN_N} negara berpembangkitan minimal {MIN_TWH} TWh "
                           f"memiliki data lengkap.")
        st.caption(f"Perubahan {base} ke {year}; selisih dihitung dari angka yang tampil (dibulatkan 1 desimal). "
                   f"Korelasi antar-perubahan memakai {n_fmt(cs['n_korelasi'])} negara berpembangkitan minimal "
                   f"{MIN_TWH} TWh pada {year}. Pola ini bersifat deskriptif.")
        lengkap = ch[ch["lengkap"]]
        if lengkap.empty:
            st.info("Tidak ada negara dengan data lengkap pada kedua tahun untuk filter ini.")
        else:
            st.plotly_chart(charts.change_scatter(lengkap, year, base), width="stretch")
            st.caption(f"Setiap titik adalah satu negara dengan data lengkap pada {base} dan {year}; ukuran = pembangkitan "
                       f"{year}. Negara dengan nilai kosong tidak digambar dan tidak diganti 0.")
        tabel_p = pd.DataFrame({
            "Negara": ch["country_name"], "Benua": ch["benua"],
            f"Pangsa {base} (%)": ch["pangsa_awal"], f"Pangsa {year} (%)": ch["pangsa_akhir"],
            "Perubahan pangsa (poin)": ch["d_pangsa"],
            f"Intensitas {base}": ch["intensitas_awal"], f"Intensitas {year}": ch["intensitas_akhir"],
            "Perubahan intensitas": ch["d_intensitas"], f"Pembangkitan {year} (TWh)": ch["pembangkitan_twh"]})
        st.dataframe(tabel_p, hide_index=True, width="stretch", column_config={
            c: st.column_config.NumberColumn(format="%.1f") for c in tabel_p.columns if c not in ("Negara", "Benua")})
        n_kosong = int((~ch["lengkap"]).sum())
        st.download_button("Unduh tabel perubahan (CSV)", tabel_p.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"perubahan_pangsa_intensitas_{base}_{year}.csv", mime="text/csv")
        st.caption(f"Intensitas dalam gCO₂e/kWh. Menampilkan {n_fmt(len(ch))} negara berdata Ember pada filter; "
                   f"{n_fmt(n_kosong)} di antaranya memiliki nilai kosong pada salah satu tahun sehingga perubahannya "
                   f"kosong (tidak diisi perkiraan).")

# ------------------------------------------------------------------ tab 4: pencilan
with tab_o:
    out = db.safe(queries.d_outliers, year, cont, grp)
    if out.empty:
        st.info(f"Tidak ada negara berpembangkitan minimal {MIN_TWH} TWh pada filter ini.")
    else:
        top = out.head(10)
        st.plotly_chart(charts.residual_bar(top), width="stretch")
        tabel_o = pd.DataFrame({
            "Peringkat": top["peringkat"].astype(int), "Negara": top["country_name"], "Benua": top["benua"],
            "Pangsa terbarukan (%)": top["pangsa"], "Pangsa nuklir (%)": top["pangsa_nuklir"],
            "Intensitas aktual": top["intensitas"], "Intensitas menurut garis": top["intensitas_garis"],
            "Selisih (aktual - garis)": top["selisih"],
            "Posisi": ["Di atas garis" if v > 0 else "Di bawah garis" for v in top["selisih"]],
            "Pembangkitan (TWh)": top["pembangkitan_twh"]})
        st.dataframe(tabel_o, hide_index=True, width="stretch", column_config={
            "Pangsa terbarukan (%)": st.column_config.NumberColumn(format="%.1f"),
            "Pangsa nuklir (%)": st.column_config.NumberColumn(format="%.1f"),
            "Intensitas aktual": st.column_config.NumberColumn(format="%.1f"),
            "Intensitas menurut garis": st.column_config.NumberColumn(format="%.1f"),
            "Selisih (aktual - garis)": st.column_config.NumberColumn(format="%.1f"),
            "Pembangkitan (TWh)": st.column_config.NumberColumn(format="%.1f")})
        st.caption(f"Pencilan pada halaman ini adalah keputusan desain, bukan standar pencilan universal: dari "
                   f"{n_fmt(len(out))} negara berpembangkitan minimal {MIN_TWH} TWh pada {year}, ditampilkan 10 negara "
                   f"dengan selisih mutlak terbesar antara intensitas aktual dan intensitas menurut garis regresi "
                   f"sederhana (garis yang sama dengan grafik sebaran). Intensitas dalam gCO₂e/kWh. Pangsa nuklir "
                   f"dari Ember sebagai informasi pembanding; sel kosong berarti tidak ada baris nuklir untuk negara "
                   f"itu dan tidak dianggap 0. Tabel ini hanya menunjukkan negara yang menyimpang dari pola umum dan tidak "
                   f"menjelaskan alasannya.")
        sorot_o = out[out["iso3_code"] == iso]
        if not sorot_o.empty:
            r = sorot_o.iloc[0]
            st.caption(f"Negara sorotan {names.get(iso, iso)}: peringkat {int(r['peringkat'])} dari {n_fmt(len(out))}, "
                       f"selisih {theme.fmt_delta(r['selisih'], 1)} gCO₂e/kWh.")
        else:
            st.caption(f"Negara sorotan ({names.get(iso, iso)}) tidak termasuk dalam daftar ini (pembangkitan di bawah "
                       f"{MIN_TWH} TWh, tanpa data Ember, atau di luar filter).")

with st.expander("Cara membaca dan definisi"):
    st.markdown(
        "- **Pangsa listrik terbarukan** adalah bagian pembangkitan listrik dari sumber terbarukan (persen). "
        "**Intensitas emisi** adalah emisi gas rumah kaca per kWh listrik (gCO₂e/kWh). Keduanya dari Ember.\n"
        "- **Korelasi Pearson (r)** menunjukkan seberapa lurus hubungan dua ukuran, dari -1 sampai 1; **Spearman** "
        "memakai peringkat sehingga tidak banyak dipengaruhi nilai ekstrem. Keduanya menghitung setiap negara satu kali.\n"
        "- **Garis regresi sederhana** adalah garis lurus yang paling dekat dengan titik-titik (kuadrat terkecil). "
        "**Lereng** = perubahan intensitas yang diperkirakan garis untuk kenaikan pangsa 1 poin; **R²** = bagian "
        "keragaman intensitas yang dijelaskan garis itu secara statistik.\n"
        f"- **Korelasi per benua** hanya ditampilkan jika benua memiliki minimal {MIN_N} negara. **Pencilan** = negara "
        f"berpembangkitan minimal {MIN_TWH} TWh dengan selisih terbesar dari garis regresi. Kedua ambang adalah "
        "keputusan desain dashboard, bukan standar ilmiah.\n"
        "- **Nilai kosong** (misalnya pangsa tidak terdefinisi karena pembangkitan 0, atau tidak ada nilai di sumber) tidak "
        "diisi dan tidak ikut dihitung; jumlah negara yang dipakai selalu ditampilkan.\n"
        "- GDP dan populasi tidak dipakai. Halaman ini menunjukkan pola observasional, bukan hubungan sebab-akibat.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka dibaca dari view `mart.v_country_year` (dan `mart.v_generation_mix` untuk pangsa nuklir) "
                "memakai akun baca-saja `np_dashboard`. Parameter dikirim terpisah dari teks SQL.")
    st.markdown("**Korelasi, lereng, dan R² per tahun:**")
    st.code(queries.D_STATS_SQL, language="sql")
    st.markdown("**Negara pencilan:**")
    st.code(queries.D_OUTLIER_SQL, language="sql")
