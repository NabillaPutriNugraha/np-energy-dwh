"""Komponen UI reusable untuk dashboard NP Energy Intelligence ("Luminous Eco-Intelligence").
Lapisan presentasi murni: tidak menyentuh koneksi database, SQL, maupun rumus perhitungan KPI."""
import html

import streamlit as st

_SVG_ICONS = {
    "eco": (
        '<svg width="78" height="62" viewBox="0 0 78 62" fill="none" aria-hidden="true">'
        '<circle cx="56" cy="18" r="11" fill="rgba(255,255,255,0.22)"/>'
        '<circle cx="56" cy="18" r="6" fill="rgba(255,255,255,0.45)"/>'
        '<path d="M22 54V28M22 28L12 18M22 28L34 22M22 28L20 12" stroke="rgba(255,255,255,0.88)" stroke-width="2.4" stroke-linecap="round"/>'
        '<circle cx="22" cy="28" r="3" fill="#FFFFFF"/>'
        '<path d="M8 54H70" stroke="rgba(255,255,255,0.35)" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M38 54L46 40L54 46L66 30" stroke="#A7F3D0" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "fossil": (
        '<svg width="78" height="62" viewBox="0 0 78 62" fill="none" aria-hidden="true">'
        '<rect x="12" y="34" width="12" height="20" rx="3" fill="rgba(255,255,255,0.28)"/>'
        '<rect x="30" y="24" width="12" height="30" rx="3" fill="rgba(255,255,255,0.42)"/>'
        '<rect x="48" y="16" width="12" height="38" rx="3" fill="rgba(253,230,138,0.55)"/>'
        '<path d="M10 18L36 28L66 42" stroke="#FDE68A" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="4 4"/>'
        '<path d="M8 54H70" stroke="rgba(255,255,255,0.35)" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "mix": (
        '<svg width="78" height="62" viewBox="0 0 78 62" fill="none" aria-hidden="true">'
        '<rect x="10" y="12" width="26" height="24" rx="4" fill="rgba(255,255,255,0.30)"/>'
        '<rect x="40" y="12" width="28" height="14" rx="4" fill="rgba(165,243,252,0.55)"/>'
        '<rect x="40" y="30" width="14" height="22" rx="4" fill="rgba(253,224,71,0.55)"/>'
        '<rect x="58" y="30" width="10" height="22" rx="4" fill="rgba(167,243,208,0.65)"/>'
        '<rect x="10" y="40" width="26" height="12" rx="4" fill="rgba(255,255,255,0.18)"/>'
        '</svg>'
    ),
    "intensity": (
        '<svg width="78" height="62" viewBox="0 0 78 62" fill="none" aria-hidden="true">'
        '<path d="M12 12V52H68" stroke="rgba(255,255,255,0.45)" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M18 18L62 46" stroke="#FDE68A" stroke-width="2.2" stroke-dasharray="4 4" stroke-linecap="round"/>'
        '<circle cx="24" cy="22" r="4" fill="rgba(255,255,255,0.55)"/>'
        '<circle cx="38" cy="30" r="5.5" fill="rgba(167,243,208,0.85)"/>'
        '<circle cx="52" cy="40" r="4.5" fill="rgba(255,255,255,0.65)"/>'
        '<circle cx="44" cy="24" r="6" stroke="#FFFFFF" stroke-width="2.2"/>'
        '</svg>'
    ),
    "quality": (
        '<svg width="78" height="62" viewBox="0 0 78 62" fill="none" aria-hidden="true">'
        '<path d="M39 8L62 17V32C62 44.5 52 52.5 39 56C26 52.5 16 44.5 16 32V17L39 8Z" fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.72)" stroke-width="2"/>'
        '<path d="M29 32L36 39L50 24" stroke="#A7F3D0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
}


def active_filter_chips(year: int, continents, all_continents, groups, all_groups,
                        country_name: str | None = None, ignore_region: bool = False) -> list[str]:
    """Membentuk daftar chip ringkas status filter aktif untuk ditampilkan di Hero Banner."""
    chips = [f"Tahun: {int(year)}"]
    if ignore_region:
        chips.append("Cakupan: Seluruh data (lintas benua & kelompok)")
    else:
        if len(continents) == len(all_continents):
            chips.append("Benua: Semua")
        elif len(continents) == 0:
            chips.append("Benua: Kosong")
        elif len(continents) <= 2:
            chips.append("Benua: " + ", ".join(continents))
        else:
            chips.append(f"Benua: {len(continents)} dipilih")

        if len(groups) == len(all_groups):
            chips.append("Kelompok: Semua")
        elif len(groups) == 0:
            chips.append("Kelompok: Kosong")
        elif len(groups) <= 2:
            chips.append("Kelompok: " + ", ".join(groups))
        else:
            chips.append(f"Kelompok: {len(groups)} dipilih")

    if country_name:
        chips.append(f"Sorotan: {country_name}")
    return chips


def hero_banner(title: str, subtitle: str, chips: list[str] | None = None, variant: str = "eco") -> None:
    """Merender Hero Banner kompak bergradien dengan chip filter aktif dan ilustrasi SVG inline."""
    v = variant if variant in _SVG_ICONS else "eco"
    chip_html = "".join(f'<span class="np-chip">{html.escape(str(c))}</span>' for c in (chips or []))
    art = _SVG_ICONS[v]
    st.markdown(
        f'<div class="np-hero np-hero--{v}">'
        f'  <div class="np-hero__body">'
        f'    <div class="np-hero__title">{html.escape(title)}</div>'
        f'    <div class="np-hero__sub">{html.escape(subtitle)}</div>'
        f'    <div class="np-hero__chips">{chip_html}</div>'
        f'  </div>'
        f'  <div class="np-hero__art">{art}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def micro_guide(text: str) -> None:
    """Merender 1 baris mikro-panduan membaca grafik di atas chart utama."""
    st.markdown(
        f'<div class="np-guide"><span>💡</span><span>{html.escape(text)}</span></div>',
        unsafe_allow_html=True,
    )


def insight_box(text: str) -> None:
    """Merender kotak insight deskriptif di bawah chart utama."""
    st.markdown(
        f'<div class="np-insight"><span>📌</span><span>{html.escape(text)}</span></div>',
        unsafe_allow_html=True,
    )


def filter_empty_message(continents, groups) -> str:
    """Pesan empty state kontekstual: membedakan filter kosong vs kombinasi filter yang tidak beririsan."""
    if not continents or not groups:
        return "Tidak ada negara yang memenuhi filter. Pilih minimal satu benua dan satu kelompok negara di sidebar."
    return "Tidak ada negara yang memenuhi kombinasi filter benua dan kelompok negara ini."


def empty_state(message: str, hint: str = "Coba pilih kembali benua, kelompok negara, atau tahun lain di panel Filter sebelah kiri.") -> None:
    """Merender kartu empty state ramah pengguna sekaligus st.info agar kontrak pesan tetap terbaca."""
    st.markdown(
        '<div class="np-empty">'
        '  <div style="font-size:1.5rem;line-height:1;">🔍</div>'
        f'  <div class="np-empty__title">{html.escape(message)}</div>'
        f'  <div class="np-empty__desc">{html.escape(hint)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.info(message)


def status_cards(items: list[dict]) -> None:
    """Merender 3 kartu ringkasan status visual (dipakai di halaman Kualitas Data)."""
    cards = []
    for it in items:
        cls = "np-status-card np-status-card--warn" if it.get("warn") else "np-status-card"
        cards.append(
            f'<div class="{cls}">'
            f'  <div class="np-status-card__eyebrow">{html.escape(str(it["eyebrow"]))}</div>'
            f'  <div class="np-status-card__val">{html.escape(str(it["value"]))}</div>'
            f'  <div class="np-status-card__note">{html.escape(str(it["note"]))}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="np-status-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def glossary_box(title: str, terms: list[tuple[str, str]]) -> None:
    """Merender kamus istilah awam dalam grid 3 kolom."""
    items = "".join(
        f'<div class="np-glossary__item">'
        f'  <div class="np-glossary__term">{html.escape(term)}</div>'
        f'  <div class="np-glossary__def">{html.escape(desc)}</div>'
        f'</div>'
        for term, desc in terms
    )
    st.markdown(
        f'<div class="np-glossary">'
        f'  <div class="np-glossary__head">{html.escape(title)}</div>'
        f'  <div class="np-glossary__grid">{items}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def etl_sidebar_card(run_id: int, waktu: str, rows_loaded: int | None = None) -> None:
    """Kotak status sinkronisasi ETL rapi di bagian bawah sidebar (memuat info sumber PostgreSQL)."""
    baris_txt = f" • {rows_loaded:,}".replace(",", ".") + " baris DW" if rows_loaded is not None else ""
    st.sidebar.markdown(
        '<div class="np-etl-box">'
        '  <div class="np-etl-box__head"><span class="np-etl-dot"></span>Sinkronisasi Data Aktif</div>'
        f'  <div class="np-etl-box__meta">Run #{int(run_id)}{html.escape(baris_txt)}<br>'
        f'Diperbarui: {html.escape(waktu)}<br>'
        'Sumber: Data Warehouse PostgreSQL (schema mart)</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def correlation_card_accent(v1, v2, v3) -> None:
    """Memberi warna aksen semantik merah coral (negatif) / hijau emerald (positif) pada 3 kartu korelasi Halaman D."""
    import math

    def _pair(val):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return "#047857", "#0F2922"
        return ("#DC2626", "#B91C1C") if float(val) < 0 else ("#059669", "#047857")

    rules = []
    for idx, val in enumerate((v1, v2, v3), start=1):
        b, fg = _pair(val)
        rules.append(
            f'[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]:nth-child({idx}) '
            f'[data-testid="stMetric"] {{ box-shadow: 0 2px 10px rgba(6, 78, 59, 0.04), inset 0 3px 0 {b}; }}'
            f'[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]:nth-child({idx}) '
            f'[data-testid="stMetricValue"] {{ color: {fg} !important; }}'
        )
    st.markdown(f"<style>{''.join(rules)}</style>", unsafe_allow_html=True)
