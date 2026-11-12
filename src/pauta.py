"""A pauta do texto do dia: a história em andamento que mais andou ontem (CARTA_EDITORIAL.md).

O texto do dia não conta um fato: ele faz um argumento sobre uma história em andamento (base/memoria/historias.json),
com todos os fatos de ontem sobre ela como prova. O código escolhe a história, sem IA:

1. cada notícia que o classificador leu (src/classify_news.py) diz de qual história ela é um passo e vale
   tamanho x peso do estágio: decisão tomada ou dado divulgado 1; o marco que a história esperava, mesmo que tenha
   chegado vazio, 1; a previsão de PIB ou de recessão de uma casa grande que muda de lado, 1; proposta em votação 0,7;
   anúncio com medida ou previsão comum 0,5; fala sem medida ou rumor 0,25;
2. a história soma as notícias dela;
3. se a direção do risco mudou, ou uma pressão mudou de lado, a história dessa pressão é a do dia;
4. senão, a de maior soma, com duas regras: a mesma história sai no máximo 2 dias seguidos, a não ser que traga uma
   decisão ou um dado de tamanho 2 ou mais; e no empate vale a que saiu em mais jornais;
5. se nenhuma história passa de 1,5, o dia é calmo e o texto é curto;
6. uma segunda história entra num parágrafo só se também passar de 1,5.

Um fato que não é passo de nenhuma história abre uma história nova no dia se for grande (tamanho 2 ou mais) e já
consumado; menor, ele espera e abre a história se voltar em 3 dos últimos 7 dias. Nos dois casos, o Pedro recebe o
aviso. A pergunta da semana do domingo (src/fundo.py, pauta_da_semana) soma as pautas dos sete dias pela mesma conta.
"""
from __future__ import annotations

import datetime as dt
import re

import direcao as direcao_mod

# Quanto menor, mais firme: fato consumado primeiro, rumor por último.
RANK = {"dado": 0, "decidido": 0, "em_votacao": 1, "anuncio": 2, "previsao": 3, "rumor": 4}
CONSUMADO = {"dado", "decidido"}
ESTAGIO_TXT = {"dado": "dado divulgado", "decidido": "decisão tomada", "em_votacao": "proposta em votação",
               "anuncio": "anúncio, sem ato formal", "previsao": "previsão (de banco, consultoria ou governo), não fato consumado",
               "rumor": "rumor"}
# O peso de cada estágio na soma da história.
PESO = {"dado": 1.0, "decidido": 1.0, "em_votacao": 0.7, "anuncio": 0.5, "previsao": 0.5, "rumor": 0.25}
PESO_SEM_MEDIDA = 0.25
CALMO = 1.5          # abaixo disso, nenhuma história andou: o dia é calmo
GRANDE = 2           # o tamanho do fato consumado que abre história no dia e que deixa a história sair 3 dias seguidos
DIAS_SEGUIDOS = 2
VOLTAS_PARA_ABRIR = 3  # um tema pequeno abre história se voltar em 3 dos últimos 7 dias
JANELA_TEMA = 7
# As datas marcadas, e como achar a notícia de cada uma: chegam como marco da história, mesmo sem novidade.
MARCADAS = {
    "pib": "o PIB do trimestre (IBGE)",
    "copom": "a decisão do Banco Central sobre a Selic (Copom)",
    "pnad": "o desemprego da PNAD (IBGE)",
}
OUTRAS_DATAS = {"ipca": "a inflação do mês, IPCA (IBGE)", "ipca15": "a prévia da inflação, IPCA-15 (IBGE)",
                "pim": "a produção industrial (IBGE)", "pmc": "as vendas do varejo (IBGE)",
                "fed": "a decisão de juros dos Estados Unidos (Fed)"}


def _bate_data(tipo: str, c: dict) -> bool:
    """Se o candidato `c` é a notícia da data marcada `tipo`."""
    if c["estagio"] not in CONSUMADO:
        return False
    t = c["titulo"]
    if tipo == "copom":
        return c["fator"] == "juro" and c.get("origem") == "banco_central" and c["estagio"] == "decidido"
    if tipo == "pib":
        return c["fator"] == "atividade" and bool(re.search(r"\bPIB\b", t)) and not re.search(r"prévia|previsão|Focus", t, re.I)
    if tipo == "pnad":
        return c["fator"] == "emprego" and bool(re.search(r"desemprego|desocupa", t, re.I))
    if tipo in ("ipca", "ipca15"):
        return c["fator"] == "juro" and c["estagio"] == "dado" and bool(re.search(r"\bIPCA", t))
    return False


