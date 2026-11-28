"""Halaman B: Ketergantungan pada Fosil.
Pertanyaan bisnis: seberapa besar ketergantungan pembangkitan listrik pada sumber fosil, dan bagaimana perubahannya?
Sumber: mart.v_country_year (pangsa listrik dan energi primer dari Renewable Energy Share).
Tahun pembanding tetap (queries.BASE_YEAR), sama dengan halaman lain."""
import pandas as pd
import streamlit as st

import charts
import components
import db
import queries
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
opts = db.safe(queries.filter_options)
names = dict(opts["countries"])
UNK = queries.UNKNOWN_CONTINENT
COLOR_PRIMER = "#E69F00"
COLOR_BASE = "#B8B8B8"
cname = names.get(f["country"], f["country"])

chips = components.active_filter_chips(
    year, f["continents"], opts["continents"], f["groups"], opts["groups"], country_name=cname
)
components.hero_banner(
    "Ketergantungan pada Fosil",
    "Seberapa besar pembangkitan listrik bergantung pada sumber fosil dan bagaimana perbandingannya dengan energi primer.",
    chips=chips,
    variant="fossil",
)
st.caption("Sumber: Data Warehouse NP Energy Intelligence (Renewable Energy Share).")

kpi = db.safe(queries.b_kpi, f["continents"], f["groups"])
if kpi.empty or year not in set(kpi["year"]) or pd.isna(kpi.loc[kpi["year"] == year, "fosil_bulat"].iloc[0]):
    components.empty_state(components.filter_empty_message(f["continents"], f["groups"]))
    st.stop()

cur = kpi[kpi["year"] == year].iloc[0]
ada_awal = base in set(kpi["year"]) and pd.notna(kpi.loc[kpi["year"] == base, "fosil_bulat"].iloc[0])
bandingkan = year != base and ada_awal
prev = kpi[kpi["year"] == base].iloc[0] if bandingkan else None
n_total = 0 if pd.isna(cur["negara_total"]) else int(cur["negara_total"])
n_berbobot = 0 if pd.isna(cur["negara_berbobot"]) else int(cur["negara_berbobot"])
semua = (len(f["continents"]) == len(opts["continents"])) and (len(f["groups"]) == len(opts["groups"]))
scope_label = f"Dunia ({n_total} negara)" if semua else f"Negara terpilih ({n_total} negara)"
tren_label = "Dunia" if semua else "Negara terpilih"


def d_poin(kolom):
    """Selisih dari angka yang ditampilkan (sudah dibulatkan 1 desimal), aman terhadap NULL/NaN."""
    if not bandingkan or pd.isna(cur[kolom]) or pd.isna(prev[kolom]):
        return None
    return theme.fmt_delta(float(cur[kolom]) - float(prev[kolom]), 1, " poin")


# ------------------------------------------------------------------ kartu KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pangsa listrik fosil", theme.fmt_pct(cur["fosil_bulat"]), d_poin("fosil_bulat"), delta_color="inverse",
          help="Rata-rata tertimbang pembangkitan listrik. Penurunan ditampilkan hijau.")
c2.metric("Pangsa listrik terbarukan", theme.fmt_pct(cur["terbarukan_bulat"]), d_poin("terbarukan_bulat"),
          help="Rata-rata tertimbang pembangkitan listrik, dari himpunan negara yang sama dengan kartu fosil.")
c3.metric("Nuklir dan lainnya (sisa)", theme.fmt_pct(cur["sisa_tampil"]), d_poin("sisa_tampil"), delta_color="off",
          help="Sisa = 100 - pangsa fosil - pangsa terbarukan, dihitung dari angka yang tampil sehingga ketiga kartu "
               "berjumlah 100,0%. Mencakup nuklir dan sumber lain di luar dua kategori utama; bukan pangsa nuklir "
               "saja. Nilai tertimbang yang tidak dibulatkan dapat berbeda hingga 0,1 poin.")
c4.metric("Negara dalam perhitungan", f"{n_berbobot} dari {n_total}",
          help="Negara yang pangsa fosil dan terbarukannya terisi dan pembangkitannya lebih dari 0. Negara tanpa "
               "nilai tidak ikut dihitung dan tidak diisi dengan perkiraan.")
