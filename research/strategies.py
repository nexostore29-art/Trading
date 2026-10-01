"""Familias de estrategias con evidencia (ver .claude/skills/trading-expert/references/estrategias.md).

Cada función recibe velas OHLC y parámetros, y devuelve las señales que consume backtester.run:
entry/exit evaluadas al cierre de la vela, ATR para el stop, multiplicador de stop y si es trailing.
"""
import itertools

import numpy as np
import pandas as pd


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def _out(entry, exit_, df, k, trail):
    return {"entry": entry.fillna(False).to_numpy(), "exit": exit_.fillna(False).to_numpy(),
            "atr": atr(df).to_numpy(), "stop_mult": k, "trail": trail}


def trend_ma(df, n, k):
    """Filtro de tendencia: comprado mientras el cierre esté sobre la SMA(n). Stop de catástrofe k·ATR."""
    ma = df["close"].rolling(n).mean()
    return _out(df["close"] > ma, df["close"] < ma, df, k, trail=False)


def donchian(df, n, m, k, regime=200):
    """Ruptura de máximo de n velas a favor de la tendencia mayor; salida por mínimo de m velas o trailing k·ATR."""
    c = df["close"]
    hi = df["high"].rolling(n).max().shift()
    lo = df["low"].rolling(m).min().shift()
    return _out((c > hi) & (c > c.ewm(span=regime).mean()), c < lo, df, k, trail=True)


def ema_cross(df, fast, slow, k):
    """Cruce de medias exponenciales; trailing k·ATR."""
    f, s = df["close"].ewm(span=fast).mean(), df["close"].ewm(span=slow).mean()
    return _out((f > s) & (f.shift() <= s.shift()), f < s, df, k, trail=True)


def rsi_mr(df, th, exit_n, k, regime=200):
    """Reversión a la media: RSI(2) sobrevendido dentro de tendencia alcista; sale al recuperar la SMA(exit_n)."""
    c = df["close"]
    return _out((rsi(c, 2) < th) & (c > c.rolling(regime).mean()), c > c.rolling(exit_n).mean(), df, k, trail=False)


FAMILIES = {"trend_ma": trend_ma, "donchian": donchian, "ema_cross": ema_cross, "rsi_mr": rsi_mr}

# Espacio de búsqueda deliberadamente pequeño: cada configuración cuenta como un intento para el Deflated Sharpe.
GRID = {
    "trend_ma": {"tf": ["4h", "1d"], "n": [20, 50, 100, 200], "k": [2, 3]},
    "donchian": {"tf": ["1h", "4h"], "n": [20, 55], "m": [10, 20], "k": [2, 3]},
    "ema_cross": {"tf": ["1h", "4h", "1d"], "fast_slow": [(9, 21), (20, 50), (50, 200)], "k": [2, 3]},
    "rsi_mr": {"tf": ["1h", "4h"], "th": [5, 10, 20], "exit_n": [5, 10], "k": [2, 3]},
}


def configs():
    for fam, grid in GRID.items():
        keys = list(grid)
        for vals in itertools.product(*grid.values()):
            p = dict(zip(keys, vals))
            if "fast_slow" in p:
                p["fast"], p["slow"] = p.pop("fast_slow")
            yield fam, p


def signals(fam, df, p):
    return FAMILIES[fam](df, **{k: v for k, v in p.items() if k != "tf"})


def config_id(fam, p):
    return fam + "|" + ",".join(f"{k}={v}" for k, v in p.items())