def vaivem(fator: str, estagio: str) -> bool:
    """O fechamento do mercado do dia: dólar, Bolsa, juros futuros, risco-país."""
    return fator == "mercado" and estagio == "dado"


def chave(c: dict) -> tuple:
    """A ordem das notícias dentro de uma história: estágio, tamanho, o vaivém do mercado atrás, jornais, manchetes;
    no empate, a ordem do classificador."""
    return (RANK.get(c["estagio"], 5), -c["tamanho"], vaivem(c["fator"], c["estagio"]), -len(c["jornais"]),
            -c["n_manchetes"], c.get("ordem", 0))


def cobertura(ids: list[str], cesta_por_id: dict | None, fontes: list[dict]) -> dict:
    """Quantas manchetes e quais jornais deram o fato. Sem a cesta do dia, vale o que o evento guardou."""
    if cesta_por_id:
        its = [cesta_por_id[i] for i in dict.fromkeys(ids) if i in cesta_por_id]
        if its:
            return {"manchetes": len(its), "jornais": sorted({it["veiculo"] for it in its})}
    return {"manchetes": len(fontes), "jornais": sorted({f["veiculo"] for f in fontes})}


def peso(c: dict) -> float:
    """O peso de uma notícia na soma da história."""
    if c.get("marco") or c.get("previsao_virou"):
        return 1.0
    if c.get("sem_medida") and c["estagio"] in ("anuncio", "previsao", "em_votacao"):
        return PESO_SEM_MEDIDA
    return PESO.get(c["estagio"], PESO_SEM_MEDIDA)


def candidatos(llm_eventos: list[dict], novos_ids: list[str], descartados: list[dict], eventos: dict,
               cesta_por_id: dict | None = None, nomes_fatores: dict | None = None) -> list[dict]:
    """Um candidato por evento que o classificador montou, na ordem dele (E1, E2...). run.py guarda, na mesma ordem,
    os eventos novos e os descartados; o descartado (continuação de um fato já contado ou dado já medido) fica fora
    da soma."""
    out, fila = [], list(novos_ids)
    desc = list(descartados)
    for k, ev in enumerate(llm_eventos, 1):
        # run.py guarda o descartado com os campos do evento: as mesmas manchetes acham o par.
        d = next((x for x in desc if x.get("noticia_ids") == ev.get("noticia_ids")), None)
        if d is not None:
            desc.remove(d)
            ev_id, base, fontes, motivo = None, ev, d.get("fontes", []), d["motivo"]
        else:
            ev_id = fila.pop(0) if fila else None
            # O evento guardado é o registro do site (o título pode ter sido reescrito depois): ele vale.
            base = {**ev, **{k: v for k, v in (eventos.get(ev_id) or {}).items()
                             if k in ("titulo_evento", "estagio", "magnitude", "fator", "direcao", "porque", "origem",
                                      "historia", "tema_novo", "marco", "previsao_virou", "sem_medida")}}
            fontes, motivo = (eventos.get(ev_id) or {}).get("fontes", []), None
        cob = cobertura([*ev.get("noticia_ids", []), *ev.get("outras_ids", [])], cesta_por_id, fontes)
        out.append({
            "id": f"E{k}", "ordem": k, "evento": ev_id, "titulo": base["titulo_evento"], "estagio": base["estagio"],
            "tamanho": base["magnitude"], "fator": base["fator"], "origem": base.get("origem"),
            "assunto": (nomes_fatores or {}).get(base["fator"], base["fator"]),
            "lado": "pesa" if base["direcao"] > 0 else "alivia", "ja_esperado": bool(ev.get("ja_no_preco")),
            "porque": base["porque"], "historia": base.get("historia") or "nova", "tema_novo": base.get("tema_novo") or "",
            "marco": bool(base.get("marco")), "previsao_virou": bool(base.get("previsao_virou")),
            "sem_medida": bool(base.get("sem_medida")), "n_manchetes": cob["manchetes"], "jornais": cob["jornais"],
            "descartado": motivo, "fontes": fontes[:6],
        })
    return out


