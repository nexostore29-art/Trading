"""DonchianTrend — ruptura de máximos a favor de la tendencia mayor (spot, solo long).

Traducción 1:1 de `donchian|tf=4h,n=20,m=20,k=3` de research/strategies.py (la configuración que el walk-forward
eligió en más ventanas). ESTADO: candidata NO promovida (DSR 0.656 < 0.95 en la corrida 20261001T171546Z_85a65b9).
Uso autorizado: paper trading / piloto de infraestructura, no como estrategia probada.

Reglas:
- Entrada: cierre > máximo de las 20 velas previas y cierre > EMA(200).
- Salida: cierre < mínimo de las 20 velas previas, o stop.
- Stop: entrada − 3·ATR(14); trailing a cierre − 3·ATR(14), solo sube.
- Tamaño: 1% de riesgo del capital, validado por el Risk Engine independiente (risk/engine.py).
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from risk import engine as risk  # noqa: E402

log = logging.getLogger(__name__)

N_ENTRY, N_EXIT, K_ATR, REGIME = 20, 20, 3.0, 200
STATE_FILE = risk.STATE_DIR / "equity.json"


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


class DonchianTrend(IStrategy):
    INTERFACE_VERSION = 3
    VERSION = "donchian-4h-20-20-3@v1"
    timeframe = "4h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 400
    minimal_roi = {"0": 100}          # sin take-profit fijo: sale por señal o trailing
    stoploss = -0.30                  # tope de seguridad; el stop real lo da custom_stoploss
    use_custom_stoploss = True
    use_exit_signal = True

    @property
    def protections(self):
        # Defensa en profundidad: además del Risk Engine.
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 1},
            {"method": "StoplossGuard", "lookback_period_candles": 42, "trade_limit": 3,
             "stop_duration_candles": 18, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 540, "trade_limit": 1,
             "stop_duration_candles": 100000, "max_allowed_drawdown": 0.15},
        ]

    # --- Indicadores y señales (idénticos a research/strategies.py) -------------------------------------------
    def populate_indicators(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df["atr"] = atr(df)
        df["ema_regime"] = df["close"].ewm(span=REGIME).mean()
        df["dc_high"] = df["high"].rolling(N_ENTRY).max().shift()
        df["dc_low"] = df["low"].rolling(N_EXIT).min().shift()
        return df

    def populate_entry_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df.loc[(df["close"] > df["dc_high"]) & (df["close"] > df["ema_regime"]), ["enter_long", "enter_tag"]] = (1, "donchian_breakout")
        return df

    def populate_exit_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df.loc[df["close"] < df["dc_low"], ["exit_long", "exit_tag"]] = (1, "donchian_low")
        return df

    # --- Estado de cuenta para el Risk Engine -----------------------------------------------------------------
    def _equity(self) -> float:
        stake = self.config["stake_currency"]
        eq = self.wallets.get_total(stake)
        for t in Trade.get_trades_proxy(is_open=True):
            df, _ = self.dp.get_analyzed_dataframe(t.pair, self.timeframe)
            px = df["close"].iloc[-1] if len(df) else t.open_rate
            eq += t.amount * px
        return eq

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        eq = self._equity()
        st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        today = current_time.astimezone(timezone.utc).date().isoformat()
        st["peak_equity"] = max(st.get("peak_equity", eq), eq)
        if st.get("day") != today:
            st["day"], st["day_start_equity"] = today, eq
        st["equity"], st["updated"] = eq, current_time.isoformat()
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, indent=2))

    def _account_state(self, pair: str) -> risk.AccountState:
        st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        eq = self._equity()
        positions = {}
        for t in Trade.get_trades_proxy(is_open=True):
            sl = t.stop_loss or t.open_rate * (1 + self.stoploss)
            positions[t.pair] = {"notional": t.amount * t.open_rate, "risk": max(0.0, (t.open_rate - sl) * t.amount)}
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last = df.iloc[-1] if len(df) else None
        candle_close_time = None
        if last is not None:
            candle_close_time = pd.Timestamp(last["date"]).to_pydatetime() + pd.Timedelta(self.timeframe).to_pytimedelta()
        return risk.AccountState(
            equity=eq, peak_equity=max(st.get("peak_equity", eq), eq), day_start_equity=st.get("day_start_equity", eq),
            positions=positions, open_orders=[], last_close=None if last is None else float(last["close"]),
            last_candle_time=candle_close_time, timeframe_minutes=240)

    def _proposal(self, pair: str, rate: float, notional: float) -> risk.OrderProposal:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        a = float(df["atr"].iloc[-1])
        return risk.OrderProposal(pair=pair, side="buy", entry=rate, stop=rate - K_ATR * a, notional=notional,
                                  strategy=type(self).__name__, strategy_version=self.VERSION)

    # --- Tamaño de posición y confirmación final --------------------------------------------------------------
    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
                            leverage, entry_tag, side, **kwargs) -> float:
        limits = risk.load_limits()
        eq = self._equity()
        prop = self._proposal(pair, current_rate, 0.0)
        fee = 2 * (self.config.get("fee", 0.001) + 0.0005)
        loss_frac = (prop.entry - prop.stop) / prop.entry + fee
        prop.notional = min(eq * limits["riesgo_por_operacion_pct"] / 100 / loss_frac, max_stake)
        d = risk.evaluate(prop, self._account_state(pair), limits)
        if not d.allowed or (min_stake and d.notional < min_stake):
            return 0.0
        return d.notional

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side,
                            **kwargs) -> bool:
        prop = self._proposal(pair, rate, amount * rate)
        st = self._account_state(pair)
        d = risk.evaluate(prop, st, risk.load_limits())
        # La orden final debe ser aprobada tal cual; si el motor la reduciría, se rechaza (el tamaño ya se ajustó antes).
        ok = d.action == risk.APPROVE
        risk.log_decision(prop, st, d)
        if not ok:
            log.warning("Risk Engine rechazó %s: %s", pair, d.reasons)
        return ok

    # --- Stop inicial y trailing ATR ---------------------------------------------------------------------------
    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        before = df[df["date"] < trade.open_date_utc]
        if before.empty:
            return None
        initial = trade.open_rate - K_ATR * float(before["atr"].iloc[-1])
        last = df.iloc[-1]
        trailing = float(last["close"]) - K_ATR * float(last["atr"])
        return stoploss_from_absolute(max(initial, trailing), current_rate, is_short=False)
