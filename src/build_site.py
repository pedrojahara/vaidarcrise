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
def svg_medidor(nota: float, base: float) -> str:
    """Medidor em HTML/CSS: legível no celular, sem texto encolhido de SVG."""
    ticks = "".join(f'<span class="tq" style="left:{v}%">{v}</span>' for v in (0, 25, 50, 75, 100))
    return (f'<div class="medidor" role="img" aria-label="Nota {num(nota, 0)} de 100; taxa histórica {num(base, 0)}">'
            f'<span class="hb" style="left:{base:.2f}%">história: {num(base, 0)}</span>'
            f'<div class="trilho"><span class="lb" style="left:{base:.2f}%"></span>'
            f'<span class="pt" style="left:{nota:.2f}%"></span></div>'
            f'<div class="tqs">{ticks}</div><p class="cc">50 = cara ou coroa</p></div>')


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
    w, h, x0, x1, y0, y1 = 480, 230, 34, 470, 15, 196
    py = lambda v: y1 - (y1 - y0) * v / 100  # noqa: E731
    datas = [dt.datetime.fromisoformat(p["gerado_em"]) for p in pontos]
    ini = min(datas)
    fim = max(max(datas), ini + dt.timedelta(days=30))
    span = (fim - ini).total_seconds()
    px = lambda d: x0 + (x1 - x0) * (d - ini).total_seconds() / span  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" class="hist" role="img" aria-label="Histórico da nota">']
    for v in (0, 25, 50, 75, 100):
        out.append(f'<line x1="{x0}" y1="{py(v)}" x2="{x1}" y2="{py(v)}" class="{"g50" if v == 50 else "gl"}"/>'
                   f'<text x="{x0 - 8}" y="{py(v) + 4}" class="tl" text-anchor="end">{v}</text>')
    for serie, cls in (("manchete", "l1"), ("curto", "l2")):
        pts = " ".join(f"{px(d):.1f},{py(100 * p[serie]):.1f}" for d, p in zip(datas, pontos))
        if len(pontos) > 1:
            out.append(f'<polyline points="{pts}" class="{cls}"/>')
        for d, p in zip(datas, pontos):
            out.append(f'<circle cx="{px(d):.1f}" cy="{py(100 * p[serie]):.1f}" r="4" class="{cls}d"/>')
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
    r["calendario"] = "Trimestres já divulgados"
    v = rodada.get("variacao") or {}
    r["metodologia"] = f"Nova metodologia (v{v.get('versao_anterior', '?')} → v{rodada['modelo']['versao']})"
    return r


