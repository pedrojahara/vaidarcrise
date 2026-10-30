"""Crescimento em risco (growth-at-risk, como no FMI): o PIB dos próximos 12 meses no cenário ruim.

O cenário ruim é o quantil 10% do crescimento do PIB nos 4 trimestres seguintes, estimado
num painel de 46 países da OCDE desde 1990 (src/calibra.py) contra quatro entradas:
- tendencia: o crescimento médio do país nos 10 anos anteriores;
- crescimento: o crescimento dos últimos 12 meses;
- juro: quanto o juro básico mudou em 12 meses;
- inflacao: quanto a inflação de 12 meses mudou em 12 meses.

As entradas do Brasil saem daqui, do mesmo jeito na calibração (mês a mês, com o que já tinha
sido divulgado) e na conta do dia. Crescimentos em 100 × log, como no painel.
"""
from __future__ import annotations

import math

ENTRADAS = ("tendencia", "crescimento", "juro", "inflacao")
# Nome das colunas no painel da OCDE (data/historico/painel_ocde.csv).
NO_PAINEL = {"tendencia": "media_pais", "crescimento": "g_4t", "juro": "d4_juro", "inflacao": "d4_infl"}
MIN_TRIMESTRES = 20


def _mes(iso: str) -> int:
    return int(iso[:4]) * 12 + int(iso[5:7]) - 1


def crescimento(ibcbr: list[dict]) -> float | None:
    """IBC-Br: média dos 3 últimos meses contra os mesmos 3 meses um ano antes."""
    por_mes = {_mes(x["data"]): x["valor"] for x in ibcbr}
    if not por_mes:
        return None
    n = max(por_mes)
    agora = [por_mes.get(n - k) for k in range(3)]
    antes = [por_mes.get(n - 12 - k) for k in range(3)]
    if None in agora or None in antes:
        return None
    return 100 * math.log(sum(agora) / sum(antes))


def variacao_mensal(serie: list[dict]) -> float | None:
    """Último valor de uma série mensal menos o do mesmo mês um ano antes (IPCA de 12 meses)."""
    por_mes = {_mes(x["data"]): x["valor"] for x in serie}
    if not por_mes:
        return None
    n = max(por_mes)
    return por_mes[n] - por_mes[n - 12] if n - 12 in por_mes else None


def variacao_diaria(serie: list[dict]) -> float | None:
    """Último valor de uma série diária menos o do último dia até a mesma data um ano antes (Selic)."""
    if not serie:
        return None
    ult = serie[-1]
    a, m, d = int(ult["data"][:4]), ult["data"][5:7], ult["data"][8:10]
    alvo = f"{a - 1}-{m}-{'28' if m + d == '0229' else d}"
    base = next((x for x in reversed(serie) if x["data"] <= alvo), None)
    if not base or _mes(alvo) - _mes(base["data"]) > 1:
        return None
    return ult["valor"] - base["valor"]


def tendencia(pib: list[tuple[int, float]]) -> float | None:
    """Média do crescimento em 12 meses (trimestre contra o mesmo trimestre do ano anterior) nos
    40 últimos trimestres divulgados. `pib` traz (número do trimestre, variação % contra o anterior)."""
    qoq = dict(pib)
    if not qoq:
        return None
    ult = max(qoq)
    g4 = []
    for t in range(ult - 39, ult + 1):
        if all(t - k in qoq for k in range(4)):
            g4.append(sum(100 * math.log(1 + qoq[t - k] / 100) for k in range(4)))
    return sum(g4) / len(g4) if len(g4) >= MIN_TRIMESTRES else None


def tri_num(t: str) -> int:
    """'3T2026' (ou '3T26') -> número sequencial do trimestre."""
    q, a = t.split("T")
    a = int(a) + (2000 if len(a) == 2 else 0)
    return a * 4 + int(q) - 1


def num_tri(n: int) -> str:
    return f"{n % 4 + 1}T{n // 4}"


def cenario(entradas: dict[str, float], coef: dict[str, float]) -> float:
    """Valor da regressão de quantil para as entradas dadas (crescimento em 100 × log)."""
    return coef["const"] + sum(coef[k] * entradas[k] for k in ENTRADAS)


def pct(y: float) -> float:
    """100 × log -> variação %."""
    return 100 * (math.exp(y / 100) - 1)
