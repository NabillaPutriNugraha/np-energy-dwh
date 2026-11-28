"""Fungsi pembuat grafik Plotly. Semua teks (judul sumbu, hover) berbahasa Indonesia dengan format angka koma desimal."""
import math

import plotly.graph_objects as go

import theme


def _clean(values):
    return [None if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in values]


def trend_chart(years, scope_values, scope_label, country_values, country_label,
                y_title, color, dec=1, suffix=""):
    """Garis tren spline per tahun dengan arsiran transparan: agregat negara terpilih + satu negara sorotan."""
    fig = go.Figure()
    fill_col = "rgba(13, 148, 136, 0.16)" if color == theme.COLOR_RENEWABLE else "rgba(213, 94, 0, 0.12)"
    series = [(scope_values, scope_label, color, "solid", 3, "tozeroy", fill_col)]
    if country_values is not None:
        series.append((country_values, country_label, theme.COLOR_HIGHLIGHT, "dash", 2.2, None, None))
    for values, name, col, dash, width, fill_mode, fcol in series:
        values = _clean(list(values))
        hover = [f"{name}<br>{int(y)}: {theme.fmt_num(v, dec)}{suffix}" if v is not None
                 else f"{name}<br>{int(y)}: tidak ada data" for y, v in zip(years, values)]
        kw = dict(fill=fill_mode, fillcolor=fcol) if fill_mode else {}
        fig.add_trace(go.Scatter(
            x=list(years), y=values, name=name, mode="lines+markers",
            line=dict(color=col, width=width, dash=dash, shape="spline", smoothing=0.55),
            marker=dict(size=8, line=dict(color="white", width=1.5)),
            hovertext=hover, hoverinfo="text", **kw,
        ))
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
                      xaxis=dict(dtick=1, tickformat="d", title=None),
                      yaxis=dict(title=y_title, rangemode="tozero", gridcolor="#E6EFEA"),
                      plot_bgcolor="white")
    return fig


def movers_bar(df):
    """Batang horizontal: negara dengan kenaikan pangsa terbarukan terbesar."""
    d = df.iloc[::-1]   # agar yang terbesar tampil di atas
    hover = [f"{r.country_name}<br>Pangsa: {theme.fmt_num(r.pangsa_awal, 1)}% menjadi "
             f"{theme.fmt_num(r.pangsa_akhir, 1)}%<br>Pembangkitan: {theme.fmt_num(r.pembangkitan_twh, 1)} TWh"
             for r in d.itertuples()]
    fig = go.Figure(go.Bar(x=d["perubahan"], y=d["country_name"], orientation="h",
                           marker_color=theme.COLOR_RENEWABLE,
                           text=[theme.fmt_delta(v, 1) for v in d["perubahan"]], textposition="outside",
                           hovertext=hover, hoverinfo="text", cliponaxis=False))
    fig.update_layout(height=380, margin=dict(l=10, r=44, t=10, b=10), plot_bgcolor="white",
                      xaxis=dict(title="Perubahan pangsa (poin persentase)", gridcolor="#E6EFEA",
                                 rangemode="tozero"),
                      yaxis=dict(title=None))
    return fig


MAP_COLORSCALE = [
    [0.0, "#FEF3C7"], [0.2, "#FEF3C7"],
    [0.2, "#99F6E4"], [0.4, "#99F6E4"],
    [0.4, "#2DD4BF"], [0.6, "#2DD4BF"],
    [0.6, "#059669"], [0.8, "#059669"],
    [0.8, "#064E3B"], [1.0, "#064E3B"],
]


def _kelas_pangsa(val: float) -> str:
    if val < 20:
        return "0–20%"
    if val < 40:
        return "20–40%"
    if val < 60:
        return "40–60%"
    if val < 80:
        return "60–80%"
    return "80–100%"


