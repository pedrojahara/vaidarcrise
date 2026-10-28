"""Uma rodada completa: coleta, classifica, calcula, grava o registro imutável e gera o site.

Uso: python src/run.py [--horas 36] [--sem-llm]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402
import classify_news  # noqa: E402
import fetch_data  # noqa: E402
import fetch_news  # noqa: E402
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
VISTAS = ROOT / "data" / "noticias_vistas.json"
RUNS = ROOT / "runs"


def _ler(p: Path, padrao):
    return json.loads(p.read_text()) if p.exists() else padrao


def _contexto(vals: list[dict]) -> str:
    return "\n".join(f"- {x['nome']}: {x['valor']:.2f} {x['unidade']} (ref. {x['ref']})" for x in vals) or "(sem dados)"


def ultima_rodada() -> dict | None:
    arqs = sorted(RUNS.glob("*.json"))
    return json.loads(arqs[-1].read_text()) if arqs else None


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=int, default=36)
    ap.add_argument("--sem-llm", action="store_true")
    args = ap.parse_args()

    agora = dt.datetime.now().astimezone()
    hoje = agora.date()
    cfg = model.carregar_config()
    cfg_hash = hashlib.sha256((ROOT / "config" / "modelo.json").read_bytes()).hexdigest()

    snap = json.loads(fetch_data.main().read_text())
    noticias = json.loads(fetch_news.main(args.horas).read_text())

    todos = _ler(EVENTOS, [])
    ativos = [e for e in todos if model.efeito_evento(e, hoje, cfg) != 0]
    vals = model.contribuicoes_indicadores(model.valores_indicadores(snap), cfg)

    # Cada manchete é classificada uma vez só: as janelas de coleta se sobrepõem entre rodadas,
    # e reclassificar a mesma notícia daria leituras diferentes do mesmo fato.
    vistas = _ler(VISTAS, {})
    noticias["itens"] = [it for it in noticias["itens"] if it["url"] not in vistas]
    llm = {"ok": False, "saida": None, "meta": {"erro": "pulado (--sem-llm)"}}
    if not args.sem_llm:
        llm = classify_news.classificar(noticias, ativos, _contexto(vals))
        if llm["ok"]:
            vistas.update({it["url"]: hoje.isoformat() for it in noticias["itens"]})
            limite = (hoje - dt.timedelta(days=10)).isoformat()
            VISTAS.write_text(json.dumps({u: d for u, d in vistas.items() if d >= limite}, indent=0))
    print("LLM:", "ok" if llm["ok"] else f"falhou: {llm['meta'].get('erro')}", "| custo:", llm["meta"].get("custo_usd"))

    por_id = {it["id"]: it for it in noticias["itens"]}
    novos, descartados = [], []
    if llm["ok"]:
        prefixo = f"ev-{hoje:%Y%m%d}-"
        seq = 1 + max((int(e["id"][len(prefixo):]) for e in todos if e["id"].startswith(prefixo)), default=0)
        for ev in llm["saida"]["eventos"]:
            fontes = [{k: por_id[i][k] for k in ("veiculo", "titulo", "url", "publicado_em")} for i in ev["noticia_ids"]]
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
                    **{k: ev[k] for k in ("titulo_evento", "canal", "direcao", "magnitude", "ja_no_preco", "porque")},
                    "veiculos": veiculos, "fontes": fontes}
            novo["efeito_inicial"] = model.efeito_inicial(novo, len(veiculos), cfg)
            novos.append(novo)
            seq += 1
        todos += novos
        (ROOT / "data" / "casos.json").write_text(json.dumps(
            {"gerado_em": agora.isoformat(timespec="seconds"),
             **{lado: [{"argumento": a["argumento"],
                        "fontes": [{k: por_id[i][k] for k in ("veiculo", "titulo", "url")} for i in a["noticia_ids"]]}
                       for a in llm["saida"][lado]] for lado in ("caso_mais_crise", "caso_menos_crise")}},
            ensure_ascii=False, indent=1))

    res = model.calcular(snap, todos, hoje, cfg)
    ant = ultima_rodada()
    variacao = None
    if ant:
        variacao = model.decompor_variacao(ant["resultado"], res, ant["insumos"]["pib"], snap.get("pib", []), cfg)
        if ant.get("modelo", {}).get("versao") != cfg["versao"]:
            variacao["versao_anterior"] = ant["modelo"]["versao"]
    # O disjuntor olha só o que dados e notícias moveram; mudança de versão é revisada antes de publicar.
    movimento = variacao["para"] - variacao["de"] - variacao["partes"].get("metodologia", 0.0) if variacao else 0.0
    em_revisao = abs(movimento) > cfg["disjuntor_pontos"]

    rodada = {
        "id": agora.strftime("%Y-%m-%dT%H%M"), "gerado_em": agora.isoformat(timespec="seconds"),
        "modelo": {"versao": cfg["versao"], "config_sha256": cfg_hash},
        "insumos": {"indicadores_coletados_em": snap["coletado_em"], "erros_coleta": snap["erros"],
                    "pib": snap.get("pib", []), "focus": snap.get("focus", {}),
                    "noticias": {"coletado_em": noticias["coletado_em"], "janela_horas": noticias["janela_horas"],
                                 "por_veiculo": noticias["por_veiculo"], "status_fontes": noticias["status_fontes"],
                                 "n_itens": len(noticias["itens"])}},
        "llm": {"ok": llm["ok"], "meta": llm["meta"], "saida": llm["saida"]},
        "eventos_novos": [e["id"] for e in novos], "eventos_descartados": descartados,
        "resultado": res, "cenarios": model.cenarios_pib(snap, res, cfg),
        "variacao": variacao, "em_revisao": em_revisao,
        "anterior": ant["id"] if ant else None,
    }
    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{rodada['id']}.json").write_text(json.dumps(rodada, ensure_ascii=False, indent=1))
    EVENTOS.parent.mkdir(exist_ok=True)
    EVENTOS.write_text(json.dumps(todos, ensure_ascii=False, indent=1))
    print(f"nota {100 * res['manchete']:.1f} | 4 tri {100 * res['curto_prazo_4t']:.1f} | "
          f"indicadores {res['indicadores_logit']:+.3f} | notícias {res['noticias_logit']:+.3f} | "
          f"eventos novos {len(novos)} | em revisão: {em_revisao}")
    build_site.main()
    return rodada


if __name__ == "__main__":
    main()