def _lados(r: dict | None) -> dict:
    return {x["id"]: x["lado"] for x in (((r or {}).get("resultado") or {}).get("direcao") or {}).get("partes", [])}


def datas_lidas(rodada: dict, cal: list[dict]) -> list[dict]:
    """As datas do calendário que caem nos dias de notícia que esta atualização leu."""
    dias = set((rodada.get("cobertura") or {}).get("dias") or [])
    if not dias:
        ontem = (dt.date.fromisoformat(rodada["gerado_em"][:10]) - dt.timedelta(days=1)).isoformat()
        dias = {ontem}
    return [x for x in cal if x["data"] in dias]


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")[:40] or "tema"


def voltas_dos_temas(eventos: dict, hoje: str) -> dict[str, set[str]]:
    """Os dias, entre os 6 anteriores a `hoje`, em que cada tema novo (que não era passo de nenhuma história) apareceu
    nas notícias (data/eventos.json; o dia é o da rodada que leu a notícia)."""
    inicio = (dt.date.fromisoformat(hoje) - dt.timedelta(days=JANELA_TEMA - 1)).isoformat()
    out: dict[str, set[str]] = {}
    for e in eventos.values():
        m = re.match(r"ev-(\d{4})(\d{2})(\d{2})-", e.get("id", ""))
        if not m or e.get("historia") != "nova" or not e.get("tema_novo"):
            continue
        dia = "-".join(m.groups())
        if inicio <= dia < hoje:
            out.setdefault(_slug(e["tema_novo"]), set()).add(dia)
    return out


def somar(cands: list[dict], historias: list[dict], voltas: dict[str, set[str]], hoje: str) -> tuple[list[dict], list[dict]]:
    """A soma de cada história com as notícias do dia, e os temas novos: os que abrem história hoje (grandes e
    consumados, ou que voltaram em 3 dos últimos 7 dias) entram na soma; os outros esperam."""
    abertas = {h["id"]: h for h in historias}
    grupos: dict[str, dict] = {}
    esperando: dict[str, dict] = {}
    for c in cands:
        if c["descartado"]:
            continue
        hid = c["historia"] if c["historia"] in abertas else None
        nova = False
        if hid is None:
            tema = _slug(c["tema_novo"] or c["titulo"])
            grande = c["estagio"] in CONSUMADO and c["tamanho"] >= GRANDE
            if not grande and len(voltas.get(tema, set()) | {hoje}) < VOLTAS_PARA_ABRIR:
                e = esperando.setdefault(tema, {"tema": tema, "titulo": c["titulo"], "candidatos": [],
                                                "dias": len(voltas.get(tema, set()) | {hoje})})
                e["candidatos"].append(c["id"])
                continue
            hid, nova = f"nova:{tema}", True
        g = grupos.setdefault(hid, {"id": hid, "titulo": (abertas.get(hid) or {}).get("titulo") or c["titulo"],
                                    "pressao": (abertas.get(hid) or {}).get("pressao"),
                                    "pressoes": (abertas.get(hid) or {}).get("pressoes") or [], "nova": nova,
                                    "pontos": 0.0, "candidatos": [], "jornais": set(), "fato_grande": False})
        g["pontos"] += c["tamanho"] * peso(c)
        g["candidatos"].append(c["id"])
        g["jornais"] |= set(c["jornais"])
        if c["estagio"] in CONSUMADO and c["tamanho"] >= GRANDE:
            g["fato_grande"] = True
    por_id = {c["id"]: c for c in cands}
    out = []
    for g in grupos.values():
        g["candidatos"].sort(key=lambda i: chave(por_id[i]))
        out.append({**g, "pontos": round(g["pontos"], 2), "jornais": len(g["jornais"])})
    out.sort(key=lambda g: (-g["pontos"], -g["jornais"]))
    return out, list(esperando.values())


