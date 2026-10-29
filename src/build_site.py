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
SENTIDOS = {"piora": ("↑", "mais", "para piorar"), "melhora": ("↓", "menos", "para melhorar"),
            "igual": ("→", "igual", "sem lado claro")}
TENDENCIAS = {"piora": ("mais", "↑", "Tende a piorar"), "estavel": ("igual", "→", "Estável"),
              "melhora": ("menos", "↓", "Tende a melhorar"), "sem_direcao": ("igual", "→", "Sem direção clara")}
# Nomes curtos para listas corridas ("Atividade, crédito e juro real"), sem o "e" de dentro dos nomes.
CURTOS = {"atividade": "Atividade", "juro": "Juro real", "credito": "Crédito", "mercado": "Mercado financeiro",
          "contas": "Contas públicas", "emprego": "Emprego", "externo": "Cenário externo"}
CHIPS = {"alerta": "alerta", "pior": "atencao", "normal": "normal", "melhor": "normal", "semdado": "semdado"}
OUTROS_ROT = {"concorda": "Concordam", "discorda": "Discordam", "neutro": "Outros"}


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


def mes_curto(ref: str) -> str:
    return f"{MESES[int(ref[5:7]) - 1][:3]}."


def mes_nome(ref: str) -> str:
    return MESES[int(ref[5:7]) - 1]


def mes_antes(ref: str, n: int) -> str:
    a, m = divmod(int(ref[:4]) * 12 + int(ref[5:7]) - 1 - n, 12)
    return f"{a:04d}-{m + 1:02d}"


# --------------------------------------------------------------------- nível
def nivel_ctx(rodada: dict, cfg: dict) -> dict:
    n = rodada["resultado"]["nivel"]
    nome = n["nome"]
    return {"nome": nome, "indice": n["indice"], "nomes": cfg["niveis"]["nomes"],
            "placa": nome.replace(" ", "<br>") if nome.startswith("Muito") else nome,
            "rot": "risco normal" if nome == "Normal" else "do normal",
            "frase": "normal" if nome == "Normal" else f"{nome.lower()} do normal",
            "anterior": cfg["niveis"]["nomes"][n["anterior"]] if n.get("anterior") is not None else None,
            "pendente": n["nome_bruto"] if n.get("bruto") is not None and n["bruto"] != n["indice"] else None}


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
        frase = f"As notícias {quando} empurram {palavra}."
    return {"com": com, "sem": sem, "simbolo": simbolo, "cls": cls, "frase": frase, "n": pr.get("n", 0), "quando": quando}


# ------------------------------------------------------------------- fatores
def _regua(x: dict, cap: str) -> dict | None:
    """Régua de um indicador: a faixa normal, a zona de alerta e a agulha de hoje."""
    if x.get("valor") is None or not x.get("escala"):
        return None
    v, (lo, hi), (n0, n1) = x["valor"], x["escala"], x["faixa_normal"]
    lim = x["limite"] if x.get("peso") else None
    mn = min(lo, v, n0, lim if lim is not None else lo)
    mx = max(hi, v, n1, lim if lim is not None else hi)
    folga = (mx - mn) * 0.06 or 1
    mn, mx = mn - folga, mx + folga

    def pc(a: float) -> float:
        return round(100 * (a - mn) / (mx - mn), 1)

    alerta = None
    if lim is not None:
        alerta = (pc(lim), 100 - pc(lim)) if x["direcao"] > 0 else (0.0, pc(lim))
    d = 2 if abs(v) < 1 and x["unidade"] in ("p.p.", "p.p. do PIB") else 1
    return {"cap": cap, "normal": (pc(n0), round(pc(n1) - pc(n0), 1)), "alerta": alerta, "agulha": pc(v),
            "rot": sinal(v, d) if x["unidade"] in ("p.p.", "p.p. do PIB", "%") and x["id"] != "focus_pib" else num(v, d),
            "eixo": (num(mn, 1), num(mx, 1)), "aria": f"Hoje em {num(v, d)}, comparado à faixa normal e à zona de alerta"}