def contexto(rodada: dict, todas: list[dict], eventos_lista: list[dict], casos: dict | None, cfg: dict) -> dict:
    res = rodada["resultado"]
    eventos = {e["id"]: e for e in eventos_lista}
    rot = rotulos(rodada, eventos)
    nota = 100 * res["manchete"]
    estr = res["estrutura"]
    # Só a história com o calendário de hoje: é a mesma conta da barra "Só a história".
    base = 100 * model.prob(estr, 0.0, res["h0"], cfg)
    hz = res.get("por_horizonte") or model.por_horizonte(res, cfg)
    pq = parcelas(nota, base, hz, res.get("shapley_perto") or model.decompor_perto(res, cfg), estr, rot,
                  len(res["indicadores"]), len(res["noticias"]))

    variacao = None
    if rodada.get("variacao"):
        v = rodada["variacao"]
        vp = sorted(((rot.get(k, k), x) for k, x in v["partes"].items()), key=lambda x: -abs(x[1]))
        # A variação exibida é a diferença das notas como aparecem (1 casa), para a conta fechar na tela.
        variacao = {"de": v["de"], "para": v["para"], "delta": round(v["para"], 1) - round(v["de"], 1), "partes": vp,
                    "versao_anterior": v.get("versao_anterior"),
                    "svg": svg_cascata(v["de"], v["para"], vp, "Nota anterior", "Nota de hoje") if vp else ""}

    hoje = dt.date.fromisoformat(rodada["gerado_em"][:10])
    inds = []
    for x in res["indicadores"]:
        fonte = FONTES_IND.get(x["id"], ("BCB", SGS_URL))
        inds.append({**x, "valor_fmt": f"{sinal(x['valor'], 2) if x['id'] in ('atividade', 'trabalho', 'familias', 'fiscal', 'cambio') else num(x['valor'], 2)} {x['unidade']}",
                     "ref_fmt": ref_fmt(x["ref"]), "pts": pq["pts"].get(f"ind:{x['id']}", 0.0),
                     "fonte_nome": fonte[0], "fonte_url": fonte[1]})
    inds.sort(key=lambda x: -abs(x["pts"]))

    evs = []
    for x in res["noticias"]:
        e = eventos.get(x["id"], x)
        fim = dt.date.fromisoformat(e["data"]) + dt.timedelta(days=cfg["noticias"]["dias_de_decaimento"])
        evs.append({**e, "canal_nome": CANAIS.get(e["canal"], e["canal"]),
                    "pts": pq["pts"].get(f"not:{x['id']}"), "logit": x["logit"], "vale_ate": data_curta(fim.isoformat()),
                    "data_fmt": data_curta(e["data"]), "dias": (hoje - dt.date.fromisoformat(e["data"])).days})
    evs.sort(key=lambda x: -abs(x["logit"]))

    focus = rodada["insumos"].get("focus", {}).get("PIB Total", [])
    pontos = [{"gerado_em": r["gerado_em"], "manchete": r["resultado"]["manchete"],
               "curto": r["resultado"]["curto_prazo_4t"], "id": r["id"]} for r in todas]
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

    # Páginas de dias antigos mostram a régua da versão em que foram calculadas.
    mesma_versao = rodada["modelo"]["versao"] == cfg["versao"]
    metodos = [{"nome": m["nome"], "h": 100 * m["risco_trimestral"],
                "base": 100 * model.prob(estr, 0.0, m["risco_trimestral"], cfg)}
               for m in cfg["taxa_base"].get("metodos", [])] if mesma_versao else []
    faixa = res.get("taxa_base_faixa")
    if mesma_versao and cfg["taxa_base"].get("faixa"):
        faixa = [model.prob(estr, 0.0, cfg["taxa_base"]["faixa"][k], cfg) for k in ("min", "max")]
    return {
        "site": SITE, "repo": REPO, "rodada": rodada, "cfg": cfg,
        "nota": nota, "nota_int": int(round(nota)), "nota_fmt": num(nota), "curto": 100 * res["curto_prazo_4t"],
        "base": base, "base_4t": 100 * res["taxa_base_4t"], "alternativas": res["alternativas"],
        "atualizado": data_longa(rodada["gerado_em"]), "atualizado_iso": rodada["gerado_em"],
        "dia": rodada["gerado_em"][:10], "medidor": svg_medidor(nota, base), "pq": pq,
        "variacao": variacao, "indicadores": inds, "eventos": evs, "casos": casos,
        "cenarios": rodada.get("cenarios", []), "focus": focus, "historico": svg_historico(pontos),
        "n_rodadas": len(pontos), "placar": placar, "estrutura": estr, "em_revisao": rodada.get("em_revisao"),
        "llm_ok": rodada["llm"]["ok"], "riscos": res["risco_trimestral"],
        "num": num, "sinal": sinal, "data_curta": data_curta,
        "horizonte": hz, "metodos": metodos, "h0": 100 * res["h0"],
        "n_ind": len(res["indicadores"]), "n_not": len(res["noticias"]),
        "faixa_base": [100 * x for x in faixa] if faixa else None,
    }


