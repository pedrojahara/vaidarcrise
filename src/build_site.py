"""Gera o site estático em docs/ a partir dos registros em runs/.

A nota vai escrita no HTML (não carregada por JavaScript) para aparecer em
prévias de links e buscadores.
"""
from __future__ import annotations

import datetime as dt
import json
import math
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
CANAIS = {"fiscal": "Fiscal", "monetario": "Monetário", "externo": "Externo", "credito": "Crédito",
          "institucional": "Institucional", "oferta": "Oferta", "atividade": "Atividade", "mercado": "Mercado"}
# Em que pé está cada notícia, como o classificador marca. Por ora o estágio só rotula o post.
ESTAGIOS = {"dado": "Dado divulgado", "decidido": "Decisão tomada", "em_votacao": "Em votação",
            "anuncio": "Anúncio", "rumor": "Rumor"}
SECOES = [("dado", "Dados divulgados"), ("decidido", "Decisões tomadas"), ("em_votacao", "Propostas em votação"),
          ("anuncio", "Anúncios, sem ato formal"), ("rumor", "Rumores"), (None, "Notícias")]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
JORNAIS = "Folha, Valor, Estadão, g1, InfoMoney, Poder360, Agência Brasil e Gazeta do Povo"
SGS_URL = "https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do?method=prepararTelaLocalizarSeries"
FONTES_IND = {
    "atividade": ("BCB, série 24364", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24364/dados/ultimos/12?formato=json"),
    "trabalho": ("IBGE/BCB, série 24369", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24369/dados/ultimos/24?formato=json"),
    "juro_real": ("BCB, série 432 e Focus", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"),
    "familias": ("BCB, série 29034", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.29034/dados/ultimos/36?formato=json"),
    "fiscal": ("BCB, série 13762", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13762/dados/ultimos/13?formato=json"),
    "cambio": ("BCB, série 1 (PTAX)", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/64?formato=json"),
}


# ------------------------------------------------------------------ formatos
def num(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 and round(abs(x), d) != 0 else "") + s


def peso_fmt(x: float) -> str:
    """Peso do estágio: uma casa quando basta (0,3; 1,0), duas quando a chance de aprovar pede (0,65)."""
    return num(x, 1 if round(x, 1) == round(x, 2) else 2)


def sinal(x: float, d: int = 1) -> str:
    if round(x, d) == 0:
        return num(0, d)
    return ("+" if x > 0 else "−") + num(abs(x), d)


def data_longa(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}, às {d.hour}h{d.minute:02d}"


def data_curta(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def data_extenso(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def hora(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.hour:02d}h{d.minute:02d}"


def tri_extenso(rotulo: str) -> str:
    """'3T26' -> '3º trimestre de 2026'."""
    q, a = rotulo.split("T")
    return f"{q}º trimestre de 20{a}"


def fechar(valores: list[float], total: float, d: int = 1) -> list[float]:
    """Arredonda cada valor a `d` casas pelo maior resto, para a soma dar exatamente `total`."""
    if not valores:
        return []
    q = 10 ** d
    piso = [math.floor(v * q) for v in valores]
    falta = round(total * q) - sum(piso)
    ordem = sorted(range(len(valores)), key=lambda i: piso[i] - valores[i] * q)  # maior resto primeiro
    for k in range(abs(falta)):
        i = ordem[k % len(ordem)] if falta > 0 else ordem[-1 - k % len(ordem)]
        piso[i] += 1 if falta > 0 else -1
    return [p / q for p in piso]


def curto(s: str, n: int = 80) -> str:
    """Corta no fim de uma palavra: os títulos do LLM podem ter até 160 caracteres."""
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def ref_fmt(ref: str) -> str:
    if len(ref) == 7:
        a, m = ref.split("-")
        return f"{MESES[int(m) - 1][:3]}/{a}"
    return data_curta(ref)


# --------------------------------------------------------------------- SVGs
def svg_cascata(inicio: float, fim: float, partes: list[tuple[str, float]], rot_ini: str, rot_fim: str,
                do_zero: bool = False) -> str:
    """Cascata em HTML: cada linha é um fator; as barras flutuam do acumulado anterior.

    `do_zero` começa o eixo em 0, para a barra inicial não parecer menor do que é.
    """
    vals, acc = [inicio, fim], inicio
    for _, v in partes:
        acc += v
        vals.append(acc)
    lo = 0.0 if do_zero else max(0.0, min(vals) - 4)
    hi = min(100.0, max(vals) + 4)
    pc = lambda v: 100 * (v - lo) / (hi - lo)  # noqa: E731
    linhas = [f'<div class="cr tot"><span class="cn">{_esc(rot_ini)}</span><span class="ct">'
              f'<i style="left:0;width:{pc(inicio):.2f}%"></i></span><span class="cv">{num(inicio)}</span></div>']
    acc = inicio
    for nome, v in partes:
        a, b = acc, acc + v
        cls = "up" if v > 0 else "dn"
        linhas.append(f'<div class="cr {cls}"><span class="cn">{_esc(nome)}</span><span class="ct">'
                      f'<i style="left:{pc(min(a, b)):.2f}%;width:{max(pc(max(a, b)) - pc(min(a, b)), 0.4):.2f}%"></i></span>'
                      f'<span class="cv">{sinal(v)}</span></div>')
        acc = b
    linhas.append(f'<div class="cr tot"><span class="cn">{_esc(rot_fim)}</span><span class="ct">'
                  f'<i style="left:0;width:{pc(fim):.2f}%"></i></span><span class="cv">{num(fim)}</span></div>')
    return f'<div class="cascata" role="img" aria-label="Decomposição da nota">{"".join(linhas)}</div>'


def svg_historico(pontos: list[dict]) -> str:
    """O multiplicador ao longo do tempo, com a linha do normal (1×)."""
    w, h, x0, x1, y0, y1 = 480, 230, 34, 470, 15, 196
    topo = max(5.0, math.ceil(max(p["m"] for p in pontos)))
    py = lambda v: y1 - (y1 - y0) * v / topo  # noqa: E731
    datas = [dt.datetime.fromisoformat(p["gerado_em"]) for p in pontos]
    ini = min(datas)
    fim = max(max(datas), ini + dt.timedelta(days=30))
    span = (fim - ini).total_seconds()
    px = lambda d: x0 + (x1 - x0) * (d - ini).total_seconds() / span  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" class="hist" role="img" aria-label="Histórico do multiplicador">']
    for v in range(int(topo) + 1):
        out.append(f'<line x1="{x0}" y1="{py(v)}" x2="{x1}" y2="{py(v)}" class="{"g50" if v == 1 else "gl"}"/>'
                   f'<text x="{x0 - 8}" y="{py(v) + 4}" class="tl" text-anchor="end">{v}×</text>')
    pts = " ".join(f"{px(d):.1f},{py(p['m']):.1f}" for d, p in zip(datas, pontos))
    if len(pontos) > 1:
        out.append(f'<polyline points="{pts}" class="l1"/>')
    for d, p in zip(datas, pontos):
        out.append(f'<circle cx="{px(d):.1f}" cy="{py(p["m"]):.1f}" r="4" class="l1d"/>')
    out.append(f'<text x="{x0}" y="{h - 6}" class="tl">{data_curta(ini.isoformat())}</text>')
    out.append(f'<text x="{x1}" y="{h - 6}" class="tl" text-anchor="end">{data_curta(fim.isoformat())}</text>')
    out.append("</svg>")
    return "".join(out)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------ contexto
def rotulos(rodada: dict, eventos: dict) -> dict[str, str]:
    res = rodada["resultado"]
    r = {f"ind:{x['id']}": x["nome"] for x in res["indicadores"]}
    r.update({f"not:{k}": f"Notícia: {curto(e['titulo_evento'])}" for k, e in eventos.items()})
    r["not:outras"] = "Outras notícias"
    r["not:antigas"] = "Notícias de dias anteriores, perdendo força"
    r["calendario"] = "Trimestres já divulgados"
    v = rodada.get("variacao") or {}
    r["metodologia"] = f"Nova metodologia (v{v.get('versao_anterior', '?')} → v{rodada['modelo']['versao']})"
    return r


def multiplicador(rodada: dict) -> float:
    """Quantas vezes a chance de recessão nos próximos 4 trimestres está acima do normal."""
    return rodada["resultado"]["curto_prazo_4t"] / rodada["resultado"]["taxa_base_4t"]


def mult_fmt(m: float, d: int = 1) -> str:
    return num(m, d) + "×"


def seta(rodada: dict, todas: list[dict]) -> dict | None:
    """Compara com a rodada mais próxima de 30 dias atrás; com menos histórico, com a primeira.

    A seta só sai do "estável" se o multiplicador andar mais de 10%.
    """
    antes = [r for r in todas if r["gerado_em"] < rodada["gerado_em"]]
    if not antes:
        return None
    quando = lambda r: dt.datetime.fromisoformat(r["gerado_em"])  # noqa: E731
    alvo = quando(rodada) - dt.timedelta(days=30)
    ref = antes[0] if quando(antes[0]) > alvo else min(antes, key=lambda r: abs(quando(r) - alvo))
    razao = multiplicador(rodada) / multiplicador(ref)
    tipo = "sobe" if razao > 1.10 else "desce" if razao < 0.90 else "igual"
    return {"tipo": tipo, "simbolo": {"sobe": "↑", "desce": "↓", "igual": "→"}[tipo],
            "palavra": {"sobe": "piorando", "desce": "melhorando", "igual": "estável"}[tipo],
            "desde": ref["gerado_em"], "de": multiplicador(ref), "razao": razao}


def variacao_12m(rodada: dict, anterior: dict | None, cfg: dict) -> dict | None:
    """A variação da chance de 12 meses gravada na rodada; nas rodadas antigas, refeita com a regra de hoje."""
    if rodada.get("variacao_12m"):
        return rodada["variacao_12m"]
    if not anterior:
        return None
    v = model.decompor_variacao(anterior["resultado"], rodada["resultado"], anterior["insumos"]["pib"],
                                rodada["insumos"]["pib"], cfg, frozenset(rodada.get("eventos_novos", [])), horizonte=4)
    if anterior["modelo"]["versao"] != rodada["modelo"]["versao"]:
        v["versao_anterior"] = anterior["modelo"]["versao"]
    return v


def contexto(rodada: dict, todas: list[dict], eventos_lista: list[dict], casos: dict | None, cfg: dict) -> dict:
    """`todas` são as rodadas até esta, inclusive."""
    res = rodada["resultado"]
    eventos = {e["id"]: e for e in eventos_lista}
    rot = rotulos(rodada, eventos)
    nota = 100 * res["manchete"]
    estr = res["estrutura"]
    curto_, normal = 100 * res["curto_prazo_4t"], 100 * res["taxa_base_4t"]
    m = multiplicador(rodada)

    # De onde vem a chance de 12 meses: do normal até a de hoje, cada fator em pontos, somando na tela.
    sh = model.decompor_12m(res, cfg)
    chaves = sorted(sh, key=lambda k: -abs(sh[k]))
    pts = dict(zip(chaves, fechar([sh[k] for k in chaves], round(curto_, 1) - round(normal, 1))))
    cascata = svg_cascata(normal, curto_, [(rot.get(k, k), pts[k]) for k in chaves], "Normal",
                          "Hoje", do_zero=True) if chaves else ""

    anterior = todas[-2] if len(todas) > 1 else None
    v = variacao_12m(rodada, anterior, cfg)
    variacao = None
    if v:
        vp = sorted(((rot.get(k, k), x) for k, x in v["partes"].items()), key=lambda x: -abs(x[1]))
        delta = round(v["para"], 1) - round(v["de"], 1)
        vp = list(zip([n for n, _ in vp], fechar([x for _, x in vp], delta)))
        variacao = {"de": v["de"], "para": v["para"], "delta": delta, "partes": vp,
                    "de_m": v["de"] / (100 * anterior["resultado"]["taxa_base_4t"]), "versao_anterior": v.get("versao_anterior"),
                    "svg": svg_cascata(v["de"], v["para"], vp, "Atualização anterior", "Hoje") if vp else ""}

    hoje = dt.date.fromisoformat(rodada["gerado_em"][:10])
    inds = []
    for x in res["indicadores"]:
        fonte = FONTES_IND.get(x["id"], ("BCB", SGS_URL))
        inds.append({**x, "valor_fmt": f"{sinal(x['valor'], 2) if x['id'] in ('atividade', 'trabalho', 'familias', 'fiscal', 'cambio') else num(x['valor'], 2)} {x['unidade']}",
                     "ref_fmt": ref_fmt(x["ref"]), "pts": pts.get(f"ind:{x['id']}", 0.0),
                     "fonte_nome": fonte[0], "fonte_url": fonte[1]})
    inds.sort(key=lambda x: -abs(x["pts"]))

    evs = []
    for x in res["noticias"]:
        e = eventos.get(x["id"], x)
        fim = dt.date.fromisoformat(e["data"]) + dt.timedelta(days=cfg["noticias"]["dias_de_decaimento"])
        evs.append({**e, "canal_nome": CANAIS.get(e["canal"], e["canal"]),
                    "pts": pts.get(f"not:{x['id']}"), "logit": x["logit"], "vale_ate": data_curta(fim.isoformat()),
                    "data_fmt": data_curta(e["data"]), "dias": (hoje - dt.date.fromisoformat(e["data"])).days})
    evs.sort(key=lambda x: -abs(x["logit"]))

    focus = rodada["insumos"].get("focus", {}).get("PIB Total", [])
    pontos = [{"gerado_em": r["gerado_em"], "m": multiplicador(r)} for r in todas]
    placar = []
    vistos = set()
    for r in todas:
        inicios = r["resultado"]["estrutura"]["inicios"]
        if not inicios:
            continue
        chave = inicios[0]
        if chave in vistos:
            continue
        vistos.add(chave)
        ate = inicios[min(3, len(inicios) - 1)]
        placar.append({"data": data_curta(r["gerado_em"]), "prob": 100 * r["resultado"]["curto_prazo_4t"],
                       "de": inicios[0], "ate": ate, "vence": "quando o IBGE divulgar o "
                       + model.label(*model.prox(*model.tri(ate))), "status": "em aberto"})

    # A chance até 2030 aparece como faixa: o período histórico usado como âncora muda o número.
    alt = sorted(100 * a["manchete"] for a in res["alternativas"])
    cen = rodada.get("cenarios") or []
    if cen and "curto_prazo_4t" not in cen[0]:  # rodadas de antes da v1.2 não gravaram o cenário de 12 meses
        cen = model.cenarios_pib({"pib": rodada["insumos"]["pib"]}, res, cfg)
    cenarios = [{**c, "m": c["curto_prazo_4t"] / res["taxa_base_4t"]} for c in cen]
    return {
        "site": SITE, "repo": REPO, "rodada": rodada, "cfg": cfg,
        "nota": nota, "nota_int": int(round(nota)), "nota_fmt": num(nota), "faixa_2030": [alt[0], alt[-1]],
        "curto": curto_, "normal": normal, "mult": m, "mult_fmt": mult_fmt(m), "seta": seta(rodada, todas),
        "atualizado": data_longa(rodada["gerado_em"]), "atualizado_iso": rodada["gerado_em"],
        "dia": rodada["gerado_em"][:10], "pts12": pts, "cascata": cascata, "n_fatores": len(chaves),
        "ind_pts": sum(v for k, v in pts.items() if k.startswith("ind:")),
        "not_pts": sum(v for k, v in pts.items() if k.startswith("not:")),
        "variacao": variacao, "indicadores": inds, "eventos": evs, "casos": casos,
        "cenarios": cenarios, "focus": focus, "historico": svg_historico(pontos),
        "n_rodadas": len(pontos), "placar": placar, "estrutura": estr, "em_revisao": rodada.get("em_revisao"),
        "llm_ok": rodada["llm"]["ok"], "num": num, "sinal": sinal, "data_curta": data_curta,
        "mult_fmt_f": mult_fmt, "h0": 100 * res["h0"], "estagios": ESTAGIOS,
        "n_ind": len(res["indicadores"]), "n_not": len(res["noticias"]),
    }


# ------------------------------------------------------------- post do dia
def conta_do_dia(rodada: dict, eventos: dict, anterior: dict | None, cfg: dict) -> dict | None:
    """A variação do multiplicador repartida entre as notícias novas (uma a uma) e o resto (em grupos).

    É a mesma conta que o post mostra e que o LLM recebe para escrever. Os pontos de
    Shapley da chance de 12 meses viram multiplicador ao dividir pelo normal de hoje; se
    o normal mudou (troca de versão), a diferença entra em "Nova metodologia". Tudo é
    arredondado pelo maior resto, para a soma fechar com a variação exibida.
    """
    v = variacao_12m(rodada, anterior, cfg)
    if not v:
        return None
    normal = 100 * rodada["resultado"]["taxa_base_4t"]
    de_m, para_m = multiplicador(anterior), multiplicador(rodada)
    partes = {k: x / normal for k, x in v["partes"].items()}
    resto = (para_m - de_m) - sum(partes.values())
    if abs(resto) > 1e-9:
        partes["metodologia"] = partes.get("metodologia", 0.0) + resto
    novos = set(rodada.get("eventos_novos", []))
    itens, grupos = [], {}
    for k, x in partes.items():
        if k.startswith("not:") and k[4:] in novos:
            e = eventos.get(k[4:], {})
            itens.append({"id": k[4:], "titulo": e.get("titulo_evento", k), "porque": e.get("porque", ""),
                          "estagio": e.get("estagio"), "origem": e.get("origem"), "fontes": e.get("fontes", []),
                          "peso": e.get("peso_estagio"), "bruto": x})
        else:
            g = "ind" if k.startswith("ind:") else "outras" if k == "not:outras" else \
                "antigas" if k.startswith("not:") else k
            grupos.setdefault(g, []).append((k, x))
    rot = rotulos(rodada, eventos)
    nomes = {"ind": "Indicadores do Banco Central e do IBGE", "antigas": rot["not:antigas"],
             "outras": rot["not:outras"], "calendario": rot["calendario"],
             "metodologia": f"Nova metodologia (v{anterior['modelo']['versao']} → v{rodada['modelo']['versao']})"}
    outros = [{"chave": g, "nome": nomes.get(g, g), "bruto": sum(x for _, x in lst), "partes": lst}
              for g, lst in grupos.items()]
    delta = round(para_m, 2) - round(de_m, 2)
    for it, pt in zip(itens + outros, fechar([it["bruto"] for it in itens] + [g["bruto"] for g in outros], delta, 2)):
        it["pts"] = pt
    for g in outros:
        if g["chave"] == "ind" and len(g["partes"]) > 1:
            det = fechar([x for _, x in g["partes"]], g["pts"], 2)
            g["detalhe"] = sorted(((rot.get(k, k), pt) for (k, _), pt in zip(g["partes"], det) if pt),
                                  key=lambda t: -abs(t[1]))
        if g["chave"] == "antigas":
            g["nota"] = "O efeito de cada notícia cai em linha reta até zero em 75 dias."
    itens.sort(key=lambda it: -abs(it["pts"]))
    descartados = rodada.get("eventos_descartados", [])
    return {"de": de_m, "para": para_m, "delta": delta, "itens": itens,
            "secoes": [(nome, lst) for est, nome in SECOES if (lst := [it for it in itens if it["estagio"] == est])],
            "outros": sorted([g for g in outros if g["pts"]], key=lambda g: -abs(g["pts"])),
            "repetidos": [d for d in descartados if d.get("motivo") == "já medido pelos indicadores"],
            "duplicados": [d for d in descartados if str(d.get("motivo", "")).startswith("mesmo fato")]}


def post_de(rodada: dict, eventos: dict, anterior: dict | None, cfg: dict) -> dict:
    """O post de um dia. Sem texto do LLM (dias antigos ou falha), sai só a conta, dita por código."""
    dia = rodada["gerado_em"][:10]
    conta = conta_do_dia(rodada, eventos, anterior, cfg)
    nots = rodada["insumos"]["noticias"]
    n, k = nots["n_itens"], len(nots.get("por_veiculo", {}))
    dias = (rodada.get("cobertura") or {}).get("dias", [])
    lidas = (f"{n} manchetes de {k} jornais publicadas em {', '.join(data_curta(d)[:5] for d in dias)}" if dias
             else f"{n} manchetes de {k} jornais")
    p = rodada.get("post") or {}
    novos = len(rodada.get("eventos_novos", []))
    m = multiplicador(rodada)
    if p.get("ok"):
        titulo, paragrafos, abre = p["titulo"], p["paragrafos"], None
        autoria = f"Escrito por um modelo de linguagem (Claude) às {hora(rodada['gerado_em'])}, depois de ler {lidas}."
        rodape = ("O risco e os pontos saem de código com pesos publicados; o texto não passa por revisão humana "
                  "antes de publicar. Erros vão para")
    else:
        if conta and round(conta["de"], 1) != round(conta["para"], 1):
            titulo = f"O risco foi de {mult_fmt(conta['de'])} para {mult_fmt(conta['para'])} o normal"
        else:
            titulo = f"O risco ficou em {mult_fmt(m)} o normal"
        if novos:
            titulo += f" com {novos} {'notícia nova' if novos == 1 else 'notícias novas'}"
        paragrafos = []
        abre = f"Foram lidas {lidas}." + (" Nenhuma entrou na conta." if not novos and rodada["llm"]["ok"] else "")
        if "post" in rodada:
            autoria = (f"Atualização automática das {hora(rodada['gerado_em'])}. O texto do dia não saiu, "
                       "então fica só a conta, feita por código.")
        else:
            autoria = (f"Atualização automática das {hora(rodada['gerado_em'])}, de antes do post diário: "
                       "só a conta, feita por código.")
        rodape = "Erros vão para"
    return {"dia": dia, "data_extenso": data_extenso(dia), "titulo": titulo, "paragrafos": paragrafos, "abre": abre,
            "autoria": autoria, "rodape": rodape, "conta": conta, "mult": m, "llm": bool(p.get("ok")),
            "link": f"/{dia}/", "registro": f"{REPO}/blob/main/runs/{rodada['id']}.json",
            "llm_ok": rodada["llm"]["ok"]}


def textos_do_editor() -> list[dict]:
    """Textos escritos à mão em editor/*.md: cabeçalho 'chave: valor', uma linha '---' e o corpo em Markdown."""
    out = []
    for arq in sorted((ROOT / "editor").glob("*.md")):
        cab, corpo = arq.read_text().split("\n---\n", 1)
        meta = {k.strip(): v.strip() for k, v in (linha.split(":", 1) for linha in cab.strip().splitlines())}
        slug = arq.stem[11:] if arq.stem[:10] == meta["data"] else arq.stem
        out.append({"dia": meta["data"], "data_extenso": data_extenso(meta["data"]), "titulo": meta["titulo"],
                    "corpo_html": markdown.markdown(corpo), "paragrafos": [], "abre": None, "conta": None,
                    "tags": meta.get("tags", ""), "editor": True, "link": f"/textos/{slug}/", "slug": slug,
                    "llm_ok": True})
    return sorted(out, key=lambda t: t["dia"], reverse=True)


def dados_publicos(rodada: dict, ctx: dict) -> dict:
    res = rodada["resultado"]
    s = ctx["seta"]
    return {
        "multiplicador_12m": round(ctx["mult"], 3), "normal_12m": round(res["taxa_base_4t"], 4),
        "probabilidade_proximos_4_trimestres": round(res["curto_prazo_4t"], 4),
        "seta": s["palavra"] if s else None, "seta_desde": s["desde"] if s else None,
        "seta_razao": round(s["razao"], 3) if s else None,
        "fatores_12m_pontos": {k: round(v, 2) for k, v in ctx["pts12"].items()},
        "probabilidade_recessao_ate_4T30": round(res["manchete"], 4), "nota": round(ctx["nota"], 1),
        "probabilidade_ate_4T30_faixa": [round(x / 100, 4) for x in ctx["faixa_2030"]],
        "risco_trimestral_base": res["h0"],
        "atualizado_em": rodada["gerado_em"],
        "versao_modelo": rodada["modelo"]["versao"], "regra": ctx["cfg"]["regra_de_resolucao"],
        "indicadores": [{k: x[k] for k in ("id", "nome", "valor", "unidade", "ref", "logit")} for x in res["indicadores"]],
        "noticias": [{"id": x["id"], "titulo": x["titulo_evento"], "logit": round(x["logit"], 4), "data": x["data"],
                      "estagio": x.get("estagio"), "origem": x.get("origem")} for x in res["noticias"]],
        "registro_completo": f"{REPO}/blob/main/runs/{rodada['id']}.json",
    }


def main() -> None:
    cfg = model.carregar_config()
    todas = [json.loads(p.read_text()) for p in sorted((ROOT / "runs").glob("*.json"))]
    if not todas:
        print("nenhuma rodada em runs/")
        return
    eventos = json.loads((ROOT / "data" / "eventos.json").read_text()) if (ROOT / "data" / "eventos.json").exists() else []
    idx = {e["id"]: e for e in eventos}
    casos_p = ROOT / "data" / "casos.json"
    casos = json.loads(casos_p.read_text()) if casos_p.exists() else None
    agenda = calendario.carregar()

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["num"] = num
    env.filters["sinal"] = sinal
    env.filters["peso"] = peso_fmt
    env.filters["mult"] = mult_fmt

    DOCS.mkdir(exist_ok=True)
    (DOCS / "og").mkdir(exist_ok=True)
    ultima = todas[-1]
    # Um post e um link permanente por dia: a última rodada do dia.
    por_dia = {}
    for r in todas:
        por_dia[r["gerado_em"][:10]] = r
    dias = sorted(por_dia)

    def anterior(r: dict) -> dict | None:
        i = next(k for k, x in enumerate(todas) if x["id"] == r["id"])
        return todas[i - 1] if i else None

    posts = {d: post_de(por_dia[d], idx, anterior(por_dia[d]), cfg) for d in dias}
    lista = [{"dia": d, "data": data_curta(d)[:5], "mult": posts[d]["mult"], "titulo": posts[d]["titulo"],
              "link": f"/{d}/"} for d in reversed(dias)]
    textos = textos_do_editor()
    # O texto do editor mais recente fica inteiro na página inicial; os outros vão para a lista.
    destaque = textos[0] if textos else None
    arquivo = sorted(lista[1:] + [{"dia": t["dia"], "data": data_curta(t["dia"])[:5], "mult": None,
                                   "titulo": t["titulo"], "link": t["link"]} for t in textos[1:]],
                     key=lambda x: x["dia"], reverse=True)

    def comum(dia: str, ctx: dict, link_nota: str) -> dict:
        pos = dias.index(dia)
        datas = calendario.janela(agenda, dt.date.fromisoformat(dia))
        # A próxima divulgação do PIB ganha destaque, com o risco em cada cenário.
        pib = next((x for x in datas if x["tipo"] == "pib"), None)
        if pib and ctx["cenarios"]:
            pib["cenarios"] = ctx["cenarios"]
        return {**ctx, "post": posts[dia], "link_nota": link_nota, "datas": datas,
                "pib_data": f"{int(pib['data'][8:])} de {MESES[int(pib['data'][5:7]) - 1]}" if pib else None,
                "dia_antes": dias[pos - 1] if pos else None, "dia_depois": dias[pos + 1] if pos + 1 < len(dias) else None,
                "data_extenso": data_extenso, "tri_extenso": tri_extenso, "hora": hora(ctx["atualizado_iso"]),
                "jornais": JORNAIS}

    for dia, r in por_dia.items():
        hist = [x for x in todas if x["gerado_em"] <= r["gerado_em"]]
        ctx = contexto(r, hist, eventos, casos, cfg)
        og = DOCS / "og" / f"{dia}.png"
        if not og.exists() or r is ultima:
            og_image.gerar(og, ctx)
        ctx = comum(dia, ctx, f"/{dia}/nota/")
        ctx.update({"og_url": f"{SITE}/og/{dia}.png", "permalink": True})
        (DOCS / dia / "nota").mkdir(parents=True, exist_ok=True)
        (DOCS / dia / "index.html").write_text(env.get_template("index.html").render(
            **ctx, canonical=f"{SITE}/{dia}/"))
        (DOCS / dia / "nota" / "index.html").write_text(env.get_template("nota.html").render(
            **ctx, canonical=f"{SITE}/{dia}/nota/"))

    dia = ultima["gerado_em"][:10]
    ctx = comum(dia, contexto(ultima, todas, eventos, casos, cfg), "/nota/")
    ctx.update({"og_url": f"{SITE}/og/{dia}.png", "permalink": False})
    (DOCS / "index.html").write_text(env.get_template("index.html").render(
        **{**ctx, "anteriores": arquivo, "destaque": destaque}, canonical=f"{SITE}/"))
    (DOCS / "nota").mkdir(exist_ok=True)
    (DOCS / "nota" / "index.html").write_text(env.get_template("nota.html").render(**ctx, canonical=f"{SITE}/nota/"))
    for t in textos:
        (DOCS / "textos" / t["slug"]).mkdir(parents=True, exist_ok=True)
        (DOCS / "textos" / t["slug"] / "index.html").write_text(env.get_template("index.html").render(
            **{**ctx, "post": t, "permalink": True, "dia_antes": None, "dia_depois": None},
            canonical=f"{SITE}{t['link']}"))
    shutil.copy(DOCS / "og" / f"{dia}.png", DOCS / "og.png")

    met = markdown.markdown((ROOT / "METODOLOGIA.md").read_text(), extensions=["tables", "toc"])
    (DOCS / "metodologia").mkdir(exist_ok=True)
    (DOCS / "metodologia" / "index.html").write_text(env.get_template("pagina.html").render(
        titulo="Metodologia", corpo=met, canonical=f"{SITE}/metodologia/", og_url=f"{SITE}/og.png", site=SITE,
        repo=REPO, cfg=cfg))

    publico = dados_publicos(ultima, ctx)
    publico["post_do_dia"] = {"titulo": posts[dia]["titulo"], "url": f"{SITE}/{dia}/",
                              "escrito_por_llm": posts[dia]["llm"]}
    (DOCS / "data.json").write_text(json.dumps(publico, ensure_ascii=False, indent=1))
    (DOCS / "historico.json").write_text(json.dumps(
        [{"id": r["id"], "gerado_em": r["gerado_em"], "multiplicador_12m": round(multiplicador(r), 3),
          "proximos_4_trimestres": round(100 * r["resultado"]["curto_prazo_4t"], 1),
          "nota": round(100 * r["resultado"]["manchete"], 1)} for r in todas], indent=1))
    (DOCS / "CNAME").write_text("vaidarcrise.com.br")
    (DOCS / ".nojekyll").touch()
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [f"{SITE}/", f"{SITE}/nota/", f"{SITE}/metodologia/"] + [f"{SITE}/{d}/" for d in dias] \
        + [f"{SITE}/{d}/nota/" for d in dias] + [f"{SITE}{t['link']}" for t in textos]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    print(f"site gerado em {DOCS} (risco {ctx['mult_fmt']} o normal; nota até 2030 {ctx['nota_fmt']})")


if __name__ == "__main__":
    main()
