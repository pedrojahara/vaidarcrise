"""O que o site mostra da base de conhecimento (base/), fase 0: o "Entenda a fundo" dos fatos do dia que têm escada
de porquês (post.escada em runs/) e a página de cada pergunta-mãe, em /perguntas/<id>/.

Tudo vem de base/: as afirmações que sustentam cada frase, as perguntas, os episódios e o último relatório do
verificador (base/conferencia/), que diz se a fonte de cada afirmação já foi conferida. build_site.py chama
escada_ctx() em cada post e gravar() no fim; um erro aqui não derruba a atualização do dia.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "base"

ROTULOS = {"fato": "Fato", "consenso": "Os estudos concordam", "maioria_com_dissenso": "A maioria concorda",
           "em_disputa": "Os economistas divergem"}
STATUS = {"em_pe": "Ainda de pé", "maioria": "A maioria defende", "em_disputa": "Em disputa", "minoria": "Minoria",
          "pouco_testada": "Pouco testada", "testada_e_nao_confirmada": "Testada e não confirmada"}
ORDEM_STATUS = ["maioria", "em_pe", "em_disputa", "pouco_testada", "minoria", "testada_e_nao_confirmada"]
NIVEIS = {1: "Revisão de muitos estudos", 2: "Estudo em revista científica", 3: "Órgão oficial",
          4: "Tese ou dissertação", 5: "Banco, consultoria ou associação", 6: "Notícia", 7: "Comentarista"}
CAUSAS = {"daqui": "Causa daqui", "de fora": "Causa de fora", "as duas": "Causas daqui e de fora"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


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
    """O status de cada afirmação no relatório mais novo do verificador; a conferência com a página aberta (no Mac)
    vale mais que a do modo offline do mesmo dia."""
    rels = sorted((BASE / "conferencia").glob("*-verifica*.json"), key=lambda p: (p.name[:10], "offline" not in p.name))
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


def escada_ctx(post: dict, cfg: dict, ligar) -> dict | None:
    """A escada de porquês de um fato do dia (post.escada em runs/), para o "Entenda a fundo" do post: cada degrau com
    o rótulo, o texto com os termos ligados, as fontes e, quando há, o link para a parte da pergunta-mãe."""
    if not post.get("escada"):
        return None
    A = {a["id"]: a for a in json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]}
    p = _perguntas().get(post.get("pergunta"))
    fontes = _Fontes(A, _conferencia())
    testes = {t["id"]: t for t in (p or {}).get("testes", [])}
    url = f"/perguntas/{p['id']}/" if p else None
    # Os termos já ligados no post não são ligados de novo no "Entenda a fundo".
    textos = list(post.get("paragrafos", [])) + [d["texto"] for d in post["escada"]]
    lig = ligar(textos, cfg)[len(post.get("paragrafos", [])):]
    degraus = []
    for d, txt in zip(post["escada"], lig):
        g = {"pergunta": d["pergunta"], "rotulo": d["rotulo"], "rotulo_nome": ROTULOS[d["rotulo"]], "texto": txt,
             "fontes": fontes.de(d["afirmacoes"]), "link": d.get("link")}
        if d.get("teste") and d["teste"] in testes:
            t = testes[d["teste"]]
            g["teste_quando"] = " e em ".join(_data(c) for c in t["conferir_em"])
        if url and d.get("teste"):
            g["mais"] = {"url": f"{url}#teste", "texto": "Como o teste funciona"}
        elif url and d["rotulo"] == "em_disputa" and d.get("liga"):
            g["mais"] = {"url": f"{url}#{d['liga']}", "texto": "As duas leituras, com o que pesa a favor e contra cada uma"}
        degraus.append(g)
    return {"degraus": degraus, "pergunta": p["pergunta"] if p else None, "url": url}


def pergunta_ctx(p: dict, A: dict, E: dict, conf: dict, cfg: dict, ligar) -> dict:
    """A pergunta-mãe para a página: resposta curta, escada (com as leituras e o teste), episódios e fontes."""
    fontes = _Fontes(A, conf)
    # Liga os termos técnicos uma vez na página toda: junta os textos na ordem em que aparecem.
    ordem: list[str] = [p["resposta_curta"]["texto"]]
    for d in p["escada"]:
        for t in (d.get("texto"), (d.get("consenso") or {}).get("texto"), d.get("em_disputa"), d.get("peso_da_evidencia")):
            if t:
                ordem.append(t)
        for lt in d.get("leituras", []):
            ordem += [lt["o_que_diz"]] + [x["texto"] for x in lt.get("a_favor", []) + lt.get("estudos", [])]
            ordem += [lt[k]["texto"] for k in ("melhor_objecao", "resposta") if lt.get(k)]
    lig = dict(zip(ordem, ligar(ordem, cfg)))

    def L(t: str | None) -> Markup | None:
        return lig.get(t, Markup.escape(t)) if t else None

    testes = {t["id"]: t for t in p.get("testes", [])}
    escada = []
    for d in p["escada"]:
        rot = "fato" if d["degrau"] == "fato" else d["rotulo"]
        g = {"id": d.get("id") or d["degrau"], "degrau": d["degrau"], "pergunta": d["pergunta"], "rotulo": rot,
             "rotulo_nome": ROTULOS[rot], "texto": L(d.get("texto")), "fontes": fontes.de(d.get("afirmacoes", []))}
        if d.get("consenso"):
            g["consenso"] = {"texto": L(d["consenso"]["texto"]), "fontes": fontes.de(d["consenso"]["afirmacoes"])}
        if d.get("em_disputa"):
            g["em_disputa"] = {"texto": L(d["em_disputa"]), "fontes": fontes.de(d.get("em_disputa_afirmacoes", []))}
        if d.get("peso_da_evidencia"):
            g["peso"] = {"texto": L(d["peso_da_evidencia"]), "fontes": fontes.de(d.get("peso_afirmacoes", []))}
        leituras = []
        for lt in sorted(d.get("leituras", []), key=lambda x: ORDEM_STATUS.index(x["status"])):
            item = {"id": lt["id"], "nome": lt["nome"], "status": lt["status"], "status_nome": STATUS[lt["status"]],
                    "o_que_diz": L(lt["o_que_diz"]), "o_que_diz_fontes": fontes.de(lt.get("o_que_diz_afirmacoes", [])),
                    "a_favor": [{"texto": L(x["texto"]), "fontes": fontes.de(x["afirmacoes"])}
                                for x in lt.get("a_favor", []) + lt.get("estudos", [])],
                    "quem_defende": lt.get("quem_defende")}
            for k in ("melhor_objecao", "resposta"):
                if lt.get(k):
                    item[k] = {"texto": L(lt[k]["texto"]), "fontes": fontes.de(lt[k].get("afirmacoes", [])),
                               "pendente": bool(lt[k].get("fonte_pendente"))}
            leituras.append(item)
        g["leituras"] = leituras
        if d.get("teste") and d["teste"] in testes:
            t = testes[d["teste"]]
            nomes = {lt["id"]: lt["nome"] for lt in d.get("leituras", [])}
            g["teste"] = {"pergunta": t["pergunta"], "como": t["como"], "limites": t["limites"],
                          "espera": [{"nome": nomes.get(k, k), "texto": v} for k, v in t["o_que_cada_leitura_espera"].items()],
                          "regra": t["regra"], "quando": [_data(c) for c in t["conferir_em"]],
                          "registrado": _data(t["registrado_em"]), "resultados": t.get("resultados", [])}
        escada.append(g)
    eps = []
    for e in sorted((E[i] for i in p.get("episodios", []) if i in E), key=lambda e: e["periodo"]["de"]):
        eps.append({"titulo": e["titulo"], "periodo": _periodo(e["periodo"]), "resumo": e["resumo"],
                    "causa": CAUSAS.get(e["causa"], e["causa"]), "fontes": fontes.de(e["afirmacoes"])})
    return {"pergunta": p["pergunta"], "id": p["id"], "atualizado": _data(p["atualizado_em"]),
            "resposta": L(p["resposta_curta"]["texto"]), "resposta_fontes": fontes.de(p["resposta_curta"]["afirmacoes"]),
            "escada": escada, "episodios": eps, "fontes": fontes.ordem,
            "mudancas": [{"data": _data(x["data"]), "o_que": x["o_que"], "motivo": x["motivo"]} for x in p.get("mudancas", [])],
            "conferidas": sum(1 for f in fontes.ordem if f["conferida"]), "total": len(fontes.ordem)}


def gravar(gravar_pagina, ctx: dict, cfg: dict, docs: Path, site: str, ligar) -> list[str]:
    """Grava /perguntas/<id>/ para cada pergunta-mãe de base/perguntas e devolve os endereços. Pergunta apagada de
    base/ sai do site."""
    pasta = docs / "perguntas"
    perguntas = _perguntas()
    if not perguntas:
        if pasta.exists():
            shutil.rmtree(pasta)
        return []
    A = {a["id"]: a for a in json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]}
    E = {e["id"]: e for e in json.loads((BASE / "episodios.json").read_text())["episodios"]}
    conf = _conferencia()
    feitos = []
    for pid, q in perguntas.items():
        gravar_pagina(pasta / pid, "pergunta.html", {**ctx, "q": pergunta_ctx(q, A, E, conf, cfg, ligar), "og_url": f"{site}/og.png",
                                                     "link_inicio": "/"}, f"{site}/perguntas/{pid}/")
        feitos.append(f"/perguntas/{pid}/")
    for sub in pasta.iterdir():
        if sub.is_dir() and sub.name not in perguntas:
            shutil.rmtree(sub)
    return feitos


