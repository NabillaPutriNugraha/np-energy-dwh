"""Halaman C: Bauran Pembangkitan.
Pertanyaan bisnis: bagaimana total pembangkitan listrik tersusun menurut kategori dan sumber, dan bagaimana perubahannya?
Sumber: HANYA mart.v_generation_mix (data Ember). Daftar kategori dan sumber diambil dari data, bukan ditulis di sini."""
import pandas as pd
import streamlit as st

import charts
import db
import queries
import style
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
cont, grp = f["continents"], f["groups"]
opts = db.safe(queries.filter_options)
names = dict(opts["countries"])

st.title("C. Bauran Pembangkitan")
st.caption("Bagaimana total pembangkitan listrik tersusun menurut kategori dan sumber pembangkitan, 2019-2023. "
           "Sumber: Data Warehouse NP Energy Intelligence (Ember).")

katalog = db.safe(queries.c_catalog)
kategori_data = charts.urut_kategori(katalog["kategori"])
sumber_kat = {k: sorted(katalog.loc[katalog["kategori"] == k, "sumber"]) for k in kategori_data}

cat = db.safe(queries.c_category, cont, grp)
src = db.safe(queries.c_source, cont, grp)
if cat.empty or year not in set(cat["year"]):
    st.info("Tidak ada data bauran pembangkitan untuk filter ini. Data bauran (Ember) tidak mencakup sebagian negara; "
            "ubah filter di sidebar.")
    st.stop()

cur = cat[cat["year"] == year].set_index("kategori")
bandingkan = year != base and base in set(cat["year"])
prev = cat[cat["year"] == base].set_index("kategori") if bandingkan else None
semua = (len(cont) == len(opts["continents"])) and (len(grp) == len(opts["groups"]))
tren_label = "Dunia" if semua else "Negara terpilih"
total = float(cur["total_twh"].iloc[0])
total_awal = float(prev["total_twh"].iloc[0]) if bandingkan else None
counts = db.safe(queries.c_counts, cont, grp).set_index("year")
totals = db.safe(queries.c_totals, cont, grp).set_index("year")
n_data = int(counts.loc[year, "negara_berdata"])
n_all = int(totals.loc[year, "negara_total"]) if year in totals.index else n_data

# ------------------------------------------------------------------ kartu KPI
WARNA_DELTA = {"Fossil": "inverse", "Renewable": "normal"}   # selain itu: netral
kolom = st.columns(1 + len(kategori_data))
kolom[0].metric("Total pembangkitan", f"{theme.fmt_num(total, 0)} TWh",
                theme.fmt_delta(round(total) - round(total_awal), 0, " TWh") if bandingkan else None,
                help="Jumlah pembangkitan semua sumber pada negara berdata Ember di filter ini. "
                     "Selisih dihitung dari angka yang ditampilkan.")
for kol, k in zip(kolom[1:], kategori_data):
    nilai = float(cur.loc[k, "pangsa_bulat"]) if k in cur.index else None
    awal = float(prev.loc[k, "pangsa_bulat"]) if (bandingkan and k in prev.index) else None
    kol.metric(f"Pangsa {charts.kategori_label(k).lower()}", theme.fmt_pct(nilai),
               theme.fmt_delta(nilai - awal, 1, " poin") if (nilai is not None and awal is not None) else None,
               delta_color=WARNA_DELTA.get(k, "off"),
               help=f"TWh kategori {charts.kategori_label(k).lower()} dibagi total TWh semua kategori, dikali 100 "
                    f"(bukan rata-rata antarnegara). Dibulatkan 1 desimal, sehingga jumlah ketiga pangsa bisa "
                    f"99,9 sampai 100,1. Jika tertulis 'tidak ada data', tidak ada baris untuk kategori ini pada filter.")
st.caption(f"{tren_label}, tahun {year}" + (f" dibandingkan {base}. " if bandingkan else
           f" (pilih tahun setelah {base} untuk melihat perubahan). ") +
           f"Bauran dihitung dari {n_data} negara berdata Ember dari {n_all} negara pada filter ini; negara tanpa data "
           f"Ember tidak ikut dihitung dan tidak dianggap 0.")
kpi_ren = db.safe(queries.kpi_by_year, cont, grp)
baris = kpi_ren[kpi_ren["year"] == year]
if not baris.empty and pd.notna(baris["terbarukan"].iloc[0]):
    st.caption(f"Catatan sumber: halaman Ringkasan, A, dan B memakai Renewable Energy Share, yang memberi pangsa "
               f"terbarukan {theme.fmt_pct(baris['terbarukan'].iloc[0])} pada filter dan tahun yang sama. "
               f"Kedua sumber data berbeda, sehingga angkanya dapat berbeda.")

