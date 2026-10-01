# Evaluación: ¿habilidad o suerte? ¿agregamos capital?

## Métricas (todas netas de comisiones)

| Métrica | Qué mide | Referencia sana |
|---|---|---|
| Retorno total y anualizado | Crecimiento | > benchmark |
| Exceso vs buy & hold BTC | Valor agregado real | > 0 ajustado por riesgo |
| Sharpe anualizado | Retorno por unidad de volatilidad | > 1 (live); desconfiar de > 3 |
| Sortino | Igual, solo volatilidad bajista | > 1.5 |
| Max drawdown | Peor caída desde máximo | Dentro del límite (15%) |
| Calmar | Retorno anual / max DD | > 1 |
| Tasa de acierto | % operaciones ganadoras | Interpretar junto con el payoff |
| Payoff ratio | Ganancia media / pérdida media | Tendencia: > 2 |
| Profit factor | Ganancias brutas / pérdidas brutas | > 1.3 |
| Expectativa | Ganancia media por operación (en R o %) | > 0 con margen sobre costos |
| PSR(0) | Probabilidad de que el Sharpe real sea > 0 | > 0.95 |
| DSR | PSR corregido por número de variantes probadas | > 0.95 |
| MinTRL | Muestra mínima para que el Sharpe sea significativo | Muestra actual ≥ MinTRL |

`scripts/eval_stats.py` calcula todo esto desde un CSV de retornos o de PnL por operación.

## Por qué una semana no alcanza

Ejemplo con 20 operaciones semanales de igual tamaño:
- Estrategia **con** ventaja (55% de acierto): ~25% de probabilidad de cerrar la semana en pérdida.
- Estrategia **sin** ventaja (50%): ~41% de probabilidad de cerrar la semana en ganancia.

Bailey & López de Prado: para que un Sharpe anual de 2 sea estadísticamente mayor que 1 al 95% hacen falta ~2.7 años de historial. Para "mayor que 0" hace falta menos, pero siempre meses, no días.

Además, Chague, De-Losso & Giovannetti (2020): de los day traders brasileños que persistieron más de 300 días, 97% perdió dinero neto de costos y no se encontró evidencia de aprendizaje con la experiencia. El punto de partida razonable es asumir que **no** hay ventaja hasta demostrarla.

## Dos ritmos de revisión

| Qué | Frecuencia | Base de decisión |
|---|---|---|
| Operativa (bugs, ejecución, cumplimiento de reglas, slippage) | Semanal | Logs del bot |
| Parámetros / lógica de la estrategia | Cada 50–100 operaciones nuevas | Backtest + datos reales; cambios pasan otra vez por backtest y paper |
| Capital | Mensual, con ≥ 2–3 meses de historial | Matriz de abajo |

Cambiar la estrategia cada semana según el resultado de esa semana = sobreajuste en vivo.

## Matriz de escalado de capital

| Condición (todas, en real, netas de costos) | Decisión |
|---|---|
| ≥ 3 meses, ≥ 100 operaciones (o MinTRL cumplido), PSR(0) > 0.95, DD dentro del límite, le gana a buy & hold ajustado por riesgo, resultados coherentes con el backtest | **Escalar** +25–50% del capital actual |
| Rentable pero muestra insuficiente o PSR < 0.95 | **Mantener** capital, seguir midiendo |
| Pérdida dentro de lo esperado por el backtest, sin violación de reglas | **Mantener**, revisar régimen |
| DD > 10% o desvío fuerte respecto al backtest | **Reducir** capital 50% y diagnosticar |
| DD ≥ 15%, violación de reglas, o error de ejecución con pérdida | **Pausar** todo, post-mortem antes de reanudar |

Agregar dinero **después de una racha ganadora corta** es el error clásico: se aumenta la exposición justo antes de que el resultado regrese a la media.

## Post-mortem de una pérdida
1. ¿Se siguieron las reglas? (si no: problema de proceso, no de estrategia)
2. ¿La pérdida está dentro de la distribución del backtest/Monte Carlo?
3. ¿Cambió el régimen de mercado?
4. ¿Hubo un problema de ejecución (slippage, orden fallida, caída de API)?
5. Acción: arreglar proceso/bug ya; cambios de estrategia → backlog con hipótesis y nuevo backtest.
