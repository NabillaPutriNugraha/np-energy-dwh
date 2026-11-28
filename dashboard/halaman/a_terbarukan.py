"""Halaman A: Perkembangan Energi Terbarukan.
Pertanyaan bisnis: bagaimana pangsa listrik terbarukan berkembang per negara, benua, dan kelompok negara?
Sumber: mart.v_country_year (pangsa dan pembangkitan listrik dari Renewable Energy Share)."""
import pandas as pd
import streamlit as st

import charts
import components
import db
import queries
import style
import theme

f = queries.current_filters()
year, base = f["year"], queries.BASE_YEAR
opts = db.safe(queries.filter_options)
names = dict(opts["countries"])
isos = [iso for iso, _ in opts["countries"]]
UNK = queries.UNKNOWN_CONTINENT
cname = names.get(f["country"], f["country"])

chips = components.active_filter_chips(
    year, f["continents"], opts["continents"], f["groups"], opts["groups"], country_name=cname
)
components.hero_banner(
    "Perkembangan Energi Terbarukan",
    "Bagaimana pangsa listrik terbarukan berkembang per negara, benua, dan kelompok negara (2019–2023).",
    chips=chips,
    variant="eco",
)
st.caption("Sumber: Data Warehouse NP Energy Intelligence (Renewable Energy Share).")

kpi = db.safe(queries.kpi_by_year, f["continents"], f["groups"])
if kpi.empty or year not in set(kpi["year"]):
    components.empty_state(components.filter_empty_message(f["continents"], f["groups"]))
    st.stop()
stats = db.safe(queries.stats_by_year, f["continents"], f["groups"]).set_index("year")
if year not in stats.index:
    components.empty_state(
        "Tidak ada negara yang memenuhi filter untuk tahun terpilih. Ubah filter di sidebar."
    )
    st.stop()

cur, s_cur = kpi[kpi["year"] == year].iloc[0], stats.loc[year]
bandingkan = year != base and base in set(kpi["year"]) and base in stats.index
prev, s_prev = (kpi[kpi["year"] == base].iloc[0], stats.loc[base]) if bandingkan else (None, None)
n_total = 0 if pd.isna(cur["negara_total"]) else int(cur["negara_total"])
n_pangsa = 0 if pd.isna(cur["negara_pangsa"]) else int(cur["negara_pangsa"])
n_ge50_cur = 0 if pd.isna(s_cur["n_ge50"]) else int(s_cur["n_ge50"])
n_ge50_prev = (0 if pd.isna(s_prev["n_ge50"]) else int(s_prev["n_ge50"])) if bandingkan else None
semua = (len(f["continents"]) == len(opts["continents"])) and (len(f["groups"]) == len(opts["groups"]))
scope_label = f"Dunia ({n_total} negara)" if semua else f"Negara terpilih ({n_total} negara)"
tren_label = "Dunia" if semua else "Negara terpilih"


def d_poin(a, b):
    """Selisih dari angka yang ditampilkan (dibulatkan 1 desimal), aman terhadap NULL/NaN."""
    if not bandingkan or pd.isna(a) or pd.isna(b):
        return None
    return theme.fmt_delta(round(float(a), 1) - round(float(b), 1), 1, " poin")


def _badge_status(val):
    if pd.isna(val) or not str(val).strip():
        return "-"
    teks = str(val).strip()
    if teks == "Valid lengkap":
        return "✓ Valid lengkap"
    if "kosong" in teks.lower():
        return f"⚠ {teks}"
    return teks


# ------------------------------------------------------------------ kartu KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pangsa listrik terbarukan", theme.fmt_pct(cur["terbarukan"]),
          d_poin(cur["terbarukan"], prev["terbarukan"]) if bandingkan else None,
          help="Rata-rata tertimbang pembangkitan listrik (sama dengan halaman Ringkasan). "
               "Selisih dihitung dari angka yang ditampilkan.")
c2.metric("Median antarnegara", theme.fmt_pct(s_cur["median"]),
          d_poin(s_cur["median"], s_prev["median"]) if bandingkan else None,
          help="Nilai tengah pangsa antarnegara tanpa pembobotan: setengah dari negara bernilai berada di "
               "bawah angka ini. Berbeda dari angka tertimbang di sebelah kiri karena setiap negara berbobot sama.")
