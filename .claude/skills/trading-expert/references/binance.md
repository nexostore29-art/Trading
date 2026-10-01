# Binance: operación técnica

Datos verificados en octubre 2026; Binance cambia comisiones y reglas — reconfirmá en la web oficial antes de decisiones grandes.

## Disponibilidad (Costa Rica)
Binance opera para usuarios de Costa Rica, con P2P en colones (CRC). Las cripto son legales pero no son moneda de curso legal; no hay un marco regulatorio específico completo. Ganancias de capital: ~15% (declaración en TRIBU-CR, formularios 113–118). Confirmar con contador.

## Comisiones
| Producto | Maker | Taker | Notas |
|---|---|---|---|
| Spot VIP 0 | 0.100% | 0.100% | 0.075% pagando con BNB (25% desc.; hay que tener BNB) |
| USDⓈ-M futuros VIP 0 | 0.020% | 0.050% | + funding cada 8h; 2% de comisión de liquidación |

Implicación: ida y vuelta en spot ≈ 0.15–0.2% + slippage. Una estrategia que hace 5 operaciones diarias paga ~1% diario en costos — imposible de superar. Preferir pocas operaciones y órdenes limit (maker).

## API key — configuración segura
1. Crear **subcuenta** dedicada al bot con solo el capital asignado.
2. Permisos: **Enable Reading** + **Enable Spot & Margin Trading**. Nunca **Enable Withdrawals**. Futuros solo cuando se llegue a esa fase.
3. **Restricción por IP** a la IP fija del servidor del bot (sin restricción de IP, Binance borra la key a los 90 días o 30 de inactividad, y la key es más vulnerable).
4. Guardar key/secret como secretos del entorno (variables de entorno / gestor de secretos), nunca en el repo ni en el chat. Añadir `config.private.json` / `.env` a `.gitignore`.
5. Rotar keys periódicamente y borrar las que no se usen.

## Testnet / demo
- Spot testnet: https://testnet.binance.vision/ (key separada; endpoints `https://testnet.binance.vision/api`).
- Futuros: Futures Demo Trading vía API.
- Freqtrade además tiene `dry_run: true`, que simula con precios reales sin enviar órdenes — suele ser más realista que el testnet (cuyo libro de órdenes es artificial).

## Tipos de orden útiles (spot)
- `LIMIT` / `LIMIT_MAKER` (solo maker, se rechaza si cruzaría el libro → asegura comisión maker).
- `STOP_LOSS_LIMIT`: al tocar `stopPrice` coloca una orden limit.
- `OCO`: take-profit + stop; si una se ejecuta, la otra se cancela. Soporta trailing en la pata contingente.
- `trailingDelta` en órdenes stop: trailing stop nativo del exchange.

## Límites de la API
- Peso de requests: 6 000 por minuto por IP (no equivale a 6 000 requests). Usar WebSockets para precios en vivo en lugar de polling.
- Límites de órdenes por cuenta (por 10 s y por día). Respetar filtros del símbolo: `PRICE_FILTER` (tick size), `LOT_SIZE` (step size), `NOTIONAL` (mínimo por orden, típicamente ~5–10 USDT). Freqtrade/CCXT los manejan.

## Librerías
- **CCXT** (Python/JS): interfaz unificada a Binance y otros exchanges.
- **python-binance** / SDK oficial `binance-connector`.
- **Freqtrade** (usa CCXT internamente) para el bot completo.
