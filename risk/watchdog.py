"""Watchdog independiente: vigila al bot desde afuera y aplica el kill switch.

Corre como proceso separado (no dentro de Freqtrade, no depende de Claude). Cada INTERVAL segundos:
- verifica que la API del bot responda (heartbeat);
- calcula capital, drawdown desde el máximo y pérdida del día;
- concilia las posiciones que el bot cree tener contra el exchange (si hay key de solo lectura configurada);
- ante una violación: detiene entradas (/stopentry), cierra posiciones si corresponde (/forceexit), crea el
  archivo KILL y alerta por Telegram. Fail-closed: si algo es incierto, no se abren posiciones nuevas.

Variables de entorno: FT_API_URL, FT_API_USER, FT_API_PASS, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
BINANCE_READ_KEY, BINANCE_READ_SECRET (opcionales), WATCHDOG_INTERVAL (s).
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk import engine as risk  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s watchdog: %(message)s")
log = logging.getLogger("watchdog")

API = os.environ.get("FT_API_URL", "http://freqtrade:8080/api/v1")
AUTH = (os.environ.get("FT_API_USER", ""), os.environ.get("FT_API_PASS", ""))
INTERVAL = int(os.environ.get("WATCHDOG_INTERVAL", "60"))
MAX_API_FAILS = 5
STATE = risk.STATE_DIR / "watchdog.json"


def alert(msg: str) -> None:
    log.warning(msg)
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": msg}, timeout=10)
        except requests.RequestException as e:
            log.error("no se pudo enviar alerta: %s", e)


def api(method: str, path: str, **kw):
    r = requests.request(method, f"{API}/{path}", auth=AUTH, timeout=15, **kw)
    r.raise_for_status()
    return r.json()


def stop_entries(reason: str) -> None:
    try:
        api("POST", "stopentry")
    except requests.RequestException as e:
        log.error("stopentry falló: %s", e)
    alert(f"⛔ Entradas detenidas: {reason}")


def kill(reason: str, close_positions: bool) -> None:
    risk.trigger_kill(reason)
    stop_entries(reason)
    if close_positions:
        try:
            for t in api("GET", "status"):
                api("POST", "forceexit", json={"tradeid": str(t["trade_id"]), "ordertype": "market"})
        except requests.RequestException as e:
            alert(f"🚨 No se pudieron cerrar posiciones ({e}). Los stops en el exchange siguen activos. Revisar YA.")
    alert(f"🛑 KILL SWITCH: {reason}. Para reanudar: revisar causa, borrar risk/state/KILL y reiniciar.")


def exchange_positions() -> dict | None:
    """Saldos reales en Binance con key de SOLO LECTURA. None si no está configurada."""
    key, sec = os.environ.get("BINANCE_READ_KEY"), os.environ.get("BINANCE_READ_SECRET")
    if not key or not sec:
        return None
    import ccxt
    bal = ccxt.binance({"apiKey": key, "secret": sec}).fetch_balance()
    return {k: v for k, v in bal["total"].items() if v and k != "USDT"}


def check_once(st: dict, limits: dict) -> dict:
    bal = api("GET", "balance")
    eq = float(bal["total"])
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    st["peak"] = max(st.get("peak", eq), eq)
    if st.get("day") != today:
        st["day"], st["day_start"] = today, eq
    dd = (eq / st["peak"] - 1) * 100
    day = (eq / st["day_start"] - 1) * 100
    st.update(equity=eq, drawdown_pct=round(dd, 2), day_pct=round(day, 2), last_ok=now.isoformat())

    if risk.kill_active():
        return st
    if dd <= -limits["drawdown_max_pct"]:
        kill(f"drawdown {dd:.1f}% ≥ {limits['drawdown_max_pct']}%", close_positions=True)
    elif day <= -limits["perdida_diaria_max_pct"] and not st.get("paused_day") == today:
        st["paused_day"] = today
        stop_entries(f"pérdida diaria {day:.1f}% ≥ {limits['perdida_diaria_max_pct']}% (se reanuda mañana)")
    elif st.get("paused_day") and st["paused_day"] != today:
        api("POST", "start")
        st.pop("paused_day")
        alert("▶️ Nuevo día UTC: entradas reanudadas")

    if not api("GET", "show_config").get("dry_run", True):
        real = exchange_positions()
        if real is not None:
            bot = {}
            for t in api("GET", "status"):
                base = t["pair"].split("/")[0]
                bot[base] = bot.get(base, 0) + float(t["amount"])
            for asset in set(real) | set(bot):
                r, b = real.get(asset, 0.0), bot.get(asset, 0.0)
                if abs(r - b) > max(1e-8, 0.02 * max(r, b)):
                    kill(f"descuadre de posiciones en {asset}: exchange {r} vs bot {b}", close_positions=False)
                    break
    return st


def main():
    limits = risk.load_limits()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    fails = 0
    while True:
        try:
            st = check_once(st, limits)
            fails = 0
        except Exception as e:  # cualquier falla del vigilante cuenta como incertidumbre operativa
            fails += 1
            log.error("chequeo falló (%d/%d): %s", fails, MAX_API_FAILS, e)
            if fails == MAX_API_FAILS:
                alert(f"🚨 Bot sin respuesta {fails} veces seguidas ({e}). Los stops en el exchange protegen lo abierto. Revisar.")
                risk.trigger_kill(f"API del bot sin respuesta: {e}")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, indent=2))
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
