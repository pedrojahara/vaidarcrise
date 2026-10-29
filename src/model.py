"""O modelo: camadas somadas em log-odds.

1. Taxa-base: risco histórico de uma recessão começar num trimestre (h0).
2. Indicadores: sinais com pesos publicados (inclusive o juro real longo do
   Tesouro) que deslocam o risco dos próximos trimestres.
3. Notícias: eventos classificados pelo LLM, cada um com teto e prazo de validade.
   Desde a v1.3 ficam fora do número (`noticias.entram_na_conta`) e viram a
   pressão por tema.

As camadas 2 e 3 valem por inteiro nos 4 primeiros trimestres ainda não
divulgados e somem até o 7º; daí em diante só vale a taxa-base. A manchete é a
chance de pelo menos um início de recessão dentro da janela. A taxa-base vem de
src/taxa_base.py e fica congelada em config/modelo.json a cada versão.
"""
from __future__ import annotations

import datetime as dt
import itertools
import json
import math
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent.parent


def carregar_config() -> dict:
    return json.loads((ROOT / "config" / "modelo.json").read_text())


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def sigm(x: float) -> float:
    return 1 / (1 + math.exp(-x))


# ---------------------------------------------------------------- trimestres
def tri(label: str) -> tuple[int, int]:
    q, a = label.split("T")
    return 2000 + int(a), int(q)


def label(ano: int, q: int) -> str:
    return f"{q}T{str(ano)[2:]}"


def prox(ano: int, q: int) -> tuple[int, int]:
    return (ano + 1, 1) if q == 4 else (ano, q + 1)


def trimestres(de: str, ate: str) -> list[str]:
    a, b = tri(de), tri(ate)
    out = []
    while a <= b:
        out.append(label(*a))
        a = prox(*a)
    return out


def estrutura(pib: list[dict], cfg: dict) -> dict:
    """Onde estamos na janela, dado o que o IBGE já divulgou."""
    janela = trimestres(cfg["janela"]["primeiro_trimestre"], cfg["janela"]["ultimo_trimestre"])
    publicados = {p["trimestre"]: p["var_qoq"] for p in pib}
    na_janela = [(t, publicados[t]) for t in janela if t in publicados]
    resolvido = any(a[1] < 0 and b[1] < 0 for a, b in zip(na_janela, na_janela[1:]))
    pendente = bool(na_janela) and na_janela[-1][1] < 0
    restantes = [t for t in janela if t not in publicados]
    # Um início de recessão no trimestre t precisa de t e t+1 dentro da janela.
    inicios = restantes[:-1] if restantes else []
    return {"janela": janela, "publicados_na_janela": na_janela, "resolvido": resolvido,
            "pendente_negativo": pendente, "inicios": inicios,
            "ultimo_publicado": pib[-1]["trimestre"] if pib else None}


def caminho(estr: dict, desloc: float, h0: float, cfg: dict) -> list[float]:
    """Risco de início de recessão em cada trimestre ainda aberto."""
    pesos = cfg["pesos_no_tempo"]
    return [sigm(logit(h0) + (pesos[i] if i < len(pesos) else 0.0) * desloc) for i in range(len(estr["inicios"]))]


def prob(estr: dict, desloc: float, h0: float, cfg: dict, horizonte: int | None = None) -> float:
    if estr["resolvido"]:
        return 1.0
    sobrevive = 1.0
    if estr["pendente_negativo"]:
        sobrevive *= 1 - sigm(logit(cfg["continuacao_apos_trimestre_negativo"]) + desloc)
    hs = caminho(estr, desloc, h0, cfg)
    if horizonte is not None:
        hs = hs[:horizonte]
    for h in hs:
        sobrevive *= 1 - h
    return 1 - sobrevive


