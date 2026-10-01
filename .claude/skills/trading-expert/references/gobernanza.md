# Gobernanza: auditoría de factibilidad, escalera de despliegue y seguridad operativa

Adoptado del documento "Autonomous Quant Trading Research System" del usuario (2026-10-01), adaptado al alcance actual (Binance spot, capital pequeño). La postura por defecto es **intentar demostrar que la estrategia NO funciona**; matar rápido una idea mala es un resultado exitoso.

## 1. Auditoría de factibilidad (antes de construir cualquier estrategia)

Responder por escrito en `strategies/<id>/hypothesis.md`. Si no hay una explicación razonable de la ventaja → **RECHAZAR**.

- Hipótesis exacta y mecanismo económico de la ventaja. ¿Por qué debería persistir? ¿Quién está del otro lado?
- Evidencia académica/empírica (citar en `sources.md`).
- Ejecutabilidad: liquidez, latencia requerida, spread, slippage esperado, comisiones, turnover.
- Datos necesarios y su costo; costo de infraestructura y de Claude/API.
- Impuestos/regulación aplicables.
- **Ganancia absoluta esperada con el capital real disponible** y si justifica el tiempo de ingeniería.

## 2. Estándar de investigación

- Criterios de aprobación/rechazo en `research/criteria.json`, **definidos y commiteados antes de ver resultados**. Nunca cambiar modelo y criterios a la vez para hacer pasar una estrategia; un cambio de criterios es una versión nueva justificada.
- Cada corrida tiene `run_id` (timestamp + commit). Resultados negativos **nunca** se borran ni se sobrescriben (`research/reports/`, `research/registry.json` append-only).
- Intentos acumulados entran en el Deflated Sharpe: cuanto más se prueba, más se exige.
- Datos con manifiesto (`data/data_manifest.json`: fuente, hashes). Si hay duda sobre integridad de datos → **NO OPERAR**.
- Rechazo automático: muere con costos x2; solo funciona en una combinación estrecha de parámetros; pequeñas modificaciones destruyen el resultado; no le gana a una alternativa simple (buy & hold, filtro MA). Si ML/Claude agrega una mejora marginal que no compensa complejidad y riesgo → rechazar el modelo complejo.

## 3. Escalera de despliegue

Capital real = 0 hasta micro-live. Cada versión pasa de nuevo por toda la escalera; **está prohibido que el sistema modifique una estrategia live y siga operando con dinero real**.

| Etapa | Objetivo | Sale si… |
|---|---|---|
| Research → backtest → OOS → walk-forward → estrés | Evidencia estadística | Pasa `criteria.json` |
| Paper (dry-run) | Validar pipeline, señales, timing, órdenes, estado, reinicios, logs, risk engine — **no demuestra rentabilidad** | 4 semanas sin incidentes; señales = backtest |
| Shadow live | Señales en vivo vs precios reales, comparar fills simulados vs mercado | Slippage y fills dentro de lo esperado |
| Micro-live | Capital mínimo (≥ orden mínima × posiciones) | Criterios de `evaluacion.md` |
| Producción | Escalado gradual | Matriz de escalado |

## 4. Risk Engine (independiente y determinista)

Claude nunca puede saltárselo ni modificar sus límites. Una recomendación de Claude **nunca** se convierte directamente en orden: toda salida que afecte posiciones usa un esquema estructurado (JSON validado), nunca prosa libre.

Valida: exposición total/por activo, correlación, volatilidad, liquidez/spread, tamaño, drawdown actual, pérdida diaria/por estrategia, órdenes abiertas y duplicadas, datos obsoletos, conectividad, sanidad de precio y de orden, apalancamiento.
Autoridad: RECHAZAR, REDUCIR o CANCELAR orden; CERRAR posición; DESACTIVAR estrategia; APAGAR sistema.

## 5. Kill switch y fail-closed

Disparadores: datos faltantes/corruptos/obsoletos, desconexión del exchange, spread anormal, posiciones inesperadas o descuadre en la reconciliación, slippage anormal, pérdidas excesivas, inestabilidad de API, excepción de estrategia, falla del risk engine. Ante incertidumbre operativa: **no abrir nada nuevo y proteger lo abierto** (stops en el exchange). Si Claude no está disponible, el sistema sigue operando con seguridad sin él.

## 6. Strategy killer (detección de deterioro de la ventaja)

Proceso aparte que monitorea en ventanas móviles: Sharpe, drawdown, slippage, turnover, tasa de acierto, payoff, volatilidad, distribución de operaciones vs la del backtest. Si el desempeño cae fuera del intervalo esperado (p. ej. percentil 5 del Monte Carlo del backtest) → desactivar y revisar, sin esperar a perder toda la ganancia histórica.

## 7. Observabilidad e incidentes

Registrar datos de entrada, señales, decisiones de riesgo, órdenes, fills, errores, decisiones de Claude y versiones (estrategia + commit), de forma que cada operación sea reconstruible.
Procedimientos escritos para: exchange caído, datos caídos, fill parcial/duplicado, posición inesperada, reinicio del servidor, reloj desfasado, volatilidad extrema, Claude no disponible.

## 8. Seguridad

Credenciales fuera de prompts y logs (gestor de secretos). Mínimo privilegio. Credenciales de investigación (solo lectura) separadas de las de ejecución. Claude nunca puede retirar fondos, cambiar destinos, desactivar logs, cambiar límites de riesgo ni la seguridad de la cuenta.

## 9. Viabilidad económica

Calcular siempre: retorno bruto − comisiones − spread − slippage − datos − infraestructura − Claude/API − FX/transferencias − impuestos = **retorno económico neto**, y la **ganancia absoluta con el capital real**. Alfa estadístico con ganancia irrelevante → marcar **NO ECONÓMICAMENTE VIABLE**. Si la evidencia muestra que el proyecto no puede producir un rendimiento neto significativo → **DETENER y documentar**; no inventar nuevas capas de IA para justificar continuar.
