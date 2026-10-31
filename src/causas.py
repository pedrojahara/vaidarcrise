"""O que causa recessão: a pesquisa por trás da aba /causas/, para a METODOLOGIA.md.

O que veio antes das altas da Selic no Brasil desde 2002, refeito aqui a partir de
data/historico/series.json. Os números dos 44 países vêm do painel da pesquisa e ficam
fixos em config/causas.json. A aba em si não usa estes números.

Uso: python src/causas.py   (imprime a chance de cada sinal vir antes de uma alta da Selic)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
CONFIG = ROOT / "config" / "causas.json"
INICIO_AUC = "2002-01"


def mes_num(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def num_mes(n: int) -> str:
    a, m = divmod(n, 12)
    return f"{a:04d}-{m + 1:02d}"


def mensal(serie: list[dict]) -> dict[str, float]:
    """Média de cada mês (as séries diárias viram mensais)."""
    soma: dict[str, list[float]] = {}
    for p in serie:
        if p.get("valor") is not None:
            soma.setdefault(p["data"][:7], []).append(p["valor"])
    return {m: sum(v) / len(v) for m, v in soma.items()}


def desloca(x: dict[str, float], k: int) -> dict[str, float]:
    """O valor de k meses antes em cada mês (k > 0) ou de k meses depois (k < 0)."""
    return {num_mes(mes_num(m) + k): v for m, v in x.items()}


def var(x: dict[str, float], k: int, pct: bool = False) -> dict[str, float]:
    antes = desloca(x, k)
    return {m: (100 * (v / antes[m] - 1) if pct else v - antes[m]) for m, v in x.items() if m in antes}


def auc(x: dict[str, float], y: dict[str, int]) -> float | None:
    """Chance de um mês antes de uma alta ter o sinal mais alto que um mês sem alta (0,5 = cara ou coroa)."""
    pos = [v for m, v in x.items() if y.get(m) == 1]
    neg = [v for m, v in x.items() if y.get(m) == 0]
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def series_brasil(series: dict) -> dict[str, dict[str, float]]:
    return {k: mensal(series[k]) for k in ("selic_meta", "ipca_12m", "focus_ipca_12m", "ibcbr", "primario_12m",
                                           "divida_bruta", "commodities", "comprometimento_renda") if k in series}


def sinais_selic(s: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Cada sinal com o que já tinha sido divulgado no mês (IBC-Br, primário e dívida saem com 2 meses de atraso)."""
    selic, foc = s["selic_meta"], s["focus_ipca_12m"]
    return {
        "economia": desloca(var(s["ibcbr"], 12, pct=True), 2),
        "preco_fora": desloca(var(s["commodities"], 12, pct=True), 1),
        "deficit_sobe": desloca(var(s["primario_12m"], 12), 2),
        "expectativa_sobe": var(foc, 6),
        "juro_real_baixo": {m: v - selic[m] for m, v in foc.items() if m in selic},
        "divida": desloca(s["divida_bruta"], 2),
    }


def alta_selic(selic: dict[str, float]) -> dict[str, int]:
    """1 se a Selic subir 1 ponto ou mais nos 12 meses seguintes."""
    depois = desloca(selic, -12)
    return {m: int(depois[m] - v >= 1) for m, v in selic.items() if m in depois and m >= INICIO_AUC}


def aucs_brasil(series: dict) -> dict:
    s = series_brasil(series)
    y = alta_selic(s["selic_meta"])
    out = {}
    for k, x in sinais_selic(s).items():
        a = auc({m: v for m, v in x.items() if m in y}, y)
        out[k] = round(a, 2) if a is not None else None
    return {"aucs": out, "altas": sum(y.values()), "meses": len(y)}


def carregar_config() -> dict:
    return json.loads(CONFIG.read_text())


def main() -> None:
    series = json.loads(HIST.read_text())["series"]
    cfg = carregar_config()
    b = aucs_brasil(series)
    print(f"Selic subiu 1 ponto ou mais nos 12 meses seguintes em {b['altas']} de {b['meses']} meses desde {INICIO_AUC}")
    for s in cfg["sinais"]:
        print(f"  {s['nome']:45s} 44 países {s.get('paises') or '—'}  Brasil {b['aucs'].get(s['id'])}")


if __name__ == "__main__":
    main()