def parcelas(nota: float, historia: float, hz: dict, sh: dict[str, float], estr: dict, rot: dict,
             n_ind: int, n_not: int) -> dict:
    """A nota em três parcelas: história até o horizonte, dados e notícias, história depois.

    É a única decomposição da página. Os inteiros das barras saem de arredondamentos
    acumulados e os fatores da cascata, do maior resto, para toda soma fechar na tela.
    """
    simples = estr["resolvido"] or not hz["n"]
    out = {"simples": simples, "pts": {}, "sh": sh, "pendente": estr["pendente_negativo"], "n": hz["n"]}
    if simples:
        return out
    perto, perto_base = 100 * hz["perto"], 100 * hz["perto_base"]
    i_base, i_perto, i_nota, i_hist = (int(round(x)) for x in (perto_base, perto, nota, historia))
    presente, depois, depois_hist = i_perto - i_base, i_nota - i_perto, i_hist - i_base
    ini, fim = round(perto_base, 1), round(perto, 1)
    chaves = sorted(sh, key=lambda k: -abs(sh[k]))
    pts = dict(zip(chaves, fechar([sh[k] for k in chaves], fim - ini)))
    ate = _ate(hz["ate"])
    so_hist = [(i_base, "h"), (depois_hist, "h2")]
    # Se dados e notícias reduzem o risco, a parcela de perto encolhe: a barra nunca ganha segmento negativo.
    hoje = [(i_base, "h"), (presente, "p"), (depois, "h2")] if presente >= 0 else [(i_perto, "m"), (depois, "h2")]
    tem_depois = len(estr["inicios"]) > hz["n"]
    out.update({
        "ate_fmt": ate, "de": estr["inicios"][0], "ate": hz["ate"], "depois_fmt": _depois(hz["ate"], estr["inicios"][-1]),
        "chegada": _chegada(hz["ate"]),
        "base": i_base, "perto": i_perto, "presente": presente, "depois": depois, "depois_hist": depois_hist,
        "historia": i_hist, "nota": i_nota, "tira": depois_hist - depois, "liquido": i_nota - i_hist,
        "sobram": 100 - i_perto, "cond": 100 * hz["depois"] / (1 - hz["perto"]) if hz["perto"] < 1 else 0.0,
        "tem_depois": tem_depois, "pts": pts, "sujeito": _sujeito(n_ind, n_not), "plural": n_ind + n_not > 1,
        "ind_pts": sum(v for k, v in pts.items() if k.startswith("ind:")),
        "not_pts": sum(v for k, v in pts.items() if k.startswith("not:")),
        "barras": [{"nome": "Só a história", "total": i_hist, "segs": so_hist},
                   {"nome": "Hoje", "total": i_nota, "segs": hoje}],
        "cascata": svg_cascata(ini, fim, [(rot.get(k, k), pts[k]) for k in chaves],
                               f"História, {ate}", f"Com os dados de hoje, {ate}", do_zero=True),
    })
    return out


def _sujeito(n_ind: int, n_not: int) -> str:
    partes = []
    if n_ind:
        partes.append(f"os {n_ind} indicadores" if n_ind > 1 else "o único indicador disponível")
    if n_not:
        partes.append(f"as {n_not} notícias valendo agora" if n_not > 1 else "a única notícia valendo agora")
    s = " e ".join(partes)
    return s[:1].upper() + s[1:]


def _depois(ate: str, ultimo: str) -> str:
    """O pedaço da janela depois do horizonte: 'de 2028 a 2030'."""
    a, q = model.prox(*model.tri(ate))
    fim = model.tri(ultimo)[0]
    if q == 1:
        return f"em {a}" if a == fim else f"de {a} a {fim}"
    return f"do {q}º trimestre de {a} até {fim}"


def _chegada(ate: str) -> str:
    """O primeiro trimestre depois do horizonte: 'a 2028' ou 'ao 2º trimestre de 2028'."""
    a, q = model.prox(*model.tri(ate))
    return f"a {a}" if q == 1 else f"ao {q}º trimestre de {a}"


def _ate(rotulo: str | None) -> str:
    """'4T27' -> 'até o fim de 2027'; '2T27' -> 'até o 2º trimestre de 2027'."""
    if not rotulo:
        return ""
    q, a = rotulo.split("T")
    return f"até o fim de 20{a}" if q == "4" else f"até o {q}º trimestre de 20{a}"


