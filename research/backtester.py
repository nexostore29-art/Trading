"""Motor de backtest de barras para spot (solo long), fiel a las reglas del skill trading-expert.

Supuestos de ejecución:
- La señal se calcula al cierre de la vela i y se ejecuta a la apertura de i+1 (sin look-ahead).
- Stop-loss intrabar: si el mínimo toca el stop, sale al stop (o a la apertura si abrió por debajo: gap).
- Comisión por lado + slippage en cada ejecución.
- Tamaño por riesgo fijo: riesgo_% del capital / (distancia al stop + costos), con tope de exposición.
- Orden mínima (notional) de Binance: si el tamaño queda por debajo, no se entra.
- Guardia diaria: si el capital cae más de daily_loss_pct desde el inicio del día UTC, no hay nuevas entradas ese día.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Config:
    capital: float = 50.0
    risk_pct: float = 1.0
    max_exposure_pct: float = 50.0
    fee_pct: float = 0.10
    slippage_pct: float = 0.05
    min_notional: float = 5.0
    daily_loss_pct: float = 3.0


@dataclass
class Result:
    equity: pd.Series                     # capital al cierre de cada vela
    trades: pd.DataFrame
    skipped_min_notional: int = 0
    params: dict = field(default_factory=dict)

    @property
    def daily_returns(self) -> pd.Series:
        return self.equity.resample("1D").last().dropna().pct_change().dropna()


def run(df: pd.DataFrame, sig: dict, cfg: Config = Config()) -> Result:
    """df: OHLC indexado por tiempo UTC. sig: entry, exit (bool arrays), atr (array), stop_mult, trail."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    entry, exit_, atr = sig["entry"], sig["exit"], sig["atr"]
    k, trail = sig["stop_mult"], sig["trail"]
    fee, slip = cfg.fee_pct / 100, cfg.slippage_pct / 100
    days = df.index.floor("D").to_numpy()

    cash, qty, stop = cfg.capital, 0.0, 0.0
    entry_px = entry_time = cost_in = None
    pend_entry = pend_exit = False
    day, day_start_eq = None, cfg.capital
    eq = np.empty(len(df))
    trades, skipped = [], 0

    def close_pos(px, i, reason):
        nonlocal cash, qty
        proceeds = qty * px * (1 - fee)
        trades.append((entry_time, df.index[i], entry_px, px, qty, proceeds - cost_in, proceeds / cost_in - 1, reason))
        cash += proceeds
        qty = 0.0

    for i in range(len(df)):
        if days[i] != day:
            day = days[i]
            day_start_eq = cash + qty * o[i]

        # 1) ejecuciones pendientes a la apertura
        if pend_exit and qty > 0:
            close_pos(o[i] * (1 - slip), i, "señal")
        elif pend_entry and qty == 0 and np.isfinite(atr[i - 1]):
            equity_now = cash
            if equity_now >= day_start_eq * (1 - cfg.daily_loss_pct / 100):
                px = o[i] * (1 + slip)
                stop_px = px - k * atr[i - 1]
                if stop_px > 0:
                    loss_frac = (px - stop_px) / px + 2 * (fee + slip)
                    notional = min(equity_now * cfg.risk_pct / 100 / loss_frac,
                                   equity_now * cfg.max_exposure_pct / 100,
                                   cash / (1 + fee))
                    if notional >= cfg.min_notional:
                        qty = notional / px
                        cost_in = notional * (1 + fee)
                        cash -= cost_in
                        entry_px, entry_time, stop = px, df.index[i], stop_px
                    else:
                        skipped += 1
        pend_entry = pend_exit = False

        # 2) stop intrabar
        if qty > 0 and l[i] <= stop:
            close_pos(min(o[i], stop) * (1 - slip), i, "stop")

        # 3) actualizar trailing y señales al cierre
        if qty > 0:
            if trail and np.isfinite(atr[i]):
                stop = max(stop, c[i] - k * atr[i])
            pend_exit = bool(exit_[i])
        else:
            pend_entry = bool(entry[i])
        eq[i] = cash + qty * c[i]

    if qty > 0:  # cerrar al final para contabilizar
        close_pos(c[-1] * (1 - slip), len(df) - 1, "fin")
        eq[-1] = cash

    cols = ["entrada", "salida", "px_entrada", "px_salida", "cantidad", "pnl_usd", "retorno", "motivo"]
    return Result(pd.Series(eq, index=df.index), pd.DataFrame(trades, columns=cols), skipped)


def buy_and_hold(df: pd.DataFrame, cfg: Config = Config()) -> pd.Series:
    c = df["close"]
    units = cfg.capital * (1 - cfg.fee_pct / 100) / (c.iloc[0] * (1 + cfg.slippage_pct / 100))
    return c * units