# --------------------------------------------------------------- indicadores
def _br(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _serie(snap: dict, key: str) -> list[dict]:
    return snap["series"].get(key, {}).get("dados", [])


def valores_indicadores(snap: dict) -> dict:
    v: dict = {}
    ibc = _serie(snap, "ibcbr")
    if len(ibc) >= 6:
        a, b = mean(x["valor"] for x in ibc[-3:]), mean(x["valor"] for x in ibc[-6:-3])
        v["atividade"] = {"valor": 100 * (a / b - 1), "ref": ibc[-1]["data"][:7]}
    des = _serie(snap, "desocupacao")
    if len(des) >= 15:
        m3 = [mean(x["valor"] for x in des[i - 2:i + 1]) for i in range(2, len(des))]
        v["trabalho"] = {"valor": m3[-1] - min(m3[-13:-1]), "ref": des[-1]["data"][:7]}
    selic, ipca = _serie(snap, "selic_meta"), snap.get("focus", {}).get("IPCA 12m")
    if selic and ipca:
        s, e = selic[-1]["valor"], float(ipca["Mediana"])
        v["juro_real"] = {"valor": 100 * ((1 + s / 100) / (1 + e / 100) - 1), "ref": selic[-1]["data"],
                          "detalhe": f"Selic de {_br(s)}% e inflação esperada de {_br(e)}% (Focus de {ipca['Data'][8:10]}/{ipca['Data'][5:7]})"}
    cr = _serie(snap, "comprometimento_renda")
    if len(cr) >= 24:
        base = cr[-37:-1] if len(cr) >= 37 else cr[:-1]
        v["familias"] = {"valor": cr[-1]["valor"] - mean(x["valor"] for x in base), "ref": cr[-1]["data"][:7],
                         "detalhe": f"{_br(cr[-1]['valor'], 1)}% da renda"}
    db = _serie(snap, "divida_bruta")
    if len(db) >= 13:
        v["fiscal"] = {"valor": db[-1]["valor"] - db[-13]["valor"], "ref": db[-1]["data"][:7],
                       "detalhe": f"{_br(db[-1]['valor'], 1)}% do PIB"}
    m = valor_mercado(_serie(snap, "juro_real_longo"))
    if m:
        v["mercado"] = m
    fx = _serie(snap, "dolar_ptax")
    if len(fx) >= 64:
        v["cambio"] = {"valor": 100 * (fx[-1]["valor"] / fx[-64]["valor"] - 1), "ref": fx[-1]["data"],
                       "detalhe": f"R$ {_br(fx[-1]['valor'])}"}
    return v


def valor_mercado(dados: list[dict], antes_de: str | None = None) -> dict | None:
    """Juro real longo (v1.3): a taxa do Tesouro IPCA+ de cerca de 10 anos menos a sua mediana nos 3 anos anteriores.

    É o indicador que reage no mesmo dia a um choque de confiança. `antes_de` refaz o valor
    que valia numa data passada (só com o que já era conhecido nela), para comparar rodadas.
    """
    if antes_de:
        dados = [x for x in dados if x["data"] < antes_de]
    if not dados:
        return None
    ult = dados[-1]
    ini = (dt.date.fromisoformat(ult["data"]) - dt.timedelta(days=3 * 365)).isoformat()
    janela = [x["valor"] for x in dados[:-1] if x["data"] >= ini]
    if len(janela) < 250:
        return None
    med = median(janela)
    return {"valor": ult["valor"] - med, "ref": ult["data"],
            "detalhe": f"taxa de {_br(ult['valor'])}% ao ano acima da inflação, contra a mediana de {_br(med)}% "
                       f"nos 3 anos anteriores (Tesouro IPCA+ {ult['vencimento'][:4]})"}


def contribuicoes_indicadores(vals: dict, cfg: dict) -> list[dict]:
    out = []
    for key, p in cfg["indicadores"].items():
        if key not in vals:
            continue
        bruto = p["inclinacao"] * (vals[key]["valor"] - p["neutro"])
        bruto = max(p["min"], min(p["max"], bruto))
        out.append({"id": key, "nome": p["nome"], "unidade": p["unidade"], "definicao": p["definicao"],
                    **vals[key], "bruto": bruto, "logit": bruto * cfg["encolhimento_indicadores"]})
    total = sum(x["logit"] for x in out)
    teto = cfg["teto_indicadores_logit"]
    if abs(total) > teto:
        for x in out:
            x["logit"] *= teto / abs(total)
    return out


# ------------------------------------------------------------------ notícias
def efeito_evento(ev: dict, hoje: dt.date, cfg: dict) -> float:
    c = cfg["noticias"]
    idade = (hoje - dt.date.fromisoformat(ev["data"])).days
    if idade < 0 or idade >= c["dias_de_decaimento"]:
        return 0.0
    return ev["efeito_inicial"] * (1 - idade / c["dias_de_decaimento"])


def peso_estagio(ev: dict, cfg: dict) -> float:
    """Quanto do efeito vale, conforme o pé em que o fato está (v1.2). Eventos sem estágio valem inteiros."""
    pesos = cfg["noticias"].get("peso_por_estagio")
    est = ev.get("estagio")
    if not pesos or est not in pesos:
        return 1.0
    if pesos[est] == "chance_aprovacao":
        lo, hi = cfg["noticias"]["faixa_chance_aprovacao"]
        ch = ev.get("chance_aprovacao")
        return min(hi, max(lo, ch if ch is not None else (lo + hi) / 2))
    return float(pesos[est])


def efeito_inicial(ev: dict, n_veiculos: int, cfg: dict) -> float:
    c = cfg["noticias"]
    e = c["efeito_por_magnitude_logit"][str(ev["magnitude"])]
    if ev["ja_no_preco"]:
        e *= c["fator_ja_no_preco"]
    if n_veiculos < 2:
        e *= c["fator_fonte_unica"]
    e *= peso_estagio(ev, cfg)
    return ev["direcao"] * min(e, c["teto_por_evento_logit"])


def pressao_por_tema(eventos: list[dict], hoje: dt.date, cfg: dict) -> dict:
    """v1.3: as notícias não mexem no número; cada tema mostra para que lado elas empurram.

    Em cada tema, conta o evento mais forte de cada sentido, metade do segundo, um quarto do
    terceiro e assim por diante: dez manchetes sobre o mesmo aperto não valem dez vezes uma.
    O efeito de cada evento já vem com o peso do estágio e perde força em linha reta até
    sumir. A seta do tema só sai de "sem pressão clara" quando o saldo passa do corte.
    """
    p = cfg["noticias"]["pressao"]

    def lado(vals: list[float]) -> float:
        return sum(v * p["fator_retorno"] ** i for i, v in enumerate(sorted(vals, reverse=True)))

    def sentido(x: float, corte: float) -> str:
        return "sobe" if x >= corte else "desce" if x <= -corte else "igual"

    por_canal: dict[str, list[tuple[float, str]]] = {}
    for ev in eventos:
        e = efeito_evento(ev, hoje, cfg)
        if e:
            por_canal.setdefault(ev["canal"], []).append((e, ev["id"]))
    temas = {}
    for canal, lst in por_canal.items():
        saldo = lado([e for e, _ in lst if e > 0]) - lado([-e for e, _ in lst if e < 0])
        temas[canal] = {"saldo": saldo, "sentido": sentido(saldo, p["corte_tema"]),
                        "eventos": [i for _, i in sorted(lst, key=lambda t: -abs(t[0]))]}
    total = sum(t["saldo"] for t in temas.values())
    return {"temas": temas, "saldo": total, "sentido": sentido(total, p["corte_geral"])}


def contribuicoes_noticias(eventos: list[dict], hoje: dt.date, cfg: dict) -> list[dict]:
    out = []
    for ev in eventos:
        e = efeito_evento(ev, hoje, cfg)
        if e != 0:
            out.append({**ev, "logit": e})
    total = sum(x["logit"] for x in out)
    teto = cfg["noticias"]["teto_total_logit"]
    if abs(total) > teto:
        for x in out:
            x["logit"] *= teto / abs(total)
    return out


# ------------------------------------------------------------------- Shapley
def shapley(jogadores: list[str], f) -> dict[str, float]:
    """Valores de Shapley exatos. f recebe um frozenset de jogadores ativos."""
    n = len(jogadores)
    cache: dict[frozenset, float] = {}

    def v(s: frozenset) -> float:
        if s not in cache:
            cache[s] = f(s)
        return cache[s]

    fat = [math.factorial(k) for k in range(n + 1)]
    out = {}
    for j in jogadores:
        outros = [x for x in jogadores if x != j]
        tot = 0.0
        for k in range(n):
            w = fat[k] * fat[n - k - 1] / fat[n]
            for comb in itertools.combinations(outros, k):
                s = frozenset(comb)
                tot += w * (v(s | {j}) - v(s))
        out[j] = tot
    return out


def agrupar(contrib: dict[str, float], maximo: int, nome_resto: str) -> tuple[dict[str, float], set[str]]:
    """Mantém os `maximo` maiores jogadores e junta o resto num só."""
    if len(contrib) <= maximo:
        return contrib, set()
    ordem = sorted(contrib, key=lambda k: abs(contrib[k]), reverse=True)
    manter, resto = ordem[:maximo - 1], ordem[maximo - 1:]
    novo = {k: contrib[k] for k in manter}
    novo[nome_resto] = sum(contrib[k] for k in resto)
    return novo, set(resto)


# --------------------------------------------------------------------- nota
def calcular(snap: dict, eventos: list[dict], hoje: dt.date, cfg: dict) -> dict:
    estr = estrutura(snap.get("pib", []), cfg)
    h0 = cfg["taxa_base"]["risco_trimestral"]
    ind = contribuicoes_indicadores(valores_indicadores(snap), cfg)
    # Desde a v1.3 as notícias não entram no número: viram pressão por tema, mostrada à parte.
    nots = contribuicoes_noticias(eventos, hoje, cfg) if cfg["noticias"].get("entram_na_conta", True) else []
    s_ind = sum(x["logit"] for x in ind)
    s_not = sum(x["logit"] for x in nots)
    desloc = s_ind + s_not

    manchete = prob(estr, desloc, h0, cfg)
    curto = prob(estr, desloc, h0, cfg, horizonte=4)
    estr_base = estrutura([], cfg)
    base_pura = prob(estr_base, 0.0, h0, cfg)
    alternativas = [{**a, "manchete_sem_ajustes": prob(estr, 0.0, a["risco_trimestral"], cfg),
                     "manchete": prob(estr, desloc, a["risco_trimestral"], cfg)}
                    for a in cfg["taxa_base"]["alternativas"]]

    # Por que a nota é essa: Shapley da taxa-base até a nota, em pontos.
    partes = {f"ind:{x['id']}": x["logit"] for x in ind}
    partes.update({f"not:{x['id']}": x["logit"] for x in nots})
    partes, agrupados = agrupar(partes, 12, "not:outras")
    jog = list(partes)
    if estr["inicios"] != estr_base["inicios"] or estr["pendente_negativo"]:
        jog.append("calendario")

    def f(s: frozenset) -> float:
        e = estr if "calendario" in s else estr_base
        return 100 * prob(e, sum(partes[k] for k in s if k != "calendario"), h0, cfg)

    sh = shapley(jog, f) if jog else {}
    sem = {x["id"]: 100 * prob(estr, desloc - x["logit"], h0, cfg) for x in nots}

    faixa = cfg["taxa_base"].get("faixa")
    res = {
        "estrutura": estr, "h0": h0, "deslocamento_logit": desloc,
        "indicadores_logit": s_ind, "noticias_logit": s_not,
        "manchete": manchete, "curto_prazo_4t": curto, "taxa_base_manchete": base_pura,
        "taxa_base_4t": prob(estr_base, 0.0, h0, cfg, horizonte=4),
        "taxa_base_faixa": [prob(estr_base, 0.0, faixa[k], cfg) for k in ("min", "max")] if faixa else None,
        "alternativas": alternativas,
        "risco_trimestral": [{"trimestre": t, "risco": h} for t, h in zip(estr["inicios"], caminho(estr, desloc, h0, cfg))],
        "indicadores": ind, "noticias": nots, "agrupados": sorted(agrupados),
        "shapley_desde_base": sh, "contrafactual_sem_evento": sem,
    }
    if "pressao" in cfg["noticias"]:
        res["pressao"] = pressao_por_tema(eventos, hoje, cfg)
    res["por_horizonte"] = por_horizonte(res, cfg)
    res["shapley_perto"] = decompor_perto(res, cfg)
    return res


def refazer(ant_res: dict, ant_pib: list, cfg: dict, mercado: dict | None) -> dict:
    """Uma rodada antiga refeita com a regra de hoje: os mesmos valores dos indicadores, o indicador
    de mercado daquela data, a taxa-base atual e as notícias só se a regra atual as conta.

    Serve para a seta e para "Nova metodologia" medirem só a troca de regra, e não confundirem
    a troca com melhora ou piora dos dados.
    """
    vals = {x["id"]: {k: x[k] for k in ("valor", "ref", "detalhe") if k in x} for x in ant_res["indicadores"]}
    if mercado and "mercado" not in vals:
        vals["mercado"] = mercado
    ind = contribuicoes_indicadores(vals, cfg)
    nots = ant_res["noticias"] if cfg["noticias"].get("entram_na_conta", True) else []
    desloc = sum(x["logit"] for x in ind) + sum(x["logit"] for x in nots)
    estr, estr_base = estrutura(ant_pib, cfg), estrutura([], cfg)
    h0 = cfg["taxa_base"]["risco_trimestral"]
    return {"indicadores": ind, "noticias": nots, "deslocamento_logit": desloc,
            "curto_prazo_4t": prob(estr, desloc, h0, cfg, horizonte=4), "manchete": prob(estr, desloc, h0, cfg),
            "taxa_base_4t": prob(estr_base, 0.0, h0, cfg, horizonte=4)}


def _n_perto(cfg: dict) -> int:
    return sum(1 for w in cfg["pesos_no_tempo"] if w > 0)


def decompor_perto(res: dict, cfg: dict) -> dict[str, float]:
    """Shapley da parcela de dados e notícias da nota por horizonte, em pontos.

    Reparte a diferença entre `perto` e `perto_base`: os fatores somam exatamente essa
    parcela. Usa o h0 da rodada, para dias antigos renderizarem com a regra em que foram
    calculados.
    """
    estr, h0 = res["estrutura"], res["h0"]
    n = _n_perto(cfg)
    partes = {f"ind:{x['id']}": x["logit"] for x in res["indicadores"]}
    partes.update({f"not:{x['id']}": x["logit"] for x in res["noticias"]})
    partes, _ = agrupar(partes, 12, "not:outras")
    return shapley(list(partes), lambda s: 100 * prob(estr, sum(partes[k] for k in s), h0, cfg, horizonte=n)) if partes else {}


def decompor_12m(res: dict, cfg: dict) -> dict[str, float]:
    """Shapley da chance de recessão nos próximos 4 trimestres, do normal até a de hoje, em pontos.

    O normal é a taxa-base de 4 trimestres, sem nenhum PIB divulgado na janela. Os fatores
    (indicadores, notícias e, quando muda a conta, os trimestres já divulgados) somam
    exatamente a diferença entre a chance de hoje e o normal.
    """
    estr, h0 = res["estrutura"], res["h0"]
    estr_base = estrutura([], cfg)
    partes = {f"ind:{x['id']}": x["logit"] for x in res["indicadores"]}
    partes.update({f"not:{x['id']}": x["logit"] for x in res["noticias"]})
    partes, _ = agrupar(partes, 12, "not:outras")
    jog = list(partes)
    if estr["inicios"][:4] != estr_base["inicios"][:4] or estr["pendente_negativo"]:
        jog.append("calendario")

    def f(s: frozenset) -> float:
        e = estr if "calendario" in s else estr_base
        return 100 * prob(e, sum(partes[k] for k in s if k != "calendario"), h0, cfg, horizonte=4)

    return shapley(jog, f) if jog else {}


def por_horizonte(res: dict, cfg: dict) -> dict:
    """A nota em dois pedaços que o leitor consegue conferir.

    `perto` é a chance de a recessão começar nos trimestres em que dados e notícias pesam;
    `depois` é o que o resto da janela acrescenta, só com a taxa-base. Como a pergunta é
    "pelo menos uma recessão", uma recessão provável mais cedo toma o lugar de uma que
    viria depois: por isso `depois` encolhe quando `perto` cresce.
    """
    estr, h0, desloc = res["estrutura"], res["h0"], res["deslocamento_logit"]
    n = _n_perto(cfg)
    tris = estr["inicios"][:n]
    perto = prob(estr, desloc, h0, cfg, horizonte=n)
    return {"ate": tris[-1] if tris else None, "n": len(tris), "perto": perto,
            "perto_base": prob(estr, 0.0, h0, cfg, horizonte=n), "depois": res["manchete"] - perto}


def cenarios_pib(snap: dict, res: dict, cfg: dict) -> list[dict]:
    """Próximo gatilho: o que acontece com a nota quando o IBGE divulgar o próximo trimestre."""
    estr = res["estrutura"]
    if estr["resolvido"] or not estr["inicios"]:
        return []
    alvo = estr["inicios"][0]
    pib = list(snap.get("pib", []))
    out = []
    for nome, val in (("negativo", -0.1), ("zero ou positivo", 0.1)):
        e = estrutura(pib + [{"trimestre": alvo, "var_qoq": val}], cfg)
        out.append({"trimestre": alvo, "cenario": nome,
                    "manchete": prob(e, res["deslocamento_logit"], res["h0"], cfg),
                    "curto_prazo_4t": prob(e, res["deslocamento_logit"], res["h0"], cfg, horizonte=4)})
    return out


def decompor_variacao(ant: dict, atual: dict, snap_ant_pib: list, snap_pib: list, cfg: dict,
                      novos: frozenset[str] = frozenset(), horizonte: int | None = None,
                      ant_refeito: dict | None = None) -> dict:
    """Shapley da variação entre duas atualizações: cada indicador, cada notícia nova e o calendário.

    As notícias que já valiam antes só perdem força com o tempo; elas entram juntas,
    como "not:antigas", para o post do dia mostrar cada fato novo pelo nome. Com
    horizonte=4, decompõe a chance dos próximos 4 trimestres (a do topo do site) em vez
    da nota até 2030.
    """
    chave = "curto_prazo_4t" if horizonte == 4 else "manchete"
    h0 = cfg["taxa_base"]["risco_trimestral"]
    e_ant, e_at = estrutura(snap_ant_pib, cfg), estrutura(snap_pib, cfg)
    # Numa troca de regra, o ponto de partida é a rodada anterior refeita com a regra nova.
    base = ant_refeito or ant
    old = {f"ind:{x['id']}": x["logit"] for x in base["indicadores"]}
    old.update({f"not:{x['id']}": x["logit"] for x in base["noticias"]})
    new = {f"ind:{x['id']}": x["logit"] for x in atual["indicadores"]}
    new.update({f"not:{x['id']}": x["logit"] for x in atual["noticias"]})
    chaves = sorted(set(old) | set(new))
    delta = {k: new.get(k, 0.0) - old.get(k, 0.0) for k in chaves}
    delta = {k: d for k, d in delta.items() if abs(d) > 1e-9}
    antigas = [k for k in delta if k.startswith("not:") and k[4:] not in novos]
    if antigas:
        soma = sum(delta.pop(k) for k in antigas)
        if abs(soma) > 1e-9:
            delta["not:antigas"] = soma
    delta, agrupados = agrupar(delta, 15, "not:outras")
    jog = list(delta)
    if e_ant["inicios"] != e_at["inicios"] or e_ant["pendente_negativo"] != e_at["pendente_negativo"]:
        jog.append("calendario")
    base_old = sum(old.values())

    def f(s: frozenset) -> float:
        e = e_at if "calendario" in s else e_ant
        return 100 * prob(e, base_old + sum(delta[k] for k in s if k != "calendario"), h0, cfg, horizonte=horizonte)

    sh = shapley(jog, f) if jog else {}
    # Numa troca de versão, a taxa-base muda: a parte "metodologia" é a nota antiga refeita com a
    # regra nova, menos a nota antiga. O resto da variação é dado e notícia, já na regra nova.
    metodologia = f(frozenset()) - 100 * ant[chave]
    if abs(metodologia) > 1e-9:
        sh["metodologia"] = metodologia
    return {"de": 100 * ant[chave], "para": 100 * atual[chave], "partes": sh, "agrupados": sorted(agrupados)}
