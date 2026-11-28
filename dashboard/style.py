"""Sistem visual dashboard NP Energy Intelligence — "Luminous Eco-Intelligence".
Lapisan presentasi saja; tidak menyentuh data, query, atau logika perhitungan KPI.
Isi: (1) CSS global offline untuk kanvas, Hero Banner, kartu KPI, sidebar, filter, tab, alert, expander,
kartu chart, tabel, mikro-panduan, kotak insight, empty state, dan kamus istilah;
(2) template Plotly bersama (font, grid, tooltip) agar semua chart konsisten; (3) logo/brand.
Font: bawaan Streamlit/sistem (Source Sans / Segoe UI). Tidak ada sumber eksternal (font/CDN)."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Palet UI Luminous Eco-Intelligence (kontras diaudit WCAG AA/AAA)
NAVY = "#064E3B"        # aksen gelap utama (Deep Emerald)
OCEAN = "#047857"       # warna primer interaktif (Emerald Deep, kontras 5,48:1 dg putih)
TEAL = "#0D9488"        # aksen sekunder (Luminous Teal)
INK = "#0F2922"         # teks utama (Deep Forest Ink, kontras > 14:1 dg putih)
MUTED = "#4A605A"       # teks sekunder / label (kontras > 6:1 dg putih & soft mint)
LINE = "#DCE5E2"        # border halus kartu & pemisah
COOL = "#F4F7F6"        # latar kanvas utama (Soft Mint-Mist)
SIDEBAR_BG = "#EAF0EE"  # latar sidebar (Cool Sage)
SURFACE = "#FFFFFF"     # permukaan kartu putih
POS_TEXT = "#059669"    # teks tren positif
POS_BG = "#DCFCE7"      # latar pil tren positif
NEG_TEXT = "#DC2626"    # teks tren negatif
NEG_BG = "#FEE2E2"      # latar pil tren negatif

FONT = "Source Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
ASSETS = Path(__file__).resolve().parent / "assets"
TEKS_PILIH_NEGARA = {"placeholder": "Pilih negara"}   # teks petunjuk widget (bawaan Streamlit berbahasa Inggris)

CSS = f"""
<style>
:root {{
  --np-navy: {NAVY};
  --np-ocean: {OCEAN};
  --np-teal: {TEAL};
  --np-ink: {INK};
  --np-muted: {MUTED};
  --np-line: {LINE};
  --np-cool: {COOL};
  --np-sidebar: {SIDEBAR_BG};
  --np-surface: {SURFACE};
  --np-pos: {POS_TEXT};
  --np-pos-bg: {POS_BG};
  --np-neg: {NEG_TEXT};
  --np-neg-bg: {NEG_BG};
}}

