#!/usr/bin/env python3
"""Tamaño de posición por riesgo fijo, con tope de exposición por activo.

Ejemplo:
    python position_size.py --capital 1000 --risk 1 --entry 60000 --stop 57000
"""
import argparse


def position_size(capital, risk_pct, entry, stop, fee_pct=0.1, slippage_pct=0.05, max_exposure_pct=30.0):
    if entry <= 0 or stop <= 0 or entry == stop:
        raise ValueError("entry y stop deben ser positivos y distintos")
    risk_usd = capital * risk_pct / 100
    # Costos ida y vuelta (comisión + slippage en entrada y salida) se suman a la distancia al stop.
    cost_frac = 2 * (fee_pct + slippage_pct) / 100
    stop_frac = abs(entry - stop) / entry
    loss_frac = stop_frac + cost_frac
    notional = risk_usd / loss_frac
    cap = capital * max_exposure_pct / 100
    capped = notional > cap
    notional = min(notional, cap)
    return {
        "lado": "long" if stop < entry else "short",
        "riesgo_usd": round(risk_usd, 2),
        "distancia_stop_pct": round(stop_frac * 100, 3),
        "costos_ida_vuelta_pct": round(cost_frac * 100, 3),
        "nocional_usd": round(notional, 2),
        "cantidad": notional / entry,
        "limitado_por_exposicion": capped,
        "perdida_real_si_stop_usd": round(notional * loss_frac, 2),
        "exposicion_pct_capital": round(notional / capital * 100, 2),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capital", type=float, required=True)
    ap.add_argument("--risk", type=float, default=1.0, help="%% del capital arriesgado (default 1)")
    ap.add_argument("--entry", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--fee", type=float, default=0.1, help="%% comisión por lado (0.075 con BNB)")
    ap.add_argument("--slippage", type=float, default=0.05, help="%% slippage por lado")
    ap.add_argument("--max-exposure", type=float, default=30.0, help="%% máximo del capital en el activo")
    a = ap.parse_args()
    r = position_size(a.capital, a.risk, a.entry, a.stop, a.fee, a.slippage, a.max_exposure)
    for k, v in r.items():
        print(f"{k:28s} {v}")


if __name__ == "__main__":
    main()
