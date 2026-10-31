"""Gera o site estático em docs/ a partir dos registros em runs/.

O nível vai escrito no HTML (não carregado por JavaScript) para aparecer em prévias
de links e buscadores. Cada dia tem a sua página, o seu resumo e a sua conta, como
foram calculados naquele dia.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calendario  # noqa: E402
import causas  # noqa: E402
import model  # noqa: E402
import og_image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = "https://vaidarcrise.com.br"
REPO = "https://github.com/pedrojahara/vaidarcrise"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
JORNAIS = "Folha, Valor, Estadão, g1, InfoMoney, Poder360, Agência Brasil e Gazeta do Povo"
ESTAGIOS = {"dado": "dado divulgado", "decidido": "decisão tomada", "em_votacao": "em votação",
            "anuncio": "anúncio", "rumor": "rumor"}
SENTIDOS = {"piora": ("↑", "mais", "para pior"), "melhora": ("↓", "menos", "para melhor"),
            "igual": ("→", "igual", "sem lado claro")}
TENDENCIAS = {"piora": ("mais", "↑", "Tende a piorar"), "estavel": ("igual", "→", "Estável"),
              "melhora": ("menos", "↓", "Tende a melhorar"), "sem_direcao": ("igual", "→", "Sem direção clara")}
# Nomes curtos para listas corridas ("Atividade, crédito e juro real"), sem o "e" de dentro dos nomes.
CURTOS = {"atividade": "Ritmo da economia", "juro": "Juro", "credito": "Dívidas das famílias", "mercado": "Mercado (dólar e juro longo)",
          "contas": "Contas do governo", "emprego": "Emprego", "externo": "Economia lá fora"}
# As entradas da conta em palavras do leitor (PERSONA.md); config/modelo.json guarda a definição técnica.
ENTRADAS_SITE = {"tendencia": "Crescimento médio dos últimos 10 anos", "crescimento": "Crescimento no último ano",
                 "juro": "Quanto a Selic mudou em um ano", "inflacao": "Quanto a inflação mudou em um ano"}
DEFINICOES_SITE = {
    "tendencia": "Quanto o PIB cresceu por ano, em média, nos últimos 10 anos (IBGE).",
    "crescimento": "Quanto a economia cresceu no último ano. Usa a prévia do PIB do Banco Central (IBC-Br): os 3 últimos meses contra os mesmos meses de um ano antes.",
    "juro": "A Selic de hoje menos a de um ano antes, em pontos.",
    "inflacao": "A inflação de 12 meses (IPCA) de hoje menos a de um ano antes, em pontos."}
CHIPS = {"pior": "atencao", "normal": "normal", "melhor": "normal", "semdado": "semdado"}
OUTROS_ROT = {"concorda": "Analistas concordam", "discorda": "Analistas veem diferente", "neutro": "Para acompanhar"}


# ------------------------------------------------------------------ formatos
def num(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 and round(abs(x), d) != 0 else "") + s


def sinal(x: float, d: int = 1) -> str:
    if round(x, d) == 0:
        return num(0, d)
    return ("+" if x > 0 else "−") + num(abs(x), d)


def data_curta(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def dia_mes(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day}/{d.month}"


def data_extenso(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def hora(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.hour:02d}h{d.minute:02d}"


def verbo_pct(x: float) -> str:
    """'cresce 1,4%', 'cai 1,8%': a queda vai no verbo, não no sinal."""
    if round(x, 1) == 0:
        return "fica parado"
    return f"{'cresce' if x > 0 else 'cai'} {num(abs(x))}%"


def mes_curto(ref: str) -> str:
    return f"{MESES[int(ref[5:7]) - 1][:3]}."


def mes_nome(ref: str) -> str:
    return MESES[int(ref[5:7]) - 1]


def mes_antes(ref: str, n: int) -> str:
    a, m = divmod(int(ref[:4]) * 12 + int(ref[5:7]) - 1 - n, 12)
    return f"{a:04d}-{m + 1:02d}"


# --------------------------------------------------------------------- nível
def nivel_ctx(rodada: dict, cfg: dict) -> dict:
    res = rodada["resultado"]
    n = res["nivel"]
    nome = n["nome"]
    g = res.get("gar") or {}
    focus = next((x for x in res["indicadores"] if x["id"] == "focus_pib" and x.get("valor") is not None), None)
    cen = None
    if g:
        cen = {"ruim": verbo_pct(g["cenario_ruim"]), "normal": verbo_pct(g["cenario_normal"]),
               "focus": verbo_pct(focus["valor"]) if focus else None}
    return {"nome": nome, "indice": n["indice"], "nomes": cfg["niveis"]["nomes"],
            "placa": nome.replace(" ", "<br>") if nome.startswith("Muito") else nome,
            "rot": "risco normal" if nome == "Normal" else f"risco {nome.lower()} do normal",
            "frase": "normal" if nome == "Normal" else f"{nome.lower()} do normal",
            "anterior": cfg["niveis"]["nomes"][n["anterior"]] if n.get("anterior") is not None else None,
            "pendente": n["nome_bruto"] if n.get("bruto") is not None and n["bruto"] != n["indice"] else None,
            "cenarios": cen}


# --------------------------------------------------------------------- notícias
def pressao_ctx(rodada: dict, eventos: dict, cfg: dict, por_fator: int = 3) -> dict:
    """A caixa da página principal: para que lado as notícias de ontem empurram cada fator."""
    pr = rodada.get("pressao") or {"fatores": {}, "sentido": "igual", "n": 0}
    nomes = cfg["fatores"]
    com = []
    for fid, p in sorted(pr["fatores"].items(), key=lambda kv: -abs(kv[1]["saldo"])):
        if p["sentido"] == "igual":
            continue
        simbolo, cls, palavra = SENTIDOS[p["sentido"]]
        nots = []
        for i in p["eventos"][:por_fator]:
            e = eventos.get(i)
            if not e:
                continue
            contra = (e["direcao"] > 0) != (p["sentido"] == "piora")
            meta = [ESTAGIOS.get(e.get("estagio")) if e.get("estagio") != "dado" else None,
                    ("alivia" if e["direcao"] < 0 else "pesa") if contra else None]
            nots.append({"titulo": e["titulo_evento"], "meta": ", ".join(x for x in meta if x),
                         "fonte": e["fontes"][0] if e.get("fontes") else None})
        com.append({"id": fid, "nome": nomes.get(fid, fid), "simbolo": simbolo, "cls": cls, "palavra": palavra,
                    "noticias": nots})
    sem = [nomes[f] for f in nomes if f not in {c["id"] for c in com}]
    simbolo, cls, palavra = SENTIDOS[pr["sentido"]]
    # "de ontem" quando a leitura cobre só a véspera; senão, as datas lidas.
    dias = (rodada.get("cobertura") or {}).get("dias") or []
    vespera = (dt.date.fromisoformat(rodada["gerado_em"][:10]) - dt.timedelta(days=1)).isoformat()
    quando = "de ontem" if dias in ([], [vespera]) else f"de {dia_mes(dias[0])} a {dia_mes(dias[-1])}"
    if not pr.get("n"):
        frase = f"Nenhuma notícia {quando} mexeu nos fatores."
    elif pr["sentido"] == "igual":
        frase = f"As notícias {quando} não empurram para um lado claro."
    else:
        frase = f"As notícias {quando} puxam {palavra}."
    return {"com": com, "sem": sem, "simbolo": simbolo, "cls": cls, "frase": frase, "n": pr.get("n", 0), "quando": quando}


# ------------------------------------------------------------------- fatores
def _regua(x: dict, cap: str) -> dict | None:
    """Régua de um indicador ou entrada da conta: a faixa normal e a agulha de hoje."""
    if x.get("valor") is None or not x.get("escala"):
        return None
    v, (lo, hi), (n0, n1) = x["valor"], x["escala"], x["faixa_normal"]
    mn, mx = min(lo, v, n0), max(hi, v, n1)
    folga = (mx - mn) * 0.06 or 1
    mn, mx = mn - folga, mx + folga

    def pc(a: float) -> float:
        return round(100 * (a - mn) / (mx - mn), 1)

    d = 2 if abs(v) < 1 and x["unidade"] in ("p.p.", "p.p. do PIB", "pontos") else 1
    return {"cap": cap, "normal": (pc(n0), round(pc(n1) - pc(n0), 1)), "agulha": pc(v),
            "rot": sinal(v, d) if x["unidade"] in ("p.p.", "p.p. do PIB", "%", "pontos") and x["id"] not in ("focus_pib", "tendencia") else num(v, d),
            "eixo": (num(mn, 1), num(mx, 1)), "aria": f"Hoje em {num(v, d)}, comparado à faixa normal"}


def _exibicao(fid: str, ind: dict, ent: dict) -> dict:
    """O valor grande do cartão, a legenda e as réguas de cada fator. Nos fatores da conta, as
    réguas das entradas vêm primeiro."""
    g = ind.get
    if fid == "atividade":
        c = ent.get("crescimento") or {}
        ref = c.get("ref")
        return {"valor": verbo_pct(c["valor"]) if c else "Sem dado",
                "legenda": f"Quanto a economia cresceu em um ano (prévia do PIB do Banco Central, de {mes_curto(mes_antes(ref, 2))} a {mes_curto(ref)})" if ref else "",
                "hoje": (("Ficou parada" if round(c["valor"], 1) == 0 else f"{'Cresceu' if c['valor'] > 0 else 'Encolheu'} {num(abs(c['valor']))}%")
                         + " em um ano") if c else "Sem dado",
                "reguas": [r for r in (_regua(c, "Na conta: crescimento no último ano, %"),
                                       _regua(ent.get("tendencia") or {}, "Na conta: crescimento médio dos últimos 10 anos, %"),
                                       _regua(g("ibcbr") or {}, "Prévia do PIB: últimos 3 meses contra os 3 anteriores, %"),
                                       _regua(g("focus_pib") or {}, "PIB que os bancos esperam para os próximos 12 meses (Focus), %")) if r]}
    if fid == "juro":
        j, i, x = ent.get("juro") or {}, ent.get("inflacao") or {}, g("juro_real") or {}
        return {"valor": f"Selic {num(j['nivel'], 2)}%" if j else "Sem dado",
                "legenda": (f"Juro básico, {num(abs(j['valor']), 2)} ponto {'abaixo' if j['valor'] < 0 else 'acima'} de um ano antes. "
                            f"Preços subiram {num(i['nivel'])}% em um ano (IPCA)" if j and i else ""),
                "hoje": f"Selic {'caiu' if j['valor'] < 0 else 'subiu'} {num(abs(j['valor']), 2)} ponto em um ano" if j else "Sem dado",
                "reguas": [r for r in (_regua(j, "Na conta: quanto a Selic mudou em um ano, pontos"),
                                       _regua(i, "Na conta: quanto a inflação de um ano mudou, pontos"),
                                       _regua(x, "Juro descontado da inflação esperada, % ao ano")) if r]}
    if fid == "credito":
        x = g("comprometimento") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}% da renda" if ok else "Sem dado",
                "legenda": f"Parte da renda das famílias que vai para parcelas e juros, {mes_nome(x['ref'])}" if ok else "",
                "hoje": f"{num(x['nivel'])}% da renda vai para parcelas e juros" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Contra a média dos 3 anos anteriores, pontos"),) if r]}
    if fid == "mercado":
        x, d = g("tesouro") or {}, g("dolar") or {}
        ok = x.get("valor") is not None
        leg = (f"Juro acima da inflação que o governo paga para pegar dinheiro até {(x.get('vencimento') or '')[:4]} "
               f"(Tesouro IPCA+), em {dia_mes(x['ref'])}") if ok else ""
        if d.get("valor") is not None:
            leg += (". " if leg else "") + f"Dólar a R$ {num(d['nivel'], 2)} em {dia_mes(d['ref'])}"
        return {"valor": f"{num(x['nivel'])}% ao ano" if ok else "Sem dado", "legenda": leg,
                "hoje": f"Governo paga {num(x['nivel'], 1)}% ao ano acima da inflação" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Esse juro contra o normal dos últimos 3 anos, pontos"),
                                       _regua(d, "Dólar, variação em 3 meses, %")) if r]}
    if fid == "contas":
        x = g("divida") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}% do PIB" if ok else "Sem dado",
                "legenda": f"Dívida do governo (União, estados e municípios) contra tudo o que o país produz em um ano, {mes_nome(x['ref'])}" if ok else "",
                "hoje": f"Dívida do governo em {num(x['nivel'])}% do PIB" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Quanto a dívida subiu em um ano, pontos do PIB"),) if r]}
    if fid == "emprego":
        x = g("sahm") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}%" if ok else "Sem dado",
                "legenda": f"Desemprego no trimestre até {mes_nome(x['ref'])} (IBGE)" if ok else "",
                "hoje": f"Desemprego em {num(x['nivel'])}%" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Desemprego médio de 3 meses contra o menor do último ano, pontos"),) if r]}
    x = g("commodities") or {}
    ok = x.get("valor") is not None
    return {"valor": (("fica parado" if round(x["valor"], 1) == 0 else f"{'sobe' if x['valor'] > 0 else 'cai'} {num(abs(x['valor']))}%")
                      if ok else "Sem dado"),
            "legenda": f"Preço de soja, minério, petróleo e outros produtos básicos em 6 meses, até {mes_nome(x['ref'])} (FMI)" if ok else "",
            "hoje": f"Produtos básicos {'subiram' if x['valor'] >= 0 else 'caíram'} {num(abs(x['valor']))}% em 6 meses" if ok else "Sem dado",
            "reguas": [r for r in (_regua(x, "Variação em 6 meses, %"),) if r]}


def efeito_txt(e: float | None) -> tuple[str, str]:
    """O efeito de um fator no cenário ruim, em palavras, e a cor: ('Piora 0,2 ponto', 'mais')."""
    if e is None:
        return "Fora da conta", ""
    if abs(e) < 0.05:
        return "Neutro", ""
    return (f"Pesa {num(abs(e), 2)} ponto", "mais") if e < 0 else (f"Ajuda {num(e, 2)} ponto", "menos")


def nota_guardado(xs: list[dict]) -> str:
    """Aviso no cartão quando um dado do fator veio de uma atualização anterior, porque a fonte falhou."""
    velhos = [x for x in xs if x.get("reaproveitado") and x.get("ref")]
    if not velhos:
        return ""
    if len(velhos) > 1:
        return "Alguns dados são de antes: a fonte não respondeu nesta atualização."
    ref = velhos[0]["ref"]
    quando = dia_mes(ref) if len(ref) == 10 else mes_nome(ref) if len(ref) == 7 else "antes"
    return f"Dado de {quando}, o último que temos: a fonte não respondeu nesta atualização."


def fatores_ctx(rodada: dict, cfg: dict) -> list[dict]:
    res = rodada["resultado"]
    ind = {x["id"]: x for x in res["indicadores"]}
    ent = {x["id"]: x for x in (res.get("gar") or {}).get("entradas", [])}
    leit = (rodada.get("leituras") or {}).get("fatores", {})
    out = []
    for f in res["fatores"]:
        d = leit.get(f["id"], {})
        t = d.get("tendencia", "sem_direcao")
        cls, seta, palavra = TENDENCIAS[t]
        outros = d.get("outros") or {"tipo": "neutro", "texto": "", "fonte": None}
        rot, cor = efeito_txt(f.get("efeito"))
        if f["na_conta"]:
            partes = [f"{ENTRADAS_SITE.get(i, ent[i]['nome'])}: {efeito_txt(ent[i]['efeito'])[0].lower()}" for i in f["entradas"] if i in ent]
            conta = "; ".join([partes[0]] + [x[0].lower() + x[1:] for x in partes[1:]]) + "." if partes else ""
        else:
            conta = cfg["fora_da_conta"].get(f["id"], "")
        out.append({
            **f, "nome": cfg["fatores"].get(f["id"], f["nome"]), **_exibicao(f["id"], ind, ent), "chip": CHIPS[f["situacao"]], "tend": {"cls": cls, "seta": seta, "palavra": palavra, "id": t},
            "efeito_rot": rot, "efeito_cls": cor, "conta": conta,
            "nota": nota_guardado([ind[i] for i in f["indicadores"] if i in ind] + [ent[i] for i in f["entradas"] if i in ent]),
            "barra": round(100 * min(abs(f.get("efeito") or 0) / 0.5, 1), 1) if cor else 0, "como": d.get("como", ""),
            "porque": [{"texto": x["texto"], "fonte": x.get("fonte"), "url": None} for x in d.get("fatos", [])]
                      + [{"texto": n["texto"], "fonte": n["fonte"]["veiculo"], "url": n["fonte"]["url"]} for n in d.get("noticias", [])],
            "outros": {"rot": OUTROS_ROT.get(outros.get("tipo"), "Outros"), "cls": outros.get("tipo", "neutro"),
                       "texto": outros.get("texto", ""), "fonte": outros.get("fonte")},
            "melhora": d.get("melhora_se", []), "piora": d.get("piora_se", []),
        })
    return out


def _juntar(nomes: list[str]) -> str:
    """'Atividade, juro real e inflação e crédito': o primeiro com maiúscula, os outros em minúscula."""
    if not nomes:
        return ""
    ns = [nomes[0]] + [n[0].lower() + n[1:] for n in nomes[1:]]
    return ns[0] if len(ns) == 1 else ", ".join(ns[:-1]) + " e " + ns[-1]


def gatilho_txt(g: dict, ent: dict) -> str:
    """O que mudaria o nível, em palavras: 'Selic subir para 17,8%'."""
    x, v = ent[g["id"]], g["valor"]
    if g["id"] == "crescimento":
        if v < 0:
            return f"a economia encolher {num(abs(v))}% em um ano"
        return f"a economia crescer {'só ' if v < x['valor'] else ''}{num(v)}% em um ano"
    alvo = x["antes"] + v
    nome = "a Selic" if g["id"] == "juro" else "a inflação de um ano"
    if alvo < 0:
        return f"{nome} cair abaixo de zero"
    return f"{nome} {'subir' if alvo > x['nivel'] else 'cair'} para {num(alvo, 1)}%"


def gatilhos_ctx(res: dict) -> list[dict]:
    """Uma frase por nível vizinho: 'Acima do normal se ...'."""
    ent = {x["id"]: x for x in (res.get("gar") or {}).get("entradas", [])}
    out = []
    for nivel in sorted({g["nivel"] for g in res.get("gatilhos", [])}, reverse=True):
        gs = [g for g in res["gatilhos"] if g["nivel"] == nivel]
        txts = [gatilho_txt(g, ent) for g in gs]
        quais = txts[0] if len(txts) == 1 else ", ".join(txts[:-1]) + " ou " + txts[-1]
        nome = gs[0]["nome_nivel"]
        alvo = "normal" if nome == "Normal" else f"{nome.lower()} do normal"
        basta = " Basta um deles, com o resto parado." if len(txts) > 1 else " Com o resto parado."
        out.append({"nivel": nivel, "sobe": nivel > res["nivel"].get("bruto", res["nivel"]["indice"]),
                    "rot": nome, "texto": f"O risco iria para {alvo} se {quais}.{basta}"})
    return out


def pontos_ctx(fatores: list[dict], res: dict | None = None) -> list[dict]:
    """Os tópicos do topo do resumo."""
    out = []
    if res is not None and res.get("gar"):
        g = res["gar"]
        out.append({"rot": "Num ano ruim", "cls": "",
                    "texto": f"O PIB {verbo_pct(g['cenario_ruim'])} em 12 meses. Em tempos normais, {verbo_pct(g['cenario_normal'])}."})
    pesam = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["efeito_cls"] == "mais"]
    aliviam = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["efeito_cls"] == "menos"]
    if pesam:
        out.append({"rot": "Atrapalham", "texto": _juntar(pesam) + ".", "cls": "mais"})
    if aliviam:
        out.append({"rot": "Ajudam", "texto": _juntar(aliviam) + ".", "cls": "menos"})
    if not pesam and not aliviam:
        out.append({"rot": "Na conta", "texto": "Tudo perto do normal.", "cls": ""})
    piora = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "piora"]
    melhora = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "melhora"]
    estaveis = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "estavel"]
    disc = [f for f in fatores if f["outros"]["cls"] == "discorda"]
    if piora:
        out.append({"rot": "Devem piorar em 6 meses", "texto": _juntar(piora) + ".", "cls": "mais"})
    if melhora:
        out.append({"rot": "Devem melhorar em 6 meses", "texto": _juntar(melhora) + ".", "cls": "menos"})
    if estaveis:
        out.append({"rot": "Devem ficar como estão", "texto": _juntar(estaveis) + ".", "cls": ""})
    if disc:
        quem = sorted({(f["outros"]["fonte"] or {}).get("veiculo", "").split(" ")[0] for f in disc} - {""})
        out.append({"rot": "Os bancos (Focus) veem diferente" if quem == ["Focus"] else "Analistas veem diferente",
                    "texto": _juntar([CURTOS.get(f["id"], f["nome"]) for f in disc]) + ".", "cls": ""})
    if res is not None:
        sobe = [x for x in gatilhos_ctx(res) if x["sobe"]]
        out.append({"rot": "O que mudaria o nível", "cls": "",
                    "texto": sobe[0]["texto"] if sobe else "Já está no nível mais alto."})
    return out


# ------------------------------------------------------------ indicadores
def _fmt(v: float, x: dict) -> str:
    u, d = x["unidade"], 2 if x["unidade"] == "p.p." and abs(v) < 1 else 1
    if x["id"] in ("focus_pib", "juro_real"):
        return f"{num(v, d)}%"
    if u == "%":
        return f"{sinal(v, d)}%"
    return f"{sinal(v, d)} p.p."


def indicadores_ctx(res: dict, cfg: dict) -> list[dict]:
    """A tabela dos indicadores do Resumo: o valor de hoje contra a faixa normal desde 2002."""
    out = []
    for x in sorted(res["indicadores"], key=lambda x: (list(cfg["fatores"]).index(x["fator"]), x["nome"])):
        out.append({"id": x["id"], "nome": x["nome"], "fator": cfg["fatores"][x["fator"]], "definicao": x["definicao"],
                    "hoje": _fmt(x["valor"], x) if x.get("valor") is not None else "Sem dado",
                    "ref": x.get("ref"), "faixa": (f"{_fmt(x['faixa_normal'][0], x)} a {_fmt(x['faixa_normal'][1], x)}"
                                                   if x.get("faixa_normal") else "–"),
                    "situacao": model.SITUACOES[x["situacao"]], "chip": CHIPS[x["situacao"]]})
    return out


def entradas_ctx(res: dict, cfg: dict) -> list[dict]:
    """A tabela da conta: cada entrada, o valor de hoje, o normal no Brasil e o efeito no cenário ruim."""
    out = []
    for x in (res.get("gar") or {}).get("entradas", []):
        def f(v: float) -> str:
            return f"{num(v)}%" if x["id"] == "tendencia" else f"{sinal(v)}%" if x["unidade"] == "%" else f"{sinal(v, 2)} pt"
        out.append({"nome": ENTRADAS_SITE.get(x["id"], x["nome"]), "definicao": DEFINICOES_SITE.get(x["id"], cfg["gar"]["entradas"][x["id"]]), "hoje": f(x["valor"]),
                    "faixa": f"{f(x['faixa_normal'][0])} a {f(x['faixa_normal'][1])}",
                    "efeito": efeito_txt(x["efeito"])[0], "cls": efeito_txt(x["efeito"])[1]})
    return out


# --------------------------------------------------------------------- posts
def post_de(rodada: dict, eventos: dict, cfg: dict) -> dict:
    """O post de um dia. Sem texto do LLM, sai um título feito por código e a caixa das notícias."""
    dia = rodada["gerado_em"][:10]
    nots = rodada["insumos"]["noticias"]
    n, k = nots["n_itens"], len(nots.get("por_veiculo", {}))
    dias = (rodada.get("cobertura") or {}).get("dias", [])
    jornais = "jornal" if k == 1 else "jornais"
    dd = [data_curta(d)[:5] for d in dias]
    quantas = f"{n} manchetes" if n is not None else "as manchetes"
    lidas = (f"{quantas} de {k} {jornais} publicadas em {' e '.join(filter(None, [', '.join(dd[:-1]), dd[-1]]))}"
             if dias else f"{quantas} de {k} {jornais}")
    p = rodada.get("post") or {}
    niv = nivel_ctx(rodada, cfg)
    if p.get("ok"):
        titulo, paragrafos = p["titulo"], p["paragrafos"]
        autoria = f"Escrito por inteligência artificial (Claude) às {hora(p.get('escrito_em') or rodada['gerado_em'])}, depois de ler {lidas}."
        rodape = "Ninguém revisa o texto antes de ele sair. Erros vão para"
    else:
        if niv["anterior"] and niv["anterior"] != niv["nome"]:
            sobe = rodada["resultado"]["nivel"]["indice"] > rodada["resultado"]["nivel"]["anterior"]
            titulo = f"Risco de recessão {'sobe' if sobe else 'cai'} para {niv['frase']}"
        else:
            titulo = f"Risco de recessão {'no normal' if niv['nome'] == 'Normal' else 'está ' + niv['frase']}"
        paragrafos = []
        autoria = (f"Atualização automática das {hora(rodada['gerado_em'])}, depois de ler {lidas}. "
                   "O texto do dia não saiu. Ficam o nível e as notícias, organizados pelo programa.")
        rodape = "Erros vão para"
    return {"dia": dia, "data_extenso": data_extenso(dia), "titulo": titulo, "paragrafos": paragrafos,
            "autoria": autoria, "rodape": rodape, "nivel": niv["nome"], "llm": bool(p.get("ok")),
            "pressao": pressao_ctx(rodada, eventos, cfg), "link": f"/{dia}/", "resumo": f"/{dia}/resumo/",
            "registro": f"{REPO}/blob/main/runs/{rodada['id']}.json", "llm_ok": rodada["llm"]["ok"]}


def textos_do_editor() -> list[dict]:
    """Textos escritos à mão em editor/*.md: cabeçalho 'chave: valor', uma linha '---' e o corpo em Markdown."""
    out = []
    for arq in sorted((ROOT / "editor").glob("*.md")):
        cab, corpo = arq.read_text().split("\n---\n", 1)
        meta = {k.strip(): v.strip() for k, v in (linha.split(":", 1) for linha in cab.strip().splitlines())}
        slug = arq.stem[11:] if arq.stem[:10] == meta["data"] else arq.stem
        out.append({"dia": meta["data"], "data_extenso": data_extenso(meta["data"]), "titulo": meta["titulo"],
                    "corpo_html": markdown.markdown(corpo), "paragrafos": [], "pressao": None,
                    "tags": meta.get("tags", ""), "editor": True, "link": f"/textos/{slug}/", "slug": slug,
                    "llm_ok": True})
    return sorted(out, key=lambda t: t["dia"], reverse=True)


# ------------------------------------------------------------------ placar
def placar_ctx(placar: list[dict], cfg: dict, ate: str) -> dict:
    linhas = []
    for p in placar:
        if p["data"] > ate:
            continue
        cls, seta, palavra = TENDENCIAS[p["leitura"]]
        res = p.get("resultado")
        if res == "substituida" and (p.get("substituida_em") or "9999") > ate:
            res = None
        if res == "substituida":
            continue
        linhas.append({"fator": cfg["fatores"][p["fator"]], "cls": cls, "leitura": f"{seta} {palavra}",
                       "data": data_curta(p["data"]), "conferir": data_curta(p["conferir_em"]),
                       "resultado": {"acertou": "Acertou", "errou": "Errou"}.get(res) if res and (p.get("conferido_em") or "9999") <= ate else None})
    feitas = [x for x in linhas if x["resultado"]]
    acertos = sum(1 for x in feitas if x["resultado"] == "Acertou")
    sub = ("Cada previsão é conferida 6 meses depois, contra o dado. Nenhuma chegou aos 6 meses ainda." if not feitas else
           f"Cada previsão é conferida 6 meses depois, contra o dado. Até agora, {acertos} de {len(feitas)} acertaram.")
    return {"linhas": linhas, "sub": sub}


# ---------------------------------------------------------- histórico do nível
def svg_niveis(historico: list[dict], recessoes: list[dict], nomes: list[str]) -> str:
    """O nível mês a mês, como a conta teria dito com coeficientes que não viram aquele ano, e as recessões."""
    if not historico:
        return ""
    w, h, x0, x1, y0, y1 = 760, 210, 96, 750, 12, 172
    meses = [x["mes"] for x in historico]
    n0 = int(meses[0][:4]) * 12 + int(meses[0][5:7]) - 1
    n1 = int(meses[-1][:4]) * 12 + int(meses[-1][5:7]) - 1

    def px(m: str) -> float:
        n = int(m[:4]) * 12 + int(m[5:7]) - 1
        return x0 + (x1 - x0) * (n - n0) / max(n1 - n0, 1)

    def py(i: int) -> float:
        return y1 - (y1 - y0) * i / 4

    out = [f'<svg viewBox="0 0 {w} {h}" class="hist" role="img" aria-label="Nível de risco mês a mês desde 2004, com as recessões">']
    for r in recessoes:
        q, a = r["inicio"].split("T")
        ini = f"{a}-{(int(q) - 1) * 3 + 1:02d}"
        q2, a2 = r["fim"].split("T")
        fim = f"{a2}-{int(q2) * 3:02d}"
        if fim < meses[0] or ini > meses[-1]:
            continue
        a_, b_ = px(max(ini, meses[0])), px(min(fim, meses[-1]))
        out.append(f'<rect x="{a_:.1f}" y="{y0 - 6}" width="{max(b_ - a_, 2):.1f}" height="{y1 - y0 + 12}" class="rec"/>')
    for i, nome in enumerate(nomes):
        out.append(f'<line x1="{x0}" y1="{py(i):.1f}" x2="{x1}" y2="{py(i):.1f}" class="gl"/>'
                   f'<text x="{x0 - 8}" y="{py(i) + 4:.1f}" class="tl" text-anchor="end">{nome}</text>')
    pts = []
    for i, x in enumerate(historico):
        xa = px(x["mes"])
        if i:
            pts.append(f"{xa:.1f},{py(historico[i - 1]['nivel']):.1f}")
        pts.append(f"{xa:.1f},{py(x['nivel']):.1f}")
    out.append(f'<polyline points="{" ".join(pts)}" class="l1"/>')
    for ano in range(int(meses[0][:4]) + (1 if meses[0][5:7] != "01" else 0), int(meses[-1][:4]) + 1, 4):
        m = f"{ano}-01"
        out.append(f'<text x="{px(m):.1f}" y="{h - 6}" class="tl" text-anchor="middle">{ano}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------- o que causa
def causas_ctx(dia: str, rodada: dict, todas: list[dict]) -> dict:
    """A aba /causas/: o que veio antes das altas de juro (44 países e Brasil) e o Brasil de hoje em cada elo."""
    cfg = causas.carregar_config()
    series = json.loads(causas.HIST.read_text())["series"]
    br = causas.aucs_brasil(series)

    def largura(a: float | None) -> float:
        return round(max(0.0, (a - 0.5) / 0.5) * 100, 1) if a is not None else 0.0

    sinais = [{**x, "brasil": br["aucs"].get(x["id"]), "w_paises": largura(x.get("paises")),
               "w_brasil": largura(br["aucs"].get(x["id"]))} for x in cfg["sinais"]]
    brutos = sorted(p for p in (ROOT / "data" / "raw").glob("*/indicadores.json") if p.parent.name <= dia)
    bruto = json.loads(brutos[-1].read_text()) if brutos else None
    hoje = causas.brasil_hoje(series, rodada["resultado"], bruto, [r for r in todas if r["gerado_em"][:10] <= dia], cfg)
    return {"sinais": sinais, "altas": br["altas"], "meses": br["meses"], "hoje": hoje}


