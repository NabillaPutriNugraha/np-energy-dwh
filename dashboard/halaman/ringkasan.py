"""Halaman Ringkasan: Hero Banner, 4 kartu KPI, 2 grafik tren spline berarsiran, peringkat perubahan pangsa, dan peta."""
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
cname = names.get(f["country"], f["country"])

chips = components.active_filter_chips(
    year, f["continents"], opts["continents"], f["groups"], opts["groups"], country_name=cname
)
components.hero_banner(
    "Ringkasan Transisi Energi Global",
    "Pangsa listrik terbarukan, ketergantungan pada fosil, dan intensitas emisi listrik (2019–2023).",
    chips=chips,
    variant="eco",
)
st.caption("Sumber: Data Warehouse NP Energy Intelligence (Renewable Energy Share & Ember).")

kpi = db.safe(queries.kpi_by_year, f["continents"], f["groups"])
if kpi.empty or year not in set(kpi["year"]):
    components.empty_state(components.filter_empty_message(f["continents"], f["groups"]))
    st.stop()

cur = kpi[kpi["year"] == year].iloc[0]
prev = kpi[kpi["year"] == base].iloc[0] if (year != base and base in set(kpi["year"])) else None
n_total = 0 if pd.isna(cur["negara_total"]) else int(cur["negara_total"])
n_pangsa = 0 if pd.isna(cur["negara_pangsa"]) else int(cur["negara_pangsa"])
semua = (len(f["continents"]) == len(opts["continents"])) and (len(f["groups"]) == len(opts["groups"]))
scope_label = f"Dunia ({n_total} negara)" if semua else f"Negara terpilih ({n_total} negara)"
tren_label = "Dunia" if semua else "Negara terpilih"


def delta(col, dec, unit):
    """Selisih dihitung dari angka yang DITAMPILKAN (sudah dibulatkan), aman terhadap nilai NULL/NaN."""
    if prev is None or pd.isna(cur[col]) or pd.isna(prev[col]):
        return None
    return theme.fmt_delta(round(float(cur[col]), dec) - round(float(prev[col]), dec), dec, unit)


c1, c2, c3, c4 = st.columns(4)
c1.metric("Pangsa listrik terbarukan", theme.fmt_pct(cur["terbarukan"]), delta("terbarukan", 1, " poin"),
          help="Rata-rata tertimbang pembangkitan listrik: SUM(pangsa x pembangkitan) / SUM(pembangkitan), "
               "hanya negara yang punya nilai. Selisih dihitung dari angka yang ditampilkan.")
c2.metric("Pangsa listrik fosil", theme.fmt_pct(cur["fosil"]), delta("fosil", 1, " poin"),
          delta_color="inverse",
          help="Rata-rata tertimbang pembangkitan listrik. Penurunan ditampilkan hijau.")
c3.metric("Intensitas emisi (gCO₂e/kWh)", theme.fmt_num(cur["intensitas"]), delta("intensitas", 0, ""),
          delta_color="inverse",
          help="Rata-rata tertimbang total pembangkitan (sumber: Ember). Penurunan ditampilkan hijau.")
c4.metric("Cakupan negara", f"{n_pangsa} dari {n_total}",
          help="Negara yang memiliki nilai pangsa listrik pada tahun terpilih. "
               "Negara tanpa nilai tidak ikut dihitung dan tidak diisi dengan perkiraan.")
st.caption(f"{scope_label}. Tahun {year}" + (f" dibandingkan {base}." if prev is not None else
           f" (pilih tahun setelah {base} untuk melihat perubahan)."))

years = kpi["year"].astype(int).tolist()
country = db.safe(queries.country_series, f["country"])
ccol = country.set_index("year") if not country.empty else pd.DataFrame()

st.subheader("Tren 2019–2023")
components.micro_guide(
    f"Bandingkan garis tebal berarsiran ({tren_label.lower()}, tertimbang pembangkitan) dengan garis putus-putus ({cname}) untuk melihat posisi relatif terhadap tren wilayah."
)
t1, t2 = st.columns(2)
with t1:
    st.markdown("**Pangsa listrik terbarukan**")
    c_ren = [ccol["terbarukan"].get(y) if "terbarukan" in ccol.columns else None for y in years]
    st.plotly_chart(charts.trend_chart(
        years, kpi["terbarukan"].tolist(), tren_label,
        c_ren, cname, theme.LABEL["terbarukan"],
        theme.COLOR_RENEWABLE, 1, "%"), width="stretch")
