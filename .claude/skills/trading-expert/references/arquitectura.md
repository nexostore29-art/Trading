# Arquitectura del sistema

```
            ┌───────────────── Claude (este skill) ─────────────────┐
            │ análisis de mercado · diseño de estrategias · reportes │
            └───────────────┬────────────────────────────────────────┘
                            │ MCP (herramientas acotadas)
┌──────────────┐   ┌────────▼─────────┐   ┌──────────────────┐
│ Datos        │──▶│ Freqtrade        │──▶│ Binance (subcta) │
│ velas, funding│  │ estrategias +    │   │ API sin retiros  │
│ F&G, macro   │   │ protections +    │   │ stops en exchange│
└──────────────┘   │ gestor de riesgo │   └──────────────────┘
                   └────────┬─────────┘
                            ▼
                   Telegram / reporte semanal / DB de operaciones
```

## Componentes

**1. Freqtrade (motor).** Código abierto (GPL-3.0), versión mensual (2026.x), Python 3.11+. Aporta: estrategias en Python, backtesting, hyperopt, dry-run, FreqAI (ML), API REST, Telegram, FreqUI. Se instala con Docker (`freqtrade/freqtrade:stable`) o pip.

Configuración clave de riesgo en `config.json`:
```json
{
  "dry_run": true,
  "trading_mode": "spot",
  "max_open_trades": 4,
  "stake_currency": "USDT",
  "stake_amount": "unlimited",
  "tradable_balance_ratio": 0.95,
  "order_types": { "entry": "limit", "exit": "limit", "stoploss": "limit", "stoploss_on_exchange": true },
  "exchange": { "name": "binance", "key": "", "secret": "", "pair_whitelist": ["BTC/USDT", "ETH/USDT"] }
}
```
En Binance spot el stop en exchange es stop-limit (`stoploss_on_exchange_limit_ratio` define el margen entre precio stop y límite). `stake_amount` dinámico se calcula en la estrategia con `custom_stake_amount()` aplicando el riesgo fijo del 1%.

**Protections** de Freqtrade (en la estrategia):
- `StoplossGuard`: pausa si hay N stops en un periodo.
- `MaxDrawdown`: pausa si el drawdown supera el umbral.
- `CooldownPeriod`: espera tras cerrar una operación en el par.
- `LowProfitPairs`: bloquea pares que vienen perdiendo.

**2. Gestor de riesgo propio.** Capa adicional (proceso o módulo) que verifica, antes de cada orden, los límites duros de `SKILL.md`: riesgo por operación, exposición por activo, riesgo total abierto, pérdida diaria, drawdown global. Si se viola → rechaza la orden y, si es drawdown, ejecuta `/stopentry` o `/forceexit all` vía la API de Freqtrade y alerta.

**3. Servidor MCP para Claude.** Permite a Claude consultar y proponer sin acceso directo a la key.
Herramientas sugeridas:
| Herramienta | Tipo |
|---|---|
| `get_portfolio`, `get_open_trades`, `get_trade_history` | lectura (API REST de Freqtrade) |
| `get_market_snapshot(pair)` — precio, MA, ATR, ADX, funding, OI | lectura |
| `get_sentiment` — Fear & Greed, flujos ETF | lectura |
| `run_backtest(strategy, timerange)` | ejecuta en sandbox |
| `get_performance_report(period)` — métricas de `eval_stats.py` | lectura |
| `propose_trade(pair, side, size, stop)` | escribe una propuesta que **pasa por el gestor de riesgo** y requiere aprobación humana |
| `pause_bot` | acción defensiva (siempre permitida) |

Existen servidores MCP de Binance de código abierto (p. ej. `nirholas/Binance-MCP`, `AnalyticAce/binance-mcp-server`), pero exponen cientos de endpoints, incluidas operaciones de trading y de billetera. Si se usan, solo con una key de **solo lectura**. Preferible un MCP propio, pequeño, que hable con Freqtrade.

**4. Reportes.** Telegram para alertas en tiempo real; reporte semanal con la plantilla de `SKILL.md`; base de datos de operaciones (SQLite de Freqtrade) como fuente para impuestos y evaluación.

## Despliegue
- Servidor con IP fija (VPS) para la whitelist de Binance; Docker Compose; reinicio automático.
- Reloj sincronizado (NTP) — Binance rechaza requests con timestamp desfasado.
- Backups de la DB y la config (sin secretos).
- Monitoreo: heartbeat; si el bot deja de reportar, alerta.

## Estructura de repositorio sugerida
```
Trading/
├── .claude/skills/trading-expert/   # este skill
├── freqtrade/user_data/
│   ├── strategies/                  # estrategias (.py)
│   ├── config.json                  # sin secretos
│   └── config.private.json          # gitignored
├── risk/                            # gestor de riesgo
├── mcp_server/                      # servidor MCP
├── reports/                         # reportes semanales
└── docker-compose.yml
```