/* ---------- Kanvas dan ritme vertikal ---------- */
[data-testid="stAppViewContainer"] {{ background: var(--np-cool); }}
[data-testid="stMainBlockContainer"] {{ max-width: 1320px; padding: 1.5rem 2rem 3.5rem !important; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {{ gap: 0.95rem; }}

/* ---------- Hierarki tipografi ---------- */
[data-testid="stMain"] h1 {{
  font-size: 1.85rem !important; line-height: 1.2 !important; font-weight: 700 !important;
  letter-spacing: -0.015em; color: var(--np-navy) !important; padding: 0 !important; margin: 0 !important;
}}
/* Sembunyikan st.title secara visual jika tepat di bawah Hero Banner (tetap ramah screen-reader & AppTest) */
[data-testid="stElementContainer"]:has(.np-hero) + [data-testid="stElementContainer"]:has(h1),
/* Sembunyikan st.info duplikat tepat di bawah .np-empty (tetap ada di DOM untuk AppTest) */
[data-testid="stElementContainer"]:has(.np-empty) + [data-testid="stElementContainer"]:has([data-testid="stAlert"]),
/* Sembunyikan caption ETL duplikat di sidebar tepat di bawah .np-etl-box (tetap ada di DOM untuk AppTest) */
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.np-etl-box) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {{
  position: absolute !important; width: 1px !important; height: 1px !important;
  padding: 0 !important; margin: -1px !important; overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important;
}}
[data-testid="stMain"] h2, [data-testid="stMain"] h3 {{
  font-size: 0.98rem !important; line-height: 1.3 !important; font-weight: 700 !important;
  text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--np-ink) !important;
  padding: 0 0 0 0.75rem !important; margin: 1.25rem 0 0.1rem 0 !important;
  border-left: 3.5px solid var(--np-ocean);
}}
/* ---------- Indikator pembaruan data (spinner & status widget) ---------- */
[data-testid="stSpinner"] {{
  background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 12px;
  padding: 0.55rem 0.95rem; color: var(--np-navy); font-weight: 650; font-size: 0.88rem;
  box-shadow: 0 2px 10px rgba(6, 78, 59, 0.06);
}}
[data-testid="stStatusWidget"] {{
  background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 999px;
  padding: 0.2rem 0.75rem; color: var(--np-navy); font-weight: 650;
  box-shadow: 0 2px 8px rgba(6, 78, 59, 0.08);
}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
  font-size: 0.85rem !important; line-height: 1.5 !important;
  color: var(--np-muted) !important; opacity: 1 !important;
}}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p {{ line-height: 1.55; color: var(--np-ink); }}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] strong {{ color: var(--np-navy); }}

