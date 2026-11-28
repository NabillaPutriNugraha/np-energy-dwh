"""Palet warna, label berbahasa Indonesia, dan format angka (koma desimal, titik ribuan)."""
import math

# Warna data utama diselaraskan dengan Luminous Eco-Intelligence dan tetap memperhatikan keterbedaan pada buta warna.
# Pemetaan warna ke makna (terbarukan, fosil, intensitas, sorotan, nuklir, coral) adalah KEPUTUSAN DESAIN proyek.
COLOR_RENEWABLE = "#059669"   # terbarukan (Emerald, kontras 3,77:1 dg putih)
COLOR_FOSSIL = "#475569"      # fosil (Slate, kontras 7,58:1 dg putih)
COLOR_INTENSITY = "#D55E00"   # intensitas emisi (Okabe-Ito Vermilion, kontras 3,84:1 dg putih)
COLOR_HIGHLIGHT = "#0072B2"   # negara sorotan (Okabe-Ito Blue, kontras 5,19:1 dg putih)
COLOR_NUCLEAR = "#CC79A7"     # nuklir (Okabe-Ito Reddish Purple, kontras 3,06:1 dg putih)
COLOR_CORAL = "#DC2626"       # aksen semantik negatif / peringkat terendah (kontras 4,83:1 dg putih)

LABEL = {
    "terbarukan": "Pangsa listrik terbarukan (%)",
    "fosil": "Pangsa listrik fosil (%)",
    "intensitas": "Intensitas emisi (gCO₂e/kWh)",
}


def _id(x: float, dec: int) -> str:
    s = f"{x:,.{dec}f}"                       # 1,234.5
    return s.replace(",", "§").replace(".", ",").replace("§", ".")   # 1.234,5


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def fmt_pct(x, dec: int = 1) -> str:
    return f"{_id(float(x), dec)}%" if _ok(x) else "tidak ada data"


def fmt_num(x, dec: int = 0) -> str:
    return _id(float(x), dec) if _ok(x) else "tidak ada data"


def fmt_delta(x, dec: int = 1, unit: str = ""):
    """Selisih bertanda untuk st.metric. Tanda minus memakai '-' biasa agar dibaca benar oleh Streamlit."""
    if not _ok(x):
        return None
    s = _id(abs(float(x)), dec)
    sign = "-" if round(float(x), dec) < 0 else "+"
    return f"{sign}{s}{unit}"
