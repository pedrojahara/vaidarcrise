"""O nível do dia.

O nível sai do cenário ruim do PIB dos próximos 12 meses (src/gar.py): o crescimento que tem
só 1 chance em 10 de ser pior, estimado num painel de 44 países a partir de quatro entradas do
Brasil. O cenário ruim de hoje é comparado ao de todos os meses desde 2004 (config/calibracao.json)
e vira um de cinco níveis, que só muda quando duas atualizações seguidas concordam.

Os nove indicadores do Resumo ficam ao lado, com a sua faixa normal, para contar a história de
cada fator; não entram no nível. As notícias também não.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import gar
import indicadores as ind

ROOT = Path(__file__).resolve().parent.parent
SITUACOES = {"pior": "Pior que o normal", "normal": "Normal", "melhor": "Melhor que o normal", "semdado": "Sem dado"}
ORDEM_SITUACAO = ["pior", "normal", "melhor", "semdado"]
# Cada entrada da conta, o fator a que pertence e o seu nome no site.
ENTRADAS = {
    "tendencia": {"fator": "atividade", "nome": "Crescimento médio em 10 anos", "unidade": "%"},
    "crescimento": {"fator": "atividade", "nome": "Crescimento em 12 meses", "unidade": "%"},
    "juro": {"fator": "juro", "nome": "Selic: variação em 12 meses", "unidade": "pontos"},
    "inflacao": {"fator": "juro", "nome": "Inflação: variação em 12 meses", "unidade": "pontos"},
}


def carregar_config() -> dict:
    return json.loads((ROOT / "config" / "modelo.json").read_text())


def carregar_calibracao() -> dict:
    return json.loads((ROOT / "config" / "calibracao.json").read_text())


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
    lo, hi = cal["faixa_normal"]
    ruim, bom = (x > hi, x < lo) if direcao > 0 else (x < lo, x > hi)
    return "pior" if ruim else "melhor" if bom else "normal"


def nivel_de(g: float, cortes: list[float]) -> int:
    """Índice do nível (0 = Muito abaixo, 4 = Muito acima): quanto pior o cenário ruim, mais alto."""
    return sum(1 for c in cortes if g <= c)


def confirmar(bruto: int, anterior: int | None, bruto_anterior: int | None) -> int:
    """O nível publicado muda só quando a conta de hoje repete a da atualização anterior."""
    if anterior is None or bruto == anterior or bruto == bruto_anterior:
        return bruto
    return anterior


# ------------------------------------------------------------------ entradas
def pib_trimestral(snap: dict) -> list[tuple[int, float]]:
    """PIB trimestral do IBGE: a cópia longa em data/historico/pib.json, atualizada pela coleta do dia."""
    base = json.loads((ROOT / "data" / "historico" / "pib.json").read_text())["pib"]
    qoq = {gar.tri_num(x["trimestre"]): x["var_qoq"] for x in base}
    qoq.update({gar.tri_num(x["trimestre"]): x["var_qoq"] for x in snap.get("pib") or []})
    return sorted(qoq.items())


def entradas(snap: dict) -> dict[str, dict]:
    """As quatro entradas de hoje, com a data de referência e o dado que explica cada uma."""
    e: dict[str, dict] = {}
    pib = pib_trimestral(snap)
    x = gar.tendencia(pib)
    if x is not None:
        e["tendencia"] = {"valor": x, "ref": gar.num_tri(pib[-1][0])}
    s = _serie(snap, "ibcbr")
    x = gar.crescimento(s)
    if x is not None:
        e["crescimento"] = {"valor": x, "ref": s[-1]["data"][:7]}
    s = _serie(snap, "selic_meta")
    x = gar.variacao_diaria(s)
    if x is not None:
        e["juro"] = {"valor": x, "ref": s[-1]["data"], "nivel": s[-1]["valor"], "antes": s[-1]["valor"] - x}
    s = _serie(snap, "ipca_12m")
    x = gar.variacao_mensal(s)
    if x is not None:
        e["inflacao"] = {"valor": x, "ref": s[-1]["data"][:7], "nivel": s[-1]["valor"], "antes": s[-1]["valor"] - x}
    return e


def idade_ok(ref: str, hoje: dt.date) -> bool:
    """Um valor guardado cobre falha de coleta até 10 dias (dado diário), 101 dias (mensal) ou 200 (trimestral)."""
    if "T" in ref:
        q, a = ref.split("T")
        ref, limite = f"{a}-{int(q) * 3:02d}-01", 200
    elif len(ref) == 10:
        limite = 10
    else:
        ref, limite = ref + "-01", 101
    return (hoje - dt.date.fromisoformat(ref)).days <= limite


def calcular(snap: dict, cfg: dict, cal: dict, anterior: int | None, guardados: dict | None = None,
             bruto_anterior: int | None = None, hoje: dt.date | None = None) -> dict:
    """O nível de hoje. `anterior` e `bruto_anterior` são o nível publicado e a conta da atualização
    do dia anterior. `guardados` traz os valores da rodada anterior (indicadores e entradas), usados
    quando a coleta de um deles falha."""
    hoje = hoje or dt.date.today()
    guardados = guardados or {}
    reaproveitados = []

    # 1. As entradas e o cenário ruim.
    ent = entradas(snap)
    for k in gar.ENTRADAS:
        x = guardados.get("entrada:" + k)
        if k not in ent and x and idade_ok(x["ref"], hoje):
            ent[k] = {**x, "reaproveitado": True}
            reaproveitados.append(k)
    falta = [k for k in gar.ENTRADAS if k not in ent]
    if falta:
        raise RuntimeError(f"sem dado para a conta do nível: {', '.join(falta)}")
    g = cal["gar"]
    coef, ref = g["coeficientes"], g["referencia"]
    valores_e = {k: ent[k]["valor"] for k in gar.ENTRADAS}
    ruim = gar.cenario(valores_e, coef)
    linhas_e = []
    for k in gar.ENTRADAS:
        meta = ENTRADAS[k]
        linhas_e.append({"id": k, **meta, **ent[k], "referencia": ref[k], "coef": coef[k],
                         "faixa_normal": g["faixas"][k]["faixa_normal"], "escala": g["faixas"][k]["escala"],
                         # Quanto a entrada de hoje, diferente da do Brasil típico, mexe no cenário ruim (pontos do PIB).
                         "efeito": coef[k] * (ent[k]["valor"] - ref[k])})

    niv = cfg["niveis"]
    cortes = g["cortes"]
    bruto = nivel_de(ruim, cortes)
    idx = confirmar(bruto, anterior, bruto_anterior)

    # O que mudaria o nível: o valor que cada entrada (com as outras paradas) precisaria ter para
    # levar o cenário ruim ao corte do nível vizinho. A tendência de 10 anos quase não se mexe e fica de fora.
    gatilhos = []
    for alvo, corte in ((bruto + 1, cortes[::-1][bruto] if bruto < 4 else None),
                        (bruto - 1, cortes[::-1][bruto - 1] if bruto > 0 else None)):
        if corte is None:
            continue
        for x in linhas_e:
            if x["id"] == "tendencia":
                continue
            novo = x["valor"] + (corte - ruim) / x["coef"]
            gatilhos.append({"id": x["id"], "nivel": alvo, "nome_nivel": niv["nomes"][alvo], "valor": novo,
                             "hoje": x["valor"]})

    # 2. Os indicadores do Resumo, com a faixa normal desde 2002.
    vals = valores(snap)
    for k, x in guardados.items():
        if not k.startswith("entrada:") and k not in vals and x.get("valor") is not None:
            vals[k] = {**x, "reaproveitado": True}
            reaproveitados.append(k)
    linhas = []
    for k, meta in cfg["indicadores"].items():
        c = cal["indicadores"].get(k, {})
        x = vals.get(k)
        linha = {"id": k, "fator": meta["fator"], "nome": meta["nome"], "unidade": meta["unidade"],
                 "definicao": meta["definicao"], "direcao": meta["direcao"],
                 "faixa_normal": c.get("faixa_normal"), "escala": c.get("escala")}
        if x is None or not c.get("faixa_normal"):
            linha.update({"valor": None, "situacao": "semdado"})
        else:
            linha.update({**x, "situacao": situacao(x["valor"], c, meta["direcao"])})
        linhas.append(linha)

    fatores = []
    for fid, nome in cfg["fatores"].items():
        mine = [x for x in linhas if x["fator"] == fid]
        das_entradas = [x for x in linhas_e if x["fator"] == fid]
        sit = min((x["situacao"] for x in mine), key=ORDEM_SITUACAO.index) if mine else "semdado"
        fatores.append({"id": fid, "nome": nome, "indicadores": [x["id"] for x in mine],
                        "entradas": [x["id"] for x in das_entradas], "na_conta": bool(das_entradas),
                        "efeito": sum(x["efeito"] for x in das_entradas) if das_entradas else None,
                        "situacao": sit, "situacao_nome": SITUACOES[sit]})
    # Primeiro os fatores da conta, do que mais piora ao que mais alivia; depois os outros.
    fatores.sort(key=lambda f: (not f["na_conta"], f["efeito"] if f["na_conta"] else 0,
                                ORDEM_SITUACAO.index(f["situacao"])))
    return {"nivel": {"indice": idx, "nome": niv["nomes"][idx], "anterior": anterior,
                      "bruto": bruto, "nome_bruto": niv["nomes"][bruto]},
            "gar": {"entradas": linhas_e, "ruim": ruim, "cenario_ruim": gar.pct(ruim + g["ajuste"]),
                    "cenario_normal": gar.pct(g["normal"] + g["ajuste"]), "cortes": cortes,
                    "ref_pib": ent["tendencia"]["ref"]},
            "indicadores": linhas, "fatores": fatores, "gatilhos": gatilhos,
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
