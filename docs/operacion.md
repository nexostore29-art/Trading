# Manual de operación — piloto de trading

Estado actual: **paper trading (dry-run)** con $50 simulados. La estrategia `DonchianTrend` es una candidata **no promovida** (ver `research/reports/`); se usa para validar la infraestructura, no como estrategia probada. Criterios de piloto y escalado: `research/criteria.json`.

## Componentes

| Componente | Archivo | Qué hace | Depende de Claude |
|---|---|---|---|
| Bot | `freqtrade/user_data/` | Calcula señales cada vela de 4h y ejecuta órdenes | No |
| Risk Engine | `risk/engine.py`, `risk/limits.json` | Aprueba/reduce/rechaza cada entrada; kill switch | No |
| Watchdog | `risk/watchdog.py` | Vigila desde afuera: heartbeat, drawdown, pérdida diaria, conciliación | No |
| Investigación | `research/` | Backtest, walk-forward, evolución controlada | Opcional |

Si Claude no está disponible, el bot, el Risk Engine y el watchdog siguen funcionando igual.

## Puesta en marcha (servidor o PC encendido 24/7)

Requisitos: Linux (VPS de ~$5/mes o PC propia), Docker y Docker Compose, acceso a `api.binance.com`.

```bash
git clone <este repo> trading && cd trading
cp freqtrade/user_data/config.private.example.json freqtrade/user_data/config.private.json
cp .env.example .env
# Completar config.private.json: jwt_secret_key, ws_token, username, password (generar con
#   python3 -c "import secrets;print(secrets.token_hex(32))")
# En dry-run NO hace falta key de Binance. Dejar exchange.key/secret vacíos.
# Completar .env con el mismo usuario/clave de la API (y Telegram si se quieren alertas).
docker compose up -d
docker compose logs -f freqtrade     # debe decir "Dry run is enabled" y "Bot heartbeat"
```

Verificación inicial (primer día):
1. `docker compose logs watchdog` muestra chequeos sin errores.
2. Probar el kill switch a propósito: `echo prueba > risk/state/KILL` → el Risk Engine rechaza entradas (ver `risk/logs/decisions.jsonl`). Luego `rm risk/state/KILL`.
3. Reiniciar el servidor y confirmar que todo vuelve solo (`restart: unless-stopped`).

## Pasar de paper a piloto real ($50)

Solo cuando se cumpla `piloto_50.requisito_para_iniciar_micro_live` en `research/criteria.json` (o con autorización explícita del usuario para un piloto de infraestructura, registrada como tal).

1. En Binance: crear **subcuenta** dedicada, transferir $50 USDT (+ un poco de BNB opcional para comisiones).
2. Crear API key de trading: permisos **Reading + Spot Trading**, **sin Withdrawals**, **restringida a la IP del servidor**.
3. Crear una segunda key de **solo lectura** para el watchdog (conciliación).
4. Poner la key de trading en `config.private.json` y la de lectura en `.env`. Nunca en el repo ni en el chat.
5. En `config.json`: `"dry_run": false`. Commit con mensaje "Inicio piloto real" para que quede registrado.

## Revisión semanal

Plantilla en `.claude/skills/trading-expert/SKILL.md`. Datos: `freqtrade/user_data/tradesv3*.sqlite`, `risk/logs/decisions.jsonl`, `risk/state/watchdog.json`. Solo se corrigen bugs/operativa; cambios de estrategia vuelven a investigación.

## Respuesta a incidentes

Principio: **ante la duda, no abrir posiciones nuevas** (fail-closed). Las posiciones abiertas tienen stop colocado en el exchange y quedan protegidas aunque el bot se caiga.

| Incidente | Señal | Respuesta automática | Acción humana |
|---|---|---|---|
| Drawdown ≥ 15% | Watchdog | Kill switch + cierre de posiciones + alerta | Post-mortem (`references/evaluacion.md`) antes de borrar `risk/state/KILL` |
| Pérdida diaria ≥ 3% | Watchdog / Risk Engine | Sin entradas hasta el día UTC siguiente | Revisar si fue mercado o error |
| Bot sin respuesta (5 chequeos) | Watchdog | Kill switch + alerta | Revisar servidor/logs; verificar en Binance que los stops sigan puestos |
| Descuadre de posiciones | Watchdog (conciliación) | Kill switch, **sin** cerrar automáticamente | Comparar Binance vs bot a mano; corregir antes de reanudar |
| Datos de mercado obsoletos | Risk Engine | Rechaza entradas | Revisar conexión a Binance |
| Precio anómalo / orden incoherente | Risk Engine | Rechaza la orden | Revisar logs de la estrategia |
| Fill parcial | Freqtrade (`unfilledtimeout`) | Cancela el resto a los 30 min | Ninguna, salvo repetición |
| Reinicio del servidor | Docker | Contenedores reinician; KILL persiste si existía | Confirmar estado con `docker compose ps` |
| Reloj desfasado | Binance rechaza requests | Órdenes fallan → sin entradas | Activar NTP (`timedatectl set-ntp true`) |
| Volatilidad extrema | Stops en exchange | Stop-limit puede no llenarse en una vela violenta | Revisar posición manualmente |
| Claude no disponible | — | Ninguna (el sistema no depende de Claude) | Ninguna |

## Reglas que no se rompen

- Los límites de `risk/limits.json` solo los cambia un humano, con commit propio.
- Una estrategia modificada no vuelve a operar con dinero real sin repetir toda la escalera (`references/gobernanza.md`).
- Nunca escalar capital por una buena semana: solo con los criterios de `research/criteria.json`.