def escolher(somas: list[dict], historias: list[dict], virada: dict, seguidas: list[str]) -> dict:
    """A história do dia. `virada` diz se a direção do risco mudou e quais pressões mudaram de lado; `seguidas`, as
    histórias dos textos do dia anteriores, do mais recente para o mais antigo."""
    abertas = {h["id"]: h for h in historias}
    if virada["direcao"] or virada["pressoes"]:
        # A direção mudou, ou uma pressão mudou de lado: a história dessa pressão é a do dia, mesmo sem notícia.
        alvo = set(virada["pressoes"])

        def da(x: dict) -> int:
            # 2: a pressão principal da história mudou; 1: uma das duas primeiras pressões dela; 0: nenhuma.
            return 2 if x.get("pressao") in alvo else 1 if set((x.get("pressoes") or [])[:2]) & alvo else 0
        da_pressao = sorted((g for g in somas if da(g)), key=lambda g: (-da(g), -g["pontos"], -g["jornais"]))
        if not da_pressao:
            da_pressao = [{"id": h["id"], "titulo": h["titulo"], "pressao": h["pressao"], "pressoes": h.get("pressoes") or [],
                           "nova": False, "pontos": 0.0, "candidatos": [], "jornais": 0, "fato_grande": False}
                          for h in sorted(historias, key=lambda h: -da(h)) if da(h)][:1]
        if da_pressao:
            g = da_pressao[0]
            quem = "a direção do risco mudou" if virada["direcao"] else "uma pressão mudou de lado"
            return {"historia": g, "motivo": f"{quem}: a história é a da pressão que mudou", "calmo": False}
        if somas:
            return {"historia": somas[0], "motivo": "a direção do risco mudou: a história que mais andou", "calmo": False}
        return {"historia": None, "motivo": "a direção do risco mudou, sem notícia", "calmo": False}
    if not somas:
        return {"historia": None, "motivo": "nenhuma notícia lida é passo de uma história", "calmo": True}
    pulada = None
    escolha = somas[0]
    repetida = len(seguidas) >= DIAS_SEGUIDOS and all(h == escolha["id"] for h in seguidas[:DIAS_SEGUIDOS])
    if repetida and not escolha["fato_grande"] and len(somas) > 1 and somas[1]["pontos"] >= CALMO:
        pulada, escolha = escolha, somas[1]
    calmo = escolha["pontos"] < CALMO
    if pulada:
        motivo = (f"{pulada['titulo']} somou mais ({pulada['pontos']}), mas saiu nos {DIAS_SEGUIDOS} últimos dias sem "
                  f"decisão ou dado grande hoje; vale a seguinte")
    elif calmo:
        motivo = f"nenhuma história passou de {CALMO}: dia calmo"
    else:
        motivo = "a história que mais andou" + (" (empate decidido pelos jornais)" if len(somas) > 1
                                                and somas[1]["pontos"] == escolha["pontos"] else "")
    return {"historia": escolha, "motivo": motivo, "calmo": calmo, "pulada": pulada["id"] if pulada else None,
            "nova": bool(escolha.get("nova")), "titulo_historia": (abertas.get(escolha["id"]) or escolha)["titulo"]}


def historias_seguidas(rodadas: list[dict], hoje: str) -> list[str]:
    """As histórias dos textos do dia anteriores a `hoje`, da mais recente para a mais antiga (um por dia)."""
    por_dia: dict[str, str | None] = {}
    for r in rodadas:
        dia = r["gerado_em"][:10]
        if dia >= hoje or ((r.get("post") or {}).get("tipo") or "dia") != "dia":
            continue
        por_dia[dia] = ((r.get("pauta") or {}).get("escolha") or {}).get("historia")
    return [por_dia[d] for d in sorted(por_dia, reverse=True) if por_dia[d]]