st.caption(f"{scope_label}. Tahun {year}" + (f" dibandingkan {base}." if bandingkan else
           f" (pilih tahun setelah {base} untuk melihat perubahan)."))

# ------------------------------------------------------------------ tren fosil vs terbarukan
st.subheader("Perkembangan pangsa fosil dan terbarukan")
components.micro_guide(
    "Amati jarak antara garis fosil (abu gelap) dan terbarukan (hijau) untuk melihat pergeseran porsi pembangkitan dari tahun ke tahun."
)
tahun_list = kpi["year"].astype(int).tolist()
seri = [dict(name="Pangsa fosil", values=kpi["fosil_bulat"].tolist(), color=theme.COLOR_FOSSIL, width=3),
        dict(name="Pangsa terbarukan", values=kpi["terbarukan_bulat"].tolist(), color=theme.COLOR_RENEWABLE, width=3)]
st.plotly_chart(charts.multi_trend(tahun_list, seri, "Pangsa listrik (%)"), width="stretch")
if bandingkan:
    st.caption(f"{tren_label}: dari {base} ke {year}, pangsa fosil berubah {d_poin('fosil_bulat')} dan pangsa "
               f"terbarukan berubah {d_poin('terbarukan_bulat')}. Keduanya tidak berjumlah 100% karena ada sumber "
               f"lain (nuklir dan lainnya: {theme.fmt_pct(cur['sisa_tampil'])} pada {year}). Garis menunjukkan pola "
               f"dari data, bukan penyebab perubahannya.")
    components.insight_box(
        f"Pada {tren_label.lower()} ({year}), pangsa fosil berada di {theme.fmt_pct(cur['fosil_bulat'])} "
        f"({d_poin('fosil_bulat')} terhadap {base}) dan terbarukan di {theme.fmt_pct(cur['terbarukan_bulat'])} "
        f"({d_poin('terbarukan_bulat')})."
    )
else:
    st.caption("Dua garis ditampilkan terpisah (tidak ditumpuk) karena keduanya tidak berjumlah 100%. "
               "Garis menunjukkan pola dari data, bukan penyebab perubahannya.")

# ------------------------------------------------------------------ perbandingan fosil: pembangkit terbesar (Grouped Bar / Dumbbell)
st.subheader("Pangsa fosil pada negara dengan pembangkitan listrik terbesar")
ctrl1, ctrl2 = st.columns([2, 3])
with ctrl1:
    n_top = st.radio("Jumlah negara", [5, 10, 15], index=1, horizontal=True, key="b_topn")
with ctrl2:
    mode_b = st.radio("Tampilan grafik", ["Batang berdampingan", "Garis rentang (Dumbbell)"], index=0, horizontal=True, key="b_chart_mode",
                      help="Batang berdampingan memudahkan perbandingan langsung dua tahun; Garis rentang menonjolkan jarak perubahannya.")
if not bandingkan:
    st.info(f"Pilih tahun setelah {base} di sidebar untuk membandingkan pangsa fosil dengan {base}.")
