# Gestión de riesgo

El riesgo se decide **antes** de entrar: dónde está la invalidación (stop) y cuánto se pierde si se toca.

## Tamaño de posición por riesgo fijo
```
riesgo_$      = capital × riesgo_%            (p. ej. 1000 × 1% = 10 USD)
distancia_%   = |entrada − stop| / entrada + costos ida y vuelta
tamaño_$      = riesgo_$ / distancia_%
```
Luego limitar por exposición máxima por activo (30% / 50% BTC-ETH). `scripts/position_size.py` lo hace.

## Stops
- **Por volatilidad:** 2–3 × ATR(14) del marco temporal operado. Evita stops dentro del ruido normal.
- **Estructurales:** debajo del último mínimo relevante / del rango.
- **Trailing:** para estrategias de tendencia, sube con el precio (ATR o EMA).
- Colocar el stop **en el exchange** (STOP_LOSS_LIMIT u OCO) para que funcione aunque el bot se caiga. En Freqtrade: `stoploss_on_exchange: true`.
- Stop-limit en movimiento violento puede no ejecutarse: dejar margen entre `stopPrice` y precio límite.

## Riesgo de ruina y rachas
Con 40% de acierto, una racha de 10 pérdidas seguidas tiene ~0.6% de probabilidad por cada ventana de 10 operaciones — en cientos de operaciones es casi seguro que ocurra alguna. Con 1% de riesgo por operación, 10 pérdidas ≈ -9.6%; con 5% ≈ -40%. Por eso el 1%.

## Kelly
Kelly completo (f* = p − (1−p)/b) maximiza el crecimiento teórico pero produce drawdowns enormes y depende de estimaciones de p y b que tienen mucho error. Usar **como máximo ¼ de Kelly**, y solo cuando p y b vienen de una muestra grande en real.

## Correlación
BTC y la mayoría de altcoins tienen correlación alta (0.7–0.9) en caídas. Cinco posiciones long en altcoins ≈ una posición grande en "cripto". Limitar el riesgo total abierto (suma de riesgos a stop) a ~5% del capital.

## Apalancamiento y futuros
- Precio de liquidación aproximado (long, aislado): entrada × (1 − 1/apalancamiento + margen de mantenimiento). Con 10x, ~-9.5%.
- Funding cada 8h puede costar >10% anual en mercados eufóricos.
- Comisión de liquidación adicional.
- Si se usan futuros: margen aislado, apalancamiento ≤ 2x, stop siempre antes del precio de liquidación.

## Riesgos no de mercado
- **Exchange:** no dejar más capital del necesario en el exchange; subcuenta dedicada.
- **API key:** sin retiros, IP whitelist, rotación periódica.
- **Bot:** caídas, bugs, datos corruptos → kill-switch, alertas, stops en exchange.
- **Operador:** cambiar reglas en caliente tras una pérdida (tilt). Toda modificación pasa por el proceso de `evaluacion.md`.