with t2:
    st.markdown("**Intensitas emisi listrik**")
    c_int = [ccol["intensitas"].get(y) if "intensitas" in ccol.columns else None for y in years]
    st.plotly_chart(charts.trend_chart(
        years, kpi["intensitas"].tolist(), tren_label,
        c_int, cname, theme.LABEL["intensitas"],
        theme.COLOR_INTENSITY, 0, ""), width="stretch")
st.caption(f"Garis tebal = {tren_label.lower()} (tertimbang pembangkitan); garis putus-putus = {cname}.")

if prev is not None and pd.notna(cur["terbarukan"]) and pd.notna(prev["terbarukan"]):
    d_ren = delta("terbarukan", 1, " poin")
    d_int = delta("intensitas", 0, " gCO₂e/kWh")
    bagian_int = f", sementara intensitas emisi berubah {d_int}" if d_int else ""
    components.insight_box(
        f"Pada cakupan {tren_label.lower()} ({base} ke {year}), pangsa listrik terbarukan tercatat "
        f"{theme.fmt_pct(cur['terbarukan'])} ({d_ren}){bagian_int}."
    )

g1, g2 = st.columns(2)
with g1:
    st.subheader("Kenaikan pangsa terbarukan terbesar")
    min_twh = st.select_slider("Pembangkitan listrik minimum (TWh)", options=[0, 1, 5, 10, 25, 50, 100],
                               value=10, key="min_twh")
    if prev is None:
        st.info(f"Pilih tahun setelah {base} di sidebar untuk melihat perubahan pangsa.")
    else:
        pool = db.safe(queries.movers_pool, year, f["continents"], f["groups"], min_twh)
        top = db.safe(queries.movers, year, f["continents"], f["groups"], min_twh)
        if top.empty:
            components.empty_state(
                "Tidak ada negara yang memenuhi filter dan ambang pembangkitan ini.",
                hint="Turunkan ambang pembangkitan minimum (TWh) atau perluas pilihan benua/kelompok di sidebar.",
            )
        else:
            st.plotly_chart(charts.movers_bar(top), width="stretch")
        st.caption(
            f"Perubahan pangsa {base} ke {year} (poin persentase). Ambang pembangkitan minimum {min_twh} TWh "
            f"(pembangkitan tahun {year}) adalah keputusan desain untuk mengurangi dominasi negara dengan "
            f"volume pembangkitan sangat kecil; ini bukan standar atau batas ilmiah. {pool} negara memenuhi "
            f"ambang ini. Ubah nilainya untuk melihat dampaknya pada peringkat.")
with g2:
    st.subheader(f"Peta pangsa listrik terbarukan {year}")
    peta = db.safe(queries.map_data, year, f["continents"], f["groups"])
    tanpa_batas = (
        peta.empty
        or set(f["continents"]) == {queries.UNKNOWN_CONTINENT}
        or (peta["iso3_code"].dropna().astype(str).str.len() != 3).all()
    )
    if tanpa_batas:
        components.empty_state(
            "Peta tidak tersedia untuk wilayah tanpa batas negara.",
            hint="Pilih satu atau lebih benua di panel Filter untuk menampilkan peta choropleth.",
        )
    else:
        st.plotly_chart(charts.share_map(peta), width="stretch")
    st.caption("Negara tanpa data pangsa tidak diwarnai. Peta mungkin memerlukan koneksi internet "
               "untuk memuat batas negara.")

with st.expander("Cara membaca dan definisi KPI"):
    st.markdown(
        "- **Pangsa listrik terbarukan dan fosil** serta **intensitas emisi** untuk banyak negara dihitung sebagai "
        "rata-rata **tertimbang pembangkitan**, sehingga negara besar berpengaruh lebih besar daripada negara kecil.\n"
        "- **Perubahan** pangsa dinyatakan dalam **poin persentase**, bukan persen.\n"
        "- Pangsa fosil dan terbarukan tidak berjumlah 100% karena ada sumber lain (misalnya nuklir).\n"
        "- Sumber pangsa dan pembangkitan listrik: Renewable Energy Share. Sumber intensitas emisi: Ember. "
        "Kedua sumber berbeda untuk beberapa negara; lihat halaman Kualitas Data.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka di halaman ini dibaca dari view `mart.v_country_year` di PostgreSQL "
                "memakai akun baca-saja `np_dashboard`. Query KPI (parameter benua dan kelompok dikirim terpisah):")
    st.code(queries.KPI_SQL, language="sql")
