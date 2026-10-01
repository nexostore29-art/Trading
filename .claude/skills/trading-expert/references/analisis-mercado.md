# Análisis de mercado cripto

Objetivo: clasificar el **régimen** actual y decidir si las condiciones favorecen a alguna estrategia del proyecto. No se busca predecir el precio exacto, sino estimar qué tipo de mercado tenemos y cuánto riesgo conviene asumir.

## Índice
1. Regímenes de mercado
2. Capa técnica (precio y volumen)
3. Capa de derivados
4. Capa on-chain
5. Capa macro y flujos
6. Sentimiento
7. Cómo sintetizar → informe

## 1. Regímenes

| Régimen | Señales típicas | Qué funciona | Qué evitar |
|---|---|---|---|
| Tendencia alcista | Precio > MA200 diaria y MA50 > MA200, máximos crecientes, funding positivo moderado | Seguimiento de tendencia, buy & hold, compras en retrocesos | Shorts, vender demasiado pronto |
| Tendencia bajista | Precio < MA200, MA50 < MA200, mínimos decrecientes | Estar en stablecoin, tamaño reducido; short solo en fase avanzada | Comprar caídas sin confirmación |
| Rango / lateral | ADX < 20, precio oscilando entre soportes/resistencias claros, volatilidad comprimida | Reversión a la media, grid con límites | Breakouts falsos con tamaño grande |
| Euforia | Funding muy alto y persistente, open interest récord, Fear & Greed > 80, subidas verticales | Reducir exposición, subir stops, tomar ganancias parciales | Entrar con apalancamiento |
| Pánico / capitulación | Fear & Greed < 20, liquidaciones masivas de longs, funding negativo | DCA escalonado en BTC/ETH con tamaño pequeño | Apalancamiento, altcoins ilíquidas |

## 2. Técnico

Usá marcos temporales de mayor a menor: semanal → diario → 4h. La señal de menor plazo solo vale si concuerda con el de mayor plazo.

- **Tendencia:** MA/EMA 50 y 200 diarias, pendiente de la MA; estructura de máximos/mínimos.
- **Momentum:** retorno de 1–8 semanas (la literatura muestra momentum de serie temporal en BTC de 1 a 8 semanas, con reversión a plazos más largos), RSI(14) para extremos, MACD como confirmación.
- **Fuerza de tendencia:** ADX(14): > 25 tendencia, < 20 rango.
- **Volatilidad:** ATR(14) para stops y tamaño de posición; Bandas de Bollinger para compresión/expansión.
- **Volumen:** confirmación de rupturas; volumen decreciente en subida = debilidad.
- **Niveles:** soportes/resistencias de marcos temporales altos, máximos/mínimos previos, números redondos.

Advertencia: los indicadores técnicos son derivados del precio. Sirven para **definir reglas y riesgo**, no como fuente de verdad. Ningún indicador aislado tiene ventaja robusta.

## 3. Derivados (muy informativos en cripto)

- **Funding rate (perpetuos, cada 8h):** positivo = los longs pagan → posicionamiento alcista. Funding extremo y persistente (> ~0.05% por 8h) = mercado sobreapalancado, riesgo de cascada de liquidaciones. Funding ~0.01% = neutral.
- **Open interest (OI):** OI subiendo con precio = nuevo dinero apalancado entrando; OI alto + funding alto = frágil. Caída brusca de OI = desapalancamiento (a menudo cerca de mínimos locales).
- **Liquidaciones:** grandes liquidaciones de longs suelen marcar mínimos de corto plazo; de shorts, máximos locales.
- **Base de futuros trimestrales / ratio long-short:** confirman apetito por apalancamiento.
- **Volatilidad implícita (Deribit DVOL):** baja = posible movimiento grande próximo.

## 4. On-chain (plazos medio–largo)

- **MVRV / MVRV Z-score:** valor de mercado vs. valor realizado. Extremos altos históricamente coinciden con techos de ciclo; bajos (< 1) con zonas de acumulación.
- **NUPL, SOPR:** ganancias/pérdidas no realizadas y realizadas.
- **Flujos a exchanges:** entradas netas grandes de BTC a exchanges = presión vendedora potencial.
- **Oferta de stablecoins:** crecimiento = liquidez disponible para comprar cripto; contracción = salida de liquidez.

Son señales lentas: útiles para la **asignación de fondo** (cuánto en BTC vs. stablecoin), no para el timing de días.

## 5. Macro y flujos

- **Liquidez global y tasas:** recortes de la Fed / dólar (DXY) débil suelen favorecer activos de riesgo; subidas de tasas y DXY fuerte, lo contrario.
- **Calendario:** FOMC, CPI, empleo (NFP) → volatilidad. Evitar abrir posiciones grandes justo antes.
- **ETFs spot de BTC/ETH:** los flujos netos diarios son hoy un motor marginal importante del precio. Varias jornadas de salidas = presión vendedora.
- **Correlación con Nasdaq/S&P:** alta en episodios de estrés.
- **Eventos idiosincráticos:** desbloqueos de tokens (token unlocks), hackeos, cambios regulatorios, delistings.

## 6. Sentimiento

- **Crypto Fear & Greed Index** (0–100): úsalo como indicador **contrario** en los extremos, no en el medio.
- Tendencias en redes/búsquedas: euforia minorista = tarde en el ciclo.

## 7. Síntesis → informe

```
## Lectura de mercado — [fecha, hora UTC]
**Régimen:** [tendencia alcista | bajista | rango | euforia | pánico] — confianza [alta/media/baja]
| Capa | Dato | Lectura |
|---|---|---|
| Técnico | BTC vs MA200 diaria, ADX, momentum 4 semanas | ... |
| Derivados | Funding, OI, liquidaciones 24h | ... |
| On-chain | MVRV, flujos a exchanges, stablecoins | ... |
| Macro | Próximo evento, flujos ETF, DXY | ... |
| Sentimiento | Fear & Greed | ... |
**Escenarios (1–4 semanas):** base / alternativo / riesgo de cola, con disparadores observables
**Acción recomendada:** [concreta, dentro de los límites] — tamaño, entrada, stop, invalidación
**Qué cambiaría la recomendación:** [condición medible]
```

Reglas del informe: cada dato con su fuente y hora; si un dato no se pudo obtener, decilo. Cuando las capas se contradicen, la recomendación por defecto es **reducir tamaño**, no elegir la capa que te gusta.
