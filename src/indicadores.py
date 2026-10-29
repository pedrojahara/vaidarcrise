"""Os nove indicadores do nível, calculados do mesmo jeito na calibração e na conta do dia.

Cada função recebe a série como era conhecida no momento da conta (lista de
{"data", "valor"} em ordem) e devolve o valor do indicador, ou None se faltar dado.
A calibração (src/calibra.py) chama as mesmas funções mês a mês, cortando cada série
no que já tinha sido divulgado naquele mês.
"""
from __future__ import annotations

import datetime as dt
from statistics import mean, median

# Dias úteis de dado do Tesouro exigidos na janela de 3 anos (cerca de 2,4 anos).
MIN_TESOURO = 600


def ibcbr(serie: list[dict]) -> float | None:
    if len(serie) < 6:
        return None
    a, b = mean(x["valor"] for x in serie[-3:]), mean(x["valor"] for x in serie[-6:-3])
    return 100 * (a / b - 1)


def focus_pib(ano: float, ano_seguinte: float, data: str) -> float:
    """PIB esperado para os próximos 12 meses: os meses que faltam no ano corrente pesam o ano corrente."""
    mes = int(data[5:7])
    return ((12 - mes) * ano + mes * ano_seguinte) / 12


def juro_real(selic: float, inflacao_esperada: float) -> float:
    return 100 * ((1 + selic / 100) / (1 + inflacao_esperada / 100) - 1)


def comprometimento(serie: list[dict]) -> float | None:
    if len(serie) < 37:
        return None
    return serie[-1]["valor"] - mean(x["valor"] for x in serie[-37:-1])


def tesouro(serie: list[dict]) -> tuple[float, float] | None:
    """Taxa do último dia menos a mediana dos 3 anos anteriores. Devolve (indicador, mediana)."""
    if not serie:
        return None
    ult = serie[-1]
    d = dt.date.fromisoformat(ult["data"])
    ini = d.replace(year=d.year - 3) if not (d.month == 2 and d.day == 29) else d.replace(year=d.year - 3, day=28)
    janela = [x["valor"] for x in serie[:-1] if x["data"] >= ini.isoformat()]
    if len(janela) < MIN_TESOURO:
        return None
    med = median(janela)
    return ult["valor"] - med, med


def _meses_antes(iso: str, n: int) -> str:
    d = dt.date.fromisoformat(iso[:10])
    a, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    return f"{a:04d}-{m + 1:02d}"


def dolar(serie: list[dict]) -> float | None:
    """Variação em 3 meses. Na série diária, contra o último dia útil até a mesma data 3 meses antes;
    na série de fim de mês (calibração), contra o fim do mês 3 meses antes."""
    if len(serie) < 2:
        return None
    ult = serie[-1]
    if "dia" in ult:
        alvo = _meses_antes(ult["data"], 3)
        base = next((x for x in reversed(serie) if x["data"][:7] == alvo), None)
    else:
        d = dt.date.fromisoformat(ult["data"])
        a, m = divmod(d.year * 12 + d.month - 1 - 3, 12)
        dia = min(d.day, [31, 29 if a % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m])
        limite = dt.date(a, m + 1, dia).isoformat()
        base = next((x for x in reversed(serie) if x["data"] <= limite), None)
        if base and (dt.date.fromisoformat(limite) - dt.date.fromisoformat(base["data"])).days > 10:
            base = None
    if not base:
        return None
    return 100 * (ult["valor"] / base["valor"] - 1)


def _mesmo_mes_antes(serie: list[dict], n: int) -> dict | None:
    alvo = _meses_antes(serie[-1]["data"], n)
    return next((x for x in reversed(serie) if x["data"][:7] == alvo), None)


def divida(serie: list[dict]) -> float | None:
    if not serie:
        return None
    base = _mesmo_mes_antes(serie, 12)
    return serie[-1]["valor"] - base["valor"] if base else None


def sahm(serie: list[dict]) -> float | None:
    if len(serie) < 15:
        return None
    m3 = [mean(x["valor"] for x in serie[i - 2:i + 1]) for i in range(2, len(serie))]
    return m3[-1] - min(m3[-13:-1])


def commodities(serie: list[dict]) -> float | None:
    if not serie:
        return None
    base = _mesmo_mes_antes(serie, 6)
    return 100 * (serie[-1]["valor"] / base["valor"] - 1) if base else None