def montar(rodada: dict, anterior: dict | None, eventos: dict, cfg: dict, cal: list[dict],
           cesta_por_id: dict | None = None, historias: list[dict] | None = None,
           seguidas: list[str] | None = None) -> dict:
    """A pauta de uma atualização: candidatos, soma por história, pressões que mudaram e a história do dia.
    Não chama o modelo de linguagem."""
    import classify_news
    if historias is None:
        historias = classify_news.historias_abertas()
    llm = (rodada.get("llm") or {}).get("saida") or {}
    cands = candidatos(llm.get("eventos", []), rodada.get("eventos_novos", []), rodada.get("eventos_descartados", []),
                       eventos, cesta_por_id, cfg.get("fatores"))
    datas = datas_lidas(rodada, cal)
    # A data marcada que saiu é o marco da história, mesmo que o classificador não tenha marcado.
    for x in datas:
        for c in cands:
            if _bate_data(x["tipo"], c):
                c["marco"] = True
    d = ((rodada.get("resultado") or {}).get("direcao") or {})
    da = (((anterior or {}).get("resultado") or {}).get("direcao") or None)
    a, b = _lados(anterior), _lados(rodada)
    mudaram = [k for k in direcao_mod.NA_SOMA if k in a and k in b and a[k] is not None and b[k] is not None and a[k] != b[k]]
    mudou_direcao = bool(anterior and da and d.get("estado") and d.get("estado") != da.get("estado"))
    hoje = rodada["gerado_em"][:10]
    somas, esperando = somar(cands, historias, voltas_dos_temas(eventos, hoje), hoje)
    esc = escolher(somas, historias, {"direcao": mudou_direcao, "pressoes": mudaram}, seguidas or [])
    h = esc["historia"]
    segunda = next((g for g in somas if h and g["id"] != h["id"] and g["pontos"] >= CALMO), None)
    nomes = cfg["direcao"]["nomes"]
    if h and h["candidatos"]:
        final = h["candidatos"][0]
    elif mudou_direcao:
        final = "D"
    elif mudaram:
        final = "P"
    else:
        final = None
    return {"versao": 2, "candidatos": cands,
            "datas": [{**x, "nome": MARCADAS.get(x["tipo"]) or OUTRAS_DATAS.get(x["tipo"], x["tipo"])} for x in datas],
            "pressoes_mudaram": [{"id": k, "nome": nomes.get(k, k), "antes": a[k], "agora": b[k]} for k in mudaram],
            "estado": d.get("estado"), "estado_anterior": (da or {}).get("estado"), "direcao_mudou": mudou_direcao,
            "historias": somas, "temas_esperando": esperando,
            "escolha": {"historia": h["id"] if h else None, "titulo": h["titulo"] if h else None,
                        "pontos": h["pontos"] if h else 0, "motivo": esc["motivo"], "calmo": esc["calmo"],
                        "nova": bool(h and h.get("nova")), "pulada": esc.get("pulada"),
                        "segunda": segunda["id"] if segunda else None},
            "final": final, "mesma_historia": (h["candidatos"][1:] if h else []),
            "segunda_historia": (segunda["candidatos"] if segunda else [])}


def candidato(p: dict, cid: str | None) -> dict | None:
    return next((c for c in p.get("candidatos", []) if c["id"] == cid), None)


def abrir_historias(pauta: dict, dia: str) -> list[str]:
    """Abre em base/memoria/historias.json as histórias novas da pauta (o tema grande e consumado, ou o que voltou em
    3 dos últimos 7 dias), para o classificador as ver a partir de amanhã. A ficha fica para a revisão de domingo
    (src/memoria.py historias --semana). Devolve os avisos ao Pedro. Não chama o modelo de linguagem."""
    import json
    import classify_news
    novas = [g for g in pauta.get("historias") or [] if g.get("nova")]
    if not novas:
        return []
    arq = classify_news.HISTORIAS
    try:
        doc = json.loads(arq.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    ids = {h["id"] for h in doc.get("historias", [])}
    avisos = []
    for g in novas:
        hid = g["id"].split(":", 1)[1].replace("-", "_")[:40]
        if hid in ids:
            continue
        c0 = candidato(pauta, g["candidatos"][0]) or {}
        doc["historias"].append({"id": hid, "titulo": c0.get("titulo", hid), "desde": dia[:7], "estado": "aberta",
                                 "pressao": None, "pressoes": [], "o_que_e": c0.get("porque", ""),
                                 "linha_do_tempo": [{"data": dia, "fato": c0.get("titulo", "")}],
                                 "proximo_marco": {"data": "", "o_que": ""}, "antigas": [],
                                 "aberta_em": dia})
        ids.add(hid)
        avisos.append(f"O texto do dia de {dia[8:10]}/{dia[5:7]} abriu uma história nova: {c0.get('titulo', hid)}. "
                      "A revisão de domingo completa a ficha; veja se ela merece ficar.")
    arq.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return avisos
