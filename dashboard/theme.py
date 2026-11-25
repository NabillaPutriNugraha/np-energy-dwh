"""Palet warna, label berbahasa Indonesia, dan format angka (koma desimal, titik ribuan)."""
import math

# Warna data utama berasal dari palet Okabe-Ito (Okabe & Ito 2008; Wong 2011) yang dirancang agar dapat dibedakan pada buta warna merah-hijau.
# Pemetaan warna ke makna (terbarukan, fosil, intensitas, sorotan, nuklir) adalah KEPUTUSAN DESAIN proyek, dipakai konsisten di semua halaman.
COLOR_RENEWABLE = "#009E73"   # terbarukan
COLOR_FOSSIL = "#4D4D4D"      # fosil
COLOR_INTENSITY = "#D55E00"   # intensitas emisi
COLOR_HIGHLIGHT = "#0072B2"   # negara sorotan
COLOR_NUCLEAR = "#CC79A7"     # nuklir (halaman C)

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
