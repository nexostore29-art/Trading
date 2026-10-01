"""Ciclo de evolución controlada: genera estrategias, las valida fuera de muestra y decide promociones.

Cómo "aprende" sin sobreajustarse:
1. Corre todas las configuraciones de strategies.GRID sobre el histórico completo.
2. Walk-forward: en cada ventana elige la mejor configuración con datos de entrenamiento (train_years)
   y la evalúa en los test_months siguientes, que no vio. La curva fuera de muestra concatenada es la
   estimación honesta de lo que el sistema habría ganado eligiendo estrategias por sí mismo.
3. Cuenta todos los intentos acumulados (registry.json) y aplica el Deflated Sharpe Ratio.
4. Solo promueve a paper trading si pasa las compuertas del skill. Cada corrida queda en el registro
   y en el diario, con lo que falló y por qué, para la siguiente iteración.

    python research/evolve.py
"""
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import subprocess

import numpy as np
import pandas as pd

import backtester as bt
import strategies as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
REG = ROOT / "research" / "registry.json"
REPORTS = ROOT / "research" / "reports"

_spec = importlib.util.spec_from_file_location("eval_stats", ROOT / ".claude/skills/trading-expert/scripts/eval_stats.py")
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)

START = "2017-01-01"     # BTC con liquidez y mercado de altcoins comparable al actual
TRAIN_YEARS = 2
TEST_MONTHS = 6
MIN_TRAIN_TRADES = 8
CRITERIA = json.loads((ROOT / "research" / "criteria.json").read_text())
_g = CRITERIA["promocion_a_paper"]
GATES = {"dsr": _g["dsr_min"], "max_dd": _g["max_dd_min"], "min_trades": _g["min_trades_oos"]}
ECON = CRITERIA["viabilidad_economica"]


def load(tf):
    df = pd.read_csv(DATA / f"BTCUSD_{tf}.csv", index_col=0, parse_dates=True)
    return df[df.index >= pd.Timestamp(START, tz="UTC")]


def stats(r: pd.Series):
    r = r.dropna()
    if len(r) < 3 or r.std() == 0:
        return {"sharpe": 0.0, "cagr": 0.0, "max_dd": 0.0, "psr": 0.0, "n": len(r)}
    eq = (1 + r).cumprod()
    m, s, skew, kurt = es.moments(list(r))
    years = len(r) / 365
    return {"sharpe": m / s * math.sqrt(365), "cagr": eq.iloc[-1] ** (1 / years) - 1,
            "max_dd": float((eq / eq.cummax() - 1).min()), "psr": es.psr(m / s, len(r), skew, kurt),
            "total": eq.iloc[-1] - 1, "n": len(r), "_m": (m, s, skew, kurt)}


def run_all(cfg):
    frames = {tf: load(tf) for tf in ("1h", "4h", "1d")}
    results = {}
    for fam, p in st.configs():
        df = frames[p["tf"]]
        res = bt.run(df, st.signals(fam, df, p), cfg)
        results[st.config_id(fam, p)] = res
    return results, frames


def walk_forward(results):
    rets = {cid: r.daily_returns for cid, r in results.items()}
    trades = {cid: r.trades for cid, r in results.items()}
    t0 = pd.Timestamp(START, tz="UTC") + pd.DateOffset(years=TRAIN_YEARS)
    end = max(s.index[-1] for s in rets.values())
    oos, picks = [], []
    while t0 < end:
        tr_start, t1 = t0 - pd.DateOffset(years=TRAIN_YEARS), min(t0 + pd.DateOffset(months=TEST_MONTHS), end)
        best, best_score = None, -np.inf
        for cid, r in rets.items():
            ntr = ((trades[cid]["entrada"] >= tr_start) & (trades[cid]["entrada"] < t0)).sum()
            if ntr < MIN_TRAIN_TRADES:
                continue
            s = stats(r[(r.index >= tr_start) & (r.index < t0)])["sharpe"]
            if s > best_score:
                best, best_score = cid, s
        if best is None:
            seg = pd.Series(0.0, index=pd.date_range(t0, t1, freq="D", inclusive="left"))
        else:
            seg = rets[best][(rets[best].index >= t0) & (rets[best].index < t1)]
        n_test = 0 if best is None else int(((trades[best]["entrada"] >= t0) & (trades[best]["entrada"] < t1)).sum())
        picks.append({"desde": t0.date().isoformat(), "hasta": t1.date().isoformat(), "elegida": best,
                      "sharpe_train": None if best is None else round(best_score, 2),
                      "retorno_test": float((1 + seg).prod() - 1), "ops_test": n_test})
        oos.append(seg)
        t0 = t1
    return pd.concat(oos), picks


