# Backtesting sin engañarse

Un backtest es un experimento, no una promesa. La mayoría de los backtests espectaculares están sobreajustados: encontraron ruido del pasado que no se repite.

## Datos
- Mínimo 3–4 años de velas, incluyendo un mercado bajista completo (2022), uno alcista y uno lateral.
- Fuente: datos de Binance (Freqtrade `download-data`), mismo exchange donde se operará.
- Cuidado con el **sesgo de supervivencia**: incluir pares que fueron deslistados si se testea un universo amplio.

## Costos realistas (incluirlos siempre)
- Comisión spot: 0.1% por lado (0.075% pagando con BNB) → ~0.15–0.2% por operación ida y vuelta.
- Slippage: 0.05% en BTC/ETH; 0.1–0.3% en altcoins medianas; más en velas volátiles.
- Futuros: 0.02% maker / 0.05% taker + funding cada 8h.
- Prueba de estrés: duplicá los costos. Si la estrategia deja de ganar, la ventaja es demasiado fina.

## Sesgos a eliminar
- **Look-ahead:** usar datos de la vela que aún no cerró. En Freqtrade, las señales se calculan sobre velas cerradas; no uses `shift(-1)` ni datos futuros.
- **Sobreajuste:** probar 500 combinaciones y quedarse con la mejor. Registrá **cuántas variantes** probaste — ese número entra en el Deflated Sharpe Ratio.
- **Snooping de régimen:** diseñar la estrategia mirando el mismo periodo con el que se valida.

## Protocolo
1. **Separar datos:** p. ej. 2021–2024 para diseño (in-sample), 2025–hoy para validación (out-of-sample). No mirar el out-of-sample hasta el final.
2. **Pocos parámetros** con valores "redondos" y razonables. Preferí mesetas: si el resultado cambia mucho al mover un parámetro ±20%, es frágil.
3. **Walk-forward:** optimizar en ventana móvil, testear en la siguiente, repetir. El resultado agregado de las ventanas de prueba es la estimación honesta.
4. **Robustez:** mismos parámetros en otros pares y otros marcos temporales; Monte Carlo reordenando operaciones para ver la distribución de drawdowns.
5. **Comparar con benchmarks:** buy & hold BTC, filtro MA200 simple (estrategia 2), y "no hacer nada" (USDT).
6. **Estadística:** calcular Sharpe, PSR y Deflated Sharpe (ver `evaluacion.md`, `scripts/eval_stats.py`). Con muchas variantes probadas, exigir DSR > 0.95.
7. **Paper trading** 4+ semanas antes de dinero real; comparar slippage y señales con lo que el backtest predijo.

## Comandos Freqtrade de referencia
```bash
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT --timeframes 1h 4h 1d --timerange 20210101-
freqtrade backtesting --strategy MiEstrategia --timeframe 4h --timerange 20210101-20241231 --fee 0.001
freqtrade backtesting --strategy MiEstrategia --timeframe 4h --timerange 20250101-          # out-of-sample
freqtrade hyperopt --strategy MiEstrategia --hyperopt-loss SharpeHyperOptLossDaily --epochs 200 --timerange 20210101-20241231
freqtrade backtesting-analysis   # desglose por señal de entrada/salida
```
Hyperopt es la herramienta más peligrosa del kit: usala con pocos parámetros, pocas épocas, y validá siempre fuera de muestra.

## Señales de alarma
- Sharpe > 3 en un backtest diario de varios años → casi seguro un error o sobreajuste.
- Curva de capital perfecta sin drawdowns.
- La mayoría de la ganancia viene de 1–3 operaciones.
- Funciona en un solo par o un solo periodo.
- Requiere más de ~5 parámetros ajustados.