else:
    top = db.safe(queries.b_topn, year, f["continents"], f["groups"], n_top)
    if top.empty:
        components.empty_state("Tidak ada negara yang memenuhi filter ini.")
    else:
        top = top.copy()
        top["label"] = [n + (" ★" if iso == f["country"] else "") for iso, n in zip(top["iso3_code"], top["country_name"])]
        components.micro_guide(
            f"Batang abu muda menunjukkan pangsa fosil {base} dan batang gelap menunjukkan {year}; urutan daftar mengikuti total pembangkitan listrik terbesar."
        )
        if mode_b == "Batang berdampingan":
            st.plotly_chart(charts.grouped_fossil_bar(top, base, year), width="stretch")
        else:
            st.plotly_chart(charts.dumbbell(top, "label", "fosil_awal", "fosil_tahun", str(base), str(year),
                                            COLOR_BASE, theme.COLOR_FOSSIL, "Pangsa listrik fosil (%)"), width="stretch")
        ok = top.dropna(subset=["fosil_awal", "fosil_tahun"])
        turun, naik, sama = int((ok["perubahan"] < 0).sum()), int((ok["perubahan"] > 0).sum()), int((ok["perubahan"] == 0).sum())
        tanpa = len(top) - len(ok)
        st.caption(f"Negara diurutkan menurut pembangkitan listrik {year} dari yang terbesar, bukan menurut pangsa fosil. "
                   f"Dari {len(top)} negara: {turun} berpangsa fosil lebih rendah daripada {base}, {naik} lebih tinggi, "
                   f"{sama} sama" + (f"; {tanpa} tanpa data pada salah satu tahun" if tanpa else "") +
                   f". Abu-abu muda = {base}, gelap = {year}. Tanda ★ = negara sorotan di sidebar (jika masuk "
                   f"daftar).")
        with st.expander("Lihat angka"):
            st.dataframe(pd.DataFrame({
                "Negara": top["country_name"], f"Pembangkitan {year} (TWh)": top["pembangkitan_twh"],
                f"Pangsa fosil {base} (%)": top["fosil_awal"], f"Pangsa fosil {year} (%)": top["fosil_tahun"],
                "Perubahan (poin)": top["perubahan"]}), hide_index=True, width="stretch", column_config={
                f"Pembangkitan {year} (TWh)": st.column_config.NumberColumn(format="%.1f"),
                f"Pangsa fosil {base} (%)": st.column_config.NumberColumn(format="%.1f"),
                f"Pangsa fosil {year} (%)": st.column_config.NumberColumn(format="%.1f"),
                "Perubahan (poin)": st.column_config.NumberColumn(format="%.1f")})

# ------------------------------------------------------------------ listrik vs energi primer
st.subheader("Pangsa terbarukan: listrik vs energi primer")
cov = db.safe(queries.b_coverage, year)
n_all = 0 if cov.empty else int(cov["negara"].sum())
n_primer = 0 if cov.empty else int(cov["berdata_primer"].sum())
n_pasang = 0 if cov.empty else int(cov["pasangan_valid"].sum())
st.info(f"Cakupan energi primer: {n_primer} negara pada {year} (dari {n_all} negara di data). Sebanyak {n_pasang} di "
        f"antaranya juga punya pangsa listrik sehingga dapat dibandingkan. Sampel ini tidak mewakili seluruh dunia, "
        f"jadi tidak ada angka agregat dunia atau benua untuk energi primer; yang ditampilkan adalah nilai per negara.")
if not cov.empty:
    urut = sorted(cov["benua"], key=lambda b: (b == UNK, b))
    cov_t = cov.set_index("benua").loc[urut].reset_index()
    cov_t["persen"] = cov_t["berdata_primer"] / cov_t["negara"] * 100
    with st.expander("Sebaran cakupan energi primer per benua (seluruh negara, tidak dipengaruhi filter)"):
        st.dataframe(pd.DataFrame({"Benua": cov_t["benua"], "Jumlah negara": cov_t["negara"],
                                   "Berdata energi primer": cov_t["berdata_primer"],
                                   "Persentase (%)": cov_t["persen"]}), hide_index=True, width="stretch",
                     column_config={"Persentase (%)": st.column_config.NumberColumn(format="%.1f")})

pairs = db.safe(queries.b_pairs, year, f["continents"], f["groups"])
if pairs.empty:
    components.empty_state("Tidak ada negara berdata energi primer pada filter ini.")