c3.metric("Negara berpangsa 50% atau lebih", f"{n_ge50_cur} negara",
          f"{n_ge50_cur - n_ge50_prev:+d} negara" if (bandingkan and n_ge50_prev is not None) else None,
          help="Jumlah negara yang pangsa terbarukannya (dibulatkan 1 desimal) mencapai 50% atau lebih.")
c4.metric("Cakupan negara", f"{n_pangsa} dari {n_total}",
          help="Negara yang punya nilai pangsa listrik pada tahun terpilih. Negara tanpa nilai tidak ikut "
               "dihitung dan tidak diisi dengan perkiraan.")
st.caption(f"{scope_label}. Tahun {year}" + (f" dibandingkan {base}." if bandingkan else
           f" (pilih tahun setelah {base} untuk melihat perubahan)."))

# ------------------------------------------------------------------ tren dengan drill-down
st.subheader("Tren pangsa listrik terbarukan")
level = st.radio("Tingkat tampilan", ["Dunia", "Benua", "Negara"], horizontal=True, key="a_level",
                 help="Dunia: satu garis agregat. Benua: satu garis per benua. Negara: bandingkan hingga 8 negara.")
years = kpi["year"].astype(int).tolist()
referensi = dict(name=tren_label, values=kpi["terbarukan"].tolist(), color=theme.COLOR_RENEWABLE, width=4)


def nilai_per_tahun(df, kolom="pangsa"):
    if df.empty or kolom not in df.columns:
        return [None] * len(years)
    return df.set_index("year")[kolom].reindex(years).tolist()


if level == "Dunia":
    components.micro_guide(
        f"Pilih tingkat Benua atau Negara di atas untuk memecah tren agregat {tren_label.lower()} menjadi perbandingan antarwilayah."
    )
    sorot = db.safe(queries.countries_series, [f["country"]])
    seri = [referensi, dict(name=cname, values=nilai_per_tahun(sorot),
                            color=theme.COLOR_HIGHLIGHT, dash="dash", width=2)]
    st.plotly_chart(charts.multi_trend(years, seri, theme.LABEL["terbarukan"]), width="stretch")
    st.caption(f"Garis hijau tebal = {tren_label.lower()} (tertimbang pembangkitan); garis putus-putus = "
               f"{cname} (negara sorotan di sidebar).")

elif level == "Benua":
    components.micro_guide(
        "Setiap garis mewakili pangsa tertimbang pembangkitan per benua; bandingkan terhadap garis hijau tebal sebagai acuan agregat."
    )
    cont = db.safe(queries.continent_series, f["continents"], f["groups"])
    if cont.empty:
        components.empty_state("Tidak ada data tren benua untuk filter ini.")
    else:
        urut = sorted(cont["benua"].unique(), key=lambda b: (b == UNK, b))
        seri = [referensi]
        for benua in urut:
            g = cont[cont["benua"] == benua]
            n_now = g.loc[g["year"] == year, "negara"]
            label = f"{benua} ({int(n_now.iloc[0])} negara)" if len(n_now) and pd.notna(n_now.iloc[0]) else benua
            if benua == UNK:
                seri.append(dict(name=label + ", bukan pembanding", values=nilai_per_tahun(g, "terbarukan"),
                                 color=charts.CONTINENT_COLORS[UNK], dash="dot", width=1.5, marker=5))
            else:
                seri.append(dict(name=label, values=nilai_per_tahun(g, "terbarukan"),
                                 color=charts.CONTINENT_COLORS.get(benua, "#666666"), width=2.5))
        st.plotly_chart(charts.multi_trend(years, seri, theme.LABEL["terbarukan"], height=400), width="stretch")

        # tabel benua pada tahun terpilih (detail drill-down)
        now = cont[cont["year"] == year].set_index("benua")
        awal = cont[cont["year"] == base].set_index("benua") if bandingkan else None
        baris = []
        for benua in urut:
            if benua not in now.index:
                continue
            p_now = now.loc[benua, "terbarukan"]
            p_awal = awal.loc[benua, "terbarukan"] if (awal is not None and benua in awal.index) else float("nan")
            selisih = (round(float(p_now), 1) - round(float(p_awal), 1)) if bandingkan and pd.notna(p_now) and pd.notna(p_awal) else None
            baris.append({"Benua": benua, "Negara": int(now.loc[benua, "negara"]),
                          "Negara berdata pangsa": int(now.loc[benua, "negara_pangsa"]),
                          f"Pangsa {base} (%)": None if not bandingkan else (None if pd.isna(p_awal) else float(p_awal)),
                          f"Pangsa {year} (%)": None if pd.isna(p_now) else float(p_now),
                          "Perubahan (poin)": selisih})
        st.dataframe(pd.DataFrame(baris), hide_index=True, width="stretch", column_config={
            f"Pangsa {base} (%)": st.column_config.NumberColumn(format="%.1f"),
            f"Pangsa {year} (%)": st.column_config.NumberColumn(format="%.1f"),
            "Perubahan (poin)": st.column_config.NumberColumn(format="%.1f")})
        if UNK in now.index:
            st.caption(f"'{UNK}' adalah {int(now.loc[UNK, 'negara'])} negara yang tidak memiliki atribut benua di sumber data "
                       f"({int(now.loc[UNK, 'negara_pangsa'])} di antaranya punya nilai pangsa). Kategori ini ditampilkan "
                       f"terpisah (abu-abu putus-putus) dan tidak dipakai sebagai pembanding antar-benua. "
                       f"Garis hijau tebal = {tren_label.lower()} sebagai acuan.")
        else:
            st.caption(f"Garis hijau tebal = {tren_label.lower()} sebagai acuan. Pangsa tiap benua dihitung tertimbang pembangkitan.")