def share_map(df):
    """Peta choropleth pangsa listrik terbarukan per negara (kode ISO3) dengan 5 kelas warna diskrit per 20%."""
    hover = [
        f"<b>{r.country_name}</b><br>Pangsa terbarukan: {theme.fmt_num(r.pangsa, 1)}%<br>"
        f"Kelompok: {_kelas_pangsa(float(r.pangsa))}"
        for r in df.itertuples()
    ]
    fig = go.Figure(go.Choropleth(
        locations=df["iso3_code"], z=df["pangsa"], zmin=0, zmax=100,
        colorscale=MAP_COLORSCALE, text=hover, hoverinfo="text",
        marker_line_color="#64748B", marker_line_width=0.6,
        colorbar=dict(
            title=dict(text="% listrik<br>terbarukan", side="top"),
            thickness=13, len=0.68, y=0.48, ypad=10,
            tickmode="array", tickvals=[10, 30, 50, 70, 90],
            ticktext=["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"],
            tickfont=dict(size=10.5),
        ),
    ))
    fig.update_geos(
        showframe=False, showcoastlines=True, coastlinecolor="#CBD5E1",
        showcountries=True, countrycolor="#94A3B8",
        showland=True, landcolor="#E2E8F0",
        projection_type="natural earth", bgcolor="rgba(0,0,0,0)",
    )
    fig.add_annotation(
        x=0.01, y=0.01, xref="paper", yref="paper", xanchor="left", yanchor="bottom",
        text="■ Abu-abu = Tidak ada data", showarrow=False,
        font=dict(size=10.5, color="#475569"),
        bgcolor="rgba(255,255,255,0.9)", bordercolor="#CBD5E1", borderwidth=1, borderpad=4,
    )
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=0, b=0))
    return fig


# =====================================================================================
# Grafik tambahan Halaman A (Fase 4-3a)
# =====================================================================================
# Warna benua (aman buta warna). 'Tidak diketahui' sengaja abu-abu agar tidak tampak sebagai pembanding utama.
CONTINENT_COLORS = {
    "Africa": "#E69F00", "Asia": "#CC79A7", "Europe": "#332288", "North America": "#56B4E9",
    "Oceania": "#8C564B", "South America": "#D55E00", "Tidak diketahui": "#BBBBBB",
}
# Warna garis untuk pembandingan beberapa negara (maksimal 8).
LINE_COLORS = ["#0072B2", "#E69F00", "#CC79A7", "#56B4E9", "#D55E00", "#332288", "#8C564B", "#117733"]


def multi_trend(years, series, y_title, dec=1, suffix="%", height=360):
    """Garis tren dengan banyak seri. Setiap seri: dict(name, values, color, width, dash).
    Nilai kosong digambar sebagai celah (tidak diisi atau diinterpolasi)."""
    fig = go.Figure()
    for s in series:
        values = _clean(list(s["values"]))
        hover = [f"{s['name']}<br>{int(y)}: {theme.fmt_num(v, dec)}{suffix}" if v is not None
                 else f"{s['name']}<br>{int(y)}: tidak ada data" for y, v in zip(years, values)]
        fig.add_trace(go.Scatter(x=list(years), y=values, name=s["name"], mode="lines+markers",
                                 line=dict(color=s["color"], width=s.get("width", 2), dash=s.get("dash", "solid")),
                                 marker=dict(size=s.get("marker", 7)), hovertext=hover, hoverinfo="text",
                                 connectgaps=False))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", yanchor="top", y=-0.15, x=0),
                      xaxis=dict(dtick=1, tickformat="d", title=None),
                      yaxis=dict(title=y_title, rangemode="tozero", gridcolor="#E6EFEA"),
                      plot_bgcolor="white")
    return fig


def rank_bar(df, color=None):
    """Batang horizontal peringkat pangsa (0-100%). df: country_name, pangsa, pembangkitan_twh."""
    d = df.iloc[::-1]   # peringkat 1 di atas
    hover = [f"{r.country_name}<br>Pangsa: {theme.fmt_num(r.pangsa, 1)}%<br>"
             f"Pembangkitan: {theme.fmt_num(r.pembangkitan_twh, 1)} TWh" for r in d.itertuples()]
    fig = go.Figure(go.Bar(x=d["pangsa"], y=d["country_name"], orientation="h",
                           marker_color=color or theme.COLOR_RENEWABLE,
                           text=[theme.fmt_pct(v, 1) for v in d["pangsa"]], textposition="outside",
                           hovertext=hover, hoverinfo="text", cliponaxis=False))
    fig.update_layout(height=380, margin=dict(l=10, r=50, t=10, b=10), plot_bgcolor="white",
                      xaxis=dict(title="Pangsa listrik terbarukan (%)", range=[0, 112],
                                 tickvals=[0, 20, 40, 60, 80, 100], gridcolor="#E6EFEA"),
                      yaxis=dict(title=None))
    return fig


