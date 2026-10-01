"""Convierte velas de 1 minuto (Bitstamp BTC/USD) a 1h, 4h y 1d.

Fuente: https://github.com/ff137/bitstamp-btcusd-minute-data (histórico + actualización diaria).
Se usa como proxy de BTC/USDT de Binance mientras la red no permita descargar datos de Binance.

    python research/prepare_data.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
BASE = "https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/main/data"
FILES = {
    "btcusd_bitstamp_1min_2012-2025.csv.gz": f"{BASE}/historical/btcusd_bitstamp_1min_2012-2025.csv.gz",
    "btcusd_bitstamp_1min_latest.csv": f"{BASE}/updates/btcusd_bitstamp_1min_latest.csv",
}
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def download():
    import urllib.request

    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = RAW / name
        if not dest.exists():
            print(f"descargando {url}")
            urllib.request.urlretrieve(url, dest)


def load_minutes():
    frames = [pd.read_csv(RAW / name) for name in FILES]
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df.drop_duplicates("timestamp").set_index("timestamp").sort_index()[list(AGG)]


def main():
    download()
    df = load_minutes()
    print(f"minutos: {len(df):,}  {df.index[0]} → {df.index[-1]}")
    OUT.mkdir(parents=True, exist_ok=True)
    for tf, rule in {"1h": "1h", "4h": "4h", "1d": "1D"}.items():
        bars = df.resample(rule, label="left", closed="left").agg(AGG).dropna()
        bars = bars[bars["volume"] > 0]
        bars.to_csv(OUT / f"BTCUSD_{tf}.csv")
        print(f"{tf}: {len(bars):,} velas")


if __name__ == "__main__":
    main()