def dados_publicos(rodada: dict, ctx: dict) -> dict:
    res = rodada["resultado"]
    return {
        "nota": round(ctx["nota"], 1), "probabilidade_recessao_ate_4T30": round(res["manchete"], 4),
        "probabilidade_proximos_4_trimestres": round(res["curto_prazo_4t"], 4),
        "taxa_base": round(ctx["base"] / 100, 4),
        "taxa_base_faixa": [round(x / 100, 4) for x in ctx["faixa_base"]] if ctx["faixa_base"] else None,
        "risco_trimestral_base": res["h0"],
        "por_horizonte": {"ate": ctx["horizonte"]["ate"], "probabilidade": round(ctx["horizonte"]["perto"], 4),
                          "so_historia": round(ctx["horizonte"]["perto_base"], 4),
                          "depois_acrescenta": round(ctx["horizonte"]["depois"], 4)},
        # As três parcelas somam a nota; os fatores somam a parcela do meio.
        "parcelas_pontos": {"historia_ate_o_horizonte": round(100 * ctx["horizonte"]["perto_base"], 2),
                            "dados_e_noticias": round(100 * (ctx["horizonte"]["perto"] - ctx["horizonte"]["perto_base"]), 2),
                            "historia_depois": round(100 * ctx["horizonte"]["depois"], 2)},
        "atualizado_em": rodada["gerado_em"],
        "versao_modelo": rodada["modelo"]["versao"], "regra": ctx["cfg"]["regra_de_resolucao"],
        "dados_e_noticias_por_fator_pontos": {k: round(v, 2) for k, v in ctx["pq"]["sh"].items()},
        "indicadores": [{k: x[k] for k in ("id", "nome", "valor", "unidade", "ref", "logit")} for x in res["indicadores"]],
        "noticias": [{"id": x["id"], "titulo": x["titulo_evento"], "logit": round(x["logit"], 4), "data": x["data"]}
                     for x in res["noticias"]],
        "registro_completo": f"{REPO}/blob/main/runs/{rodada['id']}.json",
    }


def main() -> None:
    cfg = model.carregar_config()
    todas = [json.loads(p.read_text()) for p in sorted((ROOT / "runs").glob("*.json"))]
    if not todas:
        print("nenhuma rodada em runs/")
        return
    eventos = json.loads((ROOT / "data" / "eventos.json").read_text()) if (ROOT / "data" / "eventos.json").exists() else []
    casos_p = ROOT / "data" / "casos.json"
    casos = json.loads(casos_p.read_text()) if casos_p.exists() else None

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["num"] = num
    env.filters["sinal"] = sinal

    DOCS.mkdir(exist_ok=True)
    (DOCS / "og").mkdir(exist_ok=True)
    ultima = todas[-1]
    # Um link permanente por dia: a última rodada do dia.
    por_dia = {}
    for r in todas:
        por_dia[r["gerado_em"][:10]] = r
    for dia, r in por_dia.items():
        hist = [x for x in todas if x["gerado_em"] <= r["gerado_em"]]
        ctx = contexto(r, hist, eventos, casos, cfg)
        og = DOCS / "og" / f"{dia}.png"
        if not og.exists() or r is ultima:
            og_image.gerar(og, ctx)
        ctx.update({"canonical": f"{SITE}/{dia}/", "og_url": f"{SITE}/og/{dia}.png", "permalink": True})
        (DOCS / dia).mkdir(exist_ok=True)
        (DOCS / dia / "index.html").write_text(env.get_template("index.html").render(**ctx))

    ctx = contexto(ultima, todas, eventos, casos, cfg)
    dia = ultima["gerado_em"][:10]
    ctx.update({"canonical": f"{SITE}/", "og_url": f"{SITE}/og/{dia}.png", "permalink": False})
    (DOCS / "index.html").write_text(env.get_template("index.html").render(**ctx))
    shutil.copy(DOCS / "og" / f"{dia}.png", DOCS / "og.png")

    met = markdown.markdown((ROOT / "METODOLOGIA.md").read_text(), extensions=["tables", "toc"])
    (DOCS / "metodologia").mkdir(exist_ok=True)
    (DOCS / "metodologia" / "index.html").write_text(env.get_template("pagina.html").render(
        titulo="Metodologia", corpo=met, canonical=f"{SITE}/metodologia/", og_url=f"{SITE}/og.png", site=SITE,
        repo=REPO, cfg=cfg))

    (DOCS / "data.json").write_text(json.dumps(dados_publicos(ultima, ctx), ensure_ascii=False, indent=1))
    (DOCS / "historico.json").write_text(json.dumps(
        [{"id": r["id"], "gerado_em": r["gerado_em"], "nota": round(100 * r["resultado"]["manchete"], 1),
          "proximos_4_trimestres": round(100 * r["resultado"]["curto_prazo_4t"], 1)} for r in todas], indent=1))
    (DOCS / "CNAME").write_text("vaidarcrise.com.br")
    (DOCS / ".nojekyll").touch()
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [f"{SITE}/", f"{SITE}/metodologia/"] + [f"{SITE}/{d}/" for d in sorted(por_dia)]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    print(f"site gerado em {DOCS} (nota {ctx['nota_fmt']})")


if __name__ == "__main__":
    main()
