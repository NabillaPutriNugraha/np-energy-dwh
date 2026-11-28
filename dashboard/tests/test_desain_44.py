"""Uji desain "Luminous Eco-Intelligence" (pembaruan dari Fase 4-4): menjaga kontras WCAG, keterbedaan buta warna,
konsistensi palet semantik, dan kualitas teks agar tidak berubah diam-diam.
Jalankan dari folder proyek:  python dashboard/tests/test_desain_44.py
- Kontras mengikuti rumus WCAG 2.x (luminansi relatif); ambang 4,5:1 (teks, AA), 7:1 (teks, AAA), 3:1 (objek grafis, SC 1.4.11).
- Simulasi buta warna: matriks Machado dkk. (2009) severity 100% pada RGB linear (protanopia, deuteranopia, tritanopia);
  jarak warna = CIELAB dE*ab (CIE76)."""
import inspect
import re
import sys
import tomllib
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np             # noqa: E402

import smoke_test as S         # noqa: E402
from smoke_test import check   # noqa: E402
import charts                  # noqa: E402
import theme                   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BG_CANVAS, BG_SIDEBAR, BG_CARD = "#F4F7F6", "#EAF0EE", "#FFFFFF"
AMBANG_JARAK = 10.0
AMBANG_MARGINAL = 20.0
MARGINAL_DICATAT = {
    ("semantik", "sorotan", "terbarukan"),
    ("benua", "Africa", "Asia"),
    ("benua", "Africa", "South America"),
}
MACHADO = {                   # severity 100%, diterapkan pada RGB linear
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}


def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0


def lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lum(h):
    c = lin(rgb(h))
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def kontras(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def lab(lin_rgb):
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = m @ np.clip(lin_rgb, 0, 1) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def jarak(a, b, mode):
    ca, cb = lin(rgb(a)), lin(rgb(b))
    if mode != "normal":
        m = np.array(MACHADO[mode])
        ca, cb = m @ ca, m @ cb
    return float(np.linalg.norm(lab(ca) - lab(cb)))


def min_jarak(pal, modes=("normal", *MACHADO)):
    """Pasangan terburuk dan jaraknya pada mode penglihatan yang dipilih."""
    terburuk = (None, 1e9)
    for (a, ha), (b, hb) in combinations(pal.items(), 2):
        m = min(jarak(ha, hb, md) for md in modes)
        if m < terburuk[1]:
            terburuk = ((a, b), m)
    return terburuk


def main():
    kode_charts = (ROOT / "dashboard" / "charts.py").read_text(encoding="utf-8")
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    semantik = {"terbarukan": theme.COLOR_RENEWABLE, "fosil": theme.COLOR_FOSSIL, "intensitas": theme.COLOR_INTENSITY,
                "sorotan": theme.COLOR_HIGHLIGHT, "nuklir": theme.COLOR_NUCLEAR}
    print("== Desain Luminous Eco-Intelligence (Audit WCAG & Buta Warna)")

    # ---- 1. kebenaran perhitungan (rumus acuan WCAG)
    check("T1: kontras hitam-putih = 21:1 dan putih-putih = 1:1 (rumus WCAG benar)",
          abs(kontras("#000000", "#FFFFFF") - 21.0) < 1e-9 and abs(kontras("#FFFFFF", "#FFFFFF") - 1.0) < 1e-9)
    check("T1: simulasi buta warna: abu-abu netral tetap abu-abu (matriks Machado menjumlah ke 1 per baris)",
          all(abs(sum(row) - 1.0) < 1e-3 for m in MACHADO.values() for row in m))

    # ---- 2. teks dan tema Streamlit (Luminous Eco-Intelligence)
    check("T2: teks utama terhadap kanvas Soft Mint-Mist (#F4F7F6), sidebar Cool Sage (#EAF0EE), dan kartu putih >= 7:1 (WCAG AAA)",
          kontras(cfg["textColor"], BG_CANVAS) >= 7 and kontras(cfg["textColor"], BG_SIDEBAR) >= 7 and kontras(cfg["textColor"], BG_CARD) >= 7,
          f"{kontras(cfg['textColor'], BG_CANVAS):.2f} / {kontras(cfg['textColor'], BG_SIDEBAR):.2f} / {kontras(cfg['textColor'], BG_CARD):.2f}")
    check("T2: warna primer antarmuka (#047857, teks putih di atasnya) >= 4,5:1 (WCAG 1.4.3 AA)",
          cfg["primaryColor"].upper() == "#047857" and kontras("#FFFFFF", cfg["primaryColor"]) >= 4.5,
          f"{kontras('#FFFFFF', cfg['primaryColor']):.2f}")
    check("T2: warna primer antarmuka berbeda dari warna data 'terbarukan' agar kontrol tidak terbaca sebagai data",
          cfg["primaryColor"].lower() != theme.COLOR_RENEWABLE.lower())
    check("T2: latar kanvas Soft Mint-Mist (#F4F7F6) dan sidebar Cool Sage (#EAF0EE) terpasang konsisten",
          cfg["backgroundColor"].upper() == BG_CANVAS and cfg["secondaryBackgroundColor"].upper() == BG_SIDEBAR)

    # ---- 3. warna data: pembeda pada buta warna & palet cerah M09
    for nama, pal in (("warna semantik tema (terbarukan, fosil, intensitas, sorotan, nuklir)", semantik),
                      ("kategori halaman C (Fossil, Nuklir, Renewable)", charts.KATEGORI_COLOR)):
        pasangan, nilai = min_jarak(pal)
        check(f"T3: {nama}: jarak minimum antar-warna (normal & 3 jenis buta warna) >= {AMBANG_JARAK:.0f}",
              nilai >= AMBANG_JARAK, f"terburuk {pasangan}: {nilai:.1f}")
    benua = {k: v for k, v in charts.CONTINENT_COLORS.items() if k != "Tidak diketahui"}
    pasangan, nilai = min_jarak(benua)
    check(f"T3: 6 warna benua: jarak minimum >= {AMBANG_JARAK:.0f}", nilai >= AMBANG_JARAK, f"terburuk {pasangan}: {nilai:.1f}")
    pas_src, val_src = min_jarak(charts.SUMBER_COLOR, modes=("normal",))
    check(f"T3: 9 warna sumber halaman C (palet cerah M09): jarak minimum penglihatan normal >= {AMBANG_JARAK:.0f}",
          val_src >= AMBANG_JARAK, f"terburuk {pas_src}: {val_src:.1f}")
    marginal = set()
    for nm, pal in (("semantik", semantik), ("kategoriC", charts.KATEGORI_COLOR), ("benua", benua)):
        for (a, ha), (b, hb) in combinations(pal.items(), 2):
            if min(jarak(ha, hb, md) for md in ("normal", *MACHADO)) < AMBANG_MARGINAL:
                marginal.add((nm, *sorted((a, b))))
    check(f"T3: pasangan marginal semantik/kategori/benua (jarak {AMBANG_JARAK:.0f}-{AMBANG_MARGINAL:.0f}) = daftar tercatat ({len(MARGINAL_DICATAT)} pasangan)",
          marginal == MARGINAL_DICATAT, str(sorted(marginal ^ MARGINAL_DICATAT)))
    check("T3: jumlah warna kategori per grafik <= 9 (sumber) dan 7 (benua)",
          len(charts.SUMBER_COLOR) == 9 and len(charts.CONTINENT_COLORS) == 7)
    check("T3: setiap kategori/sumber/benua punya warna unik (tidak ada dua kategori bercat sama)",
          len(set(charts.SUMBER_COLOR.values())) == len(charts.SUMBER_COLOR) and len(set(charts.CONTINENT_COLORS.values())) == len(charts.CONTINENT_COLORS)
          and len(set(charts.KATEGORI_COLOR.values())) == len(charts.KATEGORI_COLOR))
    check("T3: warna kategori halaman C konsisten dengan warna semantik tema (Renewable, Nuklir, Fossil)",
          charts.KATEGORI_COLOR["Renewable"] == theme.COLOR_RENEWABLE and charts.KATEGORI_COLOR["Nuklir"] == theme.COLOR_NUCLEAR
          and charts.KATEGORI_COLOR["Fossil"] == theme.COLOR_FOSSIL)

    # ---- 4. kontras objek grafis (WCAG 1.4.11, 3:1 terhadap putih pada warna semantik & kategori utama)
    utama = {**{f"kategori:{k}": v for k, v in charts.KATEGORI_COLOR.items()},
             **{f"semantik:{k}": v for k, v in semantik.items()},
             "semantik:coral": theme.COLOR_CORAL}
    check("T4: semua warna semantik utama (terbarukan, fosil, intensitas, sorotan, nuklir, coral) >= 3:1 terhadap putih",
          all(kontras(v, BG_CARD) >= 3.0 for v in utama.values()),
          str({k: round(kontras(v, BG_CARD), 2) for k, v in utama.items() if kontras(v, BG_CARD) < 3.0}))
    check("T4: tepi titik sebaran (MARKER_EDGE) >= 4,5:1 dan garis acuan y = x pada sebaran sumber >= 3:1 terhadap putih",
          kontras(charts.MARKER_EDGE, BG_CARD) >= 4.5 and kontras("#6B7280", BG_CARD) >= 3.0 and '"#6B7280", dash="dash"' in kode_charts)
    sumber_sebaran = "".join(inspect.getsource(f) for f in (charts.scatter_regression, charts.change_scatter, charts.source_scatter))
    check("T4: titik pada 3 grafik sebaran (D sebaran, D perubahan, Kualitas Ember vs Renewable) tidak bertepi putih",
          'line=dict(color="white"' not in sumber_sebaran and sumber_sebaran.count("line=dict(color=MARKER_EDGE") >= 3)

    # ---- 5. teks pengembang dan redundant encoding
    kode_halaman = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "dashboard" / "halaman").glob("*.py")}
    kode_theme = (ROOT / "dashboard" / "theme.py").read_text(encoding="utf-8")
    check("T5: tidak ada fungsi/halaman placeholder dan tidak ada kata 'Tahap 4-' di halaman maupun tema",
          "def placeholder" not in kode_theme and not any(re.search(r"Tahap 4-\d", t) for t in kode_halaman.values()) and "Tahap 4-" not in kode_theme)
    teks_semua = []
    for hal in ["ringkasan", "a_terbarukan", "b_fosil", "c_bauran", "d_pangsa_intensitas", "kualitas"]:
        at = S.baru()
        at.switch_page(f"halaman/{hal}.py").run()
        tt = " ".join([e.value for e in at.info] + [e.value for e in at.warning] + [e.value for e in at.caption] + [e.value for e in at.markdown]
                      + [e.value for e in at.title] + [e.value for e in at.subheader])
        teks_semua.append((hal, tt, bool(at.exception)))
    check("T5: semua 6 halaman tampil tanpa error dan tanpa teks pengembang ('Tahap 4', 'dalam pengembangan', 'placeholder', 'TODO' utuh)",
          all(not exc and not any(k in tt.lower() for k in ("tahap 4", "dalam pengembangan", "placeholder")) and not re.search(r"\btodo\b", tt.lower()) for _, tt, exc in teks_semua),
          str([h for h, tt, exc in teks_semua if exc]))
    ring = [tt for h, tt, _ in teks_semua if h == "ringkasan"][0]
    check("T5: Ringkasan merujuk ke halaman Kualitas Data tanpa catatan tahap",
          "lihat halaman Kualitas Data." in ring and "(Tahap" not in ring)
    at = S.baru()
    at.switch_page("halaman/ringkasan.py").run()
    deltas = [m.delta for m in at.metric if m.delta]
    check("T5: selisih pada kartu KPI ditulis dengan tanda +/- dan satuan (tidak hanya dibedakan lewat warna)",
          len(deltas) >= 3 and all(re.match(r"^[+-]\d", d) for d in deltas), str(deltas))
    total, lulus = len(S.HASIL), sum(S.HASIL)
    print(f"\nRINGKASAN DESAIN: {lulus} dari {total} pemeriksaan lulus")
    sys.exit(0 if lulus == total else 1)


if __name__ == "__main__":
    main()