# ------------------------------------------------------------------ pembangun seri (kategori atau sumber)
st.subheader("Komposisi bauran per tahun")
tingkat = st.radio("Tingkat detail", ["Kategori", "Sumber rinci"], horizontal=True, key="c_level",
                   help="Kategori: fosil, nuklir, terbarukan. Sumber rinci: sumber pembangkitan penyusun kategori.")
kat_pilih = None
if tingkat == "Sumber rinci":
    pilihan = st.selectbox("Rinci kategori", ["Semua kategori"] + kategori_data, key="c_kat",
                           format_func=lambda k: k if k == "Semua kategori" else charts.kategori_label(k),
                           help="Pilih satu kategori untuk melihat komposisi sumber DI DALAM kategori itu "
                                "(100% = total kategori tersebut).")
    kat_pilih = None if pilihan == "Semua kategori" else pilihan

if tingkat == "Kategori":
    daftar_item = [(k, charts.kategori_label(k), charts.kategori_color(k, i)) for i, k in enumerate(kategori_data)]
    judul_sumbu = "Pangsa pembangkitan (%)"
else:
    kategori_tampil = [kat_pilih] if kat_pilih else kategori_data
    daftar_item = [(s, charts.sumber_label(s), charts.sumber_color(s, i)) for i, s in
                   enumerate(s for k in kategori_tampil for s in sumber_kat[k])]
    judul_sumbu = (f"Pangsa dalam kategori {charts.kategori_label(kat_pilih).lower()} (%)" if kat_pilih
                   else "Pangsa pembangkitan (%)")


def ambil(cat_df, src_df, tahun):
    """item -> (TWh, pangsa dibulatkan) pada satu tahun. Item tanpa baris data tidak dimasukkan."""
    if tingkat == "Kategori":
        d = cat_df[cat_df["year"] == tahun]
        return {r.kategori: (r.twh, r.pangsa_bulat) for r in d.itertuples()}
    d = src_df[src_df["year"] == tahun]
    if kat_pilih:
        d = d[d["kategori"] == kat_pilih]
        return {r.sumber: (r.twh, r.pangsa_kategori_bulat) for r in d.itertuples()}
    return {r.sumber: (r.twh, r.pangsa_total_bulat) for r in d.itertuples()}


def buat_seri(kolom_data):
    """kolom_data = list (label_batang, dict item -> (TWh, pangsa)). Satu seri per item."""
    seri = []
    for kunci, label, warna in daftar_item:
        nilai, hover = [], []
        for lab, d in kolom_data:
            if kunci in d:
                twh, pangsa = d[kunci]
                nilai.append(float(twh))
                hover.append(f"{label}<br>{lab}: {theme.fmt_pct(pangsa)} ({theme.fmt_num(float(twh), 1)} TWh)")
            else:
                nilai.append(None)
                hover.append(f"{label}<br>{lab}: tidak ada baris data")
        seri.append(dict(name=label, color=warna, values=nilai, hover=hover))
    return seri


tahun_list = sorted(int(y) for y in cat["year"].unique())
seri_tahun = buat_seri([(str(y), ambil(cat, src, y)) for y in tahun_list])
if any((v or 0) > 0 for s_ in seri_tahun for v in s_["values"]):
    st.plotly_chart(charts.stacked_share(tahun_list, seri_tahun, judul_sumbu), width="stretch")
else:
    st.info(f"Pada filter ini {('kategori ' + charts.kategori_label(kat_pilih).lower()) if kat_pilih else 'pilihan ini'} "
            f"bernilai 0 TWh pada semua tahun, sehingga komposisinya tidak terdefinisi dan tidak digambar.")
keterangan = ("Tinggi setiap batang = 100% dari total pembangkitan "
              + (f"kategori {charts.kategori_label(kat_pilih).lower()}" if kat_pilih else tren_label.lower())
              + " pada tahun itu; tiap segmen = TWh sumber atau kategori dibagi total, dikali 100 (bukan rata-rata "
                "antarnegara). Arahkan kursor ke segmen untuk melihat angka dan TWh-nya.")
if bandingkan and tingkat == "Kategori":
    perubahan = []
    for k in kategori_data:
        if k in cur.index and k in prev.index:
            perubahan.append(f"{charts.kategori_label(k).lower()} "
                             f"{theme.fmt_delta(float(cur.loc[k, 'pangsa_bulat']) - float(prev.loc[k, 'pangsa_bulat']), 1, ' poin')}")
    if perubahan:
        keterangan += f" Dari {base} ke {year}: " + ", ".join(perubahan) + " (pola dari data, bukan penyebabnya)."
