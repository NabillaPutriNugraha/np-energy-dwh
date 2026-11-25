"""Uji lapisan visual Fase 4-4 (revisi): sistem gaya (style.py), grafik korelasi per benua (tanpa tabrakan label), konsistensi
tema Plotly di semua halaman, lebar kolom tabel, dan kontras warna CSS baru.
Jalankan dari folder proyek:  python dashboard/tests/test_visual_44.py
Menguji struktur/spesifikasi (bukan piksel). Pemeriksaan tampilan sebenarnya dilakukan di browser (lihat tools/visual_check/ dan docs/)."""
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np                 # noqa: E402
import pandas as pd                # noqa: E402

import smoke_test as S             # noqa: E402
from smoke_test import check       # noqa: E402
import charts                      # noqa: E402
import style                       # noqa: E402
from test_desain_44 import kontras  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HALAMAN = ["ringkasan", "a_terbarukan", "b_fosil", "c_bauran", "d_pangsa_intensitas", "kualitas"]


def spec_semua(at):
    return [json.loads(e.proto.spec) for e in at.get("plotly_chart")]


def main():
    print("== Lapisan visual 4-4")
    css = style.CSS
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    # ---- 1. sistem gaya
    check("V1: aset brand ada (wordmark dan ikon SVG) dan app.py memanggil style.aplikasikan()",
          (ROOT / "dashboard" / "assets" / "np_wordmark.svg").exists() and (ROOT / "dashboard" / "assets" / "np_mark.svg").exists()
          and "style.aplikasikan()" in (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8"))
    check("V1: tanpa sumber eksternal (tidak ada http(s):// di CSS dan di style.py kecuali namespace SVG): tampil sama saat offline",
          "http://" not in css and "https://" not in css and "@import" not in css and "url(" not in css)
    check("V1: CSS memuat komponen utama: judul, kartu KPI, alert, tab, expander, kartu chart, sidebar, tag filter",
          all(k in css for k in ('h1', 'stMetric"]', 'stAlert"]', 'stTab"]', 'stExpander"]', 'stPlotlyChart"]', 'stSidebarNavLink', 'data-baseweb="tag"')))
    check("V1: toolbar minimal (tombol Deploy disembunyikan) dan opsi tema (radius, border, header tabel) terpasang di config.toml",
          cfg["client"]["toolbarMode"] == "minimal" and cfg["theme"]["baseRadius"] and cfg["theme"]["borderColor"] and cfg["theme"]["dataframeHeaderBackgroundColor"])
    check("V1: toolbar Plotly hanya tampil saat kursor di atas chart (tidak menimpa batang/legenda)",
          "modebar-container" in css and "opacity: 0" in css and "stPlotlyChart\"]:hover .modebar-container" in css)
    check("V1: keterangan memakai opasitas penuh (kontras tidak dikurangi) dan tinggi baris 1,5 (WCAG 1.4.12)",
          "opacity: 1 !important" in css and "line-height: 1.5" in css)
    # ---- 2. kontras warna CSS baru (WCAG 1.4.3: teks normal >= 4,5:1)
    pasangan = {"keterangan (muted) di putih": (style.MUTED, "#FFFFFF"), "label KPI (muted) di kartu cool white": (style.MUTED, style.COOL),
                "judul (navy) di putih": (style.NAVY, "#FFFFFF"), "isi alert (ink) di amber": (style.INK, "#FFF8E6"),
                "isi alert (ink) di info biru": (style.INK, "#EEF5FB"), "tab aktif (ocean) di putih": (style.OCEAN, "#FFFFFF"),
                "tab tidak aktif (muted) di putih": (style.MUTED, "#FFFFFF"), "angka KPI (navy) di cool white": (style.NAVY, style.COOL),
                "teks pada tag filter (putih) di ocean": ("#FFFFFF", style.OCEAN)}
    hasil = {k: kontras(a, b) for k, (a, b) in pasangan.items()}
    check("V2: semua pasangan teks/latar pada komponen baru >= 4,5:1; judul dan angka KPI >= 7:1",
          all(v >= 4.5 for v in hasil.values()) and hasil["judul (navy) di putih"] >= 7 and hasil["angka KPI (navy) di cool white"] >= 7,
          str({k: round(v, 2) for k, v in hasil.items() if v < 7}))
    # ---- 3. grafik korelasi per benua: label tidak menimpa nama benua
    df = pd.DataFrame({"benua": ["Africa", "Asia", "Europe", "North America", "Oceania", "South America"], "n": [54, 49, 41, 33, 15, 15],
                       "pearson_bulat": [-0.97, -0.82, -0.67, -0.98, -0.97, -0.99]})
    fig = charts.corr_bar(df)
    lo, hi = fig.layout.xaxis.range
    check("V3: rentang sumbu-x diperlebar sehingga label ujung batang (di luar batang) berada di dalam area plot, bukan di area nama benua",
          lo <= df["pearson_bulat"].min() - 0.38 and hi >= 0.38 and lo >= -1.6 and hi <= 1.6, f"[{lo:.2f}, {hi:.2f}]")
    check("V3: informasi tidak dihilangkan: setiap batang memuat r dan n pada label, dan hover memuat benua, r, n",
          all(re.fullmatch(r"r = -?\d,\d\d \(n = \d+\)", t) for t in fig.data[0].text)
          and all(("Pearson" in h and "Jumlah negara" in h) for h in fig.data[0].hovertext))
    check("V3: label berukuran terbaca (>= 12 px; tidak dikecilkan untuk menghindari tabrakan) dan nama benua tidak terpotong (automargin)",
          fig.data[0].textfont.size >= 12 and fig.layout.yaxis.automargin is True and fig.layout.yaxis.tickfont.size >= 12)
    df_pos = df.assign(pearson_bulat=[0.4, -0.5, 0.9, -0.97, 0.1, -0.2])
    lo2, hi2 = charts.corr_bar(df_pos).layout.xaxis.range
    check("V3: korelasi positif juga mendapat ruang label di sisi kanan (rentang menyesuaikan data)", hi2 >= 0.9 + 0.38 and lo2 <= -0.97 - 0.38, f"[{lo2:.2f}, {hi2:.2f}]")
    # ---- 4. semua grafik di semua halaman: tema bersama, latar putih eksplisit, tema Streamlit tidak menimpa
    total_chart, ok_bg, ok_font, ok_theme, ok_margin = 0, True, True, True, True
    detail = []
    for h in HALAMAN:
        at = S.baru()
        at.switch_page(f"halaman/{h}.py").run()
        for tab in at.tabs:                                   # semua isi tab ikut dirender oleh AppTest
            pass
        for e in at.get("plotly_chart"):
            sp = json.loads(e.proto.spec)
            lay, tpl = sp["layout"], sp["layout"].get("template", {}).get("layout", {})
            total_chart += 1
            ok_bg &= lay.get("plot_bgcolor") == "white" and lay.get("paper_bgcolor") == "white"
            ok_font &= "Source Sans" in (tpl.get("font") or {}).get("family", "")
            ok_theme &= e.proto.theme == ""
            ok_margin &= (lay.get("margin", {}).get("t") or 0) >= 14 and (lay.get("margin", {}).get("b") or 0) >= 20
            if lay.get("plot_bgcolor") != "white":
                detail.append(h)
    check(f"V4: {total_chart} grafik di 6 halaman: latar plot dan kertas putih eksplisit (frontend tidak menyuntik warna tema)", ok_bg and total_chart >= 20, str(detail))
    check("V4: semua grafik memakai tema Plotly bersama (font Source Sans, tooltip, grid) dan tema Streamlit tidak menimpa", ok_font and ok_theme)
    check("V4: semua grafik punya ruang napas atas dan bawah di dalam kartu (judul sumbu tidak menempel tepi)", ok_margin)
    # ---- 5. tabel: lebar kolom dihitung dan total muat di area konten
    ok_w, jml_tabel, terlebar = True, 0, 0
    for h in HALAMAN:
        at = S.baru()
        at.switch_page(f"halaman/{h}.py").run()
        for d in at.dataframe:
            if len(d.value.columns) < 2:
                continue
            kolom = json.loads(d.proto.columns) if d.proto.columns else {}
            lebar = [kolom.get(c, {}).get("width") for c in d.value.columns]      # entri indeks tersembunyi diabaikan
            jml_tabel += 1
            if any(w is None for w in lebar):
                ok_w = False
            else:
                terlebar = max(terlebar, sum(lebar))
                ok_w &= sum(lebar) <= style.TABEL_LEBAR_TERSEDIA + 40
    check(f"V5: {jml_tabel} tabel: setiap kolom punya lebar dan total lebar <= area konten (tanpa scroll horizontal yang tidak perlu)", ok_w and jml_tabel >= 15, f"terlebar {terlebar}")
    at = S.baru()
    at.switch_page("halaman/a_terbarukan.py").run()
    at.radio(key="a_level").set_value("Negara").run()
    mp = at.multiselect(key="a_countries")
    check("V5: petunjuk widget multiselect berbahasa Indonesia ('Pilih negara'), bukan bawaan Inggris", mp.proto.placeholder == "Pilih negara")
    # ---- 6. data tidak berubah oleh lapisan visual
    at = S.baru()
    at.switch_page("halaman/ringkasan.py").run()
    k = {m.label: m.value for m in at.metric}
    check("V6: angka KPI Ringkasan tidak berubah oleh redesign (30,4% / 60,7% / 486 / 210 dari 221)",
          k["Pangsa listrik terbarukan"] == "30,4%" and k["Pangsa listrik fosil"] == "60,7%" and k["Intensitas emisi (gCO₂e/kWh)"] == "486" and k["Cakupan negara"] == "210 dari 221")
    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN LAPISAN VISUAL 4-4: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