# =====================================================================================
# Grafik tambahan Halaman B (Fase 4-3b & Redesign R12)
# =====================================================================================
def dumbbell(df, label_col, a_col, b_col, a_name, b_name, a_color, b_color, x_title, dec=1, unit="%"):
    """Dumbbell: dua titik per baris dihubungkan garis. Baris yang salah satu nilainya kosong hanya
    menampilkan titik yang ada (tidak diisi 0 atau perkiraan). Urutan baris mengikuti urutan df (atas ke bawah)."""
    labels = list(df[label_col])
    xs, ys = [], []
    for lab, a, b in zip(labels, df[a_col], df[b_col]):
        if _clean([a])[0] is not None and _clean([b])[0] is not None:
            xs += [a, b, None]
            ys += [lab, lab, None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#9CA3AF", width=3),
                             hoverinfo="skip", showlegend=False))
    for kolom, nama, warna in ((a_col, a_name, a_color), (b_col, b_name, b_color)):
        nilai = _clean(list(df[kolom]))
        hover = [f"{lab}<br>{nama}: {theme.fmt_num(v, dec)}{unit}" if v is not None
                 else f"{lab}<br>{nama}: tidak ada data" for lab, v in zip(labels, nilai)]
        fig.add_trace(go.Scatter(x=nilai, y=labels, mode="markers", name=nama,
                                 marker=dict(size=13, color=warna, line=dict(color="white", width=1)),
                                 hovertext=hover, hoverinfo="text"))
    fig.update_layout(height=max(300, 70 + 34 * len(labels)), margin=dict(l=10, r=20, t=10, b=10),
                      plot_bgcolor="white", legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
                      xaxis=dict(title=x_title, range=[0, 100], gridcolor="#E6EFEA"),
                      yaxis=dict(title=None, categoryorder="array", categoryarray=labels, autorange="reversed"))
    return fig


def grouped_fossil_bar(df, base, year):
    """Batang horizontal berdampingan (Grouped Bar Chart) pangsa fosil tahun pembanding vs tahun terpilih.
    Urutan baris mengikuti urutan df (atas ke bawah, menurut pembangkitan listrik terbesar)."""
    labels = list(df["label"])
    v_base = _clean(list(df["fosil_awal"]))
    v_year = _clean(list(df["fosil_tahun"]))
    fig = go.Figure()
    for vals, nama, warna in (
        (v_base, str(base), "#94A3B8"),
        (v_year, str(year), "#475569"),
    ):
        hover = [f"{lab}<br>Pangsa fosil {nama}: {theme.fmt_pct(v, 1)}" if v is not None
                 else f"{lab}<br>Pangsa fosil {nama}: tidak ada data" for lab, v in zip(labels, vals)]
        txt = [theme.fmt_pct(v, 1) if v is not None else "" for v in vals]
        fig.add_trace(go.Bar(
            y=labels, x=vals, name=nama, orientation="h", marker_color=warna,
            text=txt, textposition="outside", textfont=dict(size=10.5),
            hovertext=hover, hoverinfo="text", cliponaxis=False,
        ))
    fig.update_layout(
        barmode="group", bargap=0.24, bargroupgap=0.08,
        height=max(340, 80 + 44 * len(labels)), margin=dict(l=10, r=52, t=10, b=10),
        plot_bgcolor="white", legend=dict(orientation="h", yanchor="top", y=-0.1, x=0),
        xaxis=dict(title="Pangsa listrik fosil (%)", range=[0, 112], tickvals=[0, 20, 40, 60, 80, 100], gridcolor="#E6EFEA"),
        yaxis=dict(title=None, categoryorder="array", categoryarray=labels, autorange="reversed"),
    )
    return fig