st.caption(keterangan)

# ------------------------------------------------------------------ perbandingan dengan negara sorotan
iso = f["country"]
st.subheader(f"Perbandingan: {tren_label} dan negara sorotan, {year}")
cat_c = db.safe(queries.c_category_country, iso)
src_c = db.safe(queries.c_source_country, iso)
if cat_c.empty or year not in set(cat_c["year"]):
    st.info(f"{names.get(iso, iso)} tidak memiliki data bauran Ember pada {year}. Pilih negara sorotan lain di sidebar.")
else:
    batang = [(tren_label, ambil(cat, src, year)), (names.get(iso, iso), ambil(cat_c, src_c, year))]
    st.plotly_chart(charts.stacked_share([b[0] for b in batang], buat_seri(batang), judul_sumbu, horizontal=True),
                    width="stretch")
    st.caption("Dua batang memakai tingkat detail yang sama dengan grafik di atas. Batang negara sorotan tidak "
               "dipengaruhi filter benua dan kelompok negara. Segmen yang tidak digambar berarti tidak ada baris data "
               "untuk kategori atau sumber itu pada batang tersebut.")

# ------------------------------------------------------------------ treemap
st.subheader(f"Kontribusi sumber pembangkitan, {year}")
src_y = src[src["year"] == year]
gambar = charts.treemap_frame(src_y)
if gambar.empty:
    st.info("Tidak ada sumber dengan pembangkitan lebih dari 0 TWh pada filter ini.")
else:
    st.plotly_chart(charts.mix_treemap(src_y), width="stretch")
    dibuang = len(src_y) - len(gambar)
    st.caption("Luas = TWh pembangkitan; kategori sebagai induk dan sumber sebagai anak. Klik sebuah kategori untuk "
               "memperbesar sumber penyusunnya, dan klik bagian atas untuk kembali. "
               + (f"{dibuang} sumber bernilai 0 TWh pada filter ini tidak digambar karena tidak punya luas. "
                  if dibuang else "") +
               "Nilai 0 TWh tetap ada di data dan tabel.")

# ------------------------------------------------------------------ tabel ringkasan per sumber
st.subheader(f"Ringkasan per sumber, {year}")
baris_sumber = []
awal_idx = src[src["year"] == base].set_index(["kategori", "sumber"]) if bandingkan else None
akhir_idx = src_y.set_index(["kategori", "sumber"])
for k in kategori_data:
    for s in sumber_kat[k]:
        if (k, s) in akhir_idx.index:
            r = akhir_idx.loc[(k, s)]
            pa = float(awal_idx.loc[(k, s), "pangsa_total_bulat"]) if (awal_idx is not None and (k, s) in awal_idx.index) else None
            baris_sumber.append({"Kategori": charts.kategori_label(k), "Sumber": f"{charts.sumber_label(s)} ({s})",
                                 f"Pembangkitan {year} (TWh)": float(r["twh"]),
                                 "Pangsa total (%)": float(r["pangsa_total_bulat"]),
                                 "Pangsa dalam kategori (%)": float(r["pangsa_kategori_bulat"]),
                                 f"Pangsa total {base} (%)": pa,
                                 "Perubahan (poin)": (round(float(r["pangsa_total_bulat"]) - pa, 1) if pa is not None else None)})
        else:
            baris_sumber.append({"Kategori": charts.kategori_label(k), "Sumber": f"{charts.sumber_label(s)} ({s})",
                                 f"Pembangkitan {year} (TWh)": None, "Pangsa total (%)": None,
                                 "Pangsa dalam kategori (%)": None, f"Pangsa total {base} (%)": None,
                                 "Perubahan (poin)": None})
st.dataframe(pd.DataFrame(baris_sumber), hide_index=True, width="stretch", column_config={
    f"Pembangkitan {year} (TWh)": st.column_config.NumberColumn(format="%.1f"),
    "Pangsa total (%)": st.column_config.NumberColumn(format="%.1f"),
    "Pangsa dalam kategori (%)": st.column_config.NumberColumn(format="%.1f"),
    f"Pangsa total {base} (%)": st.column_config.NumberColumn(format="%.1f"),
    "Perubahan (poin)": st.column_config.NumberColumn(format="%.1f")})
st.caption("Sel kosong berarti tidak ada baris data untuk sumber itu pada filter ini; tidak diisi dengan 0.")

