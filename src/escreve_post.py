"""Os dados do site que o texto do dia e a pergunta da semana recebem (src/fundo.py), e o tipo do post de cada dia.

O post muda de tipo com o dia (PERSONA.md, "Os tipos de post"), e só o calendário decide:
- o fato do dia, de segunda a sábado: um argumento sobre a história em andamento que mais andou ontem;
- a pergunta da semana, no domingo: a pergunta que todo mundo está fazendo sobre a história que mais andou na semana.
Os dois saem de src/fundo.py (guia em FUNDO.md), com a pesquisa, a investigação, o esqueleto, a redação e a revisão.
Daqui eles recebem só os dados do site, com os mesmos números que a página mostra (dados_texto). Os resumos da semana e
do mês, que o site publicou até 8/11/2026, saíram do ar como tipo novo: os dois que existem continuam na página.

Uso, para ver os dados da última rodada sem gravar nada:
  python src/escreve_post.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dossie as dossie_mod  # noqa: E402
import pauta as pauta_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = dossie_mod.MESES
ESTAGIOS = pauta_mod.ESTAGIO_TXT
SENTIDO = {"piora": "para piorar", "melhora": "para melhorar", "igual": "sem lado claro"}
TIPOS = {"dia": "Fato do dia", "pergunta": "Pergunta da semana"}


# ------------------------------------------------------------------ helpers
def _lista(fontes: list[dict]) -> str:
    return ", ".join(sorted({f["veiculo"] for f in fontes}))


def _manchetes(fontes: list[dict], n: int = 3) -> str:
    return "; ".join(f"\"{f['titulo']}\" ({f['veiculo']})" for f in fontes[:n])


def _data(iso: str) -> str:
    return f"{int(iso[8:10]):02d}/{int(iso[5:7]):02d}/{iso[:4]}"


def _dia(r: dict) -> dt.date:
    return dt.date.fromisoformat(r["gerado_em"][:10])


def _dir(r: dict | None) -> dict | None:
    return ((r or {}).get("resultado") or {}).get("direcao")


def _frase_estado(estado: str) -> str:
    return "a economia está encolhendo" if estado == "encolhendo" else f"o risco de recessão está {estado}"


def _desde(d: dict, hoje: dt.date) -> str:
    m = d["desde"]
    if m[:7] >= hoje.isoformat()[:7]:
        return "neste mês"
    return f"desde {MESES[int(m[5:7]) - 1]} de {m[:4]}"


def _topo(rodada: dict, cfg: dict) -> dict:
    """O topo da página, com as mesmas frases que o leitor vê."""
    import build_site
    return build_site.direcao_ctx(rodada, cfg, json.loads((ROOT / "config" / "calibracao.json").read_text()))


def _linhas_partes(rodada: dict, cfg: dict) -> list[str]:
    """Cada pressão e, em Também acompanhamos, as outras partes do topo (o emprego, as reservas), com o lado, as frases do
    topo e a comparação com a história. Uma parte sem lado (um fato fixo, como a dívida em reais) entra só com a frase."""
    t = _topo(rodada, cfg)
    out = [t["conta"]]
    r = t.get("ritmo")
    if r:
        prev = (f" Os bancos (Focus) esperam {r['previsao']} de {r['ext_prev']}. {r['erro']}"
                if r.get("previsao") else "")
        out.append(f"- Crescimento em 12 meses (logo abaixo da placa; não muda a direção): {r['agora']} de {r['ext_agora']}, "
                   f"contra {r['antes']} de {r['ext_antes']} ({r['muda'].lower()}). {r['faixa']}{prev}")
    rp = t.get("ritmo_parte")
    if rp:
        out.append(f"- Ritmo da economia (não aparece como linha; só decide se o topo diz que a economia está encolhendo): "
                   f"{rp['palavra'].lower()}. {rp['frase']}")
    for x in [*t["pressoes"], *(t.get("tambem") or t.get("fora") or [])]:
        fora = "" if x["na_soma"] else " (Também acompanhamos; não muda a direção)"
        folga = f" {x['folga']['texto']}" if x.get("folga") else ""
        palavra = f" {x['palavra'].lower()}." if x.get("palavra") else ""
        out.append(f"- {x['nome']}{fora}:{palavra} {' '.join([x['frase'], *x['mais']])}{folga}")
    return out


def _palavra(pid: str, lado: int | None) -> str:
    import build_site
    # A mesma tabela do topo (build_site._parte_ctx): as reservas usam as palavras do emprego.
    tab = (build_site.LADO_RITMO if pid == "ritmo" else build_site.LADO_EMPREGO if pid in ("emprego", "renda", "reservas")
           else build_site.LADO_PRESSAO)
    return tab.get(lado, tab[None])[0].lower()


def _lados(r: dict) -> dict:
    return {x["id"]: x["lado"] for x in (_dir(r) or {}).get("partes", [])}


def _partes_mudaram(r0: dict | None, r1: dict, cfg: dict) -> list[dict]:
    """As partes que mudaram de lado entre duas rodadas (por exemplo, de igual para piorou). Uma parte nova
    sem nome em config/modelo.json (direcao.nomes) fica de fora."""
    a, b = _lados(r0 or {}), _lados(r1)
    nomes = cfg["direcao"]["nomes"]
    return [{"id": k, "nome": nomes[k], "antes": _palavra(k, a[k]), "agora": _palavra(k, v)}
            for k, v in b.items() if k in a and k in nomes and a[k] != v]


# Para dizer a mudança de lado numa frase inteira: "tinha melhorado e passou a piorar".
_PARTICIPIO = {"piorou": "piorado", "melhorou": "melhorado", "igual": "ficado igual", "acelerou": "acelerado",
               "desacelerou": "desacelerado", "sem dado": "ficado sem dado"}
_INFINITIVO = {"piorou": "piorar", "melhorou": "melhorar", "igual": "ficar igual", "acelerou": "acelerar",
               "desacelerou": "desacelerar", "sem dado": "ficar sem dado"}


def _mudou(x: dict) -> str:
    return (f"- {x['nome']}: tinha {_PARTICIPIO.get(x['antes'], x['antes'])} e passou a "
            f"{_INFINITIVO.get(x['agora'], x['agora'])}.")


def por_dia(rodadas: list[dict]) -> list[dict]:
    """A última rodada de cada dia, em ordem."""
    out: dict[str, dict] = {}
    for r in sorted(rodadas, key=lambda r: r["gerado_em"]):
        out[r["gerado_em"][:10]] = r
    return [out[d] for d in sorted(out)]


def tipo_do_dia(hoje: dt.date) -> str:
    """O domingo é a pergunta da semana; os outros dias, o fato do dia."""
    return "pergunta" if hoje.weekday() == 6 else "dia"


def pauta_da_rodada(rodada: dict, anterior: dict | None, eventos: dict | None, cfg: dict) -> dict | None:
    """A pauta gravada na rodada; uma rodada de antes dela ganha a pauta pela soma das histórias (src/pauta.py)."""
    if rodada.get("pauta"):
        return rodada["pauta"]
    if not ((rodada.get("llm") or {}).get("saida")):
        return None
    import calendario
    return pauta_mod.montar(rodada, anterior, eventos or {}, cfg, calendario.carregar())


def _eventos_da_historia(p: dict | None) -> set:
    """Os eventos que já entram no texto do dia como passos da história do dia e da segunda (src/fundo.py)."""
    if not p:
        return set()
    esc = p.get("escolha") or {}
    alvo = {esc.get("historia"), esc.get("segunda")} - {None}
    ids = {(pauta_mod.candidato(p, i) or {}).get("evento") for g in p.get("historias") or [] if g["id"] in alvo
           for i in g["candidatos"]}
    return ids - {None}


def _post_anterior(anterior_post: dict | None) -> list[str]:
    if not anterior_post or not anterior_post.get("ok"):
        return []
    if anterior_post.get("formato") == "historia":
        return ["", "Texto do dia anterior (não repita o argumento dele):", f"Título: {anterior_post['titulo']}",
                f"Argumento: {(anterior_post.get('pesquisa') or {}).get('argumento', '')}"]
    return []


# --------------------------------------------------------------- os dados
def dados_texto(rodada: dict, cfg: dict, datas: list[dict] | None = None, eventos: dict | None = None,
                anterior: dict | None = None, anterior_post: dict | None = None) -> str:
    """Os dados do site para o texto do dia, com os mesmos números que a página mostra. Os passos da história do dia
    ficam fora: src/fundo.py os dá no bloco da história."""
    hoje = dt.date.fromisoformat(rodada["gerado_em"][:10])
    cob = rodada.get("cobertura") or {}
    n = rodada["insumos"]["noticias"]["n_itens"]
    veic = sorted(rodada["insumos"]["noticias"].get("por_veiculo", {}))
    dias = ", ".join(_data(d) for d in cob.get("dias", [])) or "dias anteriores"
    d, da = _dir(rodada), _dir(anterior)
    mudou = da is None or da["estado"] != d["estado"]
    usados = _eventos_da_historia(pauta_da_rodada(rodada, anterior, eventos, cfg))
    l = [f"Hoje: {DIAS_SEMANA[hoje.weekday()]}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}.",
         f"Notícias lidas: {f'{n} manchetes' if n is not None else 'as manchetes'} de economia de {len(veic)} jornais ({', '.join(veic)}), publicadas em {dias}.",
         ""]
    if da is None:
        l.append(f"Direção: {_frase_estado(d['estado'])}, {_desde(d, hoje)}. É a primeira medição do site.")
    elif mudou:
        l.append(f"A DIREÇÃO MUDOU: na atualização anterior, {_frase_estado(da['estado'])}; agora, "
                 f"{_frase_estado(d['estado'])}. Essa mudança entra no texto do dia.")
    else:
        l.append(f"Direção: {_frase_estado(d['estado'])}, {_desde(d, hoje)}, como na atualização anterior. O topo do site "
                 "já mostra; não fale da direção, a não ser que o argumento precise dela.")
    if d.get("pendente") and d["pendente"] != d["estado"]:
        l.append(f"Pelos dados de hoje, a direção seria {d['pendente']}; ela só muda se o mês que vem repetir. O topo já mostra isso.")
    mp = _partes_mudaram(anterior, rodada, cfg)
    if mp:
        l += ["", "Linhas do topo que mudaram de lado desde a atualização anterior:"]
        l += [_mudou(x) for x in mp]
    l += ["", "As cinco pressões (o topo do site já mostra cada uma; use só para explicar o fato):",
          *_linhas_partes(rodada, cfg)]
    leit = (rodada.get("leituras") or {}).get("fatores", {})
    pr = rodada.get("pressao") or {}
    com_noticia = [fid for fid in pr.get("fatores", {})] if pr.get("n") else []
    fatos = [(fid, " ".join(x["texto"] for x in leit.get(fid, {}).get("fatos", []))) for fid in com_noticia]
    fatos = [(fid, t) for fid, t in fatos if t]
    if fatos:
        l += ["", "Dados mais recentes dos assuntos com notícia (use só para explicar o fato):"]
        l += [f"- {cfg['fatores'].get(fid, fid)}: {t}" for fid, t in fatos]
    if pr.get("n"):
        l += ["", f"Outras notícias de ontem por assunto (contexto: não são passos da história do dia; uma delas só entra "
                  f"no texto se servir ao argumento). No conjunto: {SENTIDO[pr['sentido']]}."]
        nomes_f = cfg["fatores"]
        for fid, pf in sorted(pr["fatores"].items(), key=lambda kv: -abs(kv[1]["saldo"])):
            l.append(f"- {nomes_f.get(fid, fid)}: {SENTIDO[pf['sentido']]}.")
            for i in [i for i in pf["eventos"] if i not in usados][:3]:
                e = (eventos or {}).get(i)
                if e:
                    l.append(f"  - {ESTAGIOS.get(e.get('estagio'), 'notícia')} | "
                             f"{'pesa' if e['direcao'] > 0 else 'alivia'} | {e['titulo_evento']} | por quê: {e['porque']} | "
                             f"jornais: {_lista(e['fontes'])} | manchetes: {_manchetes(e['fontes'])}")
    else:
        l += ["", "Nenhuma notícia lida foi relevante para o risco de recessão."]
    hoje_sai = [x for x in (datas or []) if x.get("data") == hoje.isoformat()]
    if hoje_sai:
        l += ["", "Sai hoje: " + "; ".join(x["rotulo"] for x in hoje_sai) + "."]
    l += _post_anterior(anterior_post)
    return "\n".join(l)


def contexto(rodada: dict, cfg: dict, datas: list[dict] | None = None, eventos: dict | None = None,
             anterior: dict | None = None, tipo: str | None = None, rodadas: list[dict] | None = None) -> dict:
    """O que src/fundo.py recebe da rodada: o tipo, os dados do site em texto, a configuração e os eventos.
    `rodadas` são as rodadas anteriores (sem a de hoje)."""
    rodadas = rodadas or ([anterior] if anterior else [])
    hoje = _dia(rodada)
    ant_post = next((r["post"] for r in reversed(por_dia(rodadas))
                     if (r.get("post") or {}).get("ok") and (r["post"].get("tipo") or "dia") in TIPOS
                     and _dia(r) < hoje), None)
    anterior = anterior or next((r for r in reversed(por_dia(rodadas)) if _dia(r) < hoje), None)
    return {"tipo": tipo or tipo_do_dia(hoje), "dados": dados_texto(rodada, cfg, datas, eventos, anterior, ant_post),
            "cfg": cfg, "rodada": rodada, "eventos": eventos}


def _args_da_rodada(rodada: dict) -> tuple[list[dict], int, dict]:
    import calendario
    todas = [json.loads(p.read_text()) for p in sorted((ROOT / "runs").glob("*.json"))]
    i = next(k for k, r in enumerate(todas) if r["id"] == rodada["id"])
    cfg = json.loads((ROOT / "config" / "modelo.json").read_text())
    evs = {e["id"]: e for e in json.loads((ROOT / "data" / "eventos.json").read_text())}
    dia = dt.date.fromisoformat(rodada["gerado_em"][:10])
    return todas, i, {"cfg": cfg, "datas": calendario.janela(calendario.carregar(), dia), "eventos": evs,
                      "anterior": todas[i - 1] if i else None, "tipo": tipo_do_dia(dia), "rodadas": todas[:i]}


def contexto_da_rodada(rodada: dict) -> dict:
    """O contexto de uma rodada já guardada em runs/, com as rodadas anteriores a ela, para refazer o texto com
    src/fundo.py."""
    _, _, a = _args_da_rodada(rodada)
    return contexto(rodada, a["cfg"], a["datas"], eventos=a["eventos"], anterior=a["anterior"], tipo=a["tipo"],
                    rodadas=a["rodadas"])


if __name__ == "__main__":
    # Teste: os dados do site da última rodada, sem gravar nada.
    import calendario
    todas = [json.loads(p.read_text()) for p in sorted((ROOT / "runs").glob("*.json"))]
    rod, ant = todas[-1], (todas[-2] if len(todas) > 1 else None)
    evs = {e["id"]: e for e in json.loads((ROOT / "data" / "eventos.json").read_text())}
    cfg_ = json.loads((ROOT / "config" / "modelo.json").read_text())
    ds = calendario.janela(calendario.carregar(), _dia(rod))
    print(f"[{TIPOS[tipo_do_dia(_dia(rod))]}]\n{dados_texto(rod, cfg_, ds, evs, ant)}")