# =====================================================================================
# Grafik tambahan Halaman C (Fase 4-3c & Redesign M09/T10): bauran pembangkitan
# Daftar kategori dan sumber berasal dari DATA. Kamus di bawah HANYA untuk label berbahasa Indonesia, warna, dan
# urutan tampilan; nama yang tidak ada di kamus tetap dipakai apa adanya (tidak ada nama yang diciptakan).
# =====================================================================================
KATEGORI_LABEL = {"Fossil": "Fosil", "Nuklir": "Nuklir", "Renewable": "Terbarukan"}
SUMBER_LABEL = {"Coal": "Batu bara", "Gas": "Gas", "Other fossil": "Fosil lainnya", "Nuclear": "Nuklir",
                "Bioenergy": "Bioenergi", "Hydro": "Tenaga air", "Solar": "Surya", "Wind": "Angin",
                "Other renewables": "Terbarukan lainnya"}
KATEGORI_COLOR = {"Fossil": theme.COLOR_FOSSIL, "Nuklir": theme.COLOR_NUCLEAR, "Renewable": theme.COLOR_RENEWABLE}
# Palet cerah & kontras tinggi (M09) untuk 9 sumber pembangkitan
SUMBER_COLOR = {
    "Coal": "#475569",              # Slate (Batu bara)
    "Gas": "#F97316",               # Orange (Gas)
    "Other fossil": "#8B5CF6",      # Violet (Fosil lainnya / Minyak)
    "Nuclear": "#DB2777",           # Pink/Magenta (Nuklir)
    "Hydro": "#2563EB",             # Blue (Tenaga air / Hidro)
    "Wind": "#06B6D4",              # Cyan (Angin)
    "Solar": "#F59E0B",             # Amber (Surya)
    "Bioenergy": "#10B981",         # Emerald (Bioenergi)
    "Other renewables": "#0D9488",  # Teal (Terbarukan lainnya)
}
_KATEGORI_URUT = ["Fossil", "Nuklir", "Renewable"]
_CADANGAN = ["#999999", "#BBBBBB", "#777777", "#DDDDDD"]   # untuk nama yang tidak ada di kamus


def kategori_label(nama):
    return KATEGORI_LABEL.get(nama, nama)


def sumber_label(nama):
    return SUMBER_LABEL.get(nama, nama)


def kategori_color(nama, i=0):
    return KATEGORI_COLOR.get(nama, _CADANGAN[i % len(_CADANGAN)])


def sumber_color(nama, i=0):
    return SUMBER_COLOR.get(nama, _CADANGAN[i % len(_CADANGAN)])


def urut_kategori(daftar):
    """Urutan tampilan: urutan baku untuk nama yang dikenal, sisanya menurut abjad di akhir."""
    daftar = list(dict.fromkeys(daftar))
    return sorted(daftar, key=lambda k: (_KATEGORI_URUT.index(k) if k in _KATEGORI_URUT else len(_KATEGORI_URUT), k))