# ------------------------------------------------------------------ tabel detail negara x sumber
st.subheader(f"Detail per negara dan sumber, {year}")
daftar_negara = db.safe(queries.c_countries)
nama_ember = dict(zip(daftar_negara["iso3_code"], daftar_negara["country_name"]))
d1, d2, d3, d4 = st.columns([3, 2, 2, 2])
pilih = d1.multiselect("Negara (kosongkan untuk seluruh filter)", list(nama_ember), key="c_negara",
                       format_func=lambda i: nama_ember[i], **style.TEKS_PILIH_NEGARA)
kat_tabel = d2.selectbox("Kategori", ["Semua kategori"] + kategori_data, key="c_kat_tabel",
                         format_func=lambda k: k if k == "Semua kategori" else charts.kategori_label(k))
batas = d3.select_slider("Baris maksimum", options=[50, 100, 200, 500], value=100, key="c_batas")
tampil_nol = d4.toggle("Tampilkan baris 0 TWh", value=False, key="c_nol")
kat_param = None if kat_tabel == "Semua kategori" else kat_tabel
detail = db.safe(queries.c_detail, year, cont, grp, pilih, kat_param, tampil_nol, batas)
n_cocok = db.safe(queries.c_detail_count, year, cont, grp, pilih, kat_param, tampil_nol)
n_nol = (db.safe(queries.c_detail_count, year, cont, grp, pilih, kat_param, True) - n_cocok) if not tampil_nol else 0
if detail.empty:
    st.info("Tidak ada baris yang cocok dengan pilihan ini.")
else:
    tabel = pd.DataFrame({"Negara": detail["negara"], "Tahun": detail["tahun"].astype(int),
                          "Kategori": [charts.kategori_label(k) for k in detail["kategori"]],
                          "Sumber": [f"{charts.sumber_label(s)} ({s})" for s in detail["sumber"]],
                          "Pembangkitan (TWh)": detail["twh"], "Pangsa dalam negara (%)": detail["pangsa_negara"]})
    st.dataframe(tabel, hide_index=True, width="stretch", column_config={
        "Pembangkitan (TWh)": st.column_config.NumberColumn(format="%.1f"),
        "Pangsa dalam negara (%)": st.column_config.NumberColumn(format="%.1f")})
    st.download_button("Unduh tabel (CSV)", tabel.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"bauran_pembangkitan_{year}.csv", mime="text/csv")
    st.caption(f"Menampilkan {len(detail)} dari {n_cocok} baris, diurutkan dari pembangkitan terbesar"
               + (f"; sisanya tidak ditampilkan (naikkan batas atau pilih negara)" if n_cocok > len(detail) else "")
               + (f". {n_nol} baris 0 TWh disembunyikan (aktifkan 'Tampilkan baris 0 TWh' untuk melihatnya)"
                  if n_nol else "") + ". Sel kosong berarti tidak ada nilai di sumber; tidak diisi perkiraan.")

with st.expander("Cara membaca dan definisi"):
    st.markdown(
        "- **Bauran pembangkitan** adalah susunan total pembangkitan listrik menurut sumbernya, dalam **TWh** "
        "(terawatt-jam).\n"
        "- **Kategori** adalah pengelompokan sumber (fosil, nuklir, terbarukan); **sumber** adalah jenis "
        "pembangkitan yang menyusun kategori itu. Daftar keduanya diambil dari data.\n"
        "- **Batang 100% bertumpuk:** tinggi batang selalu 100%; lebar segmen menunjukkan pangsa. Pangsa dihitung dari "
        "jumlah TWh, bukan rata-rata antarnegara, sehingga negara besar berpengaruh lebih besar.\n"
        "- **Treemap:** luas persegi = TWh; kategori sebagai induk, sumber sebagai anak. Sumber bernilai 0 TWh tidak "
        "digambar, tetapi tetap ada di tabel.\n"
        "- **Pangsa dalam kategori** menunjukkan komposisi sumber di dalam satu kategori (100% = total kategori itu).\n"
        "- **Sumber data:** Ember. Negara tanpa data Ember tidak ikut dihitung dan tidak dianggap 0. Angka pangsa "
        "terbarukan di sini dapat berbeda dari halaman lain yang memakai Renewable Energy Share.\n"
        "- Dashboard menunjukkan pola deskriptif, bukan hubungan sebab-akibat.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka dibaca dari view `mart.v_generation_mix` memakai akun baca-saja `np_dashboard`. "
                "Parameter dikirim terpisah dari teks SQL.")
    st.markdown("**Bauran per sumber (pangsa total dan dalam kategori):**")
    st.code(queries.C_SOURCE_SQL, language="sql")
    st.markdown("**Bauran per kategori (kartu dan grafik):**")
    st.code(queries.C_CATEGORY_SQL, language="sql")
