"""Titik masuk dashboard NP Energy Intelligence.
Jalankan dari folder proyek:  streamlit run dashboard/app.py
Tugas file ini: konfigurasi halaman, navigasi enam halaman, filter global di sidebar, dan informasi kesegaran data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # agar modul di folder dashboard/ bisa di-import

import streamlit as st  # noqa: E402

import components  # noqa: E402
import db  # noqa: E402
import queries  # noqa: E402
import style  # noqa: E402

st.set_page_config(page_title="NP Energy Intelligence | Transisi Energi", layout="wide",
                   initial_sidebar_state="expanded")
style.aplikasikan()

PAGES = [
    st.Page("halaman/ringkasan.py", title="Ringkasan", default=True),
    st.Page("halaman/a_terbarukan.py", title="Perkembangan Terbarukan"),
    st.Page("halaman/b_fosil.py", title="Ketergantungan Fosil"),
    st.Page("halaman/c_bauran.py", title="Bauran Pembangkitan"),
    st.Page("halaman/d_pangsa_intensitas.py", title="Pangsa vs Intensitas"),
    st.Page("halaman/kualitas.py", title="Kualitas Data"),
]


def render_sidebar():
    """Filter global. Nilainya disimpan di st.session_state (kunci f_*) dan dibaca semua halaman."""
    opts = db.safe(queries.filter_options)
    st.sidebar.markdown("### Filter Global")
    st.sidebar.selectbox("Tahun", opts["years"], index=len(opts["years"]) - 1, key="f_year",
                         help=f"Dibandingkan dengan tahun pembanding {queries.BASE_YEAR}.")
    st.sidebar.multiselect("Benua", opts["continents"], default=opts["continents"], key="f_continents",
                           placeholder="Pilih benua",
                           help="'Tidak diketahui' = negara yang tidak punya atribut benua di sumber data.")
    st.sidebar.multiselect("Kelompok negara", opts["groups"], default=opts["groups"], key="f_groups",
                           placeholder="Pilih kelompok")
    isos = [iso for iso, _ in opts["countries"]]
    names = dict(opts["countries"])
    st.sidebar.selectbox("Negara sorotan", isos, format_func=lambda i: names[i],
                         index=isos.index("IDN") if "IDN" in isos else 0, key="f_country",
                         help="Ditampilkan sebagai garis atau penanda pembanding pada grafik.")
    if st.sidebar.button("Muat ulang data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    with st.sidebar.expander("📖 Kamus Istilah & Satuan"):
        st.markdown(
            "- **Pangsa (%)**: proporsi listrik dari suatu sumber terhadap total pembangkitan.\n"
            "- **Bauran**: susunan seluruh jenis sumber pembangkit listrik (batu bara, gas, air, surya, angin, nuklir, dll.).\n"
            "- **TWh**: *Terawatt-jam*, satuan volume listrik skala besar (1 TWh = 1 miliar kWh).\n"
            "- **gCO₂e/kWh**: gram emisi gas rumah kaca per 1 kWh listrik (makin rendah makin bersih).\n"
            "- **Poin persentase**: selisih langsung dua angka persen (mis. 20% ke 25% = +5 poin)."
        )

    status = db.safe(queries.etl_status)
    if status.empty:
        st.sidebar.caption("Status ETL belum tersedia.")
    else:
        r = status.iloc[0]
        waktu = r["finished_at"].to_pydatetime().astimezone().strftime("%d-%m-%Y %H:%M")   # waktu lokal komputer
        rows_loaded = int(r["rows_loaded_dw"]) if r["rows_loaded_dw"] is not None else None
        components.etl_sidebar_card(int(r["run_id"]), waktu, rows_loaded)
        st.sidebar.caption(f"Sumber: Data Warehouse PostgreSQL (schema mart). "
                           f"ETL terakhir: run #{int(r['run_id'])}, {waktu}.")


pg = st.navigation(PAGES)
render_sidebar()
with st.spinner("Memperbarui data dan visualisasi..."):
    pg.run()