def _exibicao(fid: str, ind: dict) -> dict:
    """O valor grande do cartão, a legenda e as réguas de cada fator."""
    g = ind.get
    if fid == "atividade":
        x = g("ibcbr") or {}
        ref = x.get("ref")
        return {"valor": f"{sinal(x['valor'])}%" if x.get("valor") is not None else "Sem dado",
                "legenda": f"IBC-Br, {mes_curto(mes_antes(ref, 2))} a {mes_curto(ref)} contra os 3 meses anteriores" if ref else "",
                "hoje": f"IBC-Br {sinal(x['valor'])}% no trimestre" if x.get("valor") is not None else "Sem dado",
                "reguas": [r for r in (_regua(x, "IBC-Br: 3 meses contra os 3 anteriores, %"),
                                       _regua(g("focus_pib") or {}, "PIB esperado para os próximos 12 meses (Focus), %")) if r]}
    if fid == "juro":
        x = g("juro_real") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['valor'])}% ao ano" if ok else "Sem dado",
                "legenda": f"Selic de {num(x['selic'], 2)}% menos a inflação esperada em 12 meses ({num(x['inflacao_esperada'])}%)" if ok else "",
                "hoje": f"{num(x['valor'])}% ao ano" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Juro real ex-ante, % ao ano"),) if r]}
    if fid == "credito":
        x = g("comprometimento") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}% da renda" if ok else "Sem dado",
                "legenda": f"Parte da renda das famílias que vai para dívidas, {mes_nome(x['ref'])}" if ok else "",
                "hoje": f"{num(x['nivel'])}% da renda em dívidas" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Contra a média dos 3 anos anteriores, pontos"),) if r]}
    if fid == "mercado":
        x, d = g("tesouro") or {}, g("dolar") or {}
        ok = x.get("valor") is not None
        leg = f"Tesouro IPCA+ {(x.get('vencimento') or '')[:4]} em {dia_mes(x['ref'])}" if ok else ""
        if d.get("valor") is not None:
            leg += ("; " if leg else "") + f"dólar a R$ {num(d['nivel'], 2)} em {dia_mes(d['ref'])}"
        return {"valor": f"{num(x['nivel'], 2)}% ao ano" if ok else "Sem dado", "legenda": leg,
                "hoje": f"Tesouro IPCA+ a {num(x['nivel'], 2)}%" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Tesouro IPCA+ contra a mediana de 3 anos, pontos"),
                                       _regua(d, "Dólar, variação em 3 meses, %")) if r]}
    if fid == "contas":
        x = g("divida") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}% do PIB" if ok else "Sem dado",
                "legenda": f"Dívida bruta do governo geral, {mes_nome(x['ref'])}" if ok else "",
                "hoje": f"Dívida em {num(x['nivel'])}% do PIB" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Alta em 12 meses, pontos do PIB"),) if r]}
    if fid == "emprego":
        x = g("sahm") or {}
        ok = x.get("valor") is not None
        return {"valor": f"{num(x['nivel'])}%" if ok else "Sem dado",
                "legenda": f"Desemprego no trimestre até {mes_nome(x['ref'])} (PNAD)" if ok else "",
                "hoje": f"Desemprego em {num(x['nivel'])}%" if ok else "Sem dado",
                "reguas": [r for r in (_regua(x, "Regra de Sahm, pontos"),) if r]}
    x = g("commodities") or {}
    ok = x.get("valor") is not None
    return {"valor": f"{sinal(x['valor'])}%" if ok else "Sem dado",
            "legenda": f"Preço das commodities em 6 meses até {mes_nome(x['ref'])} (índice do FMI)" if ok else "",
            "hoje": f"Commodities {sinal(x['valor'])}% em 6 meses" if ok else "Sem dado",
            "reguas": [r for r in (_regua(x, "Variação em 6 meses, %"),) if r]}