# --------------------------------------------------------------------- dados
def dados_publicos(rodada: dict, ctx: dict) -> dict:
    res = rodada["resultado"]
    leit = (rodada.get("leituras") or {}).get("fatores", {})
    g = res.get("gar") or {}
    return {
        "nivel": res["nivel"]["nome"], "escala": ctx["cfg"]["niveis"]["nomes"],
        "pergunta": ctx["cfg"]["pergunta"], "atualizado_em": rodada["gerado_em"],
        "pib_12_meses": {"cenario_ruim_pct": round(g["cenario_ruim"], 2), "cenario_ruim_em_tempos_normais_pct": round(g["cenario_normal"], 2),
                         "o_que_e": "Crescimento do PIB nos 4 trimestres seguintes ao último divulgado que tem 1 chance em 10 de ser pior."} if g else None,
        "entradas": [{"id": x["id"], "nome": x["nome"], "valor": round(x["valor"], 4), "ref": x["ref"],
                      "efeito_no_cenario_ruim_pontos": round(x["efeito"], 4)} for x in g.get("entradas", [])],
        "fatores": [{"id": f["id"], "nome": ctx["cfg"]["fatores"].get(f["id"], f["nome"]), "na_conta": f["na_conta"],
                     "efeito_no_cenario_ruim_pontos": round(f["efeito"], 4) if f.get("efeito") is not None else None,
                     "situacao": f["situacao_nome"], "tendencia": leit.get(f["id"], {}).get("tendencia")} for f in res["fatores"]],
        "indicadores": [{"id": x["id"], "nome": x["nome"], "fator": x["fator"],
                         "valor": round(x["valor"], 4) if x.get("valor") is not None else None, "unidade": x["unidade"],
                         "ref": x.get("ref"), "situacao": model.SITUACOES[x["situacao"]],
                         "faixa_normal": [round(v, 4) for v in x["faixa_normal"]] if x.get("faixa_normal") else None}
                        for x in res["indicadores"]],
        "pressao_noticias": {"sentido": rodada["pressao"]["sentido"],
                             "fatores": {k: v["sentido"] for k, v in rodada["pressao"]["fatores"].items()}},
        "registro_completo": f"{REPO}/blob/main/runs/{rodada['id']}.json",
    }


