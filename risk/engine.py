"""Risk Engine independiente y determinista.

No depende de Freqtrade ni de Claude: recibe una propuesta de orden y el estado de la cuenta, y devuelve una
decisión estructurada. Tiene autoridad para APROBAR, REDUCIR o RECHAZAR órdenes y para activar el kill switch.

El kill switch es un archivo (risk/state/KILL). Mientras exista, no se abre ninguna posición nueva, aunque el bot
se reinicie (fail-closed). Solo un humano lo borra, después de revisar la causa.
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIMITS_FILE = ROOT / "limits.json"
STATE_DIR = ROOT / "state"
KILL_FILE = STATE_DIR / "KILL"
LOG_FILE = ROOT / "logs" / "decisions.jsonl"

APPROVE, REDUCE, REJECT = "APPROVE", "REDUCE", "REJECT"


def load_limits(path: Path = LIMITS_FILE) -> dict:
    return json.loads(path.read_text())


@dataclass
class OrderProposal:
    pair: str
    side: str                 # "buy" (solo long spot)
    entry: float
    stop: float
    notional: float           # USD propuestos
    leverage: float = 1.0
    strategy: str = ""
    strategy_version: str = ""


@dataclass
class AccountState:
    equity: float                         # capital total marcado a mercado
    peak_equity: float                    # máximo histórico del capital
    day_start_equity: float               # capital al inicio del día UTC
    positions: dict = field(default_factory=dict)   # pair -> {"notional": float, "risk": float}
    open_orders: list = field(default_factory=list) # pares con órdenes de entrada abiertas
    last_close: float | None = None       # último cierre conocido del par
    last_candle_time: datetime | None = None
    timeframe_minutes: int = 240


@dataclass
class Decision:
    action: str
    notional: float
    reasons: list
    kill: bool = False

    @property
    def allowed(self) -> bool:
        return self.action in (APPROVE, REDUCE)


def kill_active(kill_file: Path = KILL_FILE) -> str | None:
    if not kill_file.exists():
        return None
    return kill_file.read_text().strip() or "activo"


def trigger_kill(reason: str, kill_file: Path = KILL_FILE) -> None:
    kill_file.parent.mkdir(parents=True, exist_ok=True)
    if not kill_file.exists():
        kill_file.write_text(f"{datetime.now(timezone.utc).isoformat()} {reason}\n")


def evaluate(order: OrderProposal, st: AccountState, limits: dict, now: datetime | None = None,
             kill_file: Path = KILL_FILE) -> Decision:
    """Evalúa una orden de entrada. Las verificaciones van de la más grave a la menos grave."""
    now = now or datetime.now(timezone.utc)
    L = limits

    def reject(*why, kill=False):
        if kill:
            trigger_kill("; ".join(why), kill_file)
        return Decision(REJECT, 0.0, list(why), kill)

    if (k := kill_active(kill_file)):
        return reject(f"kill switch activo: {k}")
    if st.equity <= 0 or st.peak_equity <= 0:
        return reject("estado de cuenta inválido", kill=True)

    dd = (st.equity / st.peak_equity - 1) * 100
    if dd <= -L["drawdown_max_pct"]:
        return reject(f"drawdown {dd:.1f}% ≥ límite {L['drawdown_max_pct']}%", kill=True)
    day = (st.equity / st.day_start_equity - 1) * 100 if st.day_start_equity > 0 else 0.0
    if day <= -L["perdida_diaria_max_pct"]:
        return reject(f"pérdida diaria {day:.1f}% ≥ límite {L['perdida_diaria_max_pct']}%")

    if order.side != "buy":
        return reject("solo se permiten compras spot (long)")
    if order.leverage > L["apalancamiento_max"]:
        return reject(f"apalancamiento {order.leverage}x > {L['apalancamiento_max']}x")
    if order.pair not in L["pares_permitidos"]:
        return reject(f"par {order.pair} fuera del universo permitido")
    if order.pair in st.positions or order.pair in st.open_orders:
        return reject("orden duplicada: ya hay posición u orden abierta en el par")

    if st.last_candle_time is None:
        return reject("sin datos de mercado")
    age = now - st.last_candle_time
    if age > timedelta(minutes=st.timeframe_minutes * (L["datos_obsoletos_max_velas"] + 1)):
        return reject(f"datos obsoletos: última vela hace {age}")
    if not (order.entry > 0 and 0 < order.stop < order.entry):
        return reject(f"orden incoherente: entrada {order.entry}, stop {order.stop}")
    if st.last_close and abs(order.entry / st.last_close - 1) * 100 > L["desvio_precio_max_pct"]:
        return reject(f"precio fuera de rango: {order.entry} vs último cierre {st.last_close}")

    reasons, notional = [], order.notional
    stop_frac = (order.entry - order.stop) / order.entry
    max_risk_notional = st.equity * L["riesgo_por_operacion_max_pct"] / 100 / stop_frac
    if notional > max_risk_notional:
        notional = max_risk_notional
        reasons.append(f"riesgo por operación > {L['riesgo_por_operacion_max_pct']}%")
    base = order.pair.split("/")[0]
    cap_pct = L["exposicion_max_btc_eth_pct"] if base in ("BTC", "ETH") else L["exposicion_max_activo_pct"]
    if notional > st.equity * cap_pct / 100:
        notional = st.equity * cap_pct / 100
        reasons.append(f"exposición en {base} > {cap_pct}%")
    open_risk = sum(p.get("risk", 0.0) for p in st.positions.values())
    room = st.equity * L["riesgo_abierto_total_max_pct"] / 100 - open_risk
    if room <= 0:
        return reject(f"riesgo abierto total ≥ {L['riesgo_abierto_total_max_pct']}%")
    if notional * stop_frac > room:
        notional = room / stop_frac
        reasons.append("riesgo abierto total")
    if notional < L["orden_minima_usd"]:
        return reject(f"tamaño {notional:.2f} USD < orden mínima {L['orden_minima_usd']} USD", *reasons)
    if notional < order.notional - 1e-9:
        return Decision(REDUCE, notional, reasons)
    return Decision(APPROVE, notional, ["dentro de límites"])


def log_decision(order: OrderProposal, st: AccountState, d: Decision, log_file: Path = LOG_FILE) -> None:
    """Auditoría: cada decisión queda registrada para poder reconstruir por qué se hizo (o no) cada operación."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "orden": asdict(order),
           "estado": {**asdict(st), "last_candle_time": str(st.last_candle_time)}, "decision": asdict(d)}
    with log_file.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