def fatores_ctx(rodada: dict, cfg: dict) -> list[dict]:
    res = rodada["resultado"]
    ind = {x["id"]: x for x in res["indicadores"]}
    leit = (rodada.get("leituras") or {}).get("fatores", {})
    out = []
    for f in res["fatores"]:
        d = leit.get(f["id"], {})
        t = d.get("tendencia", "sem_direcao")
        cls, seta, palavra = TENDENCIAS[t]
        outros = d.get("outros") or {"tipo": "neutro", "texto": "", "fonte": None}
        mine = [ind[i] for i in f["indicadores"] if i in ind]
        na_conta = any(x.get("peso") for x in mine)
        if f.get("avisou"):
            a, n = f["avisou"]
            historico = f"{f['forca']}: alertou antes de {a} de {n} recessões medidas"
        else:
            motivos = sorted({x["motivo"] for x in mine if x.get("motivo")})
            historico = "Não antecipou as recessões desde 2002" + (f": {motivos[0]}" if len(motivos) == 1 else "")
        out.append({
            **f, **_exibicao(f["id"], ind), "chip": CHIPS[f["situacao"]], "tend": {"cls": cls, "seta": seta, "palavra": palavra, "id": t},
            "peso_rotulo": f["peso_rotulo"] if na_conta else "Não entra no nível", "na_conta": na_conta,
            "barra": round(100 * min(f["parte"] / 0.5, 1), 1), "como": d.get("como", ""),
            "historico": historico,
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


def gatilho_txt(g: dict, x: dict) -> str:
    """O que mudaria o nível, em palavras: 'dólar subir 18,8% em 3 meses'."""
    lim = g["limite"]
    return {
        "ibcbr": f"IBC-Br cair {num(abs(lim))}% no trimestre",
        "focus_pib": f"Focus esperar PIB abaixo de {num(lim)}% em 12 meses",
        "tesouro": f"Tesouro IPCA+ subir {num(lim, 2)} ponto acima da mediana de 3 anos",
        "dolar": f"dólar subir {num(lim)}% em 3 meses",
        "commodities": f"commodities caírem {num(abs(lim))}% em 6 meses",
        "juro_real": f"juro real passar de {num(lim)}%",
        "comprometimento": f"renda comprometida subir {num(lim)} ponto acima da média de 3 anos",
        "divida": f"dívida subir {num(lim)} pontos do PIB em 12 meses",
        "sahm": f"regra de Sahm passar de {num(lim)} ponto",
    }.get(g["id"], x.get("nome", g["id"]))


def pontos_ctx(fatores: list[dict], res: dict | None = None) -> list[dict]:
    """Os tópicos do topo do resumo."""
    pesam = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["peso_rotulo"] in ("Forte", "Moderado")] or \
            [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["parte"] > 0]
    piora = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "piora"]
    melhora = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "melhora"]
    estaveis = [CURTOS.get(f["id"], f["nome"]) for f in fatores if f["tend"]["id"] == "estavel"]
    disc = [f for f in fatores if f["outros"]["cls"] == "discorda"]
    out = [{"rot": "Pesam mais", "texto": (_juntar(pesam) + ".") if pesam else "Nenhum fator está na zona de alerta.", "cls": ""}]
    if piora:
        out.append({"rot": "Tendem a piorar", "texto": _juntar(piora) + ".", "cls": "mais"})
    if melhora:
        out.append({"rot": "Tendem a melhorar", "texto": _juntar(melhora) + ".", "cls": "menos"})
    if estaveis:
        out.append({"rot": "Estáveis", "texto": _juntar(estaveis) + ".", "cls": ""})
    if disc:
        quem = sorted({(f["outros"]["fonte"] or {}).get("veiculo", "").split(" ")[0] for f in disc} - {""})
        out.append({"rot": "Discordamos" + (f" do {quem[0]}" if len(quem) == 1 else ""),
                    "texto": _juntar([CURTOS.get(f["id"], f["nome"]) for f in disc]) + ".", "cls": ""})
    if res is not None:
        ind = {x["id"]: x for x in res["indicadores"]}
        g = res.get("gatilhos") or []
        sobe = [x for x in g if x["nivel"] > res["nivel"].get("bruto", res["nivel"]["indice"])]
        if sobe:
            txts = [gatilho_txt(x, ind.get(x["id"], {})) for x in sobe]
            quais = txts[0] if len(txts) == 1 else ", ".join(txts[:-1]) + " ou " + txts[-1]
            nomes = {x["nome_nivel"] for x in sobe}
            alvo = "um nível acima" if len(nomes) > 1 else "normal" if nomes == {"Normal"} else f"{nomes.pop().lower()} do normal"
            frase = f"{quais} levaria o risco a {alvo}."
            out.append({"rot": "Mudaria o nível", "cls": "", "texto": frase[0].upper() + frase[1:]})
        else:
            out.append({"rot": "Mudaria o nível", "cls": "", "texto": "Nenhum indicador sozinho muda o nível hoje."})
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
    """A tabela da página da conta: cada indicador com o valor de hoje, a faixa normal, o limite e o peso."""
    total = sum(x["peso"] for x in res["indicadores"]) or 1
    out = []
    for x in sorted(res["indicadores"], key=lambda x: (-x["peso"], x["nome"])):
        if x.get("peso"):
            hist = f"Alertou antes de {x['episodios_avisados']} de {x['episodios_na_amostra']} recessões"
        else:
            hist = (x.get("motivo") or "sem dado suficiente").capitalize()
        out.append({"id": x["id"], "nome": x["nome"], "fator": cfg["fatores"][x["fator"]], "definicao": x["definicao"],
                    "hoje": _fmt(x["valor"], x) if x.get("valor") is not None else "Sem dado",
                    "ref": x.get("ref"), "faixa": (f"{_fmt(x['faixa_normal'][0], x)} a {_fmt(x['faixa_normal'][1], x)}"
                                                   if x.get("faixa_normal") else "–"),
                    "limite": _fmt(x["limite"], x) if x.get("peso") and x.get("limite") is not None else "–",
                    "situacao": model.SITUACOES[x["situacao"]], "chip": CHIPS[x["situacao"]],
                    "peso": f"{round(100 * x['peso'] / total)}%" if x.get("peso") else "0", "historico": hist})
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
        autoria = f"Escrito por um modelo de linguagem (Claude) às {hora(rodada['gerado_em'])}, depois de ler {lidas}."
        rodape = "O texto não passa por revisão humana antes de publicar. Erros vão para"
    else:
        if niv["anterior"] and niv["anterior"] != niv["nome"]:
            sobe = rodada["resultado"]["nivel"]["indice"] > rodada["resultado"]["nivel"]["anterior"]
            titulo = f"Risco de recessão {'sobe' if sobe else 'cai'} para {niv['frase']}"
        else:
            titulo = f"Risco de recessão {'no normal' if niv['nome'] == 'Normal' else 'está ' + niv['frase']}"
        paragrafos = []
        autoria = (f"Atualização automática das {hora(rodada['gerado_em'])}, depois de ler {lidas}. "
                   "O texto do dia não saiu; ficam o nível e as notícias, organizados por código.")
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
    sub = ("Cada leitura é conferida em 6 meses contra o dado. Nenhuma conferida ainda." if not feitas else
           f"Cada leitura é conferida em 6 meses contra o dado. Até agora, {acertos} de {len(feitas)} acertaram.")
    return {"linhas": linhas, "sub": sub}