# ---------------------------------------------------------------------- main
def main() -> None:
    cfg = model.carregar_config()
    cal = model.carregar_calibracao()
    todas = [json.loads(p.read_text()) for p in sorted((ROOT / "runs").glob("*.json"))]
    if not todas:
        print("nenhuma rodada em runs/")
        return
    eventos = json.loads((ROOT / "data" / "eventos.json").read_text()) if (ROOT / "data" / "eventos.json").exists() else []
    idx = {e["id"]: e for e in eventos}
    placar = json.loads((ROOT / "data" / "placar.json").read_text()) if (ROOT / "data" / "placar.json").exists() else []
    mensal_p = ROOT / "data" / "historico" / "mensal.json"
    mensal = json.loads(mensal_p.read_text()) if mensal_p.exists() else {}
    agenda = calendario.carregar()

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["num"] = num
    env.filters["sinal"] = sinal

    DOCS.mkdir(exist_ok=True)
    (DOCS / "og").mkdir(exist_ok=True)
    ultima = todas[-1]
    # Um post e um link permanente por dia: a última rodada do dia.
    por_dia = {}
    for r in todas:
        por_dia[r["gerado_em"][:10]] = r
    dias = sorted(por_dia)
    # Sobra de páginas de dias que não existem mais nos registros (rodada refeita): saem do site.
    for p in DOCS.iterdir():
        if p.is_dir() and len(p.name) == 10 and p.name[4] == "-" and p.name not in por_dia:
            shutil.rmtree(p)
    for p in (DOCS / "og").glob("*.png"):
        if p.stem not in por_dia:
            p.unlink()

    posts = {d: post_de(por_dia[d], idx, cfg) for d in dias}
    lista = [{"dia": d, "data": data_curta(d)[:5], "nivel": posts[d]["nivel"], "titulo": posts[d]["titulo"],
              "link": f"/{d}/"} for d in reversed(dias)]
    textos = textos_do_editor()
    destaque = textos[0] if textos else None
    arquivo = sorted(lista[1:] + [{"dia": t["dia"], "data": data_curta(t["dia"])[:5], "nivel": None,
                                   "titulo": t["titulo"], "link": t["link"]} for t in textos[1:]],
                     key=lambda x: x["dia"], reverse=True)
    historico_svg = svg_niveis(mensal.get("nivel_fora_da_amostra", []), cal.get("recessoes", []), cfg["niveis"]["nomes"])

    def contexto(dia: str, r: dict, permalink: bool) -> dict:
        pos = dias.index(dia)
        base = f"/{dia}/" if permalink else "/"
        fat = fatores_ctx(r, cfg)
        return {"cfg": cfg, "cal": cal, "repo": REPO, "site": SITE, "dia": dia, "permalink": permalink,
                "nivel": nivel_ctx(r, cfg), "post": posts[dia], "fatores": fat, "pontos": pontos_ctx(fat, r["resultado"]),
                "data_titulo": f"{int(dia[8:10])} de {MESES[int(dia[5:7]) - 1]}",
                "tabela": indicadores_ctx(r["resultado"], cfg), "entradas": entradas_ctx(r["resultado"], cfg),
                "gatilhos": gatilhos_ctx(r["resultado"]),
                "indicadores": r["resultado"]["indicadores"], "placar": placar_ctx(placar, cfg, dia),
                "datas": calendario.janela(agenda, dt.date.fromisoformat(dia)), "jornais": JORNAIS,
                "hora": hora(r["gerado_em"]), "atualizado_iso": r["gerado_em"],
                "link_inicio": base, "link_resumo": f"{base}resumo/", "link_nota": f"{base}nota/",
                "dia_antes": dias[pos - 1] if pos else None, "dia_depois": dias[pos + 1] if pos + 1 < len(dias) else None,
                "data_curta": data_curta, "data_extenso": data_extenso, "historico_svg": historico_svg,
                "og_url": f"{SITE}/og/{dia}.png", "dia_mes": dia_mes}

    abas = {"index.html": "inicio", "resumo.html": "resumo", "causas.html": "causas", "nota.html": "nota"}

    def gravar(caminho: Path, tpl: str, ctx: dict, canonical: str) -> None:
        caminho.mkdir(parents=True, exist_ok=True)
        (caminho / "index.html").write_text(env.get_template(tpl).render(**{"aba": abas.get(tpl), **ctx},
                                                                          canonical=canonical))

    for dia, r in por_dia.items():
        ctx = contexto(dia, r, True)
        og = DOCS / "og" / f"{dia}.png"
        og_image.gerar(og, {"nivel": ctx["nivel"], "dia": dia, "data_curta": data_curta})
        gravar(DOCS / dia, "index.html", ctx, f"{SITE}/{dia}/")
        gravar(DOCS / dia / "resumo", "resumo.html", ctx, f"{SITE}/{dia}/resumo/")
        gravar(DOCS / dia / "nota", "nota.html", ctx, f"{SITE}/{dia}/nota/")

    dia = ultima["gerado_em"][:10]
    ctx = contexto(dia, ultima, False)
    gravar(DOCS, "index.html", {**ctx, "anteriores": arquivo, "destaque": destaque}, f"{SITE}/")
    gravar(DOCS / "resumo", "resumo.html", ctx, f"{SITE}/resumo/")
    gravar(DOCS / "nota", "nota.html", ctx, f"{SITE}/nota/")
    try:
        gravar(DOCS / "causas", "causas.html", {**ctx, "causas": causas_ctx(dia, ultima, todas), "og_url": f"{SITE}/og.png"},
               f"{SITE}/causas/")
    except (KeyError, OSError, ValueError, ZeroDivisionError) as e:  # a aba não pode derrubar a atualização do dia
        print(f"aviso: a aba /causas/ não foi refeita ({e!r})")
    for t in textos:
        gravar(DOCS / "textos" / t["slug"], "index.html",
               {**ctx, "post": t, "permalink": True, "dia_antes": None, "dia_depois": None}, f"{SITE}{t['link']}")
    shutil.copy(DOCS / "og" / f"{dia}.png", DOCS / "og.png")

    met = ('<p class="intro-met">Esta página é para quem quer conferir ou refazer a conta, com as fórmulas e os testes. '
           'A versão curta está em <a href="/nota/">Como a conta funciona</a>.</p>\n'
           + markdown.markdown((ROOT / "METODOLOGIA.md").read_text(), extensions=["tables", "toc"]))
    gravar(DOCS / "metodologia", "pagina.html", {**ctx, "titulo": "Metodologia", "corpo": met, "og_url": f"{SITE}/og.png"},
           f"{SITE}/metodologia/")

    publico = dados_publicos(ultima, ctx)
    publico["post_do_dia"] = {"titulo": posts[dia]["titulo"], "url": f"{SITE}/{dia}/", "escrito_por_llm": posts[dia]["llm"]}
    (DOCS / "data.json").write_text(json.dumps(publico, ensure_ascii=False, indent=1))
    (DOCS / "historico.json").write_text(json.dumps(
        [{"id": r["id"], "gerado_em": r["gerado_em"], "nivel": r["resultado"]["nivel"]["nome"]} for r in todas],
        ensure_ascii=False, indent=1))
    (DOCS / "CNAME").write_text("vaidarcrise.com.br")
    (DOCS / ".nojekyll").touch()
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [f"{SITE}/", f"{SITE}/resumo/", f"{SITE}/causas/", f"{SITE}/nota/", f"{SITE}/metodologia/"] \
        + [f"{SITE}/{d}/{s}" for d in dias for s in ("", "resumo/", "nota/")] + [f"{SITE}{t['link']}" for t in textos]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    print(f"site gerado em {DOCS} (nível {ctx['nivel']['nome']})")


if __name__ == "__main__":
    main()