else:  # Negara
    if "a_countries" not in st.session_state:   # pilihan awal: negara sorotan + 5 pembangkit terbesar
        top = db.safe(queries.top_generators, year, 5)
        st.session_state["a_countries"] = list(dict.fromkeys([f["country"]] + top["iso3_code"].tolist()))[:8]
    pilih = st.multiselect("Negara yang dibandingkan (maksimal 8)", isos, format_func=lambda i: names[i],
                           key="a_countries", max_selections=8, **style.TEKS_PILIH_NEGARA)
    if not pilih:
        components.empty_state("Pilih minimal satu negara untuk ditampilkan.")
    else:
        data = db.safe(queries.countries_series, pilih)
        seri = [referensi]
        for i, iso in enumerate(pilih):
            g = data[data["iso3_code"] == iso]
            seri.append(dict(name=names[iso], values=nilai_per_tahun(g),
                             color=charts.LINE_COLORS[i % len(charts.LINE_COLORS)], width=2.5))
        st.plotly_chart(charts.multi_trend(years, seri, theme.LABEL["terbarukan"], height=400), width="stretch")
        st.caption(f"Pilihan negara tidak dipengaruhi filter benua dan kelompok. Garis hijau tebal = "
                   f"{tren_label.lower()} (sesuai filter). Celah pada garis berarti negara itu tidak punya nilai "
                   f"pada tahun tersebut.")

if pd.notna(cur["terbarukan"]) and pd.notna(s_cur["median"]):
    components.insight_box(
        f"Pada {year}, pangsa tertimbang {tren_label.lower()} sebesar {theme.fmt_pct(cur['terbarukan'])} "
        f"dibandingkan median antarnegara {theme.fmt_pct(s_cur['median'])}, dengan {n_ge50_cur} negara mencapai pangsa 50% atau lebih."
    )

# ------------------------------------------------------------------ peringkat
st.subheader(f"Peringkat pangsa listrik terbarukan {year}")
components.micro_guide(
    "Geser ambang pembangkitan minimum untuk menyaring negara bervolume sangat kecil; gunakan tab Tertinggi (hijau) dan Terendah (merah coral)."
)
min_twh = st.select_slider("Pembangkitan listrik minimum (TWh)", options=[0, 1, 5, 10, 25, 50, 100],
                           value=10, key="a_min_twh")
ties_df = db.safe(queries.ranking_ties, year, f["continents"], f["groups"], min_twh)
ties = ties_df.iloc[0] if not ties_df.empty else None
n_pool = 0 if (ties is None or pd.isna(ties["n_pool"])) else int(ties["n_pool"])
if n_pool == 0:
    components.empty_state(
        "Tidak ada negara yang memenuhi filter dan ambang pembangkitan ini.",
        hint="Turunkan ambang pembangkitan minimum (TWh) atau pilih lebih banyak benua/kelompok di sidebar.",
    )
