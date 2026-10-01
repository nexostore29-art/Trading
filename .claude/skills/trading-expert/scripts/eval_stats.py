#!/usr/bin/env python3
"""Métricas de desempeño y significancia estadística (solo librería estándar).

Entrada: CSV o texto con una columna numérica (la última columna numérica de cada fila).
  - Por defecto: retornos periódicos en fracción (0.012 = +1.2%) — p. ej. diarios.
  - Con --trades: retorno por operación en fracción.
  - Con --benchmark archivo: retornos del benchmark (mismos periodos) para comparar.

Ejemplos:
    python eval_stats.py retornos_diarios.csv --periods-per-year 365
    python eval_stats.py operaciones.csv --trades --n-trials 20
"""
import argparse
import math
import sys
from statistics import NormalDist, mean, stdev

N = NormalDist()


def load(path):
    vals = []
    with open(path) as f:
        for line in f:
            nums = []
            for tok in line.replace(";", ",").split(","):
                try:
                    nums.append(float(tok.strip()))
                except ValueError:
                    pass
            if nums:
                vals.append(nums[-1])
    return vals


def moments(x):
    m, s = mean(x), stdev(x)
    n = len(x)
    skew = sum(((v - m) / s) ** 3 for v in x) / n
    kurt = sum(((v - m) / s) ** 4 for v in x) / n  # no-exceso (normal = 3)
    return m, s, skew, kurt


def psr(sr, n, skew, kurt, sr_star=0.0):
    """Probabilistic Sharpe Ratio (Bailey & López de Prado). sr por periodo."""
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return N.cdf((sr - sr_star) * math.sqrt(n - 1) / denom)


def min_trl(sr, skew, kurt, sr_star=0.0, conf=0.95):
    if sr <= sr_star:
        return float("inf")
    z = N.inv_cdf(conf)
    return 1 + (1 - skew * sr + (kurt - 1) / 4 * sr ** 2) * (z / (sr - sr_star)) ** 2


def expected_max_sr(n_trials, sr_var):
    """SR máximo esperado entre n_trials estrategias sin ventaja (para el Deflated Sharpe)."""
    if n_trials <= 1:
        return 0.0
    g = 0.5772156649
    return math.sqrt(sr_var) * ((1 - g) * N.inv_cdf(1 - 1 / n_trials) + g * N.inv_cdf(1 - 1 / (n_trials * math.e)))


def max_drawdown(rets):
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return mdd, eq - 1


def binom_p_value(wins, n, p=0.5):
    """P(X >= wins) bajo azar (moneda de probabilidad p)."""
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(wins, n + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--trades", action="store_true", help="cada valor es el retorno de una operación")
    ap.add_argument("--periods-per-year", type=float, default=365, help="365 diario cripto, 52 semanal")
    ap.add_argument("--trades-per-year", type=float, default=None, help="para anualizar con --trades")
    ap.add_argument("--n-trials", type=int, default=1, help="nº de variantes probadas (Deflated Sharpe)")
    ap.add_argument("--benchmark", help="CSV de retornos del benchmark, mismos periodos")
    a = ap.parse_args()

    x = load(a.file)
    if len(x) < 3:
        sys.exit("Se necesitan al menos 3 valores")
    n = len(x)
    m, s, skew, kurt = moments(x)
    sr = m / s if s > 0 else 0.0
    ppy = a.trades_per_year if a.trades else a.periods_per_year
    mdd, total = max_drawdown(x)

    print(f"Observaciones ({'operaciones' if a.trades else 'periodos'}): {n}")
    print(f"Retorno total compuesto:   {total:+.2%}")
    print(f"Max drawdown:              {mdd:.2%}")
    print(f"Media por obs.:            {m:+.4%}   desvío: {s:.4%}")
    print(f"Asimetría: {skew:+.2f}   curtosis: {kurt:.2f}")
    if ppy:
        print(f"Sharpe anualizado:         {sr * math.sqrt(ppy):.2f}")
        neg = [v for v in x if v < 0]
        if len(neg) > 1:
            dd = math.sqrt(sum(v * v for v in neg) / n)
            print(f"Sortino anualizado:        {m / dd * math.sqrt(ppy):.2f}")
        years = n / ppy
        if years > 0 and total > -1:
            cagr = (1 + total) ** (1 / years) - 1
            print(f"Retorno anualizado:        {cagr:+.2%}")
            if mdd < 0:
                print(f"Calmar:                    {cagr / -mdd:.2f}")

    wins = [v for v in x if v > 0]
    losses = [v for v in x if v < 0]
    print(f"Tasa de acierto:           {len(wins) / n:.1%}")
    if wins and losses:
        print(f"Payoff (gan. media/pérd.): {mean(wins) / -mean(losses):.2f}")
        print(f"Profit factor:             {sum(wins) / -sum(losses):.2f}")
    print(f"p-valor acierto vs 50%:    {binom_p_value(len(wins), n):.3f}  (bajo = difícil que sea azar)")

    print("\n-- Significancia (Bailey & López de Prado) --")
    print(f"PSR(SR>0):                 {psr(sr, n, skew, kurt):.3f}   (objetivo > 0.95)")
    mt = min_trl(sr, skew, kurt)
    print(f"MinTRL (95%):              {'∞' if math.isinf(mt) else f'{mt:.0f}'} obs.  | actuales: {n}  -> "
          f"{'SUFICIENTE' if n >= mt else 'INSUFICIENTE'}")
    if a.n_trials > 1:
        sr0 = expected_max_sr(a.n_trials, 1 / (n - 1))
        print(f"Deflated Sharpe ({a.n_trials} variantes): {psr(sr, n, skew, kurt, sr0):.3f}   (objetivo > 0.95)")

    if a.benchmark:
        b = load(a.benchmark)[:n]
        if len(b) == n:
            _, btot = max_drawdown(b)
            bdd, _ = max_drawdown(b)
            diff = [xi - bi for xi, bi in zip(x, b)]
            print("\n-- Contra benchmark --")
            print(f"Benchmark total: {btot:+.2%}  DD: {bdd:.2%}")
            print(f"PSR(exceso > 0): {psr(mean(diff) / stdev(diff), n, *moments(diff)[2:]):.3f}")
        else:
            print("\nBenchmark con distinta cantidad de periodos; omitido.")


if __name__ == "__main__":
    main()
