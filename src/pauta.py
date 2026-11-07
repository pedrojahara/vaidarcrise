"""A pauta do fato do dia: os degraus que dão a escolha padrão (CARTA_EDITORIAL.md, "Os degraus").

O código monta a lista de candidatos com as notícias que o classificador leu e escolhe pelo primeiro
degrau que acontecer:
1. a direção do risco mudou;
2. uma das cinco pressões mudou de lado desde a atualização anterior;
3. um choque grande e raro: tamanho 3, já consumado (dado divulgado ou decisão tomada);
4. saiu, nos dias que o site leu, uma data marcada que mexe numa linha do topo: o PIB do trimestre,
   a decisão do Copom e o desemprego da PNAD, nessa ordem;
5. fora isso, a notícia de estágio mais firme (fato consumado, proposta em votação, anúncio, previsão,
   rumor), depois a de maior tamanho, depois a que não é o vaivém do mercado do dia, depois a que saiu em
   mais jornais e em mais manchetes.

O vaivém do mercado do dia (o fechamento do dólar, da Bolsa e dos juros, fator "mercado" e estágio "dado")
fica atrás dos outros fatos do mesmo estágio e tamanho, porque sai todo dia em todo jornal (a contagem de
jornais o favoreceria sempre) e o topo já mostra o dólar e o juro de 10 anos. Um movimento grande do mercado
ganha pelo tamanho que o classificador lhe der.

Os pontos da caixa "Para onde as notícias empurram" (src/model.py) medem para que lado cada assunto é
empurrado e não decidem a manchete: aqui não há desconto por "o mercado já esperava", cada notícia conta
sozinha (notícias de sinal oposto do mesmo assunto não se anulam) e a cobertura conta jornais de verdade.
A IA editora (src/editora.py) lê esta pauta e só sai da escolha padrão por um motivo da lista fechada.
Os resumos da semana e do mês usam a mesma ordem (`chave_evento`).
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
# As datas marcadas do degrau 4, na ordem de prioridade, e como achar a notícia de cada uma.
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
    return False


def vaivem(fator: str, estagio: str) -> bool:
    """O fechamento do mercado do dia: dólar, Bolsa, juros futuros, risco-país."""
    return fator == "mercado" and estagio == "dado"


def chave(c: dict) -> tuple:
    """A ordem do degrau 5: estágio, tamanho, o vaivém do mercado atrás, jornais, manchetes; no empate, a ordem do
    classificador."""
    return (RANK.get(c["estagio"], 5), -c["tamanho"], vaivem(c["fator"], c["estagio"]), -len(c["jornais"]),
            -c["n_manchetes"], c.get("ordem", 0))


def chave_evento(e: dict) -> tuple:
    """A mesma ordem para um evento guardado em data/eventos.json (resumos da semana e do mês)."""
    cob = e.get("cobertura") or {}
    jornais = cob.get("jornais") or e.get("veiculos") or sorted({f["veiculo"] for f in e.get("fontes", [])})
    n = cob.get("manchetes") or len(e.get("fontes", []))
    return (RANK.get(e.get("estagio"), 5), -e.get("magnitude", 1), vaivem(e.get("fator"), e.get("estagio")),
            -len(jornais), -n, e.get("data", ""), e["id"])


def cobertura(ids: list[str], cesta_por_id: dict | None, fontes: list[dict]) -> dict:
    """Quantas manchetes e quais jornais deram o fato. Sem a cesta do dia, vale o que o evento guardou."""
    if cesta_por_id:
        its = [cesta_por_id[i] for i in dict.fromkeys(ids) if i in cesta_por_id]
        if its:
            return {"manchetes": len(its), "jornais": sorted({it["veiculo"] for it in its})}
    return {"manchetes": len(fontes), "jornais": sorted({f["veiculo"] for f in fontes})}


def candidatos(llm_eventos: list[dict], novos_ids: list[str], descartados: list[dict], eventos: dict,
               cesta_por_id: dict | None = None, nomes_fatores: dict | None = None) -> list[dict]:
    """Um candidato por evento que o classificador montou, na ordem dele (E1, E2...). run.py guarda, na mesma ordem,
    os eventos novos e os descartados; o descartado (continuação de um fato já contado ou dado já medido) aparece
    para a editora, mas não é escolha padrão."""
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
                             if k in ("titulo_evento", "estagio", "magnitude", "fator", "direcao", "porque", "origem")}}
            fontes, motivo = (eventos.get(ev_id) or {}).get("fontes", []), None
        cob = cobertura([*ev.get("noticia_ids", []), *ev.get("outras_ids", [])], cesta_por_id, fontes)
        out.append({
            "id": f"E{k}", "ordem": k, "evento": ev_id, "titulo": base["titulo_evento"], "estagio": base["estagio"],
            "tamanho": base["magnitude"], "fator": base["fator"], "origem": base.get("origem"),
            "assunto": (nomes_fatores or {}).get(base["fator"], base["fator"]),
            "lado": "pesa" if base["direcao"] > 0 else "alivia", "ja_esperado": bool(ev.get("ja_no_preco")),
            "porque": base["porque"], "n_manchetes": cob["manchetes"], "jornais": cob["jornais"],
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


def escolha_padrao(cands: list[dict], estado: str | None, estado_ant: str | None, mudaram: list[str],
                   datas: list[dict]) -> dict:
    """O primeiro degrau que acontece. Devolve {"degrau", "motivo", "padrao"}; padrao é o id do candidato (E1...),
    "D" (a direção mudou), "P" (uma pressão mudou de lado) ou None (dia sem notícia que mexa no risco)."""
    if estado_ant is not None and estado is not None and estado != estado_ant:
        return {"degrau": 1, "motivo": f"a direção do risco mudou: estava {estado_ant} e ficou {estado}", "padrao": "D"}
    if mudaram:
        return {"degrau": 2, "motivo": "uma pressão mudou de lado", "padrao": "P"}
    ok = [c for c in cands if not c["descartado"]]
    choque = sorted((c for c in ok if c["tamanho"] == 3 and c["estagio"] in CONSUMADO), key=chave)
    if choque:
        return {"degrau": 3, "motivo": "choque grande e raro, já consumado", "padrao": choque[0]["id"]}
    tipos = {x["tipo"] for x in datas}
    for t, nome in MARCADAS.items():
        if t in tipos:
            m = sorted((c for c in ok if _bate_data(t, c)), key=chave)
            if m:
                return {"degrau": 4, "motivo": f"data marcada: {nome}", "padrao": m[0]["id"], "data_marcada": t}
    if ok:
        best = sorted(ok, key=chave)[0]
        return {"degrau": 5, "motivo": "a notícia de estágio mais firme e maior tamanho; no empate, a que não é o vaivém do "
                                       "mercado do dia e a que saiu em mais jornais",
                "padrao": best["id"]}
    return {"degrau": 0, "motivo": "nenhuma notícia lida mexe no risco", "padrao": None}


def montar(rodada: dict, anterior: dict | None, eventos: dict, cfg: dict, cal: list[dict],
           cesta_por_id: dict | None = None) -> dict:
    """A pauta de uma atualização: candidatos, datas marcadas dos dias lidos, pressões que mudaram e escolha padrão.
    Não chama o modelo de linguagem."""
    llm = (rodada.get("llm") or {}).get("saida") or {}
    cands = candidatos(llm.get("eventos", []), rodada.get("eventos_novos", []), rodada.get("eventos_descartados", []),
                       eventos, cesta_por_id, cfg.get("fatores"))
    d = ((rodada.get("resultado") or {}).get("direcao") or {})
    da = (((anterior or {}).get("resultado") or {}).get("direcao") or None)
    a, b = _lados(anterior), _lados(rodada)
    mudaram = [k for k in direcao_mod.NA_SOMA if k in a and k in b and a[k] is not None and b[k] is not None and a[k] != b[k]]
    datas = datas_lidas(rodada, cal)
    esc = escolha_padrao(cands, d.get("estado"), (da or {}).get("estado") if anterior else None, mudaram, datas)
    nomes = cfg["direcao"]["nomes"]
    return {"versao": 1, "candidatos": cands, "datas": [{**x, "nome": MARCADAS.get(x["tipo"]) or OUTRAS_DATAS.get(x["tipo"], x["tipo"])}
                                                       for x in datas],
            "pressoes_mudaram": [{"id": k, "nome": nomes.get(k, k), "antes": a[k], "agora": b[k]} for k in mudaram],
            "estado": d.get("estado"), "estado_anterior": (da or {}).get("estado"),
            **esc}


def candidato(p: dict, cid: str | None) -> dict | None:
    return next((c for c in p.get("candidatos", []) if c["id"] == cid), None)


def titulo_escolha(p: dict) -> str | None:
    """O fato que a pauta escolheu, numa linha (para a editora dos dias seguintes e para os resumos)."""
    cid = p.get("final", p.get("padrao"))
    if cid == "D":
        return f"a direção do risco mudou: estava {p.get('estado_anterior')} e ficou {p.get('estado')}"
    if cid == "P":
        return "mudou de lado: " + ", ".join(x["nome"] for x in p.get("pressoes_mudaram", []))
    c = candidato(p, cid)
    return c["titulo"] if c else None