def stacked_share(categories, series, axis_title, horizontal=False, height=None):
    """Batang 100% bertumpuk. categories = label batang; series = list dict(name, color, values, hover) dengan
    values dalam TWh (None = tidak ada baris data, tidak digambar). Plotly menormalkan tinggi batang ke 100%."""
    fig = go.Figure()
    for s in series:
        vals = _clean(list(s["values"]))
        kw = dict(orientation="h", y=list(categories), x=vals) if horizontal else dict(x=list(categories), y=vals)
        fig.add_trace(go.Bar(name=s["name"], marker_color=s["color"], hovertext=s["hover"], hoverinfo="text", **kw))
    fig.update_layout(barmode="stack", barnorm="percent", plot_bgcolor="white",
                      height=height or (330 if not horizontal else 160 + 36 * len(categories)),
                      margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", yanchor="top", y=-0.18 if not horizontal else -0.3, x=0))
    if horizontal:
        fig.update_xaxes(title=axis_title, range=[0, 100], gridcolor="#E6EFEA")
        fig.update_yaxes(title=None, autorange="reversed")
    else:
        fig.update_yaxes(title=axis_title, range=[0, 100], gridcolor="#E6EFEA")
        fig.update_xaxes(title=None, dtick=1, tickformat="d")
    return fig


def treemap_frame(df):
    """Baris yang boleh digambar pada treemap: hanya TWh > 0 dan bukan NULL (luas 0 tidak bermakna)."""
    d = df[df["twh"].notna() & (df["twh"] > 0)]
    return d.copy()


def mix_treemap(df):
    """Treemap kategori (induk) dan sumber (anak), luas = TWh. df = baris sumber satu tahun (kolom kategori, sumber, twh)."""
    d = treemap_frame(df)
    ids, labels, parents, values, colors, hover = [], [], [], [], [], []
    for i, kat in enumerate(urut_kategori(d["kategori"])):
        anak = d[d["kategori"] == kat].sort_values("twh", ascending=False)
        ids.append(kat); labels.append(kategori_label(kat)); parents.append("")
        values.append(float(anak["twh"].sum())); colors.append(kategori_color(kat, i))
        hover.append(f"{kategori_label(kat)}<br>{theme.fmt_num(float(anak['twh'].sum()), 1)} TWh")
        for j, r in enumerate(anak.itertuples()):
            ids.append(f"{kat}/{r.sumber}"); labels.append(sumber_label(r.sumber)); parents.append(kat)
            values.append(float(r.twh)); colors.append(sumber_color(r.sumber, j))
            hover.append(f"{sumber_label(r.sumber)} ({kategori_label(kat)})<br>{theme.fmt_num(float(r.twh), 1)} TWh")
    fig = go.Figure(go.Treemap(ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
                               marker=dict(colors=colors), hovertext=hover, hoverinfo="text",
                               textinfo="label+percent root", tiling=dict(pad=2)))
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
    return fig


# =====================================================================================
# Grafik Halaman D (Fase 4-3d & Redesign R17): pangsa terbarukan vs intensitas emisi (keduanya Ember)
# =====================================================================================
MARKER_EDGE = "#4B5563"   # tepi titik sebaran: abu gelap netral (kontras 7,6:1 terhadap putih) agar warna terang tetap terbaca
D_X_TITLE = "Pangsa listrik terbarukan, Ember (%)"
D_Y_TITLE = "Intensitas emisi (gCO₂e/kWh)"


def _size_ref(values, max_px: int = 44) -> float:
    """sizeref untuk ukuran titik berbasis LUAS: negara terbesar bergaris tengah max_px piksel."""
    positif = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v)) and v > 0]
    return 2.0 * (max(positif) if positif else 1.0) / (max_px ** 2)


