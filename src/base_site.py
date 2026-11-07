"""O que o site mostra da base de conhecimento (base/): o "Entenda a fundo" dos fatos do dia que têm escada de porquês
(post.escada em runs/) e a página de cada pressão do topo que já tem pergunta publicada, em /perguntas/<id>/.

Uma página por pressão: cada pergunta de base/perguntas diz a pressão dela (pressao, uma das chaves de
direcao.nomes em config/modelo.json). Cada fato do dia leva à página da pressão onde a corrente de porquês termina
(post.pergunta). Rascunho (publicada: false) não vira página, mas o teste dele aparece no post que o cita.

Tudo vem de base/: as afirmações que sustentam cada frase, as perguntas, os episódios e o último relatório do
verificador (base/conferencia/), que diz se a fonte de cada afirmação já foi conferida. build_site.py chama
escada_ctx() em cada post e gravar() no fim; um erro aqui não derruba a atualização do dia.
"""
from __future__ import annotations

import datetime as dt
import json
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
    não abre nenhuma e marca toda fonte como "nao_aberta": só vale quando não há outro relatório."""
    rels = sorted((BASE / "conferencia").glob("*-verifica*.json"), key=lambda p: ("offline" not in p.name, p.name[:10]))
    if not rels:
        return {}
    return json.loads(rels[-1].read_text()).get("afirmacoes", {})


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
        elif a["tipo"] == "site":
            como = "trecho conferido no site" if st == "conferido" else "trecho a conferir"
        else:
            como = "trecho conferido no texto da fonte" if st == "conferido" else "a conferir no texto da fonte"
        # O título de série ou de arquivo do site é para quem confere a conta, não para a leitora.
        titulo = f.get("titulo") if a["tipo"] == "documento" else None
        return {"quem": f["quem"], "titulo": titulo, "url": f.get("url"), "nivel": NIVEIS.get(f["nivel"], ""),
                "conferida": st == "conferido", "como": como}


def _perguntas() -> dict:
    return {json.loads(p.read_text())["id"]: json.loads(p.read_text()) for p in sorted((BASE / "perguntas").glob("*.json"))}


def publicadas() -> dict:
    """As perguntas que já têm página. Um rascunho (publicada: false) guarda a disputa e o teste até a página sair."""
    return {k: q for k, q in _perguntas().items() if q.get("publicada", True)}


def pergunta_da_pressao(pid: str) -> dict | None:
    """O link para a página da pressão do topo, se ela já existe: uma página por pressão."""
    for q in publicadas().values():
        if q.get("pressao") == pid:
            return {"url": f"/perguntas/{q['id']}/", "texto": q["pergunta"]}
    return None


def _posts_ligados() -> dict[str, list[dict]]:
    """Os fatos do dia com escada (runs/), por pergunta: o mais novo primeiro, um por dia."""
    por_dia: dict[str, dict] = {}
    for arq in sorted((ROOT / "runs").glob("*.json")):
        post = json.loads(arq.read_text()).get("post") or {}
        if post.get("escada") and post.get("pergunta"):
            por_dia[arq.stem[:10]] = post
    out: dict[str, list[dict]] = {}
    for dia in sorted(por_dia, reverse=True):
        post = por_dia[dia]
        out.setdefault(post["pergunta"], []).append({"dia": dia, "data": f"{int(dia[8:10])}/{int(dia[5:7])}",
                                                     "titulo": post.get("titulo"), "url": f"/{dia}/"})
    return out


def _regra_do_teste(t: dict) -> str:
    """A regra do teste numa frase da leitora, com os números da regra registrada."""
    g, r = t.get("quem_ganha", {}), t["regra"]
    lo, hi = r["favorece_l_fora_entre"]
    fmt = lambda x: f"{x:.0f}".replace("-", "−")
    return (f"Se a alta contra o real passar a dos dois pesos em mais de {fmt(r['favorece_l_daqui_acima_de'])} pontos, "
            f"pesa mais {g.get('l-daqui', 'a primeira leitura')}. Se a diferença ficar entre {fmt(lo)} e {fmt(hi)} pontos, "
            f"pesa mais {g.get('l-fora', 'a segunda')}. Fora disso, o teste não decide.")


def escada_ctx(post: dict, cfg: dict, ligar) -> dict | None:
    """A escada de porquês de um fato do dia (post.escada em runs/), para o "Entenda a fundo" do post: cada degrau com
    o rótulo, o texto com os termos ligados e as fontes; o degrau do teste traz a regra; no fim, o link para a página
    da pressão onde a corrente termina, se ela já existe."""
    if not post.get("escada"):
        return None
    A = {a["id"]: a for a in json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]}
    todas = _perguntas()
    p = todas.get(post.get("pergunta"))
    fontes = _Fontes(A, _conferencia())
    # O teste fica na pergunta da pressão dele, mesmo quando a página ainda é rascunho.
    testes = {t["id"]: t for q in todas.values() for t in q.get("testes", [])}
    # Os termos já ligados no post não são ligados de novo no "Entenda a fundo".
    textos = list(post.get("paragrafos", [])) + [d["texto"] for d in post["escada"]]
    lig = ligar(textos, cfg)[len(post.get("paragrafos", [])):]
    degraus = []
    for d, txt in zip(post["escada"], lig):
        g = {"pergunta": d["pergunta"], "rotulo": d.get("rotulo"), "rotulo_nome": ROTULOS.get(d.get("rotulo")),
             "texto": txt, "fontes": fontes.de(d["afirmacoes"]), "link": d.get("link")}
        if d.get("teste") and d["teste"] in testes:
            t = testes[d["teste"]]
            g["teste"] = {"quando": " e em ".join(_data(c) for c in t["conferir_em"]), "como": t["como"],
                          "regra": _regra_do_teste(t), "limites": t["limites"],
                          "resultados": [{"data": _data(r["conferido_em"]), "texto": r.get("texto", "")} for r in t.get("resultados", [])]}
        degraus.append(g)
    # O link do fim vai para a página da pressão onde a corrente termina. Se essa pressão ainda não tem página, vai
    # para a parte da aba O que causa recessão que explica a pressão, como o "Como isso funciona" do topo.
    ponte = None
    termina = post.get("termina_em") or (p or {}).get("pressao")
    if p and p.get("publicada", True):
        ponte = {"url": f"/perguntas/{p['id']}/", "pergunta": p["pergunta"],
                 "pressao": cfg["direcao"]["nomes"].get(p.get("pressao"), "")}
    elif termina and cfg["direcao"].get("causas", {}).get(termina):
        ponte = {"url": cfg["direcao"]["causas"][termina], "aba": True}
    return {"degraus": degraus, "ponte": ponte}


def pergunta_ctx(p: dict, A: dict, E: dict, conf: dict, cfg: dict, ligar, posts: list[dict], outras: list[dict],
                 hoje: str) -> dict:
    """A página de uma pressão: a resposta, o que muda para a leitora, se é coisa de um governo só (com os casos
    desde 2002), as explicações da mais aceita à menos, o que está em jogo agora, os fatos do dia ligados e, recolhido
    no fim, como a página foi conferida."""
    fontes = _Fontes(A, conf)
    esc = {d["degrau"]: d for d in p["escada"]}
    raiz, depois = esc.get("raiz"), esc.get("o_que_vem_depois")
    gov, agora = p.get("governo"), p.get("agora")
    # Liga os termos técnicos uma vez na página toda: junta os textos na ordem em que aparecem.
    ordem: list[str] = [p["resposta_curta"]["texto"]]
    ordem += [x["texto"] for x in (depois, gov) if x]
    if raiz:
        ordem.append(raiz.get("peso_da_evidencia") or "")
        for lt in raiz.get("leituras", []):
            ordem += [lt.get("resumo") or lt["o_que_diz"]]
    if agora:
        ordem.append(agora["texto"])
    lig = dict(zip(ordem, ligar(ordem, cfg)))

    def L(t: str | None) -> Markup | None:
        return lig.get(t, Markup.escape(t)) if t else None

    def bloco(x: dict | None, pergunta: str | None = None) -> dict | None:
        if not x:
            return None
        return {"pergunta": pergunta or x.get("pergunta"), "texto": L(x["texto"]), "fontes": fontes.de(x.get("afirmacoes", []))}

    resposta = {"texto": L(p["resposta_curta"]["texto"]), "fontes": fontes.de(p["resposta_curta"]["afirmacoes"])}
    muda = bloco(depois)
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
            "atualizado": _data(p["atualizado_em"]), "resposta": resposta, "muda": muda, "governo": governo,
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
    ligados = _posts_ligados()
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