else:
    tab_atas, tab_bawah = st.tabs(["Tertinggi", "Terendah"])
    with tab_atas:
        st.plotly_chart(charts.rank_bar(db.safe(queries.ranking, year, f["continents"], f["groups"], min_twh, "atas"),
                                        color=theme.COLOR_RENEWABLE), width="stretch")
    with tab_bawah:
        st.plotly_chart(charts.rank_bar(db.safe(queries.ranking, year, f["continents"], f["groups"], min_twh, "bawah"),
                                        color=theme.COLOR_CORAL), width="stretch")
    st.caption(
        f"Dari {n_pool} negara yang memenuhi ambang, {int(ties['n_tertinggi'])} berpangsa "
        f"{theme.fmt_pct(ties['nilai_tertinggi'])} (tertinggi) dan {int(ties['n_terendah'])} berpangsa "
        f"{theme.fmt_pct(ties['nilai_terendah'])} (terendah). Nilai seri diurutkan menurut pembangkitan terbesar. "
        f"Ambang pembangkitan minimum {min_twh} TWh (pembangkitan tahun {year}) adalah keputusan desain untuk "
        f"mengurangi dominasi negara dengan volume pembangkitan sangat kecil; ini bukan standar atau batas ilmiah. "
        f"Ubah nilainya untuk melihat dampaknya pada peringkat.")

# ------------------------------------------------------------------ tabel detail
st.subheader("Tabel detail negara")
tabel = db.safe(queries.country_table, year, f["continents"], f["groups"])
if tabel.empty:
    components.empty_state("Tidak ada data tabel negara untuk filter ini.")
else:
    tampil = pd.DataFrame({
        "Negara": tabel["country_name"], "Benua": tabel["benua"], "Kelompok negara": tabel["kelompok"],
        f"Pangsa {base} (%)": tabel["pangsa_awal"], f"Pangsa {year} (%)": tabel["pangsa_tahun"],
        "Perubahan (poin)": tabel["perubahan"] if bandingkan else None,
        f"Pembangkitan {year} (TWh)": tabel["pembangkitan_twh"],
        "Status kelengkapan": [_badge_status(v) for v in tabel["status_kelengkapan"]]})
    st.dataframe(tampil, hide_index=True, width="stretch", column_config={
        f"Pangsa {base} (%)": st.column_config.NumberColumn(format="%.1f"),
        f"Pangsa {year} (%)": st.column_config.NumberColumn(format="%.1f"),
        "Perubahan (poin)": st.column_config.NumberColumn(format="%.1f"),
        f"Pembangkitan {year} (TWh)": st.column_config.NumberColumn(format="%.1f")})
    st.download_button("Unduh tabel (CSV)", tampil.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"pangsa_terbarukan_{year}.csv", mime="text/csv")
st.caption("Sel kosong berarti negara itu tidak punya nilai di sumber data; nilai tidak diisi dengan perkiraan. "
           "Status kelengkapan hanya menunjukkan ada atau tidaknya nilai kosong pada kolom indikator pangsa "
           "(listrik dan energi primer); bukan penilaian bahwa seluruh baris lengkap atau tidak lengkap.")

with st.expander("Cara membaca dan definisi"):
    st.markdown(
        "- **Pangsa tertimbang**: SUM(pangsa x pembangkitan) / SUM(pembangkitan), hanya negara yang bernilai. "
        "Negara besar berpengaruh lebih besar. **Median** memperlakukan setiap negara sama.\n"
        "- **Perubahan** dalam **poin persentase** dan dihitung dari angka yang ditampilkan (dibulatkan 1 desimal).\n"
        "- **Peringkat** memakai pangsa yang dibulatkan 1 desimal; jika seri, negara dengan pembangkitan lebih besar "
        "di atas.\n"
        "- Pangsa tinggi tidak otomatis berarti pembangkitan terbarukan besar: negara kecil bisa berpangsa tinggi "
        "dengan volume kecil. Karena itu ada ambang pembangkitan minimum pada peringkat.")
with st.expander("Sumber data dan query"):
    st.markdown("Semua angka dibaca dari view `mart.v_country_year` memakai akun baca-saja `np_dashboard`. "
                "Parameter (tahun, benua, kelompok, ambang) dikirim terpisah dari teks SQL.")
    st.markdown("**Pangsa tertimbang per benua per tahun:**")
    st.code(queries.CONTINENT_SQL, language="sql")
    st.markdown("**Peringkat tertinggi (terendah memakai ASC):**")
    st.code(queries.RANK_TOP_SQL, language="sql")