def scatter_regression(df, intersep, lereng, x_min, x_max, year, sorotan=None, nama_sorotan=None):
    """Sebaran pangsa (x) vs intensitas (y); ukuran = pembangkitan, warna = benua; garis regresi sederhana;
    4 label zona kuadran di latar; titik non-sorotan lebih lembut (opacity 0.35) agar sorotan menonjol."""
    fig = go.Figure()
    sizeref = _size_ref(df["pembangkitan_twh"])
    for benua in sorted(df["benua"].unique()):
        d = df[df["benua"] == benua]
        hover = [f"<b>{r.country_name}</b> ({benua}), {year}<br>"
                 f"Pangsa listrik terbarukan (Ember): {theme.fmt_pct(r.pangsa_bulat, 1)}<br>"
                 f"Intensitas emisi: {theme.fmt_num(r.intensitas_bulat, 1)} gCO₂e/kWh<br>"
                 f"Pembangkitan: {theme.fmt_num(r.pembangkitan_bulat, 1)} TWh" for r in d.itertuples()]
        fig.add_trace(go.Scatter(
            x=d["pangsa"].tolist(), y=d["intensitas"].tolist(), mode="markers", name=benua,
            marker=dict(size=d["pembangkitan_twh"].tolist(), sizemode="area", sizeref=sizeref, sizemin=4,
                        color=CONTINENT_COLORS.get(benua, "#999999"), opacity=0.35, line=dict(color=MARKER_EDGE, width=0.5)),
            hovertext=hover, hoverinfo="text"))
    xs = [float(x_min), float(x_max)]
    ys = [float(intersep) + float(lereng) * x for x in xs]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Garis regresi sederhana",
                             line=dict(color="#1F2933", width=2, dash="dash"),
                             hovertext=[f"Garis regresi: intensitas = {theme.fmt_num(intersep, 1)} + "
                                        f"({theme.fmt_num(lereng, 1)}) x pangsa<br>Pangsa {theme.fmt_num(x, 1)}%: "
                                        f"{theme.fmt_num(y, 1)} gCO₂e/kWh" for x, y in zip(xs, ys)], hoverinfo="text"))
    if sorotan is not None and len(sorotan):
        r = sorotan.iloc[0]
        fig.add_trace(go.Scatter(
            x=[r["pangsa"]], y=[r["intensitas"]], mode="markers", name=f"Sorotan: {nama_sorotan}",
            marker=dict(size=22, symbol="circle-open", color=theme.COLOR_HIGHLIGHT, line=dict(width=3.5)),
            hovertext=[f"<b>{r['country_name']}</b> (sorotan), {year}<br>"
                       f"Pangsa listrik terbarukan (Ember): {theme.fmt_pct(r['pangsa_bulat'], 1)}<br>"
                       f"Intensitas emisi: {theme.fmt_num(r['intensitas_bulat'], 1)} gCO₂e/kWh<br>"
                       f"Pembangkitan: {theme.fmt_num(r['pembangkitan_bulat'], 1)} TWh"], hoverinfo="text"))
    # 4 label zona kuadran transparan di latar grafik (tidak mengubah fig.data)
    kuadran = [
        (0.02, 0.98, "left", "top", "Terbarukan Rendah • Emisi Tinggi", "rgba(254, 226, 226, 0.65)", "#991B1B"),
        (0.98, 0.98, "right", "top", "Terbarukan Tinggi • Emisi Tinggi", "rgba(254, 243, 199, 0.65)", "#92400E"),
        (0.02, 0.03, "left", "bottom", "Terbarukan Rendah • Emisi Rendah", "rgba(224, 242, 254, 0.65)", "#075985"),
        (0.98, 0.03, "right", "bottom", "Terbarukan Tinggi • Emisi Rendah", "rgba(209, 250, 229, 0.70)", "#065F46"),
    ]
    for qx, qy, xa, ya, teks, bg, fg in kuadran:
        fig.add_annotation(
            x=qx, y=qy, xref="paper", yref="paper", xanchor=xa, yanchor=ya,
            text=teks, showarrow=False, font=dict(size=10.5, color=fg),
            bgcolor=bg, borderpad=4,
        )
    fig.update_layout(height=540, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", yanchor="top", y=-0.14, x=0),
                      xaxis=dict(title=D_X_TITLE, range=[-3, 103], gridcolor="#E6EFEA", zeroline=False),
                      yaxis=dict(title=D_Y_TITLE, rangemode="tozero", gridcolor="#E6EFEA"))
    return fig


