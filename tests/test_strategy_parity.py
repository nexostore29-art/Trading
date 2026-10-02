"""La estrategia de Freqtrade debe generar exactamente las mismas señales que el motor de investigación.

Si esto falla, el backtest de investigación deja de describir lo que el bot hace en vivo.
Requiere data/processed/BTCUSD_4h.csv (python research/prepare_data.py) y freqtrade instalado.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "BTCUSD_4h.csv"
pytest.importorskip("freqtrade")
if not DATA.exists():
    pytest.skip("faltan datos procesados", allow_module_level=True)

sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "freqtrade" / "user_data" / "strategies"))
import strategies as research  # noqa: E402
from DonchianTrend import K_ATR, N_ENTRY, N_EXIT, DonchianTrend  # noqa: E402


@pytest.fixture(scope="module")
def frames():
    df = pd.read_csv(DATA, index_col=0, parse_dates=True)
    df = df[df.index >= pd.Timestamp("2017-01-01", tz="UTC")]
    ft = df.reset_index().rename(columns={"timestamp": "date"})
    strat = DonchianTrend({"stake_currency": "USDT", "dry_run": True, "timeframe": "4h"})
    ft = strat.populate_indicators(ft.copy(), {"pair": "BTC/USDT"})
    ft = strat.populate_entry_trend(ft, {"pair": "BTC/USDT"})
    ft = strat.populate_exit_trend(ft, {"pair": "BTC/USDT"})
    sig = research.donchian(df, n=N_ENTRY, m=N_EXIT, k=K_ATR)
    return ft, sig


def test_entradas_identicas(frames):
    ft, sig = frames
    assert np.array_equal(ft["enter_long"].fillna(0).astype(bool).to_numpy(), sig["entry"])


def test_salidas_identicas(frames):
    ft, sig = frames
    assert np.array_equal(ft["exit_long"].fillna(0).astype(bool).to_numpy(), sig["exit"])


def test_atr_identico(frames):
    ft, sig = frames
    assert np.allclose(ft["atr"].to_numpy(), sig["atr"], equal_nan=True)


def test_hay_senales(frames):
    ft, _ = frames
    assert ft["enter_long"].fillna(0).sum() > 100
