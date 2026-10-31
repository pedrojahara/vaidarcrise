"""Gera o site estático em docs/ a partir dos registros em runs/.

A direção do risco vai escrita no HTML (não carregada por JavaScript) para aparecer em
prévias de links e buscadores. Cada dia tem a sua página, como foi calculada naquele dia.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

from urllib.parse import quote

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
# Os tipos de post (PERSONA.md): o retrato, escrito à mão, fica fixo no topo; os outros saem da atualização das 06h30.
TIPOS_POST = {"dia": "Fato do dia", "semana": "A semana", "mes": "O mês", "retrato": "Retrato do Brasil"}
ESTAGIOS = {"dado": "dado divulgado", "decidido": "decisão tomada", "em_votacao": "em votação",
            "anuncio": "anúncio", "rumor": "rumor"}
SENTIDOS = {"piora": ("↑", "mais", "para pior"), "melhora": ("↓", "menos", "para melhor"),
            "igual": ("→", "igual", "sem lado claro")}
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


# -------------------------------------------------------------------- direção
ESTADO = {"subindo": ("↑", "mais", "Subindo"), "igual": ("→", "igual", "Igual"), "caindo": ("↓", "menos", "Caindo"),
          "encolhendo": ("↓", "mais", "Encolhendo")}
LADO_PRESSAO = {1: ("Apertou", "mais"), 0: ("Igual", "igual"), -1: ("Folgou", "menos"), None: ("Sem dado", "igual")}
LADO_RITMO = {1: ("Esfriou", "mais"), 0: ("Igual", "igual"), -1: ("Acelerou", "menos"), None: ("Sem dado", "igual")}
LADO_EMPREGO = {1: ("Piorou", "mais"), 0: ("Igual", "igual"), -1: ("Melhorou", "menos"), None: ("Sem dado", "igual")}
NUMERAIS = ["Nenhuma", "Uma", "Duas", "Três", "Quatro", "Cinco"]


def mes_ano(ref: str, com_ano: bool | None = None, hoje: str | None = None) -> str:
    """'junho' ou 'junho de 2025' (o ano só quando não é o de hoje)."""
    nome = MESES[int(ref[5:7]) - 1]
    if com_ano or (com_ano is None and hoje and ref[:4] != hoje[:4]):
        return f"{nome} de {ref[:4]}"
    return nome


def _quando(m: dict) -> str:
    """'de junho a setembro' (dado mensal) ou 'do fim de julho a 30/10' (dado diário)."""
    a, b = m["ref_antes"], m["ref"]
    if m.get("dia") and len(m["dia"]) == 10 and m["dia"][:7] == b and m.get("diario"):
        return f"do fim de {mes_nome(a)} a {dia_mes(m['dia'])}"
    return f"de {mes_nome(a)} a {mes_nome(b)}"


def _quanto_normal(m: dict, unidade: str) -> str:
    """Quanto a medida andou contra o vaivém normal dela: 'passou raspando', 'dentro do normal'."""
    mud, corte = abs(m["mudanca"]), m["corte"]
    c = f"{num(corte, 2 if corte < 1 else 1)}{unidade}"
    if m["lado"] in (None, 0):
        return f"Ficou dentro do vaivém normal de 3 meses, que vai até {c}."
    if mud < 1.25 * corte:
        return f"Passou raspando do vaivém normal de 3 meses, que vai até {c}."
    return f"Passou do vaivém normal de 3 meses, que vai até {c}."


def folga_ctx(pid: str, f: dict | None, teto: float | None = None) -> dict | None:
    """A folga de uma parte: o nível de hoje contra todos os meses desde o começo da série."""
    if not f:
        return None
    p, desde = f["pior_que_pct"], f["desde"]
    frases = {
        "contas": ("A dívida", "mais alta", "mais baixa", "Está no maior valor desde"),
        "parcelas": ("A parte da renda que vai para dívidas", "mais alta", "mais baixa", "É a maior desde"),
        "mercado": ("O juro de 10 anos", "mais alto", "mais baixo", "É o maior desde"),
        "inflacao": ("A inflação esperada", "mais alta", "mais baixa", "É a maior desde"),
        "juro": ("Descontada a inflação esperada, a Selic", "mais alta", "mais baixa", "É a maior desde"),
        "emprego": ("O desemprego", "mais alto", "mais baixo", "É o maior desde"),
    }[pid]
    sujeito, alto, baixo, recorde = frases
    if f["recorde_ruim"]:
        rot, txt = "Nenhuma", f"{recorde} {desde}, quando começa a série."
    elif f["recorde_bom"]:
        rot, txt = "Muita", f"{sujeito} está no menor valor desde {desde}, quando começa a série."
    elif p >= 90:
        rot, txt = "Quase nenhuma", f"{sujeito} está {alto} que em {p}% dos meses desde {desde}."
    elif p >= 70:
        rot, txt = "Pouca", f"{sujeito} está {alto} que em {p}% dos meses desde {desde}."
    elif p > 30:
        rot, txt = "Média", f"{sujeito} está no meio do que o Brasil viu desde {desde}."
    else:
        rot, txt = "Muita", f"{sujeito} está {baixo} que em {100 - p}% dos meses desde {desde}."
    if pid == "juro":
        txt = txt.replace("a Selic está", f"a Selic dá {num(f['valor'])}% ao ano e está").replace(
            "a Selic está no meio", f"a Selic dá {num(f['valor'])}% ao ano, no meio")
    if pid == "inflacao" and teto is not None and f["valor"] > teto:
        txt += f" Mas está acima do teto da meta do Banco Central, de {num(teto)}%."
    return {"rot": rot, "texto": txt}


def _parte_ctx(x: dict, cfg: dict, hoje: str) -> dict:
    """Uma linha do topo: o nome, o que aconteceu em 3 meses, o vaivém normal, a folga e quem mexe."""
    p = cfg["direcao"]
    pid, ms = x["id"], x["medidas"]
    tabela = LADO_RITMO if pid == "ritmo" else LADO_EMPREGO if pid == "emprego" else LADO_PRESSAO
    palavra, cls = tabela[x["lado"]]
    frases, normal = [], ""
    m = next(iter(ms.values()), None)
    if pid == "contas" and "divida" in ms and ms["divida"]["agora"] is not None:
        d = ms["divida"]
        frases.append(f"A dívida do governo foi de {num(d['antes'])}% para {num(d['agora'])}% do PIB, {_quando(d)}.")
        normal = _quanto_normal(d, " ponto")
        pr = ms.get("primario")
        if pr and pr.get("agora") is not None and pr.get("antes") is not None and abs(pr["agora"] - pr["antes"]) >= 0.05:
            def gasto(v: float) -> str:
                return (f"gastou {num(v)}% do PIB a mais do que arrecadou" if v > 0
                        else f"arrecadou {num(-v)}% do PIB a mais do que gastou")
            if (pr["agora"] > 0) == (pr["antes"] > 0):
                frases.append(f"Sem contar os juros, o governo {gasto(pr['agora'])} nos 12 meses até {mes_nome(pr['ref'])}, "
                              f"contra {num(abs(pr['antes']))}% nos 12 meses até {mes_nome(pr['ref_antes'])}.")
            else:
                frases.append(f"Sem contar os juros, o governo {gasto(pr['agora'])} nos 12 meses até {mes_nome(pr['ref'])}. "
                              f"Nos 12 meses até {mes_nome(pr['ref_antes'])}, {gasto(pr['antes'])}.")
            if pr["agora"] < pr["antes"] and d["agora"] > d["antes"]:
                frases.append("A dívida sobe mesmo assim, porque os juros sobre ela pesam mais que essa melhora.")
    elif pid == "parcelas" and m and m["agora"] is not None:
        frases.append(f"A parte da renda das famílias que vai para parcelas e juros foi de {num(m['antes'])}% para "
                      f"{num(m['agora'])}%, {_quando(m)}.")
        normal = _quanto_normal(m, " ponto")
    elif pid == "mercado" and "dolar" in ms and ms["dolar"]["agora"] is not None:
        d = {**ms["dolar"], "diario": True}
        frases.append(f"O dólar foi de R$ {num(d['antes'], 2)} para R$ {num(d['agora'], 2)}, {_quando(d)}"
                      f" ({'alta' if d['mudanca'] > 0 else 'queda'} de {num(abs(d['mudanca']))}%).")
        normal = "Dólar: " + _quanto_normal(d, "%")[0].lower() + _quanto_normal(d, "%")[1:]
        j = ms.get("juro_longo")
        if j and j.get("agora") is not None:
            frases.append(f"O juro que o governo paga, acima da inflação, para pegar dinheiro por uns 10 anos foi de "
                          f"{num(j['antes'])}% para {num(j['agora'])}% ao ano.")
            normal += " Juro de 10 anos: " + _quanto_normal(j, " ponto")[0].lower() + _quanto_normal(j, " ponto")[1:]
            normal += " Os dois contam como um só: se um aperta e o outro folga, fica igual."
    elif pid == "inflacao" and m and m["agora"] is not None:
        cd = 2 if abs(m["agora"] - p["teto_meta_inflacao"]) < 0.05 else 1  # perto do teto da meta, a segunda casa decide
        frases.append(f"Os bancos (Focus) esperam que os preços subam {num(m['agora'], cd)}% "
                      f"nos próximos 12 meses. Em {mes_nome(m['ref_antes'])}, esperavam {num(m['antes'], cd)}%.")
        normal = _quanto_normal(m, " ponto")
    elif pid == "juro" and m and m["agora"] is not None:
        verbo = "subiu" if m["agora"] > m["antes"] else "caiu" if m["agora"] < m["antes"] else "ficou"
        if verbo == "ficou":
            frases.append(f"A Selic ficou em {num(m['agora'], 2)}%, {_quando(m)}.")
        else:
            frases.append(f"A Selic {verbo} de {num(m['antes'], 2)}% para {num(m['agora'], 2)}%, {_quando(m)}.")
        frases.append("A Selic é o juro que o Banco Central decide e que serve de base para os juros dos bancos.")
        normal = _quanto_normal(m, " ponto")
    elif pid == "ritmo" and m and m["mudanca"] is not None:
        frases.append(f"A prévia do PIB do Banco Central {'cresceu' if m['mudanca'] >= 0 else 'caiu'} {num(abs(m['mudanca']))}% "
                      f"nos 3 meses até {mes_nome(m['ref'])}, contra os 3 meses anteriores.")
        normal = _quanto_normal(m, "%")
    elif pid == "emprego" and m and m["agora"] is not None:
        frases.append(f"O desemprego foi de {num(m['antes'])}% para {num(m['agora'])}%, no trimestre até "
                      f"{mes_nome(m['ref'])}, contra o trimestre até {mes_nome(m['ref_antes'])}.")
        normal = _quanto_normal(m, " ponto")
    if not frases:
        frases.append("Sem dado nesta atualização.")
    return {"id": pid, "nome": p["nomes"][pid], "palavra": palavra, "cls": cls, "na_soma": x["na_soma"],
            "frase": frases[0], "mais": frases[1:], "normal": normal,
            "folga": folga_ctx(pid, x.get("folga"), p.get("teto_meta_inflacao")),
            "quem": p["quem_mexe"].get(pid, ""), "causas": p["causas"].get(pid)}


def direcao_ctx(rodada: dict, cfg: dict, cal: dict) -> dict:
    """O topo da página: para que lado anda o risco, desde quando, as cinco pressões, o ritmo, o emprego e o que segura."""
    d = rodada["resultado"]["direcao"]
    hoje = rodada["gerado_em"][:10]
    seta, cls, nome = ESTADO[d["estado"]]
    partes = [_parte_ctx(x, cfg, hoje) for x in d["partes"]]
    pressoes = [x for x in partes if x["na_soma"]]
    ap, fo = d["apertaram"], d["folgaram"]
    if ap and fo:
        conta = (f"{NUMERAIS[ap]} das cinco pressões que costumam vir antes de uma recessão {'apertou' if ap == 1 else 'apertaram'} "
                 f"nos últimos 3 meses, e {NUMERAIS[fo].lower()} {'folgou' if fo == 1 else 'folgaram'}.")
    elif ap:
        conta = (f"{NUMERAIS[ap]} das cinco pressões que costumam vir antes de uma recessão {'apertou' if ap == 1 else 'apertaram'} "
                 "nos últimos 3 meses. Nenhuma folgou.")
    elif fo:
        conta = (f"{NUMERAIS[fo]} das cinco pressões que costumam vir antes de uma recessão {'folgou' if fo == 1 else 'folgaram'} "
                 "nos últimos 3 meses. Nenhuma apertou.")
    else:
        conta = "Nenhuma das cinco pressões que costumam vir antes de uma recessão andou mais que o normal nos últimos 3 meses."
    if d["estado"] == "encolhendo":
        rit = next((x for x in d["partes"] if x["id"] == "ritmo"), {})
        mud = ((rit.get("medidas") or {}).get("ritmo") or {}).get("mudanca")
        conta = (f"A prévia do PIB do Banco Central caiu {num(abs(mud))}% em 3 meses, contra os 3 anteriores. " if mud is not None else "") + conta
    t = (cal.get("direcao") or {}).get("teste") or {}
    pib = (t.get("pib_12m_depois") or {}).get(d["estado"])
    historia = None
    if pib is not None and d["estado"] != "encolhendo":
        historia = (f"Desde 2004, depois dos meses em que o risco esteve {d['estado']}, o PIB "
                    f"{'cresceu em média ' + num(pib) + '%' if pib > 0.05 else 'ficou parado, em média,' if pib >= -0.05 else 'caiu em média ' + num(abs(pib)) + '%'}"
                    " nos 12 meses seguintes.")
    desde = d["desde"]
    pend = None
    if d.get("pendente") and d["pendente"] != d["estado"]:
        pend = f"Pelos dados de hoje, a direção seria {d['pendente']}. Ela só muda se o mês que vem repetir."
    res = rodada["resultado"]
    reservas = next((x for x in res.get("indicadores", []) if x["id"] == "reservas" and x.get("valor")), None)
    segura = []
    for s in cfg["direcao"]["o_que_segura"]:
        r = f", que somavam US$ {num(reservas['valor'] / 1000, 0)} bilhões em {mes_ano(reservas['ref'], hoje=hoje)}" if reservas else ""
        segura.append({"texto": s["texto"].replace("{reservas}", r), "fonte": s["fonte"]})
    return {"estado": d["estado"], "seta": seta, "cls": cls, "nome": nome, "palavra": d["estado"],
            "titulo": "A economia está encolhendo" if d["estado"] == "encolhendo" else f"O risco de recessão está {d['estado']}",
            "desde": f"desde {mes_ano(desde, hoje=hoje)}" if desde[:7] < hoje[:7] else "neste mês",
            "conta": conta, "historia": historia, "pendente": pend,
            "pressoes": pressoes, "fora": [x for x in partes if not x["na_soma"]], "segura": segura,
            "placa": nome, "longa": len(nome) > 8}


def gar_ctx(rodada: dict) -> dict | None:
    """A conta dos 44 países, que fica só em Como funciona: o PIB num ano ruim e em tempos normais."""
    g = rodada["resultado"].get("gar")
    if not g:
        return None
    return {"ruim": verbo_pct(g["cenario_ruim"]), "normal": verbo_pct(g["cenario_normal"])}


def svg_direcao(linha: list[dict], recessoes: list[dict]) -> str:
    """A direção mês a mês desde 2004, com as recessões e os governos. Feito para caber no celular."""
    if not linha:
        return ""
    w, x0, x1 = 360, 6, 354
    n0 = int(linha[0]["mes"][:4]) * 12 + int(linha[0]["mes"][5:7]) - 1
    n1 = int(linha[-1]["mes"][:4]) * 12 + int(linha[-1]["mes"][5:7]) - 1 + 1

    def px(m: str, fim: bool = False) -> float:
        n = int(m[:4]) * 12 + int(m[5:7]) - 1 + (1 if fim else 0)
        return x0 + (x1 - x0) * (n - n0) / max(n1 - n0, 1)

    cls = {"S": "d-s", "I": "d-i", "C": "d-c", "E": "d-e"}
    nomes = {"S": "subindo", "I": "igual", "C": "caindo", "E": "encolhendo"}
    blocos: list[dict] = []
    for x in linha:
        if blocos and blocos[-1]["estado"] == x["estado"]:
            blocos[-1]["fim"] = x["mes"]
        else:
            blocos.append({"inicio": x["mes"], "fim": x["mes"], "estado": x["estado"]})
    out = [f'<svg viewBox="0 0 {w} 150" class="linha-dir" role="img" aria-label="Direção do risco mês a mês desde '
           f'{linha[0]["mes"][:4]}, com as recessões e os governos">']
    out.append(f'<text x="{x0}" y="12" class="tl">Direção</text>')
    for b in blocos:
        a, z = px(b["inicio"]), px(b["fim"], True)
        out.append(f'<rect x="{a:.1f}" y="18" width="{max(z - a, 0.8):.1f}" height="34" class="{cls[b["estado"]]}">'
                   f'<title>{nomes[b["estado"]].capitalize()}: de {mes_nome(b["inicio"])} de {b["inicio"][:4]} a '
                   f'{mes_nome(b["fim"])} de {b["fim"][:4]}</title></rect>')
    out.append(f'<text x="{x0}" y="70" class="tl">Recessão</text>')
    for r in recessoes:
        q, a_ = r["inicio"].split("T")
        ini = f"{a_}-{(int(q) - 1) * 3 + 1:02d}"
        q2, a2 = r["fim"].split("T")
        fim = f"{a2}-{int(q2) * 3:02d}"
        if fim < linha[0]["mes"] or ini > linha[-1]["mes"]:
            continue
        a, z = px(max(ini, linha[0]["mes"])), px(min(fim, linha[-1]["mes"]), True)
        out.append(f'<rect x="{a:.1f}" y="76" width="{z - a:.1f}" height="8" class="rec"/>')
    governos = [("Lula 1 e 2", "2003-01", "2010-12"), ("Dilma", "2011-01", "2016-04"), ("Temer", "2016-05", "2018-12"),
                ("Bolsonaro", "2019-01", "2022-12"), ("Lula 3", "2023-01", "2026-12")]
    out.append(f'<text x="{x0}" y="102" class="tl">Governo</text>')
    for nome, ini, fim in governos:
        ini, fim = max(ini, linha[0]["mes"]), min(fim, linha[-1]["mes"])
        if ini > fim:
            continue
        a, z = px(ini) + 1, px(fim, True) - 1
        out.append(f'<line x1="{a:.1f}" x2="{z:.1f}" y1="108" y2="108" class="gov"/>'
                   f'<line x1="{a:.1f}" x2="{a:.1f}" y1="104" y2="112" class="gov"/>'
                   f'<text x="{(a + z) / 2:.1f}" y="124" class="tg" text-anchor="middle">{nome}</text>')
    for ano in range(int(linha[0]["mes"][:4]), int(linha[-1]["mes"][:4]) + 1, 6):
        out.append(f'<text x="{px(f"{ano}-01"):.1f}" y="144" class="tl" text-anchor="{"start" if ano == int(linha[0]["mes"][:4]) else "middle"}">{ano}</text>')
    out.append("</svg>")
    return "".join(out)


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
    tipo = p.get("tipo") or "dia"
    d = rodada["resultado"]["direcao"]
    secoes = []
    if p.get("ok"):
        titulo, paragrafos = p["titulo"], p["paragrafos"]
        secoes = p.get("secoes") or [{"paragrafos": paragrafos}]
        hr = hora(p.get("escrito_em") or rodada["gerado_em"])
        per = p.get("periodo") or {}
        if tipo in ("semana", "mes") and per:
            autoria = (f"Escrito por inteligência artificial (Claude) às {hr}, com as {per['rodadas']} atualizações do site "
                       f"de {dia_mes(per['de'])} a {dia_mes(per['ate'])}.")
        else:
            autoria = f"Escrito por inteligência artificial (Claude) às {hr}, depois de ler {lidas}."
        rodape = "Ninguém revisa o texto antes de ele sair."
    else:
        tipo = "dia"
        titulo = ("A economia está encolhendo" if d["estado"] == "encolhendo"
                  else f"O risco de recessão está {d['estado']}")
        paragrafos = []
        autoria = (f"Atualização automática das {hora(rodada['gerado_em'])}, depois de ler {lidas}. "
                   "O texto do dia não saiu. Ficam a direção do risco e as notícias, organizadas pelo programa.")
        rodape = ""
    link = f"/{dia}/"
    zap = None
    if tipo in ("semana", "mes"):
        zap = "https://wa.me/?text=" + quote(f"{titulo} {SITE}{link}")
    return {"dia": dia, "data_extenso": data_extenso(dia), "titulo": titulo, "paragrafos": paragrafos, "secoes": secoes,
            "tipo": tipo, "tipo_nome": TIPOS_POST[tipo], "zap": zap,
            "autoria": autoria, "rodape": rodape, "direcao": d["estado"], "llm": bool(p.get("ok")),
            "pressao": pressao_ctx(rodada, eventos, cfg), "link": link,
            "registro": f"{REPO}/blob/main/runs/{rodada['id']}.json", "llm_ok": rodada["llm"]["ok"]}


def textos_do_editor() -> list[dict]:
    """Textos escritos à mão em editor/*.md: cabeçalho 'chave: valor', uma linha '---' e o corpo em Markdown."""
    out = []
    for arq in sorted((ROOT / "editor").glob("*.md")):
        cab, corpo = arq.read_text().split("\n---\n", 1)
        meta = {k.strip(): v.strip() for k, v in (linha.split(":", 1) for linha in cab.strip().splitlines())}
        slug = arq.stem[11:] if arq.stem[:10] == meta["data"] else arq.stem
        tipo = meta.get("tipo", "")
        out.append({"dia": meta["data"], "data_extenso": data_extenso(meta["data"]), "titulo": meta["titulo"],
                    "corpo_html": markdown.markdown(corpo, extensions=["tables"]), "paragrafos": [], "secoes": [],
                    "pressao": None, "tipo": tipo, "tipo_nome": TIPOS_POST.get(tipo, ""), "autoria": meta.get("autoria"),
                    "tags": meta.get("tags", ""), "editor": True, "link": f"/textos/{slug}/", "slug": slug,
                    "llm_ok": True, "palavras": len(corpo.split())})
    return sorted(out, key=lambda t: t["dia"], reverse=True)


# --------------------------------------------------------------------- dados
def dados_publicos(rodada: dict, ctx: dict) -> dict:
    res = rodada["resultado"]
    d = res["direcao"]
    g = res.get("gar") or {}
    return {
        "direcao": d["estado"], "desde": d["desde"], "pergunta": ctx["cfg"]["pergunta"], "atualizado_em": rodada["gerado_em"],
        "soma": d["soma"], "apertaram": d["apertaram"], "folgaram": d["folgaram"],
        "partes": [{"id": x["id"], "nome": ctx["cfg"]["direcao"]["nomes"][x["id"]], "na_soma": x["na_soma"],
                    "lado": {1: "apertou", 0: "igual", -1: "folgou", None: None}[x["lado"]],
                    "medidas": {k: {c: (round(v, 4) if isinstance(v, float) else v) for c, v in m.items()}
                                for k, m in x["medidas"].items()},
                    "folga": x.get("folga")} for x in d["partes"]],
        "pib_num_ano_ruim_12_meses": {"pct": round(g["cenario_ruim"], 2), "em_tempos_normais_pct": round(g["cenario_normal"], 2),
                                      "o_que_e": "Crescimento do PIB nos 4 trimestres seguintes ao último divulgado que tem 1 chance em 10 de ser pior (conta dos 44 países)."} if g else None,
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
    lista = [{"dia": d, "data": data_curta(d)[:5], "tipo": posts[d]["tipo_nome"], "titulo": posts[d]["titulo"],
              "link": f"/{d}/"} for d in reversed(dias)]
    textos = textos_do_editor()
    # O retrato mais novo fica fixo no topo da página principal; o resto dos textos à mão entra no arquivo.
    retrato = next((t for t in textos if t["tipo"] == "retrato"), None)
    arquivo = sorted(lista[1:] + [{"dia": t["dia"], "data": data_curta(t["dia"])[:5], "tipo": t["tipo_nome"] or "Texto",
                                   "titulo": t["titulo"], "link": t["link"]} for t in textos if t is not retrato],
                     key=lambda x: x["dia"], reverse=True)
    def contexto(dia: str, r: dict, permalink: bool) -> dict:
        pos = dias.index(dia)
        base = f"/{dia}/" if permalink else "/"
        return {"cfg": cfg, "cal": cal, "repo": REPO, "site": SITE, "dia": dia, "permalink": permalink,
                "dir": direcao_ctx(r, cfg, cal), "gar": gar_ctx(r), "post": posts[dia],
                "teste": (cal.get("direcao") or {}).get("teste") or {},
                "linha_svg": svg_direcao(r["resultado"]["direcao"].get("linha", []), cal.get("recessoes", [])),
                "data_titulo": f"{int(dia[8:10])} de {MESES[int(dia[5:7]) - 1]}",
                "datas": calendario.janela(agenda, dt.date.fromisoformat(dia)), "jornais": JORNAIS,
                "hora": hora(r["gerado_em"]), "atualizado_iso": r["gerado_em"],
                "link_inicio": base, "link_nota": "/nota/",
                "dia_antes": dias[pos - 1] if pos else None, "dia_depois": dias[pos + 1] if pos + 1 < len(dias) else None,
                "data_curta": data_curta, "data_extenso": data_extenso, "mes_ano": mes_ano,
                "og_url": f"{SITE}/og/{dia}.png", "dia_mes": dia_mes}

    abas = {"index.html": "inicio", "causas.html": "causas", "nota.html": "nota"}

    def gravar(caminho: Path, tpl: str, ctx: dict, canonical: str) -> None:
        caminho.mkdir(parents=True, exist_ok=True)
        (caminho / "index.html").write_text(env.get_template(tpl).render(**{"aba": abas.get(tpl), **ctx},
                                                                          canonical=canonical))

    def desviar(caminho: Path, destino: str) -> None:
        """Endereço antigo (Fator por fator e a conta de cada dia) que agora leva a outra página."""
        caminho.mkdir(parents=True, exist_ok=True)
        (caminho / "index.html").write_text(
            f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Vai dar crise?</title>'
            f'<link rel="canonical" href="{SITE}{destino}"><meta name="robots" content="noindex">'
            f'<meta http-equiv="refresh" content="0; url={destino}"></head>'
            f'<body><p><a href="{destino}">Esta página mudou de lugar.</a></p></body></html>')

    for dia, r in por_dia.items():
        ctx = contexto(dia, r, True)
        og = DOCS / "og" / f"{dia}.png"
        og_image.gerar(og, {"dir": ctx["dir"], "dia": dia, "data_curta": data_curta,
                            "tipo": posts[dia]["tipo"], "tipo_nome": posts[dia]["tipo_nome"]})
        gravar(DOCS / dia, "index.html", ctx, f"{SITE}/{dia}/")
        desviar(DOCS / dia / "resumo", f"/{dia}/")
        desviar(DOCS / dia / "nota", "/nota/")

    dia = ultima["gerado_em"][:10]
    ctx = contexto(dia, ultima, False)
    gravar(DOCS, "index.html", {**ctx, "anteriores": arquivo, "retrato": retrato}, f"{SITE}/")
    desviar(DOCS / "resumo", "/")
    gravar(DOCS / "nota", "nota.html", ctx, f"{SITE}/nota/")
    try:
        gravar(DOCS / "causas", "causas.html", {**ctx, "og_url": f"{SITE}/causas/og.png"}, f"{SITE}/causas/")
    except (KeyError, OSError, ValueError, ZeroDivisionError) as e:  # a aba não pode derrubar a atualização do dia
        print(f"aviso: a aba /causas/ não foi refeita ({e!r})")
    for p in (DOCS / "textos").glob("*"):
        if p.is_dir() and p.name not in {t["slug"] for t in textos}:  # texto apagado de editor/: sai do site
            shutil.rmtree(p)
    for t in textos:
        gravar(DOCS / "textos" / t["slug"], "index.html",
               {**ctx, "post": t, "permalink": True, "dia_antes": None, "dia_depois": None}, f"{SITE}{t['link']}")
    # Links fixos para encaminhar: /semana/ e /mes/ mostram o último post de cada tipo, com o link do dia como canônico
    # (por isso ficam fora do sitemap).
    for tipo, pasta in (("semana", "semana"), ("mes", "mes")):
        d = next((d for d in reversed(dias) if posts[d]["tipo"] == tipo), None)
        if d:
            gravar(DOCS / pasta, "index.html", contexto(d, por_dia[d], True), f"{SITE}/{d}/")
        elif (DOCS / pasta).exists():
            shutil.rmtree(DOCS / pasta)
    shutil.copy(DOCS / "og" / f"{dia}.png", DOCS / "og.png")

    met = ('<p class="intro-met">Esta página é para quem quer conferir ou refazer a conta, com as fórmulas e os testes. '
           'A versão curta está em <a href="/nota/">Como funciona</a>.</p>\n'
           + markdown.markdown((ROOT / "METODOLOGIA.md").read_text(), extensions=["tables", "toc"]))
    gravar(DOCS / "metodologia", "pagina.html", {**ctx, "titulo": "Metodologia", "corpo": met, "og_url": f"{SITE}/og.png"},
           f"{SITE}/metodologia/")

    publico = dados_publicos(ultima, ctx)
    publico["post_do_dia"] = {"tipo": posts[dia]["tipo_nome"], "titulo": posts[dia]["titulo"], "url": f"{SITE}/{dia}/",
                              "escrito_por_llm": posts[dia]["llm"]}
    (DOCS / "data.json").write_text(json.dumps(publico, ensure_ascii=False, indent=1))
    (DOCS / "historico.json").write_text(json.dumps(
        [{"id": r["id"], "gerado_em": r["gerado_em"], "direcao": r["resultado"]["direcao"]["estado"],
          "desde": r["resultado"]["direcao"]["desde"]} for r in todas],
        ensure_ascii=False, indent=1))
    (DOCS / "CNAME").write_text("vaidarcrise.com.br")
    (DOCS / ".nojekyll").touch()
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    urls = [f"{SITE}/", f"{SITE}/causas/", f"{SITE}/nota/", f"{SITE}/metodologia/"] \
        + [f"{SITE}/{d}/" for d in dias] + [f"{SITE}{t['link']}" for t in textos]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(f"<url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n")
    print(f"site gerado em {DOCS} (direção: {ctx['dir']['estado']} {ctx['dir']['desde']})")


if __name__ == "__main__":
    main()