# ---------------------------------------------------------- histórico do nível
def svg_niveis(historico: list[dict], recessoes: list[dict], nomes: list[str]) -> str:
    """O nível mês a mês, como a conta teria dito sem ver o bloco de anos de cada mês, e as recessões."""
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

    out = [f'<svg viewBox="0 0 {w} {h}" class="hist" role="img" aria-label="Nível de risco mês a mês desde 2002, com as recessões">']
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


# --------------------------------------------------------------------- dados
def dados_publicos(rodada: dict, ctx: dict) -> dict:
    res = rodada["resultado"]
    leit = (rodada.get("leituras") or {}).get("fatores", {})
    return {
        "nivel": res["nivel"]["nome"], "escala": ctx["cfg"]["niveis"]["nomes"],
        "pergunta": ctx["cfg"]["pergunta"], "atualizado_em": rodada["gerado_em"],
        "fatores": [{"id": f["id"], "nome": f["nome"],
                     "peso_hoje": f["peso_rotulo"] if any(x["peso"] for x in res["indicadores"] if x["fator"] == f["id"])
                     else "Não entra no nível", "situacao": f["situacao_nome"],
                     "tendencia": leit.get(f["id"], {}).get("tendencia")} for f in res["fatores"]],
        "indicadores": [{"id": x["id"], "nome": x["nome"], "fator": x["fator"],
                         "valor": round(x["valor"], 4) if x.get("valor") is not None else None, "unidade": x["unidade"],
                         "ref": x.get("ref"), "situacao": model.SITUACOES[x["situacao"]],
                         "limite_de_alerta": round(x["limite"], 4) if x.get("peso") and x.get("limite") is not None else None,
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
                "tabela": indicadores_ctx(r["resultado"], cfg),
                "indicadores": r["resultado"]["indicadores"], "placar": placar_ctx(placar, cfg, dia),
                "datas": calendario.janela(agenda, dt.date.fromisoformat(dia)), "jornais": JORNAIS,
                "hora": hora(r["gerado_em"]), "atualizado_iso": r["gerado_em"],
                "link_inicio": base, "link_resumo": f"{base}resumo/", "link_nota": f"{base}nota/",
                "dia_antes": dias[pos - 1] if pos else None, "dia_depois": dias[pos + 1] if pos + 1 < len(dias) else None,
                "data_curta": data_curta, "data_extenso": data_extenso, "historico_svg": historico_svg,
                "og_url": f"{SITE}/og/{dia}.png", "dia_mes": dia_mes}

    abas = {"index.html": "inicio", "resumo.html": "resumo", "nota.html": "nota"}

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
    for t in textos:
        gravar(DOCS / "textos" / t["slug"], "index.html",
               {**ctx, "post": t, "permalink": True, "dia_antes": None, "dia_depois": None}, f"{SITE}{t['link']}")
    shutil.copy(DOCS / "og" / f"{dia}.png", DOCS / "og.png")

    met = markdown.markdown((ROOT / "METODOLOGIA.md").read_text(), extensions=["tables", "toc"])
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
    urls = [f"{SITE}/", f"{SITE}/resumo/", f"{SITE}/nota/", f"{SITE}/metodologia/"] \
        + [f"{SITE}/{d}/{s}" for d in dias for s in ("", "resumo/", "nota/")] + [f"{SITE}{t['link']}" for t in textos]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    print(f"site gerado em {DOCS} (nível {ctx['nivel']['nome']})")


if __name__ == "__main__":
    main()
