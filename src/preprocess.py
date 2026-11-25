"""Preprocessing: raw -> processed. Output: data/processed/*.csv dan logs/preprocess.log"""
import csv, io, logging
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT, LOGS = ROOT / "data/raw", ROOT / "data/processed", ROOT / "logs"
OUT.mkdir(parents=True, exist_ok=True); LOGS.mkdir(exist_ok=True)
logging.basicConfig(filename=LOGS / "preprocess.log", filemode="w", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("preprocess")
Y0, Y1 = 2019, 2023

EMBER_COLS = ["area", "iso_3_code", "year", "area_type", "electricity_source", "is_aggregated_source",
    "generation_twh", "generation_yoy_change_twh", "generation_yoy_change_pct", "share_of_generation_pct",
    "share_of_generation_yoy_change_pct_points", "capacity_gw", "emissions_mtco2e",
    "emissions_yoy_change_mtco2e", "emissions_yoy_change_pct", "share_of_emissions_pct",
    "emissions_intensity_gco2e/kwh", "continent", "ember_region", "eu_member", "oecd_member",
    "g20_member", "g7_member", "asean_member"]
NUMERIC = EMBER_COLS[6:17]

def read_ember_raw(path):
    """Baris yang seluruhnya dibungkus kutip (karena koma di nama sumber) terbaca 1 kolom -> diurai ulang."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    body, fixed = rows[1:], 0
    for i, r in enumerate(body):
        if len(r) == 1:
            body[i] = next(csv.reader(io.StringIO(r[0]))); fixed += 1
    df = pd.DataFrame(body, columns=EMBER_COLS)
    log.info("EMBER raw=%d baris, baris rusak diperbaiki=%d", len(df), fixed)
    return df, fixed

def clean_ember(df):
    df = df.replace("", pd.NA)
    df["year"] = pd.to_numeric(df["year"]).astype(float)
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c])
    df["is_aggregated_source"] = df["is_aggregated_source"].map({"True": True, "False": False})
    n0 = len(df)
    df = df[df["year"].between(Y0, Y1)]
    log.info("filter tahun %d-%d: %d -> %d", Y0, Y1, n0, len(df))
    n1 = len(df); df = df[df["area_type"] == "Country or economy"]
    log.info("filter area_type=Country or economy: %d -> %d", n1, len(df))
    n2 = len(df); df = df[df["iso_3_code"].notna()]
    log.info("buang ISO3 kosong: %d -> %d", n2, len(df))
    keep = (~df["is_aggregated_source"]) | df["electricity_source"].isin(["Total generation", "Renewables"])
    n3 = len(df); df = df[keep]
    log.info("buang agregat selain Total generation/Renewables: %d -> %d", n3, len(df))
    n4 = len(df); df = df[df["electricity_source"] != "Net imports"]
    log.info("buang 'Net imports' (bukan sumber pembangkitan): %d -> %d", n4, len(df))
    return df.reset_index(drop=True)

def clean_renewable(path):
    df = pd.read_csv(path)
    log.info("RENEWABLE raw=%d baris x %d kolom", *df.shape)
    n0 = len(df); df = df[df["year"].between(Y0, Y1)]
    log.info("filter tahun %d-%d: %d -> %d", Y0, Y1, n0, len(df))
    n1 = len(df); df = df[df["iso_code"].notna()]
    log.info("buang baris tanpa iso_code (wilayah/agregat): %d -> %d", n1, len(df))
    return df.reset_index(drop=True)

if __name__ == "__main__":
    raw, fixed = read_ember_raw(RAW / "release_generation_yearly_global.csv")
    em = clean_ember(raw)
    rn = clean_renewable(RAW / "renewable_energy_share_2000_2025.csv")
    em.to_csv(OUT / "ember_cleaned_2019_2023.csv", index=False)
    rn.to_csv(OUT / "renewable_cleaned_2019_2023.csv", index=False)
    log.info("selesai: ember=%d, renewable=%d", len(em), len(rn))
    print("ember:", em.shape, "| renewable:", rn.shape)
