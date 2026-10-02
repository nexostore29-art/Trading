from datetime import datetime, timedelta, timezone

import pytest

from risk import engine as risk

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


@pytest.fixture
def limits():
    return risk.load_limits()


@pytest.fixture
def kill_file(tmp_path):
    return tmp_path / "KILL"


def state(**kw):
    base = dict(equity=50.0, peak_equity=50.0, day_start_equity=50.0, positions={}, open_orders=[],
                last_close=60000.0, last_candle_time=NOW - timedelta(hours=1), timeframe_minutes=240)
    base.update(kw)
    return risk.AccountState(**base)


def order(**kw):
    base = dict(pair="BTC/USDT", side="buy", entry=60000.0, stop=57000.0, notional=10.0)
    base.update(kw)
    return risk.OrderProposal(**base)


def ev(o, s, limits, kill_file):
    return risk.evaluate(o, s, limits, now=NOW, kill_file=kill_file)


def test_orden_valida_se_aprueba(limits, kill_file):
    d = ev(order(), state(), limits, kill_file)
    assert d.action == risk.APPROVE and d.notional == 10.0


def test_reduce_por_riesgo_y_exposicion(limits, kill_file):
    # stop a 5%: 2% de riesgo máx -> 20 USD; exposición BTC 50% -> 25 USD; pide 40 -> 20
    d = ev(order(notional=40.0), state(), limits, kill_file)
    assert d.action == risk.REDUCE and d.notional == pytest.approx(20.0)


def test_reduce_por_exposicion(limits, kill_file):
    # stop a 1%: riesgo permite 100 USD, exposición 50% del capital -> 25 USD
    d = ev(order(stop=59400.0, notional=100.0), state(), limits, kill_file)
    assert d.action == risk.REDUCE and d.notional == pytest.approx(25.0)


def test_rechaza_bajo_minimo(limits, kill_file):
    d = ev(order(notional=3.0), state(), limits, kill_file)
    assert d.action == risk.REJECT


def test_drawdown_activa_kill_switch_persistente(limits, kill_file):
    d = ev(order(), state(equity=42.0, peak_equity=50.0, day_start_equity=42.0), limits, kill_file)
    assert d.action == risk.REJECT and d.kill and kill_file.exists()
    # aunque el capital se recupere, sigue bloqueado hasta que un humano borre el archivo
    d2 = ev(order(), state(), limits, kill_file)
    assert d2.action == risk.REJECT and "kill switch" in d2.reasons[0]


def test_perdida_diaria_bloquea_sin_kill(limits, kill_file):
    d = ev(order(), state(equity=48.4, day_start_equity=50.0), limits, kill_file)
    assert d.action == risk.REJECT and not kill_file.exists()


@pytest.mark.parametrize("o,why", [
    (order(pair="DOGE/USDT"), "universo"),
    (order(side="sell"), "long"),
    (order(leverage=3.0), "apalancamiento"),
    (order(stop=61000.0), "incoherente"),
    (order(entry=63000.0, stop=60000.0), "rango"),
])
def test_rechazos_de_sanidad(limits, kill_file, o, why):
    d = ev(o, state(), limits, kill_file)
    assert d.action == risk.REJECT and why in " ".join(d.reasons)


def test_datos_obsoletos(limits, kill_file):
    d = ev(order(), state(last_candle_time=NOW - timedelta(hours=13)), limits, kill_file)
    assert d.action == risk.REJECT and "obsoletos" in d.reasons[0]


def test_sin_datos(limits, kill_file):
    assert ev(order(), state(last_candle_time=None), limits, kill_file).action == risk.REJECT


def test_duplicada(limits, kill_file):
    s = state(positions={"BTC/USDT": {"notional": 10.0, "risk": 0.5}})
    assert ev(order(), s, limits, kill_file).action == risk.REJECT


def test_riesgo_abierto_total(limits, kill_file):
    lim = {**limits, "pares_permitidos": ["BTC/USDT", "ETH/USDT"]}
    s = state(positions={"ETH/USDT": {"notional": 20.0, "risk": 2.5}})  # 5% de 50 ya usado
    assert ev(order(), s, lim, kill_file).action == risk.REJECT


def test_log_auditoria(tmp_path, limits, kill_file):
    o, s = order(), state()
    d = ev(o, s, limits, kill_file)
    f = tmp_path / "log.jsonl"
    risk.log_decision(o, s, d, log_file=f)
    assert '"APPROVE"' in f.read_text()
