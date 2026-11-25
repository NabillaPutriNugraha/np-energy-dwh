"""Sistem visual dashboard NP Energy Intelligence (lapisan presentasi saja; tidak menyentuh data, query, atau logika).
Isi: (1) CSS global untuk hierarki tipografi, kartu KPI, sidebar, filter, tab, alert, expander, kartu chart, dan tabel;
(2) template Plotly bersama (font, grid, tooltip) agar semua chart konsisten; (3) logo/brand.
Semua nilai di sini adalah KEPUTUSAN DESAIN PROYEK (bukan hasil penelitian); dasar dan batasannya ada di README_tambahan_4-4.md.
Font: bawaan Streamlit (Source Sans, sudah dibundel sehingga bekerja offline). Tidak ada sumber eksternal (font/CDN)."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY, OCEAN, TEAL = "#0F2A47", "#0072B2", "#009E73"
INK, MUTED, LINE, COOL = "#1F2933", "#52606D", "#D9E2EC", "#F4F7FA"
FONT = "Source Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
ASSETS = Path(__file__).resolve().parent / "assets"
TEKS_PILIH_NEGARA = {"placeholder": "Pilih negara"}   # teks petunjuk widget (bawaan Streamlit berbahasa Inggris)

CSS = f"""
<style>
:root {{ --np-navy:{NAVY}; --np-ocean:{OCEAN}; --np-teal:{TEAL}; --np-ink:{INK}; --np-muted:{MUTED}; --np-line:{LINE}; --np-cool:{COOL}; }}