def corr_bar(df):
    """Batang horizontal korelasi Pearson per benua. df: benua, n, pearson_bulat (hanya benua yang n-nya cukup).
    Label (r dan n) diletakkan di luar ujung batang; rentang sumbu x diperlebar sebesar ruang label supaya label berada
    DI DALAM area plot dan tidak menimpa nama benua pada sumbu y (tanpa mengecilkan font dan tanpa menghapus informasi)."""
    d = df.iloc[::-1]
    r = [float(x) for x in d["pearson_bulat"]]
    pad = 0.42                                           # lebar ruang label dalam satuan sumbu x (label ~ 18 karakter)
    lo, hi = min(min(r), 0.0) - pad, max(max(r), 0.0) + pad
    lo, hi = max(lo, -1 - pad), min(hi, 1 + pad)
    fig = go.Figure(go.Bar(
        x=r, y=d["benua"].tolist(), orientation="h", width=0.62,
        marker_color=[CONTINENT_COLORS.get(b, "#999999") for b in d["benua"]],
        text=[f"r = {theme.fmt_num(x, 2)} (n = {int(n)})" for x, n in zip(r, d["n"])],
        textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#0F2922"),
        hovertext=[f"{b}<br>Pearson: {theme.fmt_num(x, 2)}<br>Jumlah negara: {int(n)}"
                   for b, x, n in zip(d["benua"], r, d["n"])], hoverinfo="text"))
    fig.update_layout(height=max(300, 90 + 54 * len(d)), margin=dict(l=10, r=20, t=10, b=10),
                      xaxis=dict(title="Korelasi Pearson (r)", range=[lo, hi], tickvals=[-1, -0.5, 0, 0.5, 1],
                                 ticktext=["-1", "-0,5", "0", "0,5", "1"], gridcolor="#E6EFEA", zeroline=True, zerolinecolor="#6B7280", zerolinewidth=1.5),
                      yaxis=dict(title=None, automargin=True, tickfont=dict(size=12.5, color="#0F2922")))
    return fig


def change_scatter(df, year, base):
    """Sebaran perubahan: x = perubahan pangsa (poin), y = perubahan intensitas; hanya negara bernilai lengkap."""
    fig = go.Figure()
    sizeref = _size_ref(df["pembangkitan_raw"])
    for benua in sorted(df["benua"].unique()):
        d = df[df["benua"] == benua]
        hover = [f"<b>{r.country_name}</b> ({benua})<br>Pangsa {base} ke {year}: {theme.fmt_num(r.pangsa_awal, 1)}% ke "
                 f"{theme.fmt_num(r.pangsa_akhir, 1)}% ({theme.fmt_delta(r.d_pangsa, 1, ' poin')})<br>"
                 f"Intensitas {base} ke {year}: {theme.fmt_num(r.intensitas_awal, 1)} ke "
                 f"{theme.fmt_num(r.intensitas_akhir, 1)} ({theme.fmt_delta(r.d_intensitas, 1, ' gCO₂e/kWh')})<br>"
                 f"Pembangkitan {year}: {theme.fmt_num(r.pembangkitan_twh, 1)} TWh" for r in d.itertuples()]
        fig.add_trace(go.Scatter(
            x=d["d_pangsa"].tolist(), y=d["d_intensitas"].tolist(), mode="markers", name=benua,
            marker=dict(size=d["pembangkitan_raw"].tolist(), sizemode="area", sizeref=sizeref, sizemin=4,
                        color=CONTINENT_COLORS.get(benua, "#999999"), opacity=0.72, line=dict(color=MARKER_EDGE, width=0.5)),
            hovertext=hover, hoverinfo="text"))
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", yanchor="top", y=-0.16, x=0),
                      xaxis=dict(title=f"Perubahan pangsa terbarukan {base} ke {year} (poin persentase)",
                                 gridcolor="#E6EFEA", zeroline=True, zerolinecolor="#6B7280"),
                      yaxis=dict(title=f"Perubahan intensitas emisi {base} ke {year} (gCO₂e/kWh)",
                                 gridcolor="#E6EFEA", zeroline=True, zerolinecolor="#6B7280"))
    return fig


def residual_bar(df):
    """Batang horizontal selisih (aktual dikurangi garis regresi) untuk negara pencilan. df urut peringkat 1 dulu."""
    d = df.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["selisih"], y=d["country_name"], orientation="h",
        marker_color=["#E69F00" if v > 0 else "#56B4E9" for v in d["selisih"]],
        text=[theme.fmt_delta(v, 1) for v in d["selisih"]], textposition="outside", cliponaxis=False,
        hovertext=[f"{r.country_name} ({r.benua})<br>Intensitas aktual: {theme.fmt_num(r.intensitas, 1)} gCO₂e/kWh<br>"
                   f"Menurut garis: {theme.fmt_num(r.intensitas_garis, 1)} gCO₂e/kWh<br>"
                   f"Selisih: {theme.fmt_delta(r.selisih, 1)} gCO₂e/kWh" for r in d.itertuples()], hoverinfo="text"))
    fig.update_layout(height=max(300, 70 + 34 * len(d)), margin=dict(l=10, r=60, t=10, b=10), plot_bgcolor="white",
                      xaxis=dict(title="Selisih intensitas: aktual dikurangi garis regresi (gCO₂e/kWh)",
                                 gridcolor="#E6EFEA", zeroline=True, zerolinecolor="#6B7280"),
                      yaxis=dict(title=None))
    return fig


