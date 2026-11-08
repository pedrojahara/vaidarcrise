"""A atualização do dia: calcula a direção do risco, lê as manchetes do dia anterior, escreve o post e gera o site.

O post muda de tipo com o dia (src/escreve_post.py): fato do dia de segunda a sábado, resumo da semana
aos domingos e resumo do mês no primeiro domingo do mês. É sempre um post por dia, nesta mesma atualização.

Uso: python src/run.py             (atualização do dia; não faz nada se já houver uma hoje)
     python src/run.py --coletar   (só junta manchetes ao acervo, sem LLM e sem publicar)
     python src/run.py --forcar    (atualiza mesmo que já haja uma hoje)
     python src/run.py --sem-llm   (só dados)
     python src/run.py --sem-pesquisa (o fato do dia sai sem a pesquisa do dia antes; a leitura a fundo faz tudo depois)

No fato do dia, a pesquisa do dia (src/fundo.py, pensar) roda antes do post, e o mesmo caderno de fontes serve
às 100 palavras e à leitura a fundo, escrita depois do post (src/fundo.py --hoje, no run.sh).

Os feeds de alguns jornais guardam só as 10 últimas manchetes. A coleta de hora em
hora junta tudo num acervo local, e a atualização da manhã (05h45) lê o dia anterior inteiro.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402
import calendario  # noqa: E402
import classify_news  # noqa: E402
import direcao  # noqa: E402
import dossie as dossie_mod  # noqa: E402
import editora  # noqa: E402
import escreve_post  # noqa: E402
import fetch_data  # noqa: E402
import fetch_news  # noqa: E402
import model  # noqa: E402
import pauta as pauta_mod  # noqa: E402
import revisa_texto  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
VISTAS = ROOT / "data" / "noticias_vistas.json"
ACERVO = ROOT / "data" / "manchetes.json"
RUNS = ROOT / "runs"
DIAS_NO_ACERVO = 5
DIAS_RECENTES = 10
# Quantas rodadas para trás se procura um valor guardado (a idade do dado é que decide se ele vale).
RODADAS_GUARDADAS = 40


def _ler(p: Path, padrao):
    return json.loads(p.read_text()) if p.exists() else padrao


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _contexto(res: dict) -> str:
    return "\n".join(f"- {x['nome']}: {x['valor']:.2f} {x['unidade']} (ref. {x['ref']})"
                     for x in res["indicadores"] if x.get("valor") is not None) or "(sem dados)"


def ultima_rodada(antes_de: dt.date | None = None) -> dict | None:
    arqs = sorted(p for p in RUNS.glob("*.json") if antes_de is None or p.name[:10] < antes_de.isoformat())
    return json.loads(arqs[-1].read_text()) if arqs else None


def guardados(rodadas: list[dict]) -> dict:
    """Os valores que podem cobrir uma falha de coleta: para cada indicador e entrada, o da rodada mais
    recente que o tinha (rodadas da mais nova para a mais velha), inclusive os que ela mesma já tinha
    reaproveitado, porque a falha pode durar mais de um dia. A idade (pela data de referência do dado)
    é conferida em model.calcular. As entradas da conta do nível vão com o prefixo 'entrada:'."""
    out: dict[str, dict] = {}
    for ant in rodadas:
        for x in (ant["resultado"].get("gar") or {}).get("entradas", []):
            out.setdefault("entrada:" + x["id"], {k: v for k, v in x.items() if k in ("valor", "ref", "nivel", "antes")})
        for x in ant["resultado"]["indicadores"]:
            if x.get("valor") is not None:
                out.setdefault(x["id"], {k: v for k, v in x.items() if k in (
                    "valor", "ref", "nivel", "mediana", "vencimento", "selic", "inflacao_esperada", "focus_data",
                    "ano", "ano_seguinte")})
    return out


def acumular(horas: int) -> dict:
    """Coleta as manchetes e junta ao acervo local (fica fora do git). Devolve o acervo."""
    col = fetch_news.coletar(horas)
    acervo = _ler(ACERVO, {"itens": {}, "coletas": []})
    novos = 0
    for it in col["itens"]:
        if it["url"] not in acervo["itens"]:
            acervo["itens"][it["url"]] = it
            novos += 1
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DIAS_NO_ACERVO)).isoformat()
    acervo["itens"] = {u: it for u, it in acervo["itens"].items() if it["publicado_em"] >= limite}
    acervo["coletas"] = (acervo["coletas"] + [{"em": col["coletado_em"], "novos": novos,
                                               "status": col["status_fontes"]}])[-72:]
    ACERVO.parent.mkdir(exist_ok=True)
    ACERVO.write_text(json.dumps(acervo, ensure_ascii=False, indent=0))
    print(f"coleta: {novos} manchetes novas, {len(acervo['itens'])} no acervo")
    return acervo


def manchetes_do_dia_anterior(acervo: dict, vistas: dict, agora: dt.datetime) -> tuple[list[dict], list[str]]:
    """Manchetes ainda não lidas, publicadas antes da meia-noite de hoje (no máximo 3 dias atrás)."""
    meia_noite = dt.datetime.combine(agora.date(), dt.time(0), tzinfo=agora.tzinfo)
    inicio = meia_noite - dt.timedelta(days=3)
    out = []
    for it in acervo["itens"].values():
        quando = dt.datetime.fromisoformat(it["publicado_em"]).astimezone(agora.tzinfo)
        if it["url"] not in vistas and inicio <= quando < meia_noite:
            out.append(it)
    dias = sorted({dt.datetime.fromisoformat(it["publicado_em"]).astimezone(agora.tzinfo).date().isoformat()
                   for it in out})
    return out, dias


def main() -> dict | None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coletar", action="store_true")
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--horas", type=int, default=32)
    ap.add_argument("--sem-llm", action="store_true")
    ap.add_argument("--sem-pesquisa", action="store_true", help="o fato do dia sai sem a pesquisa antes (mais rápido)")
    args = ap.parse_args()

    # Coleta e atualização podem cair na mesma hora: uma espera a outra; a coleta desiste.
    (ROOT / "logs").mkdir(exist_ok=True)
    trava = open(ROOT / "logs" / ".trava", "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | (fcntl.LOCK_NB if args.coletar else 0))
    except BlockingIOError:
        print("coleta: outra rodada em andamento; fica para a próxima")
        return None

    agora = dt.datetime.now().astimezone()
    hoje = agora.date()
    acervo = acumular(args.horas)
    if args.coletar:
        return None
    if not args.forcar and any(p.name.startswith(hoje.isoformat()) for p in RUNS.glob("*.json")):
        print(f"já há atualização de {hoje.isoformat()}; nada a publicar (use --forcar)")
        return None

    cfg = model.carregar_config()
    cal = model.carregar_calibracao()
    snap = json.loads(fetch_data.main().read_text())
    calendario.atualizar(hoje)

    # 1. A direção do risco: só dados. A conta dos 44 países (o PIB num ano ruim) segue calculada para a
    # página Como funciona, mas não decide nada no topo.
    todas_r = [json.loads(p.read_text()) for p in sorted(RUNS.glob("*.json"))]
    recentes_r = todas_r[-RODADAS_GUARDADAS:][::-1]
    ant = recentes_r[0] if recentes_r else None
    # O nível de referência é o do último dia anterior: uma atualização refeita no mesmo dia não confirma a si mesma.
    ref = ultima_rodada(antes_de=hoje)
    nivel_ant = ref["resultado"]["nivel"]["indice"] if ref else None
    bruto_ant = ref["resultado"]["nivel"].get("bruto") if ref else None
    res = model.calcular(snap, cfg, cal, nivel_ant, guardados(recentes_r), bruto_ant)
    res["direcao"] = direcao.calcular(snap, cfg, cal, [r for r in todas_r if r["gerado_em"][:10] < hoje.isoformat()], hoje)
    d = res["direcao"]
    print(f"direção: {d['estado']} desde {d['desde']} (soma {d['soma']}; {d['apertaram']} pioraram, {d['folgaram']} melhoraram)"
          f" | num ano ruim, PIB {res['gar']['cenario_ruim']:+.2f}% | faltando: {res['faltando']} | reaproveitados: {res['reaproveitados']}")

    # 2. As notícias do dia anterior.
    vistas = _ler(VISTAS, {})
    pendentes, dias = manchetes_do_dia_anterior(acervo, vistas, agora)
    cesta, por_veiculo = fetch_news.cesta(pendentes)
    ultima_coleta = acervo["coletas"][-1]
    noticias = {"coletado_em": ultima_coleta["em"], "janela_horas": args.horas,
                "status_fontes": ultima_coleta["status"], "por_veiculo": por_veiculo, "itens": cesta}
    bruto = ROOT / "data" / "raw" / hoje.isoformat() / "noticias.json"
    bruto.parent.mkdir(parents=True, exist_ok=True)
    bruto.write_text(json.dumps(noticias, ensure_ascii=False, indent=1))
    coletas_24h = sum(1 for c in acervo["coletas"]
                      if dt.datetime.fromisoformat(c["em"]) >= agora - dt.timedelta(hours=24))
    cobertura = {"dias": dias, "no_acervo": len(pendentes), "na_cesta": len(cesta), "coletas_24h": coletas_24h}
    print(f"manchetes de {', '.join(dias) or '(nenhum dia)'}: {len(pendentes)} no acervo, {len(cesta)} na cesta "
          f"{por_veiculo} | coletas nas últimas 24h: {coletas_24h}")

    todos = _ler(EVENTOS, [])
    limite = (hoje - dt.timedelta(days=DIAS_RECENTES)).isoformat()
    recentes = [e for e in todos if e["data"] >= limite]

    llm = {"ok": False, "saida": None, "meta": {"erro": "pulado (--sem-llm)"}}
    if not args.sem_llm:
        llm = classify_news.classificar(noticias, recentes, _contexto(res))
        if llm["ok"]:
            # Cada manchete é lida uma vez só, inclusive as que ficaram fora da cesta.
            vistas.update({it["url"]: hoje.isoformat() for it in pendentes})
            lim_v = (hoje - dt.timedelta(days=10)).isoformat()
            VISTAS.write_text(json.dumps({u: d for u, d in vistas.items() if d >= lim_v}, indent=0))
    print("LLM:", "ok" if llm["ok"] else f"falhou: {llm['meta'].get('erro')}", "| custo:", llm["meta"].get("custo_usd"))

    por_id = {it["id"]: it for it in cesta}

    def fontes_de(ids: list[str]) -> list[dict]:
        return [{k: por_id[i][k] for k in ("veiculo", "titulo", "url", "publicado_em")} for i in ids if i in por_id]

    novos, descartados = [], []
    if llm["ok"]:
        prefixo = f"ev-{hoje:%Y%m%d}-"
        seq = 1 + max((int(e["id"][len(prefixo):]) for e in todos if e["id"].startswith(prefixo)), default=0)
        for ev in llm["saida"]["eventos"]:
            fontes = fontes_de(ev["noticia_ids"])
            if ev["ja_nos_indicadores"]:
                descartados.append({**ev, "motivo": "já medido pelos indicadores", "fontes": fontes})
                continue
            dup = next((e for e in todos if e["id"] == ev.get("duplicata_de")), None)
            if dup is not None:
                urls = {f["url"] for f in dup["fontes"]}
                dup["fontes"] += [f for f in fontes if f["url"] not in urls]
                descartados.append({**ev, "motivo": f"mesmo fato do evento {dup['id']}", "fontes": fontes})
                continue
            veiculos = sorted({f["veiculo"] for f in fontes})
            # O evento vale a partir da manchete mais antiga que o sustenta, não do dia da rodada.
            data_ev = min(dt.datetime.fromisoformat(f["publicado_em"]).astimezone(agora.tzinfo).date() for f in fontes)
            novo = {"id": f"ev-{hoje:%Y%m%d}-{seq:02d}", "data": data_ev.isoformat(),
                    **{k: ev[k] for k in ("titulo_evento", "estagio", "origem", "fator", "direcao", "magnitude",
                                          "ja_no_preco", "porque")},
                    # Quem decidiu, o tipo de decisão e o objetivo declarado (src/decisoes.py).
                    **{k: ev.get(k, d) for k, d in (("decisor", "nenhum"), ("instrumento", "nenhum"), ("objetivo", ""))},
                    "chance_aprovacao": ev["chance_aprovacao"] if ev["estagio"] == "em_votacao" else None,
                    "veiculos": veiculos, "fontes": fontes}
            # Quantas manchetes e jornais deram o fato (todas, não só as 6 citadas): a pauta do fato do dia usa.
            novo["cobertura"] = pauta_mod.cobertura([*ev["noticia_ids"], *ev.get("outras_ids", [])], por_id, fontes)
            novo["pontos"] = model.efeito(novo, cfg)
            novos.append(novo)
            seq += 1
        todos += novos

    pressao = model.pressao(novos, cfg)

    # 3. Os fatos de dados do dia, com a história de cada um, para o post.
    mensal = _ler(ROOT / "data" / "historico" / "mensal.json", {})
    fatos = dossie_mod.fatos_de_dados(res, snap, mensal)
    leituras = {"fatores": {fid: {"fatos": fatos.get(fid, [])} for fid in cfg["fatores"]}}

    rodada = {
        "id": agora.strftime("%Y-%m-%dT%H%M"), "gerado_em": agora.isoformat(timespec="seconds"),
        "regras": {"config_sha256": _sha(ROOT / "config" / "modelo.json"),
                   "calibracao_sha256": _sha(ROOT / "config" / "calibracao.json")},
        "insumos": {"indicadores_coletados_em": snap["coletado_em"], "erros_coleta": snap["erros"],
                    "pib": snap.get("pib", []), "focus": snap.get("focus", {}),
                    "noticias": {"coletado_em": noticias["coletado_em"], "janela_horas": noticias["janela_horas"],
                                 "por_veiculo": noticias["por_veiculo"], "status_fontes": noticias["status_fontes"],
                                 "n_itens": len(cesta)}},
        "cobertura": cobertura,
        "llm": {"ok": llm["ok"], "meta": llm["meta"], "saida": llm["saida"]},
        "eventos_novos": [e["id"] for e in novos], "eventos_descartados": descartados,
        "resultado": res, "pressao": pressao, "leituras": leituras,
        "anterior": ant["id"] if ant else None,
        "revisao_texto": {"classificacao": revisa_texto.problemas_classificacao(llm["saida"]) if llm["ok"] else []},
    }

    # 4. A pauta do fato do dia: os degraus dão a escolha padrão (src/pauta.py), e a IA editora (src/editora.py)
    # só sai dela por um motivo da lista fechada da carta editorial (CARTA_EDITORIAL.md).
    if llm["ok"]:
        pt = pauta_mod.montar(rodada, ant, {e["id"]: e for e in todos}, cfg, calendario.carregar(), por_id)
        if escreve_post.tipo_do_dia(hoje) == "dia":
            pt = editora.escolher(pt, rodada, cfg, editora.fatos_anteriores(todas_r, hoje), cesta)
        else:
            pt = {**pt, "final": pt["padrao"], "mesma_historia": [], "cuidados": []}
        rodada["pauta"] = pt
        print(f"pauta: degrau {pt['degrau']} ({pt['motivo']}), padrão {pt['padrao']}, final {pt['final']}: "
              f"{pauta_mod.titulo_escolha(pt)} | editora: {(pt.get('editora') or {}).get('conferencia', 'não rodou')}")

    post = {"ok": False, "meta": [{"erro": "pulado: sem leitura de notícias"}]}
    if llm["ok"]:
        datas = calendario.janela(calendario.carregar(), hoje)
        # A semana sai do registro das rodadas; o mês, dos dados do dia e da rodada do começo do mês, se houver.
        # 45 dias cobrem o mês anterior inteiro e os dias antes dele.
        corte = (hoje - dt.timedelta(days=45)).isoformat()
        anteriores = [r for r in todas_r if r["id"][:10] >= corte]
        evs = {e["id"]: e for e in todos}
        # 5. No fato do dia, a pesquisa vem antes do post (src/fundo.py, pensar): a mesma pesquisa e o mesmo
        # editor-chefe servem às 100 palavras (o porquê e o e daí) e à leitura a fundo, que é escrita depois do post
        # (fundo.py --hoje, no segundo push do run.sh). Sem a pesquisa, o post sai como antes, só com os dados.
        pensado, porque = None, None
        pt = rodada.get("pauta") or {}
        if (escreve_post.tipo_do_dia(hoje) == "dia" and pt.get("final", pt.get("padrao")) is not None
                and not args.sem_pesquisa):
            try:
                import fundo
                cx = escreve_post.contexto(rodada, cfg, datas, evs, ant, "dia", anteriores, snap)
                pensado = fundo.pensar(rodada, cx, limite_min=float(os.environ.get("VDC_PESQUISA_MIN", "30")))
                porque = fundo.para_o_post(pensado)
                print(f"pesquisa do dia: {pensado.get('etapa') or ('sem achado' if pensado.get('sem_achado') else 'erro')}"
                      f" | {pensado.get('erro') or pensado.get('tese', '')[:120]} | porquê: {'sim' if porque else 'não'}")
            except Exception as ex:  # noqa: BLE001
                print(f"aviso: a pesquisa do dia falhou ({ex!r}); o post sai só com os dados")
        post = escreve_post.escrever(rodada, cfg, datas, eventos=evs, anterior=ant, rodadas=anteriores, snap=snap,
                                     porque=porque)
        if pensado is not None:
            post["fundo"] = pensado
            if pensado.get("etapa") == "pensado":
                fundo.ligar(post, pensado)
        print(f"post ({post.get('tipo', 'dia')}):", post.get("titulo") if post["ok"] else f"falhou: {post.get('erro') or post['meta'][-1].get('erro')}",
              "| problemas:", post.get("problemas"), "| teste do porquê:", (post.get("teste") or {}).get("ok"))
    rodada["post"] = post
    # O site não cria página de pergunta sozinho (decisão do Pedro em 8/11/2026): quando sente falta de uma, a rodada
    # grava o aviso no registro do dia e o run.sh mostra no Mac. O Pedro decide.
    try:
        import base_site
        avisos = base_site.falta_pagina([*todas_r, rodada], cfg, hoje.isoformat())
    except Exception as ex:  # noqa: BLE001
        avisos = []
        print(f"aviso: a conta da página que falta não rodou ({ex!r})")
    if avisos:
        rodada["avisos_ao_pedro"] = avisos
        for a in avisos:
            print(f"AVISO AO PEDRO: {a}")

    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{rodada['id']}.json").write_text(json.dumps(rodada, ensure_ascii=False, indent=1))
    EVENTOS.parent.mkdir(exist_ok=True)
    EVENTOS.write_text(json.dumps(todos, ensure_ascii=False, indent=1))
    print(f"direção {res['direcao']['estado']} | pressão das notícias: {pressao['sentido']} | eventos novos {len(novos)}")
    build_site.main()
    return rodada


if __name__ == "__main__":
    main()