/* ---------- Kanvas dan ritme vertikal ---------- */
[data-testid="stMainBlockContainer"] {{ max-width: 1280px; padding: 2.2rem 2rem 4rem !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {{ gap: 1.05rem; }}

/* ---------- Hierarki tipografi: judul halaman > deskripsi > judul bagian > keterangan ---------- */
[data-testid="stMain"] h1 {{ font-size: 1.9rem !important; line-height: 1.2 !important; font-weight: 700 !important;
  letter-spacing: -0.015em; color: var(--np-navy) !important; padding: 0 !important; margin: 0 !important; }}
[data-testid="stElementContainer"]:has(h1) + [data-testid="stElementContainer"] [data-testid="stCaptionContainer"] p {{
  font-size: 1.02rem !important; line-height: 1.5 !important; color: var(--np-muted) !important; opacity: 1 !important; max-width: 62rem; }}
[data-testid="stElementContainer"]:has(h1) {{ margin-bottom: -.35rem; }}
[data-testid="stMain"] h2, [data-testid="stMain"] h3 {{ font-size: 1.14rem !important; line-height: 1.3 !important; font-weight: 650 !important;
  color: var(--np-navy) !important; letter-spacing: -0.005em; padding: 0 0 0 .75rem !important; margin: 1.5rem 0 0 0 !important;
  border-left: 3px solid var(--np-ocean); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ font-size: .86rem !important; line-height: 1.5 !important; color: var(--np-muted) !important; opacity: 1 !important; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p {{ line-height: 1.55; }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] strong {{ color: var(--np-navy); }}

/* ---------- Kartu KPI: label kecil > angka utama > selisih ---------- */
[data-testid="stMetric"] {{ background: var(--np-cool); border: 1px solid var(--np-line); border-radius: 10px;
  padding: .85rem 1rem .8rem; min-height: 7.4rem; box-shadow: inset 0 3px 0 var(--np-navy); }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] > div {{ overflow: visible !important; }}
[data-testid="stMetricLabel"] p {{ font-size: .8rem !important; font-weight: 600 !important; color: var(--np-muted) !important; line-height: 1.25; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.95rem !important; font-weight: 650 !important; color: var(--np-navy) !important;
  line-height: 1.2 !important; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }}
[data-testid="stMetricDelta"] {{ font-size: .8rem !important; font-weight: 600; font-variant-numeric: tabular-nums; }}

/* ---------- Alert: tenang, bukan blok warna penuh ---------- */
[data-testid="stAlert"] {{ border-radius: 8px; border: 1px solid var(--np-line); border-left-width: 4px; padding: .15rem .25rem; }}
[data-testid="stAlert"] p {{ color: var(--np-ink) !important; font-size: .92rem; line-height: 1.5; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {{ background: #FFF8E6; border-color: #EBD9A8; border-left-color: #B7791F; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {{ background: #EEF5FB; border-color: #CFE0EE; border-left-color: var(--np-ocean); }}

/* ---------- Tab dan expander ---------- */
[data-testid="stTab"] {{ padding: .55rem 1.05rem; }}
[data-testid="stTab"] p {{ font-size: .93rem; font-weight: 600; color: var(--np-muted); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--np-ocean); }}
[data-testid="stExpander"] details {{ border: 1px solid var(--np-line); border-radius: 10px; background: #fff; }}
[data-testid="stExpander"] summary p {{ font-weight: 600; font-size: .93rem; color: var(--np-navy); }}

/* ---------- Chart sebagai kartu; toolbar Plotly hanya muncul saat kursor di atas chart ---------- */
[data-testid="stPlotlyChart"] {{ border: 1px solid #E3E9F0; border-radius: 10px; padding: 0; background: #fff; overflow: hidden; }}
.js-plotly-plot .modebar-container {{ opacity: 0; transition: opacity .15s ease; }}
[data-testid="stPlotlyChart"]:hover .modebar-container {{ opacity: 1; }}
[data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; }}

/* ---------- Tombol ---------- */
.stButton button, .stDownloadButton button {{ font-size: .86rem; font-weight: 600; border-radius: 8px; }}

/* ---------- Sidebar: brand, navigasi, filter ---------- */
[data-testid="stSidebar"] {{ border-right: 1px solid var(--np-line); }}
[data-testid="stSidebarHeader"] {{ padding-top: 1.3rem; padding-bottom: .4rem; }}
[data-testid="stSidebarHeader"] img {{ height: 2.6rem; }}
[data-testid="stSidebarNavLink"] {{ border-radius: 6px; padding: .42rem .7rem; font-size: .92rem; color: var(--np-ink); }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: #fff; box-shadow: inset 3px 0 0 var(--np-ocean); font-weight: 650; color: var(--np-navy); }}
[data-testid="stSidebarUserContent"] h3 {{ font-size: .74rem !important; font-weight: 700 !important; letter-spacing: .09em; text-transform: uppercase;
  color: var(--np-muted) !important; border-left: 0 !important; padding: 0 !important; margin: .2rem 0 .1rem !important; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: .8rem; font-weight: 600; color: var(--np-muted); }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{ font-size: .72rem; height: 1.45rem; padding: 0 .1rem 0 .4rem; margin: .08rem; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div:first-child {{ max-height: 9.2rem; overflow-y: auto; scrollbar-width: thin; }}
</style>
"""


def _template() -> go.layout.Template:
    sumbu = dict(automargin=True, gridcolor="#E8EDF2", linecolor="#CBD5E1", zerolinecolor="#94A3B8", ticks="outside", tickcolor="#CBD5E1", ticklen=4,
                 tickfont=dict(size=11, color=MUTED), title=dict(font=dict(size=12, color=MUTED)))
    return go.layout.Template(layout=dict(
        font=dict(family=FONT, size=12, color="#334155"), paper_bgcolor="white", plot_bgcolor="white",
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(family=FONT, size=12, color=INK)),
        xaxis=sumbu, yaxis=sumbu, legend=dict(font=dict(size=11.5, color="#334155"), title=dict(font=dict(size=11.5, color=MUTED))),
        title=dict(font=dict(size=14, color=NAVY))))


pio.templates["np"] = _template()
pio.templates.default = "np"


TABEL_LEBAR_TERSEDIA = 1090     # perkiraan lebar area konten pada layar 1440 px (keputusan desain; hanya memengaruhi lebar kolom)


def _lebar_kolom(df: "pd.DataFrame", konfig: dict) -> dict:
    """Lebar piksel tiap kolom dari panjang judul/isi, lalu diskalakan agar total muat di area konten (tanpa menggeser data)."""
    lebar = {}
    for kol in df.columns:
        judul = len(str(kol)) * 6.4 + 28
        if pd.api.types.is_numeric_dtype(df[kol]):
            lebar[kol] = min(max(judul, 80), 160)
        else:
            isi = df[kol].astype(str).str.len().head(300).max() if len(df) else 0
            lebar[kol] = min(max(judul, (isi or 0) * 6.4 + 26, 90), 230)
    total = sum(lebar.values())
    if total > TABEL_LEBAR_TERSEDIA:                       # penyempitan terutama pada kolom teks; judul kolom angka dijaga hampir utuh
        angka = [k for k in df.columns if pd.api.types.is_numeric_dtype(df[k])]
        teks = [k for k in df.columns if k not in angka]
        tot_angka, tot_teks = sum(lebar[k] for k in angka), sum(lebar[k] for k in teks)
        f_angka = 0.96
        f_teks = (TABEL_LEBAR_TERSEDIA - f_angka * tot_angka) / tot_teks if tot_teks else 1.0
        if not teks or f_teks < 0.62:                      # tidak ada kolom teks, atau teks terlalu sempit: bagi beban ke semua kolom
            f_angka = f_teks = TABEL_LEBAR_TERSEDIA / total
        lebar = {k: max(v * (f_angka if k in angka else f_teks), 70) for k, v in lebar.items()}
    return {k: int(round(v)) for k, v in lebar.items()}


def aplikasikan() -> None:
    """Dipanggil sekali per run dari app.py: CSS global, brand/logo, dan tema Plotly bawaan untuk st.plotly_chart."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.logo(str(ASSETS / "np_wordmark.svg"), icon_image=str(ASSETS / "np_mark.svg"), size="large")
    asli = getattr(st.plotly_chart, "_np_asli", st.plotly_chart)       # selalu bungkus ulang dari fungsi asli (aman untuk reload modul)

    def plotly_chart(figure_or_data, *args, **kwargs):
        kwargs.setdefault("theme", None)                              # tema Plotly kita, bukan tema Streamlit
        fig = figure_or_data
        if isinstance(fig, go.Figure):
            # Latar eksplisit putih (frontend menyuntik warna tema bila tidak disetel) dan ruang napas di dalam kartu chart.
            tambah_atas, tambah_bawah = 14, 20
            m = fig.layout.margin
            fig.update_layout(plot_bgcolor=fig.layout.plot_bgcolor or "white", paper_bgcolor=fig.layout.paper_bgcolor or "white",
                              margin=dict(t=(m.t if m.t is not None else 20) + tambah_atas, b=(m.b if m.b is not None else 20) + tambah_bawah,
                                        l=(m.l if m.l is not None else 80) + 8, r=(m.r if m.r is not None else 80) + 8))
            if fig.layout.height:
                fig.update_layout(height=int(fig.layout.height) + tambah_atas + tambah_bawah)
        return asli(fig, *args, **kwargs)

    plotly_chart._np_asli = asli
    st.plotly_chart = plotly_chart

    asli_df = getattr(st.dataframe, "_np_asli", st.dataframe)

    def dataframe(data=None, *args, **kwargs):
        if isinstance(data, pd.DataFrame) and not data.empty and len(data.columns) > 1:
            konfig = dict(kwargs.get("column_config") or {})
            for kol, lb in _lebar_kolom(data, konfig).items():
                if kol in konfig and isinstance(konfig[kol], dict):
                    konfig[kol] = {**konfig[kol], "width": konfig[kol].get("width") or lb}
                elif kol not in konfig:
                    konfig[kol] = st.column_config.Column(width=lb)
            kwargs["column_config"] = konfig
        return asli_df(data, *args, **kwargs)

    dataframe._np_asli = asli_df
    st.dataframe = dataframe