else:
    valid = pairs[pairs["terbarukan_listrik"].notna()].copy()
    n_pair = st.selectbox("Jumlah negara pada grafik", [5, 10, 15, 20], index=1, key="b_pair_n",
                          help="Negara berpasangan data dengan pembangkitan listrik terbesar pada tahun terpilih.")
    if valid.empty:
        components.empty_state("Tidak ada negara berpasangan data pada filter ini.")
    else:
        g = valid.head(n_pair).copy()
        g["label"] = [n + (" ★" if iso == f["country"] else "") for iso, n in zip(g["iso3_code"], g["country_name"])]
        st.plotly_chart(charts.dumbbell(g, "label", "terbarukan_listrik", "terbarukan_primer",
                                        "Pangsa terbarukan pada listrik", "Pangsa terbarukan pada energi primer",
                                        theme.COLOR_RENEWABLE, COLOR_PRIMER, "Pangsa terbarukan (%)"), width="stretch")
        rendah, sama_p, tinggi = (int((valid["selisih"] > 0).sum()), int((valid["selisih"] == 0).sum()),
                                  int((valid["selisih"] < 0).sum()))
        kosong = pairs[pairs["terbarukan_listrik"].isna()]
        st.caption(f"Dari {len(valid)} negara berpasangan data pada filter ini: {rendah} berpangsa energi primer lebih "
                   f"rendah daripada pangsa listrik, {sama_p} sama (pada 1 desimal), {tinggi} lebih tinggi. "
                   f"Negara diurutkan menurut pembangkitan listrik {year}." +
                   (f" Tanpa pangsa listrik pada {year} (tidak disertakan pada grafik, tidak diisi 0): "
                    f"{', '.join(kosong['country_name'])}." if len(kosong) else "") +
                   " Pangsa energi primer mencakup seluruh penggunaan energi, bukan hanya listrik, sehingga "
                   "penyebutnya berbeda dan kedua angka tidak setara; selisihnya hanya menunjukkan perbedaan "
                   "keduanya, tanpa menjelaskan penyebabnya.")
        tabel = pd.DataFrame({
            "Negara": pairs["country_name"], "Benua": pairs["benua"],
            f"Terbarukan pada listrik {year} (%)": pairs["terbarukan_listrik"],
            f"Terbarukan pada energi primer {year} (%)": pairs["terbarukan_primer"],
            "Selisih listrik - energi primer (poin)": pairs["selisih"],
            f"Pembangkitan {year} (TWh)": pairs["pembangkitan_twh"],
            "Keterangan": ["Pangsa listrik kosong" if pd.isna(a) else ("Sama" if s == 0 else "")
                           for a, s in zip(pairs["terbarukan_listrik"], pairs["selisih"])]})
        st.dataframe(tabel, hide_index=True, width="stretch", column_config={
            f"Terbarukan pada listrik {year} (%)": st.column_config.NumberColumn(format="%.1f"),
            f"Terbarukan pada energi primer {year} (%)": st.column_config.NumberColumn(format="%.1f"),
            "Selisih listrik - energi primer (poin)": st.column_config.NumberColumn(format="%.1f"),
            f"Pembangkitan {year} (TWh)": st.column_config.NumberColumn(format="%.1f")})
        st.caption("Sel kosong berarti tidak ada nilai di sumber data; nilai tidak diisi dengan perkiraan.")

with st.expander("Cara membaca dan definisi"):
    st.markdown(
        "- **Pangsa fosil dan terbarukan (kartu dan tren)** dihitung tertimbang pembangkitan listrik pada himpunan "
        "negara yang sama, sehingga negara besar berpengaruh lebih besar.\n"
        "- **Nuklir dan lainnya (sisa)** = 100 - fosil - terbarukan; bukan pangsa nuklir saja.\n"
        "- **Perubahan** dalam **poin persentase**, dihitung dari angka yang ditampilkan (dibulatkan 1 desimal).\n"
        "- **Energi primer** hanya tersedia untuk sebagian negara, dan tidak diagregasi; bobot energi primer tidak "
        "dicampur dengan bobot pembangkitan listrik.\n"
        "- Dashboard menunjukkan pola deskriptif, bukan sebab-akibat.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka dibaca dari view `mart.v_country_year` memakai akun baca-saja `np_dashboard`. "
                "Parameter dikirim terpisah dari teks SQL.")
    st.markdown("**KPI dan tren (fosil, terbarukan, sisa):**")
    st.code(queries.B_KPI_SQL, language="sql")
    st.markdown("**Negara dengan pembangkitan terbesar (perbandingan fosil):**")
    st.code(queries.B_TOPN_SQL, language="sql")