def deflated(st_, n_trials):
    m, s, skew, kurt = st_["_m"]
    sr0 = es.expected_max_sr(n_trials, 1 / (st_["n"] - 1))
    return es.psr(m / s, st_["n"], skew, kurt, sr0)


def main():
    now = datetime.now(timezone.utc)
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        sha = "nogit"
    stamp = now.strftime("%Y-%m-%d")
    run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{sha or 'nogit'}"
    cfg = bt.Config()
    results, frames = run_all(cfg)
    reg = json.loads(REG.read_text()) if REG.exists() else {"intentos_acumulados": 0, "evaluados": [], "historial": [], "campeon": None}
    nuevos = [cid for cid in results if cid not in reg["evaluados"]]
    reg["evaluados"] += nuevos
    reg["intentos_acumulados"] += len(nuevos)
    n_trials = reg["intentos_acumulados"]

    oos, picks = walk_forward(results)
    s_oos = stats(oos)
    s_oos["dsr"] = deflated(s_oos, n_trials)
    oos_trades = sum(p["ops_test"] for p in picks)

    d1 = frames["1d"]
    bh = bt.buy_and_hold(d1, cfg).pct_change().dropna()
    s_bh = stats(bh[bh.index >= oos.index[0]])

    # Tabla de configuraciones (periodo completo) — solo diagnóstico, no sirve para elegir (sesgo de selección)
    rows = []
    for cid, r in results.items():
        s = stats(r.daily_returns)
        rows.append({"config": cid, "sharpe": s["sharpe"], "cagr": s["cagr"], "max_dd": s["max_dd"],
                     "ops": len(r.trades), "acierto": (r.trades["retorno"] > 0).mean() if len(r.trades) else 0,
                     "omitidas_min": r.skipped_min_notional})
    table = pd.DataFrame(rows).sort_values("sharpe", ascending=False)

    fam_wf = {}
    for fam in st.FAMILIES:
        sub = {k: v for k, v in results.items() if k.startswith(fam + "|")}
        f_oos, _ = walk_forward(sub)
        fam_wf[fam] = stats(f_oos)

    # Estrés de costos: mismas reglas con comisión y slippage duplicados
    cfg2 = bt.Config(fee_pct=cfg.fee_pct * 2, slippage_pct=cfg.slippage_pct * 2)
    res2, _ = run_all(cfg2)
    oos2, _ = walk_forward(res2)
    s_oos2 = stats(oos2)

    # Viabilidad económica: ganancia absoluta neta según capital
    net_rate = s_oos["cagr"] * (1 - ECON["impuesto_ganancias"]) if s_oos["cagr"] > 0 else s_oos["cagr"]
    econ_rows = [(cap, cap * net_rate, cap * net_rate - ECON["costos_fijos_anuales_usd"])
                 for cap in (50, 500, 1000, 5000, 20000, 100000)]
    breakeven = ECON["costos_fijos_anuales_usd"] / net_rate if net_rate > 0 else float("inf")
    viable_now = econ_rows[0][2] > ECON["ganancia_neta_anual_minima_usd"]

    checks = {
        f"DSR > {GATES['dsr']}": s_oos["dsr"] > GATES["dsr"],
        f"Max DD > {GATES['max_dd']:.0%}": s_oos["max_dd"] > GATES["max_dd"],
        f"Operaciones fuera de muestra ≥ {GATES['min_trades']}": oos_trades >= GATES["min_trades"],
        "Sharpe > buy & hold BTC (mismo periodo)": s_oos["sharpe"] > s_bh["sharpe"],
        "Sigue rentable con costos x2": s_oos2["cagr"] > 0,
    }
    aprobado = all(checks.values())
    last = picks[-1]["elegida"]
    decision = (f"PROMOVER a paper trading: {last}" if aprobado else
                "NO PROMOVER — seguir investigando (ver compuertas fallidas)")
    if aprobado:
        reg["campeon"] = {"config": last, "fecha": datetime.now(timezone.utc).isoformat()}
    reg["historial"].append({
        "fecha": datetime.now(timezone.utc).isoformat(), "intentos_acumulados": n_trials,
        "oos_sharpe": round(s_oos["sharpe"], 3), "oos_cagr": round(s_oos["cagr"], 4),
        "oos_max_dd": round(s_oos["max_dd"], 4), "dsr": round(s_oos["dsr"], 3),
        "compuertas": {k: bool(v) for k, v in checks.items()}, "decision": decision,
        "config_actual": last, "run_id": run_id, "criterios_version": CRITERIA["version"],
        "estres_costos_x2_cagr": round(s_oos2["cagr"], 4),
    })
    REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False))

    REPORTS.mkdir(parents=True, exist_ok=True)
    pct = lambda x: f"{x:+.1%}"
    lines = [
        f"# Fase 1 — Evolución de estrategias ({stamp})", "",
        f"Datos: BTC/USD Bitstamp (proxy de BTC/USDT Binance), {START} → {d1.index[-1].date()}. "
        f"Capital simulado ${cfg.capital:.0f}, riesgo {cfg.risk_pct}%/operación, exposición máx. {cfg.max_exposure_pct:.0f}%, "
        f"comisión {cfg.fee_pct}% + slippage {cfg.slippage_pct}% por lado, orden mínima ${cfg.min_notional:.0f}.", "",
        f"Corrida `{run_id}` · criterios v{CRITERIA['version']} (definidos antes de ver resultados) · "
        f"configuraciones: {len(results)} · intentos acumulados (para DSR): {n_trials}", "",
        "## Resultado del sistema completo (walk-forward, fuera de muestra)", "",
        "| Métrica | Sistema auto-seleccionado | Buy & hold BTC |", "|---|---|---|",
        f"| Periodo | {oos.index[0].date()} → {oos.index[-1].date()} | igual |",
        f"| Retorno total | {pct(s_oos['total'])} | {pct(s_bh['total'])} |",
        f"| Retorno anual | {pct(s_oos['cagr'])} | {pct(s_bh['cagr'])} |",
        f"| Sharpe | {s_oos['sharpe']:.2f} | {s_bh['sharpe']:.2f} |",
        f"| Max drawdown | {s_oos['max_dd']:.1%} | {s_bh['max_dd']:.1%} |",
        f"| PSR (SR>0) | {s_oos['psr']:.3f} | {s_bh['psr']:.3f} |",
        f"| Deflated Sharpe | {s_oos['dsr']:.3f} | — |",
        f"| Operaciones | {oos_trades} | 1 |", "",
        "## Compuertas", "", *[f"- {'✅' if v else '❌'} {k}" for k, v in checks.items()], "",
        f"**Decisión:** {decision}", "",
        "## Estrés de costos (comisión y slippage x2)", "",
        f"Retorno anual {pct(s_oos2['cagr'])} · Sharpe {s_oos2['sharpe']:.2f} · Max DD {s_oos2['max_dd']:.1%}", "",
        "## Viabilidad económica", "",
        f"Retorno anual fuera de muestra después de impuestos (~{ECON['impuesto_ganancias']:.0%}): {pct(net_rate)}. "
        f"Costos fijos asumidos: ${ECON['costos_fijos_anuales_usd']}/año ({ECON['detalle_costos']})", "",
        "| Capital | Ganancia neta/año | Después de costos fijos |", "|---|---|---|",
        *[f"| ${c:,.0f} | ${g:,.2f} | ${n:,.2f} |" for c, g, n in econ_rows], "",
        f"Capital de equilibrio: ${breakeven:,.0f}. Con $50: "
        f"{'viable' if viable_now else '**NO ECONÓMICAMENTE VIABLE** como fuente de ingreso — solo tiene sentido como validación del sistema'}.", "",
        "## Walk-forward por familia (fuera de muestra)", "",
        "| Familia | Retorno anual | Sharpe | Max DD |", "|---|---|---|---|",
        *[f"| {f} | {pct(v['cagr'])} | {v['sharpe']:.2f} | {v['max_dd']:.1%} |" for f, v in fam_wf.items()], "",
        "## Qué eligió el sistema en cada ventana", "",
        "| Test desde | hasta | Config elegida (con datos previos) | Sharpe train | Retorno test | Ops test |",
        "|---|---|---|---|---|---|",
        *[f"| {p['desde']} | {p['hasta']} | `{p['elegida']}` | {p['sharpe_train']} | {pct(p['retorno_test'])} | {p['ops_test']} |" for p in picks], "",
        "## Top 10 configuraciones en el periodo completo (sesgado: solo diagnóstico)", "",
        "| Config | Sharpe | Retorno anual | Max DD | Ops | Acierto | Omitidas por mínimo |", "|---|---|---|---|---|---|---|",
        *[f"| `{r.config}` | {r.sharpe:.2f} | {pct(r.cagr)} | {r.max_dd:.1%} | {r.ops} | {r.acierto:.0%} | {r.omitidas_min} |"
          for r in table.head(10).itertuples()],
    ]
    out = REPORTS / f"fase1_{run_id}.md"   # nunca se sobrescriben resultados anteriores
    out.write_text("\n".join(lines) + "\n")
    table.to_csv(REPORTS / f"configs_{run_id}.csv", index=False)
    print("\n".join(lines))
    print(f"\nReporte: {out}")


if __name__ == "__main__":
    main()
