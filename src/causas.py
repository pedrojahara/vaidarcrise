"""O que causa recessão: os números da aba /causas/.

Duas partes:
- O que veio antes das altas da Selic no Brasil desde 2002, refeito aqui a partir de
  data/historico/series.json. Os números dos 44 países vêm do painel da pesquisa e ficam
  fixos em config/causas.json.
- As quatro perguntas de "E hoje?" (economia no limite, juro freando, dívida crescendo, famílias
  apertadas): o dado mais recente contra a faixa normal ou contra os meses desde 2004.

Uso: python src/causas.py   (imprime a chance de cada sinal vir antes de uma alta da Selic)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
CONFIG = ROOT / "config" / "causas.json"
INICIO_AUC, INICIO_HOJE = "2002-01", "2004-01"
# Atenção: fora da metade do meio dos meses desde 2004, para o lado que pressiona (como no Resumo).
CORTE = 75


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


# -------------------------------------------------------------- Brasil hoje
def percentil(hist: dict[str, float], v: float) -> int:
    xs = [x for m, x in hist.items() if m >= INICIO_HOJE]
    return round(100 * sum(1 for x in xs if x <= v) / len(xs)) if xs else 50


def num(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 and round(abs(x), d) != 0 else "") + s


def pct(x: float, d: int = 2) -> str:
    """13,75 e 15 (sem os zeros do fim)."""
    s = num(x, d)
    return s.rstrip("0").rstrip(",") if "," in s else s


def _pontos(v: float) -> str:
    """'0,6 ponto', '5,1 pontos'."""
    return f"{num(abs(v))} ponto{'s' if round(abs(v), 1) >= 2 else ''}"


def perguntas_hoje(series: dict, res: dict, bruto: dict | None) -> list[dict]:
    """As quatro perguntas de "E hoje?", com resposta curta e o dado que a sustenta.

    O tom (atencao, meio, calmo) segue o Resumo: atenção quando o dado sai da faixa normal da
    calibração para o lado que pressiona; sem faixa, quando passa dos 3 de cada 4 meses desde 2004.
    """
    hist = {k: mensal(series[k]) for k in ("desocupacao", "comprometimento_renda") if k in series}
    ind = {x["id"]: x for x in res["indicadores"]}
    ent = {x["id"]: x for x in (res.get("gar") or {}).get("entradas", [])}
    out = []

    def p(pergunta, resposta, tom, texto):
        out.append({"pergunta": pergunta, "resposta": resposta, "tom": tom, "texto": texto})

    # 1. A economia no limite: desemprego baixo (a padaria com o forno cheio).
    sahm = ind.get("sahm") or {}
    if sahm.get("nivel") is not None and hist.get("desocupacao"):
        d, h = sahm["nivel"], hist["desocupacao"]
        menor = min(h.values())
        cheio = percentil(h, d) <= 100 - CORTE
        t = (f"O desemprego está em {pct(d, 1)}%, perto do menor desde 2012 ({pct(menor, 1)}%)." if d - menor <= 0.5
             else f"O desemprego está em {pct(d, 1)}%. O menor desde 2012 foi {pct(menor, 1)}%.")
        devagar = "crescimento" in ent and "tendencia" in ent and ent["crescimento"]["valor"] < ent["tendencia"]["valor"]
        if "crescimento" in ent and "tendencia" in ent:
            c, m = ent["crescimento"]["valor"], ent["tendencia"]["valor"]
            t += (f" {'Mas a' if cheio and devagar else 'A'} economia cresce {pct(c, 1)}% em um ano, "
                  f"{'abaixo' if devagar else 'acima'} da média de 10 anos ({pct(m, 1)}%).")
        p("A economia está no limite?", ("Quase" if devagar else "Sim") if cheio else "Não",
          "atencao" if cheio and not devagar else "meio" if cheio else "calmo", t)

    # 2. O freio: juro descontada a inflação esperada, contra a faixa normal do Brasil.
    jr = ind.get("juro_real") or {}
    if jr.get("valor") is not None and jr.get("faixa_normal"):
        v, (lo, hi) = jr["valor"], jr["faixa_normal"]
        if v > hi:
            r, tom, onde = "Sim", "atencao", "Fica acima do normal"
        elif v >= lo + 0.75 * (hi - lo):
            r, tom, onde = "Quase", "meio", "Fica perto do teto do normal"
        elif v < lo:
            r, tom, onde = "Não", "calmo", "Fica abaixo do normal"
        else:
            r, tom, onde = "No normal", "calmo", "Fica dentro do normal"
        t = (f"Descontada a inflação esperada, o juro está em {pct(v, 1)}% ao ano. "
             f"{onde} no Brasil (de {pct(lo, 1)}% a {pct(hi, 1)}%).")
        if "juro" in ent and ent["juro"].get("nivel") is not None:
            t += f" A Selic está em {pct(ent['juro']['nivel'])}%, contra {pct(ent['juro']['antes'])}% um ano antes."
        p("O juro está freando a economia?", r, tom, t)

    # 3. A bola de neve: dívida contra um ano antes, e o que o governo gasta além do que arrecada, sem juros.
    dv = ind.get("divida") or {}
    if dv.get("valor") is not None and dv.get("nivel") is not None:
        v, n = dv["valor"], dv["nivel"]
        hi = (dv.get("faixa_normal") or [None, float("inf")])[1]
        r, tom = ("Sim", "atencao") if v > hi else ("Devagar", "meio") if v > 0 else ("Não", "calmo")
        t = (f"A dívida do governo está em {pct(n, 1)}% do PIB, {_pontos(v)} {'acima' if v > 0 else 'abaixo'} de um ano antes."
             if round(v, 1) != 0 else f"A dívida do governo está em {pct(n, 1)}% do PIB, igual a um ano antes.")
        prim = (bruto or {}).get("series", {}).get("primario_12m", {}).get("dados") or []
        if prim:
            z = prim[-1]["valor"]  # + é gastar mais do que arrecada
            t += (f" Sem contar os juros, o governo gasta {pct(z, 1)}% do PIB a mais do que arrecada." if z > 0 else
                  f" Sem contar os juros, o governo arrecada {pct(-z, 1)}% do PIB a mais do que gasta.")
        p("A dívida do governo está crescendo?", r, tom, t)

    # 4. As famílias: quanto da renda vai para parcelas e juros.
    cp = ind.get("comprometimento") or {}
    if cp.get("nivel") is not None and hist.get("comprometimento_renda"):
        n, h = cp["nivel"], hist["comprometimento_renda"]
        alto, recorde = percentil(h, n) > CORTE, n >= max(h.values())
        fim = (f", o maior desde {min(h)[:4]}." if recorde else
               f", mais do que em 3 de cada 4 meses desde {INICIO_HOJE[:4]}." if alto else ", dentro do normal.")
        p("As famílias estão apertadas?", "Sim" if alto else "Não", "atencao" if alto else "calmo",
          f"{pct(n, 1)}% da renda das famílias vai para parcelas e juros{fim}")
    return out


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
