"""O nível do dia.

Nove indicadores, cada um com o seu limite de alerta estimado na história desde 2002
(src/calibra.py, config/calibracao.json). Os que passam do limite entram num composto;
o composto vira uma chance de recessão à frente relativa à média da história; e essa
razão vira um de cinco níveis, que só muda quando duas atualizações seguidas concordam. As notícias não
entram aqui.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import indicadores as ind

ROOT = Path(__file__).resolve().parent.parent
SITUACOES = {"alerta": "Zona de alerta", "pior": "Pior que o normal", "normal": "Normal",
             "melhor": "Melhor que o normal", "semdado": "Sem dado"}
ORDEM_SITUACAO = ["alerta", "pior", "normal", "melhor", "semdado"]


def carregar_config() -> dict:
    return json.loads((ROOT / "config" / "modelo.json").read_text())


def carregar_calibracao() -> dict:
    return json.loads((ROOT / "config" / "calibracao.json").read_text())


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def sigm(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def _serie(snap: dict, key: str) -> list[dict]:
    return snap["series"].get(key, {}).get("dados", [])


def _focus_anos(snap: dict) -> tuple[float, float, str] | None:
    linhas = snap.get("focus", {}).get("PIB Total") or []
    if not linhas:
        return None
    data = linhas[0]["Data"]
    ano = int(data[:4])
    por_ano = {str(x["DataReferencia"]): float(x["Mediana"]) for x in linhas}
    if str(ano) in por_ano and str(ano + 1) in por_ano:
        return por_ano[str(ano)], por_ano[str(ano + 1)], data
    return None


def valores(snap: dict) -> dict[str, dict]:
    """O valor de cada indicador hoje, com a data de referência e o dado bruto que o explica."""
    v: dict[str, dict] = {}
    s = _serie(snap, "ibcbr")
    x = ind.ibcbr(s)
    if x is not None:
        v["ibcbr"] = {"valor": x, "ref": s[-1]["data"][:7]}
    f = _focus_anos(snap)
    if f:
        v["focus_pib"] = {"valor": ind.focus_pib(*f), "ref": f[2], "ano": f[0], "ano_seguinte": f[1]}
    selic, ipca = _serie(snap, "selic_meta"), snap.get("focus", {}).get("IPCA 12m")
    if selic and ipca:
        v["juro_real"] = {"valor": ind.juro_real(selic[-1]["valor"], float(ipca["Mediana"])), "ref": selic[-1]["data"],
                          "selic": selic[-1]["valor"], "inflacao_esperada": float(ipca["Mediana"]), "focus_data": ipca["Data"]}
    s = _serie(snap, "comprometimento_renda")
    x = ind.comprometimento(s)
    if x is not None:
        v["comprometimento"] = {"valor": x, "ref": s[-1]["data"][:7], "nivel": s[-1]["valor"]}
    s = _serie(snap, "juro_real_longo")
    t = ind.tesouro(s)
    if t:
        v["tesouro"] = {"valor": t[0], "ref": s[-1]["data"], "nivel": s[-1]["valor"], "mediana": t[1],
                        "vencimento": s[-1].get("vencimento")}
    s = _serie(snap, "dolar_ptax")
    x = ind.dolar(s)
    if x is not None:
        v["dolar"] = {"valor": x, "ref": s[-1]["data"], "nivel": s[-1]["valor"]}
    s = _serie(snap, "divida_bruta")
    x = ind.divida(s)
    if x is not None:
        v["divida"] = {"valor": x, "ref": s[-1]["data"][:7], "nivel": s[-1]["valor"]}
    s = _serie(snap, "desocupacao")
    x = ind.sahm(s)
    if x is not None:
        v["sahm"] = {"valor": x, "ref": s[-1]["data"][:7], "nivel": s[-1]["valor"]}
    s = _serie(snap, "commodities")
    x = ind.commodities(s)
    if x is not None:
        v["commodities"] = {"valor": x, "ref": s[-1]["data"][:7], "nivel": s[-1]["valor"]}
    return v


def situacao(x: float, cal: dict, direcao: int) -> str:
    if cal.get("peso") and cal.get("limite") is not None:
        if (direcao > 0 and x >= cal["limite"]) or (direcao < 0 and x <= cal["limite"]):
            return "alerta"
    lo, hi = cal["faixa_normal"]
    ruim, bom = (x > hi, x < lo) if direcao > 0 else (x < lo, x > hi)
    return "pior" if ruim else "melhor" if bom else "normal"


def nivel_de(r: float, cortes: list[float]) -> int:
    """Índice do nível pela razão (0 = Muito abaixo, 4 = Muito acima)."""
    return sum(1 for c in cortes if r >= c)


def confirmar(bruto: int, anterior: int | None, bruto_anterior: int | None) -> int:
    """O nível publicado muda só quando a conta de hoje repete a da atualização anterior."""
    if anterior is None or bruto == anterior or bruto == bruto_anterior:
        return bruto
    return anterior


def peso_rotulo(share: float, cfg: dict) -> str:
    c = cfg["peso_hoje"]
    if share >= c["forte"]:
        return "Forte"
    if share >= c["moderado"]:
        return "Moderado"
    return "Pequeno" if share > 0 else "Nenhum hoje"


def forca_rotulo(cal: dict, cfg: dict) -> str:
    if not cal.get("peso"):
        return "Não antecipou recessões"
    c = cfg["forca_historica"]
    return "Forte" if cal["nsr"] < c["forte"] else "Moderada" if cal["nsr"] < c["moderada"] else "Fraca"


def calcular(snap: dict, cfg: dict, cal: dict, anterior: int | None, guardados: dict | None = None,
             bruto_anterior: int | None = None) -> dict:
    """O nível de hoje. `anterior` e `bruto_anterior` são o nível publicado e a conta da atualização
    do dia anterior. `guardados` traz os valores da rodada anterior, usados quando a coleta de um
    indicador falha (no máximo 10 dias de idade para os diários e 70 para os mensais)."""
    vals = valores(snap)
    reaproveitados = []
    for k, x in (guardados or {}).items():
        if k not in vals and x.get("valor") is not None:
            vals[k] = {**x, "reaproveitado": True}
            reaproveitados.append(k)
    linhas = []
    for k, meta in cfg["indicadores"].items():
        c = cal["indicadores"].get(k, {})
        x = vals.get(k)
        linha = {"id": k, "fator": meta["fator"], "nome": meta["nome"], "unidade": meta["unidade"],
                 "definicao": meta["definicao"], "direcao": meta["direcao"], "peso": c.get("peso", 0.0),
                 "limite": c.get("limite"), "faixa_normal": c.get("faixa_normal"), "escala": c.get("escala"),
                 "nsr": c.get("nsr"), "episodios_avisados": c.get("episodios_avisados"),
                 "episodios_na_amostra": c.get("episodios_na_amostra"), "motivo": c.get("motivo"),
                 "forca": forca_rotulo(c, cfg) if c else "Sem dado"}
        if x is None or not c.get("faixa_normal"):
            linha.update({"valor": None, "sinal": 0, "situacao": "semdado"})
        else:
            sit = situacao(x["valor"], c, meta["direcao"])
            linha.update({**x, "sinal": int(sit == "alerta"), "situacao": sit})
        linhas.append(linha)

    com_dado = [x for x in linhas if x["peso"] > 0 and x["valor"] is not None]
    den = sum(x["peso"] for x in com_dado)
    comp = sum(x["peso"] * x["sinal"] for x in com_dado) / den if den else 0.0
    for x in linhas:
        x["parte"] = x["peso"] * x["sinal"] / den if den and x["valor"] is not None else 0.0
    a, b = cal["regressao"]["a"], cal["regressao"]["b"]
    pbar, k = cal["media"], cal["k"]

    def razao_de(c: float) -> float:
        return sigm(logit(pbar) + k * (a + b * c - logit(pbar))) / pbar

    razao = razao_de(comp)
    niv = cfg["niveis"]
    bruto = nivel_de(razao, niv["cortes_razao"])
    idx = confirmar(bruto, anterior, bruto_anterior)
    # O que mudaria o nível sozinho: cada indicador fora do alerta que, se passasse do limite,
    # levaria a conta a outro nível.
    gatilhos = []
    for x in com_dado:
        if x["sinal"]:
            continue
        novo = nivel_de(razao_de(comp + x["peso"] / den), niv["cortes_razao"])
        if novo != bruto:
            gatilhos.append({"id": x["id"], "limite": x["limite"], "nivel": novo, "nome_nivel": niv["nomes"][novo]})

    fatores = []
    for fid, nome in cfg["fatores"].items():
        mine = [x for x in linhas if x["fator"] == fid]
        share = sum(x["parte"] for x in mine)
        sit = min((x["situacao"] for x in mine), key=ORDEM_SITUACAO.index)
        com_peso = [x for x in mine if x["peso"] > 0]
        melhor = min(com_peso, key=lambda x: x["nsr"]) if com_peso else None
        fatores.append({"id": fid, "nome": nome, "indicadores": [x["id"] for x in mine], "parte": share,
                        "peso_rotulo": peso_rotulo(share, cfg), "situacao": sit, "situacao_nome": SITUACOES[sit],
                        "forca": melhor["forca"] if melhor else "Não antecipou recessões",
                        "avisou": [melhor["episodios_avisados"], melhor["episodios_na_amostra"]] if melhor else None})
    fatores.sort(key=lambda f: (-f["parte"], ORDEM_SITUACAO.index(f["situacao"])))
    return {"nivel": {"indice": idx, "nome": niv["nomes"][idx], "anterior": anterior,
                      "bruto": bruto, "nome_bruto": niv["nomes"][bruto]},
            "composto": comp, "chance_relativa": razao, "indicadores": linhas, "fatores": fatores, "gatilhos": gatilhos,
            "reaproveitados": reaproveitados, "faltando": [x["id"] for x in linhas if x["valor"] is None]}


# ------------------------------------------------------------------ notícias
def peso_estagio(ev: dict, cfg: dict) -> float:
    pesos = cfg["noticias"]["peso_por_estagio"]
    est = ev.get("estagio")
    if est not in pesos:
        return 1.0
    if pesos[est] == "chance_aprovacao":
        lo, hi = cfg["noticias"]["faixa_chance_aprovacao"]
        ch = ev.get("chance_aprovacao")
        return min(hi, max(lo, ch if ch is not None else (lo + hi) / 2))
    return float(pesos[est])


def efeito(ev: dict, cfg: dict) -> float:
    """Pontos de uma notícia: tamanho × estágio, metade se um jornal só, metade se o mercado já esperava."""
    c = cfg["noticias"]
    e = c["pontos_por_magnitude"][str(ev["magnitude"])] * peso_estagio(ev, cfg)
    if len(ev.get("veiculos", [])) < 2:
        e *= c["fator_fonte_unica"]
    if ev.get("ja_no_preco"):
        e *= c["fator_ja_no_preco"]
    return ev["direcao"] * e


def pressao(eventos: list[dict], cfg: dict) -> dict:
    """Para que lado as notícias do dia empurram, fator a fator. Em cada fator e lado, a notícia mais
    forte conta inteira, a segunda metade, a terceira um quarto: dez manchetes do mesmo aperto não
    valem dez vezes uma."""
    c = cfg["noticias"]

    def lado(vals: list[float]) -> float:
        return sum(v * c["retorno"] ** i for i, v in enumerate(sorted(vals, reverse=True)))

    def sentido(x: float, corte: float) -> str:
        return "piora" if x >= corte else "melhora" if x <= -corte else "igual"

    por_fator: dict[str, list[tuple[float, str]]] = {}
    for ev in eventos:
        por_fator.setdefault(ev["fator"], []).append((efeito(ev, cfg), ev["id"]))
    fatores = {}
    for fid, lst in por_fator.items():
        saldo = lado([e for e, _ in lst if e > 0]) - lado([-e for e, _ in lst if e < 0])
        fatores[fid] = {"saldo": saldo, "sentido": sentido(saldo, c["corte_fator"]),
                        "eventos": [i for _, i in sorted(lst, key=lambda t: -abs(t[0]))]}
    total = sum(f["saldo"] for f in fatores.values())
    return {"fatores": fatores, "saldo": total, "sentido": sentido(total, c["corte_geral"]), "n": len(eventos)}
