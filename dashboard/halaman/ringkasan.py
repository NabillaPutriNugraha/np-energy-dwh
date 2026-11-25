"""Halaman Ringkasan: 4 kartu KPI, 2 grafik tren, peringkat perubahan pangsa, dan peta."""
import streamlit as st

import charts
import db
import queries
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
opts = db.safe(queries.filter_options)
names = dict(opts["countries"])

st.title("Ringkasan Transisi Energi Global")
st.caption("Pangsa listrik terbarukan, ketergantungan pada fosil, dan intensitas emisi listrik, 2019-2023. "
           "Sumber: Data Warehouse NP Energy Intelligence.")

kpi = db.safe(queries.kpi_by_year, f["continents"], f["groups"])
if kpi.empty or year not in set(kpi["year"]):
    st.info("Tidak ada negara yang memenuhi filter. Pilih minimal satu benua dan satu kelompok negara di sidebar.")
    st.stop()

cur = kpi[kpi["year"] == year].iloc[0]
prev = kpi[kpi["year"] == base].iloc[0] if (year != base and base in set(kpi["year"])) else None
n_total = int(cur["negara_total"])
semua = (len(f["continents"]) == len(opts["continents"])) and (len(f["groups"]) == len(opts["groups"]))
scope_label = f"Dunia ({n_total} negara)" if semua else f"Negara terpilih ({n_total} negara)"
tren_label = "Dunia" if semua else "Negara terpilih"


def delta(col, dec, unit):
    """Selisih dihitung dari angka yang DITAMPILKAN (sudah dibulatkan), agar pembaca yang mengurangkan
    angka di kartu dan grafik mendapat hasil yang sama."""
    if prev is None:
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
c4.metric("Cakupan negara", f"{int(cur['negara_pangsa'])} dari {n_total}",
          help="Negara yang memiliki nilai pangsa listrik pada tahun terpilih. "
               "Negara tanpa nilai tidak ikut dihitung dan tidak diisi dengan perkiraan.")
st.caption(f"{scope_label}. Tahun {year}" + (f" dibandingkan {base}." if prev is not None else
           f" (pilih tahun setelah {base} untuk melihat perubahan)."))

years = kpi["year"].astype(int).tolist()
country = db.safe(queries.country_series, f["country"])
cname = names.get(f["country"], f["country"])
ccol = country.set_index("year")

st.subheader("Tren 2019-2023")
t1, t2 = st.columns(2)
with t1:
    st.markdown("**Pangsa listrik terbarukan**")
    st.plotly_chart(charts.trend_chart(
        years, kpi["terbarukan"].tolist(), tren_label,
        [ccol["terbarukan"].get(y) for y in years], cname, theme.LABEL["terbarukan"],
        theme.COLOR_RENEWABLE, 1, "%"), width="stretch")
with t2:
    st.markdown("**Intensitas emisi listrik**")
    st.plotly_chart(charts.trend_chart(
        years, kpi["intensitas"].tolist(), tren_label,
        [ccol["intensitas"].get(y) for y in years], cname, theme.LABEL["intensitas"],
        theme.COLOR_INTENSITY, 0, ""), width="stretch")
st.caption(f"Garis tebal = {tren_label.lower()} (tertimbang pembangkitan); garis putus-putus = {cname}.")

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
            st.info("Tidak ada negara yang memenuhi filter dan ambang pembangkitan ini.")
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
    if peta.empty:
        st.info("Tidak ada data pangsa untuk filter ini.")
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