# =====================================================================================
# Grafik halaman Kualitas Data (Fase 4-3e)
# =====================================================================================
def coverage_bar(df, year):
    """Batang horizontal coverage (%) per indikator pada satu tahun dengan label gabungan absolut+persen dan legenda sumber."""
    d = df.iloc[::-1]
    label = [f"{i} ({s})" for i, s in zip(d["indikator"], d["sumber"])]
    warna = [theme.COLOR_RENEWABLE if s == "Renewable" else theme.COLOR_HIGHLIGHT for s in d["sumber"]]
    hover = [f"{lab}<br>Tersedia: {theme.fmt_num(t, 0)} dari {theme.fmt_num(m, 0)} negara master ({theme.fmt_pct(c, 1)})"
             for lab, t, m, c in zip(label, d["tersedia"], d["negara_master"], d["coverage"])]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["coverage"].tolist(), y=label, orientation="h", marker_color=warna,
        text=[f"{theme.fmt_num(t, 0)} dari {theme.fmt_num(m, 0)} ({theme.fmt_pct(c, 1)})"
              for t, m, c in zip(d["tersedia"], d["negara_master"], d["coverage"])],
        textposition="outside", cliponaxis=False, hovertext=hover, hoverinfo="text", showlegend=False,
    ))
    # Legenda warna sumber data (tidak mengubah data[0] yang diverifikasi test_halaman_kualitas)
    for nama_sumber, col in (("Sumber: Renewable Energy Share", theme.COLOR_RENEWABLE), ("Sumber: Ember", theme.COLOR_HIGHLIGHT)):
        fig.add_trace(go.Bar(x=[None], y=[None], orientation="h", name=nama_sumber, marker_color=col, showlegend=True))
    fig.update_layout(
        height=max(320, 90 + 44 * len(d)), margin=dict(l=10, r=145, t=10, b=10), plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0),
        xaxis=dict(title=f"Coverage {year} (% dari negara master)", range=[0, 122],
                   tickvals=[0, 20, 40, 60, 80, 100], gridcolor="#E6EFEA"),
        yaxis=dict(title=None),
    )
    return fig


def source_scatter(df, year):
    """Pangsa terbarukan Ember (y) vs Renewable (x) per negara pada satu tahun, dengan garis y = x sebagai acuan."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Kedua sumber sama (y = x)",
                             line=dict(color="#6B7280", dash="dash", width=2), hoverinfo="skip"))
    for benua in sorted(df["benua"].unique()):
        d = df[df["benua"] == benua]
        hover = [f"<b>{r.country_name}</b> ({benua}), {year}<br>Renewable: {theme.fmt_pct(r.pangsa_renewable_bulat, 1)}<br>"
                 f"Ember: {theme.fmt_pct(r.pangsa_ember_bulat, 1)}" for r in d.itertuples()]
        fig.add_trace(go.Scatter(x=d["pangsa_renewable"].tolist(), y=d["pangsa_ember"].tolist(), mode="markers", name=benua,
                                 marker=dict(size=8, color=CONTINENT_COLORS.get(benua, "#999999"), opacity=0.8,
                                             line=dict(color=MARKER_EDGE, width=0.5)),
                                 hovertext=hover, hoverinfo="text"))
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", yanchor="top", y=-0.24, x=0),
                      xaxis=dict(title="Pangsa listrik terbarukan, Renewable Energy Share (%)", range=[-3, 103], gridcolor="#E6EFEA"),
                      yaxis=dict(title="Pangsa listrik terbarukan, Ember (%)", range=[-3, 103], gridcolor="#E6EFEA"))
    return fig
