# Familias de estrategias

Empezá siempre por estrategias simples con evidencia y pocos parámetros. Cada parámetro extra es una oportunidad de sobreajustar.

## 1. Seguimiento de tendencia / momentum de serie temporal (núcleo recomendado)

**Evidencia:** Liu & Tsyvinski (NBER) documentan momentum de serie temporal en cripto de 1 a 8 semanas; múltiples estudios muestran que reglas de media móvil en BTC reducen drawdown frente a buy & hold y en varios periodos mejoran el retorno ajustado por riesgo.

**Por qué funciona:** sub-reacción inicial a la información y flujos que se retroalimentan (FOMO, liquidaciones). **Cuándo falla:** mercados laterales con "latigazos" (whipsaws) que generan muchas pérdidas pequeñas.

**Plantilla:**
- Universo: BTC, ETH y ~5–10 pares líquidos.
- Filtro de régimen: solo long si cierre diario > MA200 (o EMA 100–200).
- Entrada: ruptura de máximo de N días (Donchian 20–55) o cruce EMA rápida/lenta en 4h–1d, confirmada por el filtro.
- Salida: trailing stop a 2–3 × ATR, o cierre bajo la EMA lenta.
- Tamaño: por volatilidad (riesgo 1% / distancia al stop).
- Expectativa típica: tasa de acierto 35–45%, ganancias promedio 2–3× las pérdidas.

## 2. Asignación con filtro de tendencia (la más robusta, poca operación)

Mantener BTC/ETH cuando están sobre su MA de 50–200 días y pasar a USDT cuando están debajo. Pocas operaciones al año → comisiones despreciables. Buena **línea base** contra la que medir cualquier estrategia más activa.

## 3. Reversión a la media (para rangos)

- RSI(2–14) o Bollinger extremos dentro de un rango confirmado (ADX < 20) y **a favor** de la tendencia mayor.
- Stops estrictos: cuando el rango se rompe, las pérdidas son grandes.
- Alta tasa de acierto, ganancias pequeñas → muy sensible a comisiones. Exige órdenes limit (maker).

## 4. DCA (compra periódica) y DCA por valor

No es trading: es acumulación disciplinada. DCA reforzado en pánico (Fear & Greed < 20, MVRV bajo) históricamente mejoró el precio promedio. Útil como componente de largo plazo del capital.

## 5. Grid trading

Compra/venta escalonada dentro de un rango. Gana en lateral, **pierde fuerte** si el precio sale del rango (queda "atrapado" en la bajada). Solo con límites de rango y stop global.

## 6. Carry de funding (neutral a mercado)

Comprar spot y vender perpetuo por el mismo monto cuando el funding es positivo: cobra el funding sin exposición direccional. Riesgos: funding se vuelve negativo, riesgo de exchange, margen en la pata corta. Requiere futuros → solo después de la fase 3.

## 7. Lo que **no** recomendamos (y por qué)

| Idea | Problema |
|---|---|
| Scalping de alta frecuencia | Competís contra market makers con latencia de microsegundos; las comisiones minoristas (0.075–0.1%) se comen la ventaja |
| Apalancamiento alto (> 3x) | Una vela de -10% liquida un 10x; las cascadas de liquidación son frecuentes en cripto |
| Memecoins / nuevos listados | Liquidez fina, manipulación, sin historial para testear |
| Señales de Telegram / "gurús" | Sin registro verificable; incentivo a venderte la señal, no a ganar |
| ML "caja negra" sin hipótesis | Altísimo riesgo de sobreajuste; usar FreqAI solo con validación walk-forward estricta |
| Martingala / promediar a la baja sin stop | Riesgo de ruina casi seguro a largo plazo |

## Portafolio sugerido para empezar (ajustable)

- 50–70%: asignación con filtro de tendencia en BTC/ETH (estrategia 2).
- 20–40%: estrategia activa de seguimiento de tendencia (1).
- 10–20%: reserva en USDT para DCA en pánico / oportunidades.

Combinar estrategias poco correlacionadas suaviza la curva de capital más que optimizar una sola.

## Ficha de estrategia (llenar antes de testear)

```
Nombre / versión:
Hipótesis (por qué debería funcionar, en una frase):
Régimen en el que debería ganar / perder:
Universo y marco temporal:
Reglas de entrada (exactas):
Reglas de salida y stop (exactas):
Tamaño de posición:
Parámetros (lista y rango razonable — cuantos menos, mejor):
Criterio de éxito en backtest y en paper trading:
Criterio para descartarla:
```
