"""O que o site mostra da base de conhecimento (base/): a leitura a fundo dos fatos do dia (post.fundo em runs/, feita
por src/fundo.py) e a página de cada pressão do topo que já tem pergunta publicada, em /perguntas/<id>/.

Uma página por pressão: cada pergunta de base/perguntas diz a pressão dela (pressao, uma das chaves de
direcao.nomes em config/modelo.json). Cada fato do dia leva, numa linha logo abaixo do texto, à página do assunto do
fato; se o assunto não tem página, à da pressão da tese da leitura a fundo; se nenhuma tem, à parte da aba O que causa
recessão que explica a pressão (ponte()). Rascunho (publicada: false) não vira página.

O site não guarda teste nem placar e não promete conferir nada depois (decisão do Pedro em 8/11/2026, repetida em
9/11): a página mostra a análise e para aí, e src/verifica_base.py barra pergunta com teste ou texto com promessa.

Tudo vem de base/: as afirmações que sustentam cada frase, as perguntas, os episódios e o último relatório do
verificador (base/conferencia/), que diz se a fonte de cada afirmação já foi conferida. build_site.py chama
fundo_ctx() em cada post e gravar() no fim; um erro aqui não derruba a atualização do dia.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "base"

ROTULOS = {"fato": "Os dados mostram", "consenso": "Os estudos concordam", "maioria_com_dissenso": "A maioria concorda",
           "em_disputa": "Os economistas discordam"}
STATUS = {"em_pe": "Ainda de pé", "maioria": "A maioria defende", "em_disputa": "Em disputa", "minoria": "Minoria",
          "pouco_testada": "Pouco testada", "testada_e_nao_confirmada": "Testada e não confirmada"}
ORDEM_STATUS = ["maioria", "em_pe", "em_disputa", "pouco_testada", "minoria", "testada_e_nao_confirmada"]
# Na página, as explicações principais viram cartões; as outras, uma linha cada, em grupos com título em português.
CARTOES = {"maioria": "A maioria dos estudos aponta", "em_pe": "Os economistas ainda discordam"}
GRUPOS = [({"em_disputa", "minoria"}, "Explica uma parte, e os economistas discordam", "Explicam uma parte, e os economistas discordam"),
          ({"pouco_testada"}, "Ainda pouco testada", "Ainda pouco testadas"),
          ({"testada_e_nao_confirmada"}, "Os dados não confirmaram", "Os dados não confirmaram")]
NIVEIS = {1: "Revisão de muitos estudos", 2: "Estudo em revista científica", 3: "Órgão oficial",
          4: "Tese ou dissertação", 5: "Banco, consultoria ou associação", 6: "Notícia", 7: "Comentarista"}
CAUSAS = {"daqui": "daqui", "de fora": "de fora", "as duas": "as duas"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
DIAS_DO_AGORA = 30


def _mes(ref: str) -> str:
    return f"{MESES[int(ref[5:7]) - 1]} de {ref[:4]}"


def _periodo(p: dict) -> str:
    de, ate = p["de"], p["ate"]
    if de[:4] == ate[:4]:
        return f"{MESES[int(de[5:7]) - 1]} a {_mes(ate)}"
    return f"{_mes(de)} a {_mes(ate)}"


def _data(iso: str) -> str:
    return f"{int(iso[8:10])}/{int(iso[5:7])}/{iso[:4]}"


def _conferencia() -> dict:
    """O status de cada afirmação no relatório mais novo do verificador que abriu as páginas (no Mac). O modo offline
    não abre nenhuma e marca todo documento como "nao_aberta", mas confere por inteiro os dados, os trechos do site e
    as contas: o relatório offline mais novo, se não for mais velho que o do Mac, vale para esses três tipos e para as
    afirmações que o do Mac ainda não tinha."""
    rels = sorted((BASE / "conferencia").glob("*-verifica*.json"), key=lambda p: p.name)
    com_rede = [p for p in rels if "offline" not in p.name]
    sem_rede = [p for p in rels if "offline" in p.name]
    conf = json.loads(com_rede[-1].read_text()).get("afirmacoes", {}) if com_rede else {}
    if sem_rede and (not com_rede or sem_rede[-1].name[:10] >= com_rede[-1].name[:10]):
        for i, r in json.loads(sem_rede[-1].read_text()).get("afirmacoes", {}).items():
            if r.get("tipo") != "documento" or i not in conf:
                conf[i] = r
    return conf


class _Fontes:
    """Numera as fontes na ordem em que aparecem na página, para a lista do fim."""

    def __init__(self, A: dict, conf: dict):
        self.A, self.conf, self.ordem, self.n = A, conf, [], {}

    def de(self, ids: list[str]) -> list[dict]:
        out = []
        for i in dict.fromkeys(ids):
            a = self.A.get(i)
            if not a:
                continue
            chave = a["fonte"].get("url") or a["fonte"]["quem"]
            if chave not in self.n:
                self.n[chave] = len(self.ordem) + 1
                self.ordem.append(self._item(i, a))
            item = {"n": self.n[chave], "quem": a["fonte"]["quem"], "url": a["fonte"].get("url"),
                    "conferida": self.ordem[self.n[chave] - 1]["conferida"]}
            # Duas afirmações do mesmo jornal ou do mesmo órgão aparecem uma vez só na linha de fontes.
            igual = next((x for x in out if x["quem"] == item["quem"]), None)
            if igual:
                igual["conferida"] = igual["conferida"] and item["conferida"]
                continue
            out.append(item)
        return out

    def _item(self, i: str, a: dict) -> dict:
        st = (self.conf.get(i) or {}).get("status")
        f = a["fonte"]
        if a["tipo"] == "dado":
            como = "número conferido com os dados do site" if st == "conferido" else "número a conferir"
        elif a["tipo"] == "conta":
            como = "conta refeita com os dados do site" if st == "conferido" else "conta a refazer"
        elif a["tipo"] == "site":
            como = "trecho conferido no site" if st == "conferido" else "trecho a conferir"
        else:
            como = "trecho conferido no texto da fonte" if st == "conferido" else "a conferir no texto da fonte"
        # O título de série ou de arquivo do site é para quem confere a conta, não para a leitora.
        titulo = f.get("titulo") if a["tipo"] == "documento" else None
        # A conta é do site, com as séries de órgãos oficiais: não é o órgão falando.
        nivel = "Conta do site com dados oficiais" if a["tipo"] == "conta" else NIVEIS.get(f["nivel"], "")
        return {"quem": f["quem"], "titulo": titulo, "url": f.get("url"), "nivel": nivel,
                "conferida": st == "conferido", "como": como}


def _perguntas() -> dict:
    return {json.loads(p.read_text())["id"]: json.loads(p.read_text()) for p in sorted((BASE / "perguntas").glob("*.json"))}


def publicadas() -> dict:
    """As perguntas que já têm página. Um rascunho (publicada: false) guarda a disputa até a página sair."""
    return {k: q for k, q in _perguntas().items() if q.get("publicada", True)}


def pergunta_da_pressao(pid: str) -> dict | None:
    """O link para a página da pressão do topo, se ela já existe: uma página por pressão."""
    for q in publicadas().values():
        if q.get("pressao") == pid:
            return {"url": f"/perguntas/{q['id']}/", "texto": q["pergunta"]}
    return None


def menu(cfg: dict) -> list[dict]:
    """O menu Grandes perguntas do cabeçalho: primeiro a aba O que causa recessão, que explica como as pressões levam à
    recessão, e depois as páginas publicadas, na ordem das pressões do topo."""
    ordem = list(cfg["direcao"]["nomes"])
    lista = sorted(publicadas().values(), key=lambda q: ordem.index(q["pressao"]) if q.get("pressao") in ordem else 99)
    return [{"url": "/causas/", "pergunta": "O que causa recessão?", "rotulo": "Para começar"}] + [
        {"url": f"/perguntas/{q['id']}/", "pergunta": q["pergunta"],
         "rotulo": cfg["direcao"]["nomes"].get(q.get("pressao"), "")} for q in lista]


# O assunto das notícias (fator, em config/modelo.json "fatores") e as pressões do topo que ele cobre. "Juro e
# inflação" cobre duas; Ritmo da economia, Emprego e Economia lá fora não são pressões que mudam a placa e não têm
# página própria pela regra de uma página por pressão.
PRESSOES_DO_ASSUNTO = {"juro": ["juro", "inflacao"], "credito": ["parcelas"], "mercado": ["mercado"],
                       "contas": ["contas"], "atividade": ["ritmo"], "emprego": ["emprego"], "externo": []}
# Economia lá fora não é pressão do topo; na aba, a parte dela é a das causas de fora.
ABA_DO_ASSUNTO = {"externo": "/causas/#t-outros"}
# Como a linha do post chama cada pressão: "O básico sobre o juro".
SOBRE = {"juro": "o juro", "inflacao": "a inflação esperada", "contas": "as contas do governo",
         "parcelas": "as dívidas das famílias", "mercado": "a desconfiança de quem investe"}


# No assunto "Juro e inflação", o título do fato diz qual das duas páginas ele pede: o Copom e a Selic levam à do juro;
# o Focus, o IPCA e os preços, à da inflação esperada. Sem pista no título, vale a tese da leitura a fundo.
PISTAS_DO_TITULO = [("juro", re.compile(r"\b(Copom|Selic)\b", re.I)),
                    ("inflacao", re.compile(r"\b(Focus|IPCA|IPCA-15|infla[çc][ãa]o|pre[çc]os?)\b", re.I))]
# A rodada avisa o Pedro quando um assunto sem página aparece neste tanto de fatos do dia nestes dias (decisão do Pedro
# em 8/11/2026: o site não cria página sozinho; ele avalia cada caso).
VEZES_DO_AVISO = 3
DIAS_DO_AVISO = 30


def _fato_escolhido(rodada: dict) -> dict:
    pauta = rodada.get("pauta") or {}
    final = pauta.get("final")
    return next((c for c in pauta.get("candidatos") or [] if c.get("id") == final), {})


def assunto_do_fato(rodada: dict) -> str | None:
    """O assunto do fato do dia que a pauta escolheu (src/pauta.py), como o classificador de notícias marcou."""
    return _fato_escolhido(rodada).get("fator")


def titulo_do_fato(rodada: dict) -> str | None:
    """O título do fato do dia que a pauta escolheu, que desempata o assunto "Juro e inflação"."""
    return _fato_escolhido(rodada).get("titulo")


def _partes_da_aba() -> dict[str, str]:
    """O título de cada parte da aba O que causa recessão, pelo id da âncora (templates/causas.html)."""
    html = (ROOT / "templates" / "causas.html").read_text()
    return {m[0]: re.sub(r"\s+", " ", m[1]).strip() for m in re.findall(r'<h2 id="(t-[a-z]+)">([^<]+)</h2>', html)}


def _posts_ligados(cfg: dict) -> dict[str, list[dict]]:
    """Os fatos do dia (runs/) que levam a cada página, pela mesma regra da linha do post: o mais novo primeiro, um
    por dia (a última rodada do dia, como no site)."""
    por_dia: dict[str, dict] = {}
    for arq in sorted((ROOT / "runs").glob("*.json")):
        por_dia[arq.stem[:10]] = json.loads(arq.read_text())
    out: dict[str, list[dict]] = {}
    for dia in sorted(por_dia, reverse=True):
        r = por_dia[dia]
        post = r.get("post") or {}
        if not post.get("ok") or (post.get("tipo") or "dia") != "dia":
            continue
        pt = ponte(post, cfg, assunto_do_fato(r), titulo_do_fato(r))
        if pt and not pt.get("aba"):
            out.setdefault(pt["id"], []).append({"dia": dia, "data": f"{int(dia[8:10])}/{int(dia[5:7])}",
                                                 "titulo": post.get("titulo"), "url": f"/{dia}/"})
    return out


def ponte(post: dict, cfg: dict, assunto: str | None, titulo: str | None = None) -> dict | None:
    """A linha logo abaixo do fato do dia, que leva ao básico do assunto. A ordem segue o que a leitora acabou de ler:
    1. a página de uma pressão do assunto do fato (em "Juro e inflação", que tem duas, o título do fato decide: Copom
       ou Selic, a do juro; Focus, IPCA ou preços, a da inflação esperada; sem pista, a da tese da leitura a fundo);
    2. a página da pressão da tese da leitura a fundo (post.termina_em, gravado por src/fundo.py);
    3. a parte da aba O que causa recessão que explica o assunto (ou, sem ele, a pressão da tese), com o título da
       parte no link.
    Sem assunto nem tese (posts antigos, dias sem pauta), não há linha."""
    pags = {q["pressao"]: q for q in publicadas().values() if q.get("pressao")}
    tese = post.get("termina_em")
    do_assunto = PRESSOES_DO_ASSUNTO.get(assunto or "", [])
    com_pagina = [pid for pid in do_assunto if pid in pags]
    pelo_titulo = next((pid for pid, rx in PISTAS_DO_TITULO if pid in com_pagina and rx.search(titulo or "")), None)
    if len(com_pagina) > 1 and pelo_titulo:
        escolha = pelo_titulo
    elif tese in com_pagina:
        escolha = tese
    elif com_pagina:
        escolha = com_pagina[0]
    elif tese in pags:
        escolha = tese
    else:
        escolha = None
    if escolha:
        q = pags[escolha]
        sobre = SOBRE.get(escolha)
        return {"id": q["id"], "url": f"/perguntas/{q['id']}/", "texto": q["pergunta"],
                "rotulo": f"O básico sobre {sobre}" if sobre else "O básico, em 5 minutos"}
    causas = cfg["direcao"].get("causas", {})
    urls = [causas.get(pid) for pid in do_assunto] + [ABA_DO_ASSUNTO.get(assunto or ""), causas.get(tese or "")]
    url = next((u for u in urls if u), None)
    if not url:
        return None
    titulo = _partes_da_aba().get(url.split("#", 1)[-1]) if "#" in url else None
    return {"url": url, "texto": titulo or "O que causa recessão", "rotulo": "O básico, na página O que causa recessão",
            "aba": True}


def falta_pagina(rodadas: list[dict], cfg: dict, hoje: str) -> list[str]:
    """Os avisos ao Pedro de que talvez falte uma página (decisão dele em 8/11/2026: o site não cria pergunta sozinho).
    Dois sinais: um assunto sem página de pressão em VEZES_DO_AVISO fatos do dia ou mais nos últimos DIAS_DO_AVISO
    dias (o link do fato caiu na página O que causa recessão), e o editor-chefe da pesquisa do dia dizendo que sentiu
    falta de uma página (post.fundo.pagina_que_falta). Uma rodada por dia, a última."""
    por_dia: dict[str, dict] = {}
    for r in rodadas:
        por_dia[(r.get("gerado_em") or r.get("id") or "")[:10]] = r
    inicio = (dt.date.fromisoformat(hoje) - dt.timedelta(days=DIAS_DO_AVISO)).isoformat()
    sem_pagina: dict[str, list[str]] = {}
    avisos = []
    for dia in sorted(d for d in por_dia if inicio < d <= hoje):
        r = por_dia[dia]
        post = r.get("post") or {}
        if not post.get("ok") or (post.get("tipo") or "dia") != "dia":
            continue
        assunto = assunto_do_fato(r)
        pt = ponte(post, cfg, assunto, titulo_do_fato(r))
        if assunto and (pt is None or pt.get("aba")):
            sem_pagina.setdefault(assunto, []).append(dia)
        falta = ((post.get("fundo") or {}).get("pagina_que_falta") or "").strip()
        if dia == hoje and falta:
            avisos.append(f"O editor-chefe sentiu falta de uma página no fato do dia de {_data(dia)}: {falta}")
    nomes = cfg.get("fatores", {})
    for assunto, dias in sem_pagina.items():
        if len(dias) >= VEZES_DO_AVISO and hoje in dias:
            avisos.append(f"{len(dias)} fatos do dia nos últimos {DIAS_DO_AVISO} dias foram sobre {nomes.get(assunto, assunto)}, "
                          f"que não tem página própria ({', '.join(_data(d)[:-5] for d in dias)}). Vale uma página?")
    return avisos


def fundo_ctx(post: dict, cfg: dict, ligar) -> dict | None:
    """A leitura a fundo de um fato do dia (post.fundo em runs/, feita por src/fundo.py), para o post: a tese no botão,
    o texto corrido com os termos ligados à Wikipédia, as fontes e o link da página da pressão. O site não promete
    conferir nada depois (decisão do Pedro em 8/11/2026): a previsão com data que as leituras antigas tinham não aparece.
    As marcas do caderno ([c3]) saem do texto e viram a lista de fontes."""
    import fundo as fundo_mod
    f = post.get("fundo") or {}
    if not f.get("ok") or not f.get("texto"):
        return None
    bl = fundo_mod.blocos(f["texto"])
    pars = [fundo_mod.sem_marcas(b["p"]).strip() for b in bl if "p" in b]
    # Os termos já ligados no post não são ligados de novo na leitura a fundo.
    n = len(post.get("paragrafos", []))
    lig = iter(ligar([*post.get("paragrafos", []), *pars], cfg)[n:])
    blocos = [{"h": b["h"]} if "h" in b else {"p": next(lig)} for b in bl]
    cad = {c["id"]: c for c in f.get("caderno", [])}
    usadas = [cad[i] for i in dict.fromkeys(fundo_mod.marcas(f["texto"])) if i in cad]
    fontes, vistas = [], set()

    def quem(q: str, url: str | None) -> str:
        # O bastidor da pesquisa ("resumo da busca", "página não aberta") fica no registro, não na página.
        q = re.sub(r"\s*\([^)]*(busca|abert|página|resultado|memória)[^)]*\)", "", q or "", flags=re.I)
        q = re.sub(r"^(memória do (momento|site)|dados do site)\b[^(]*", "", q, flags=re.I).strip(" ,;")
        q = re.sub(r"^\((.*)\)$", r"\1", q).strip()
        if not q and url:
            q = re.sub(r"^www\d?\.", "", url.split("/")[2]) if "://" in url else ""
        return q or "fonte"

    so_site = False
    for c in usadas:
        if c["tipo"] == "conta":
            continue
        fos = [c.get("fonte") or {}] if (c.get("fonte") or {}).get("url") else c.get("fontes_memoria") or []
        if c["tipo"] == "site" and not fos:
            so_site = True
        for fo in fos if c["tipo"] != "documento" else [c.get("fonte") or {}]:
            nome = quem(fo.get("quem"), fo.get("url"))
            chave = fo.get("url") or fo.get("quem")
            if chave and chave not in vistas and nome not in vistas:
                vistas |= {chave, nome}
                fontes.append({"quem": nome, "url": fo.get("url")})
    if any(c["tipo"] == "conta" for c in usadas):
        fontes.append({"quem": "contas do site com as séries do Banco Central e do IBGE", "url": None})
    if so_site:
        fontes.append({"quem": "os dados e as notícias do dia, no registro do site", "url": None})
    palavras = sum(len(p.split()) for p in pars)
    return {"titulo": f["titulo"], "minutos": max(3, round(palavras / 200)), "blocos": blocos, "fontes": fontes}


def _paragrafos(texto: str) -> list[str]:
    return [t.strip() for t in texto.split("\n\n") if t.strip()]


def pergunta_ctx(p: dict, A: dict, E: dict, conf: dict, cfg: dict, ligar, posts: list[dict], outras: list[dict],
                 hoje: str) -> dict:
    """A página de uma pressão: a resposta, o que muda para a leitora, se é coisa de um governo só (com os casos
    desde 2002), as explicações da mais aceita à menos, o que está em jogo agora, os fatos do dia ligados e, recolhido
    no fim, como a página foi conferida."""
    fontes = _Fontes(A, conf)
    esc = {d["degrau"]: d for d in p["escada"]}
    raiz, depois = esc.get("raiz"), esc.get("o_que_vem_depois")
    gov, agora, medida = p.get("governo"), p.get("agora"), p.get("medida")
    # Liga os termos técnicos uma vez na página toda: junta os textos na ordem em que aparecem. Um texto com linha em
    # branco ("\n\n") vira mais de um parágrafo, como o passo "O que isso muda para você?".
    ordem: list[str] = [p["resposta_curta"]["texto"]]
    ordem += [t for x in (depois, medida, gov) if x for t in _paragrafos(x["texto"])]
    if raiz:
        ordem.append(raiz.get("peso_da_evidencia") or "")
        for lt in raiz.get("leituras", []):
            ordem += [lt.get("resumo") or lt["o_que_diz"]]
    if agora:
        ordem += _paragrafos(agora["texto"])
    lig = dict(zip(ordem, ligar(ordem, cfg)))

    def L(t: str | None) -> Markup | None:
        return lig.get(t, Markup.escape(t)) if t else None

    def bloco(x: dict | None, pergunta: str | None = None) -> dict | None:
        if not x:
            return None
        return {"pergunta": pergunta or x.get("pergunta"), "paragrafos": [L(t) for t in _paragrafos(x["texto"])],
                "fontes": fontes.de(x.get("afirmacoes", []))}

    resposta = {"texto": L(p["resposta_curta"]["texto"]), "fontes": fontes.de(p["resposta_curta"]["afirmacoes"])}
    muda = bloco(depois)
    # Como o topo mede a pressão desta página, em duas ou três frases, com o link para Como funciona.
    como_mede = bloco(medida)
    governo = bloco(gov)
    eps = []
    for e in sorted((E[i] for i in p.get("episodios", []) if i in E), key=lambda e: e["periodo"]["de"]):
        de, ate = e["periodo"]["de"][:4], e["periodo"]["ate"][:4]
        anos = de if de == ate else f"{de}–{ate[2:]}"
        eps.append({"anos": anos, "titulo": e["titulo"], "periodo": _periodo(e["periodo"]), "resumo": e["resumo"],
                    "causa": CAUSAS.get(e["causa"], e["causa"]), "causa_cls": e["causa"].replace(" ", "-"),
                    "fontes": fontes.de(e["afirmacoes"])})

    explic = None
    if raiz:
        cartoes, grupos = [], []
        def detalhe(lt: dict, com_objecao: bool) -> dict:
            item = {"a_favor": [{"texto": Markup.escape(x["texto"]), "fontes": fontes.de(x["afirmacoes"])}
                                for x in lt.get("a_favor", []) + lt.get("estudos", [])],
                    "quem_defende": lt.get("quem_defende")}
            for k in ("melhor_objecao", "resposta"):
                if lt.get(k) and (k != "melhor_objecao" or com_objecao):
                    item[k] = {"texto": Markup.escape(lt[k]["texto"]), "fontes": fontes.de(lt[k].get("afirmacoes", [])),
                               "pendente": bool(lt[k].get("fonte_pendente"))}
            return item
        leituras = sorted(raiz.get("leituras", []), key=lambda x: ORDEM_STATUS.index(x["status"]))
        for lt in leituras:
            if lt["status"] in CARTOES:
                mo = lt.get("melhor_objecao") or {}
                cartoes.append({"id": lt["id"], "titulo": lt.get("titulo") or lt["nome"], "peso": CARTOES[lt["status"]],
                                "texto": L(lt["o_que_diz"]), "fontes": fontes.de(lt.get("o_que_diz_afirmacoes", [])),
                                "contra": {"texto": Markup.escape(mo.get("texto", "")), "fontes": fontes.de(mo.get("afirmacoes", []))} if mo else None,
                                "detalhe": detalhe(lt, False)})
        for sts, um, varios in GRUPOS:
            itens = [lt for lt in leituras if lt["status"] in sts]
            if itens:
                grupos.append({"titulo": um if len(itens) == 1 else varios,
                               "itens": [{"id": lt["id"], "texto": L(lt.get("resumo") or lt["o_que_diz"]),
                                          "detalhe": detalhe(lt, True)} for lt in itens]})
        explic = {"peso": L(raiz.get("peso_da_evidencia")), "peso_fontes": fontes.de(raiz.get("peso_afirmacoes", [])),
                  "cartoes": cartoes, "grupos": grupos}

    # "O que está em jogo agora" só aparece quando um fato do dia dos últimos 30 dias terminou nesta pressão.
    em_jogo = None
    if agora and posts and (dt.date.fromisoformat(hoje) - dt.date.fromisoformat(posts[0]["dia"])).days <= DIAS_DO_AGORA:
        em_jogo = {**bloco(agora), "atualizado": _data(agora["atualizado_em"])}

    return {"pergunta": p["pergunta"], "id": p["id"], "pressao": cfg["direcao"]["nomes"].get(p.get("pressao"), ""),
            "atualizado": _data(p["atualizado_em"]), "resposta": resposta, "muda": muda, "medida": como_mede, "governo": governo,
            "episodios": eps, "explicacoes": explic, "agora": em_jogo, "fatos": posts, "outras": outras,
            "fontes": fontes.ordem, "conferidas": sum(1 for f in fontes.ordem if f["conferida"]), "total": len(fontes.ordem),
            "mudancas": [{"data": _data(x["data"]), "o_que": x["o_que"], "motivo": x["motivo"]} for x in p.get("mudancas", [])]}


def gravar(gravar_pagina, ctx: dict, cfg: dict, docs: Path, site: str, ligar) -> list[str]:
    """Grava /perguntas/<id>/ para cada pergunta publicada de base/perguntas (uma por pressão do topo) e devolve os
    endereços. Pergunta apagada ou de volta a rascunho sai do site."""
    pasta = docs / "perguntas"
    perguntas = publicadas()
    if not perguntas:
        if pasta.exists():
            shutil.rmtree(pasta)
        return []
    A = {a["id"]: a for a in json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]}
    E = {e["id"]: e for e in json.loads((BASE / "episodios.json").read_text())["episodios"]}
    conf = _conferencia()
    ligados = _posts_ligados(cfg)
    nomes = cfg["direcao"]["nomes"]
    ordem = list(nomes)
    lista = sorted(perguntas.values(), key=lambda q: ordem.index(q["pressao"]) if q.get("pressao") in ordem else 99)
    hoje = dt.date.today().isoformat()
    feitos = []
    for q in lista:
        pid = q["id"]
        outras = [{"pressao": nomes.get(o.get("pressao"), ""), "pergunta": o["pergunta"], "url": f"/perguntas/{o['id']}/",
                   "aqui": o["id"] == pid} for o in lista] if len(lista) > 1 else []
        qc = pergunta_ctx(q, A, E, conf, cfg, ligar, ligados.get(pid, []), outras, hoje)
        gravar_pagina(pasta / pid, "pergunta.html", {**ctx, "q": qc, "og_url": f"{site}/og.png", "link_inicio": "/"},
                      f"{site}/perguntas/{pid}/")
        feitos.append(f"/perguntas/{pid}/")
    if pasta.exists():
        for sub in pasta.iterdir():
            if sub.is_dir() and sub.name not in perguntas:
                shutil.rmtree(sub)
    return feitos