/* ---------- Hero Banner Bergradien ---------- */
.np-hero {{
  display: flex; align-items: center; justify-content: space-between; gap: 1.25rem;
  min-height: 88px; padding: 1rem 1.4rem; border-radius: 16px; color: #FFFFFF;
  box-shadow: 0 6px 20px rgba(6, 78, 59, 0.12); margin-bottom: 0.25rem;
  position: relative; overflow: hidden;
}}
.np-hero--eco {{ background: linear-gradient(125deg, #064E3B 0%, #047857 55%, #0D9488 100%); }}
.np-hero--fossil {{ background: linear-gradient(125deg, #1E293B 0%, #475569 55%, #92400E 100%); }}
.np-hero--mix {{ background: linear-gradient(125deg, #0F2A47 0%, #1D4ED8 55%, #0891B2 100%); }}
.np-hero--intensity {{ background: linear-gradient(125deg, #134E4A 0%, #0F766E 55%, #B45309 100%); }}
.np-hero--quality {{ background: linear-gradient(125deg, #1E293B 0%, #334155 55%, #047857 100%); }}
.np-hero__body {{ flex: 1; min-width: 0; }}
.np-hero__title {{
  font-size: 1.45rem; font-weight: 750; line-height: 1.2; letter-spacing: -0.015em;
  color: #FFFFFF; margin: 0 0 0.25rem 0;
}}
.np-hero__sub {{
  font-size: 0.88rem; line-height: 1.45; color: rgba(255, 255, 255, 0.92); margin: 0 0 0.55rem 0;
}}
.np-hero__chips {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
.np-chip {{
  display: inline-flex; align-items: center; gap: 0.3rem;
  background: rgba(255, 255, 255, 0.16); border: 1px solid rgba(255, 255, 255, 0.28);
  color: #FFFFFF; font-size: 0.76rem; font-weight: 600;
  padding: 0.16rem 0.6rem; border-radius: 999px; letter-spacing: 0.01em;
}}
.np-hero__art {{ flex-shrink: 0; opacity: 0.9; display: flex; align-items: center; }}

/* ---------- Kartu KPI (stMetric): permukaan putih, tinggi seragam, aksen atas 3px, judul ALL CAPS ---------- */
[data-testid="stMetric"] {{
  background: var(--np-surface);
  border: 1px solid var(--np-line);
  border-radius: 14px;
  padding: 0.95rem 1.1rem 0.9rem;
  min-height: 132px;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04), inset 0 3px 0 var(--np-ocean);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
[data-testid="stMetric"]:hover {{
  box-shadow: 0 6px 16px rgba(6, 78, 59, 0.08), inset 0 3px 0 var(--np-teal);
}}
[data-testid="stMetricLabel"] {{ min-height: 2.2em; overflow: visible !important; }}
[data-testid="stMetricLabel"] > div {{ overflow: visible !important; }}
[data-testid="stMetricLabel"] p {{
  font-size: 0.75rem !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: 0.06em !important;
  color: var(--np-muted) !important; line-height: 1.3;
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}}
[data-testid="stMetricValue"] {{
  font-size: 1.875rem !important; font-weight: 700 !important; color: var(--np-ink) !important;
  line-height: 1.2 !important; letter-spacing: -0.015em; font-variant-numeric: tabular-nums;
  margin-top: 0.15rem;
}}
[data-testid="stMetricDelta"] {{
  font-size: 0.78rem !important; font-weight: 650 !important; font-variant-numeric: tabular-nums;
  border-radius: 999px; padding: 0.12rem 0.55rem; width: fit-content; margin-top: 0.25rem;
}}
[data-testid="stMetricDelta"][style*="rgb(9, 171, 59)"],
[data-testid="stMetricDelta"][style*="rgb(33, 195, 84)"],
[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]):not([style*="rgb(255"]):not([style*="rgb(128"]) {{
  background: var(--np-pos-bg); color: var(--np-pos) !important;
}}
[data-testid="stMetricDelta"][style*="rgb(255, 43, 43)"],
[data-testid="stMetricDelta"][style*="rgb(255, 75, 75)"] {{
  background: var(--np-neg-bg); color: var(--np-neg) !important;
}}
/* Aksen khusus kartu korelasi (Halaman D) */
.np-corr-neg [data-testid="stMetric"] {{
  box-shadow: 0 2px 10px rgba(220, 38, 38, 0.06), inset 0 3px 0 #DC2626;
}}
.np-corr-neg [data-testid="stMetricValue"] {{ color: #B91C1C !important; }}
.np-corr-pos [data-testid="stMetric"] {{
  box-shadow: 0 2px 10px rgba(5, 150, 105, 0.06), inset 0 3px 0 #059669;
}}
.np-corr-pos [data-testid="stMetricValue"] {{ color: #047857 !important; }}

/* ---------- Mikro-Panduan, Insight Box, Empty State, Status Cards & Kamus ---------- */
.np-guide {{
  display: flex; align-items: flex-start; gap: 0.5rem;
  background: #EDF7F4; border: 1px solid #C8E6DC; border-radius: 10px;
  padding: 0.5rem 0.85rem; font-size: 0.85rem; line-height: 1.5; color: var(--np-ink);
  margin: 0.15rem 0 0.25rem 0;
}}
.np-insight {{
  display: flex; align-items: flex-start; gap: 0.55rem;
  background: var(--np-surface); border: 1px solid var(--np-line); border-left: 4px solid var(--np-teal);
  border-radius: 10px; padding: 0.65rem 0.95rem; font-size: 0.87rem; line-height: 1.5;
  color: var(--np-ink); box-shadow: 0 1px 6px rgba(6, 78, 59, 0.04); margin: 0.25rem 0;
}}
.np-empty {{
  background: var(--np-surface); border: 1px dashed #94B8AE; border-radius: 14px;
  padding: 1.35rem 1.5rem; text-align: center; color: var(--np-ink);
  box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04); margin: 0.5rem 0;
}}
.np-empty__title {{ font-size: 1rem; font-weight: 700; color: var(--np-navy); margin: 0.35rem 0 0.25rem; }}
.np-empty__desc {{ font-size: 0.88rem; line-height: 1.5; color: var(--np-muted); margin: 0; }}
.np-status-grid {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.85rem; margin: 0.35rem 0 0.5rem;
}}
.np-status-card {{
  background: var(--np-surface); border: 1px solid var(--np-line); border-radius: 14px;
  padding: 0.9rem 1.05rem; box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04);
  border-left: 4px solid var(--np-ocean);
}}
.np-status-card--warn {{ border-left-color: #D97706; }}
.np-status-card__eyebrow {{
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--np-muted); margin-bottom: 0.2rem;
}}
.np-status-card__val {{ font-size: 1.25rem; font-weight: 750; color: var(--np-ink); margin-bottom: 0.2rem; }}
.np-status-card__note {{ font-size: 0.82rem; line-height: 1.45; color: var(--np-muted); }}
.np-glossary {{
  background: var(--np-surface); border: 1px solid var(--np-line); border-radius: 14px;
  padding: 0.95rem 1.15rem; box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04); margin-bottom: 0.4rem;
}}
.np-glossary__head {{
  font-size: 0.82rem; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--np-navy); margin-bottom: 0.55rem;
}}
.np-glossary__grid {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.85rem;
}}
.np-glossary__item {{
  background: #F8FBFA; border: 1px solid #E3ECE9; border-radius: 10px; padding: 0.65rem 0.8rem;
}}
.np-glossary__term {{ font-size: 0.86rem; font-weight: 700; color: var(--np-navy); margin-bottom: 0.2rem; }}
.np-glossary__def {{ font-size: 0.82rem; line-height: 1.5; color: var(--np-muted); }}

/* ---------- Alert: banner elegan dan tenang ---------- */
[data-testid="stAlert"] {{
  border-radius: 12px; border: 1px solid var(--np-line); border-left-width: 4px; padding: 0.25rem 0.4rem;
}}
[data-testid="stAlert"] p {{ color: var(--np-ink) !important; font-size: 0.9rem; line-height: 1.5; }}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {{
  background: #FFFBEB; border-color: #FDE68A; border-left-color: #B45309;
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {{
  background: #ECFDF5; border-color: #A7F3D0; border-left-color: var(--np-ocean);
}}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {{
  background: #FEF2F2; border-color: #FECACA; border-left-color: var(--np-neg);
}}

/* ---------- Tab dan expander ---------- */
[data-testid="stTab"] {{ padding: 0.55rem 1.05rem; border-radius: 8px 8px 0 0; }}
[data-testid="stTab"] p {{ font-size: 0.91rem; font-weight: 600; color: var(--np-muted); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--np-ocean); font-weight: 700; }}
[data-testid="stExpander"] details {{
  border: 1px solid var(--np-line); border-radius: 12px; background: var(--np-surface);
  box-shadow: 0 1px 6px rgba(6, 78, 59, 0.03);
}}
[data-testid="stExpander"] summary p {{ font-weight: 650; font-size: 0.91rem; color: var(--np-navy); }}

/* ---------- Chart & tabel sebagai kartu putih ---------- */
[data-testid="stPlotlyChart"] {{
  border: 1px solid var(--np-line); border-radius: 14px; padding: 0;
  background: var(--np-surface); overflow: hidden;
  box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04);
}}
.js-plotly-plot .modebar-container {{ opacity: 0; transition: opacity 0.15s ease; }}
[data-testid="stPlotlyChart"]:hover .modebar-container {{ opacity: 1; }}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--np-line); border-radius: 14px; overflow: hidden;
  background: var(--np-surface); box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04);
}}

/* ---------- Tombol ---------- */
.stButton button, .stDownloadButton button {{
  font-size: 0.85rem; font-weight: 650; border-radius: 10px;
  border: 1px solid #B7D4CA; background: var(--np-surface); color: var(--np-navy);
}}
.stButton button:hover, .stDownloadButton button:hover {{
  border-color: var(--np-ocean); background: #ECFDF5; color: var(--np-navy);
}}

/* ---------- Sidebar: Cool Sage, navigasi pil, tag multiselect lembut, & kartu ETL ---------- */
[data-testid="stSidebar"] {{
  background: var(--np-sidebar); border-right: 1px solid var(--np-line);
}}
[data-testid="stSidebarHeader"] {{ padding-top: 1.15rem; padding-bottom: 0.35rem; }}
[data-testid="stSidebarHeader"] img {{ height: 2.55rem; }}
[data-testid="stSidebarNavLink"] {{
  border-radius: 10px; padding: 0.45rem 0.75rem; font-size: 0.9rem; color: var(--np-ink);
  margin-bottom: 0.12rem;
}}
[data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: var(--np-surface); box-shadow: inset 3.5px 0 0 var(--np-ocean), 0 1px 4px rgba(6, 78, 59, 0.06);
  font-weight: 700; color: var(--np-navy);
}}
[data-testid="stSidebarUserContent"] h3 {{
  font-size: 0.74rem !important; font-weight: 750 !important; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--np-muted) !important;
  border-left: 0 !important; padding: 0 !important; margin: 0.3rem 0 0.15rem !important;
}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
  font-size: 0.78rem; font-weight: 650; color: var(--np-muted);
}}
[data-testid="stSidebar"] [data-baseweb="tag"],
[data-testid="stSidebar"] span[data-baseweb="tag"] {{
  background: #D1FAE5 !important; background-color: #D1FAE5 !important; color: #065F46 !important;
  border: 1px solid #A7F3D0 !important; border-radius: 999px !important;
  font-size: 0.73rem; font-weight: 600; height: 1.5rem; padding: 0 0.25rem 0 0.5rem; margin: 0.1rem;
}}
[data-testid="stSidebar"] [data-baseweb="tag"] span,
[data-testid="stSidebar"] [data-baseweb="tag"] svg,
[data-testid="stSidebar"] [data-baseweb="tag"] button {{
  color: #065F46 !important; fill: #065F46 !important;
}}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div:first-child {{
  max-height: 96px; overflow-y: auto; scrollbar-width: thin;
}}
.np-etl-box {{
  background: var(--np-surface); border: 1px solid var(--np-line); border-radius: 12px;
  padding: 0.7rem 0.85rem; margin-top: 0.65rem;
  box-shadow: 0 1px 6px rgba(6, 78, 59, 0.04);
}}
.np-etl-box__head {{
  display: flex; align-items: center; gap: 0.4rem;
  font-size: 0.72rem; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--np-navy); margin-bottom: 0.25rem;
}}
.np-etl-dot {{
  width: 8px; height: 8px; border-radius: 999px; background: #10B981; display: inline-block;
}}
.np-etl-box__meta {{ font-size: 0.78rem; line-height: 1.45; color: var(--np-muted); }}
</style>
"""


def _template() -> go.layout.Template:
    sumbu = dict(
        automargin=True, gridcolor="#E6EFEA", linecolor="#CBD9D4", zerolinecolor="#94A8A1",
        ticks="outside", tickcolor="#CBD9D4", ticklen=4,
        tickfont=dict(size=11, color=MUTED), title=dict(font=dict(size=12, color=MUTED)),
    )
    return go.layout.Template(layout=dict(
        font=dict(family=FONT, size=12, color=INK), paper_bgcolor="white", plot_bgcolor="white",
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD9D4", font=dict(family=FONT, size=12, color=INK)),
        xaxis=sumbu, yaxis=sumbu,
        legend=dict(font=dict(size=11.5, color=INK), title=dict(font=dict(size=11.5, color=MUTED))),
        title=dict(font=dict(size=14, color=NAVY)),
    ))


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
            fig.update_layout(
                plot_bgcolor=fig.layout.plot_bgcolor or "white",
                paper_bgcolor=fig.layout.paper_bgcolor or "white",
                margin=dict(
                    t=(m.t if m.t is not None else 20) + tambah_atas,
                    b=(m.b if m.b is not None else 20) + tambah_bawah,
                    l=(m.l if m.l is not None else 80) + 8,
                    r=(m.r if m.r is not None else 80) + 8,
                ),
            )
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
