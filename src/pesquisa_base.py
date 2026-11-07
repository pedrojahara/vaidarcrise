"""Pesquisa e conferência da base de conhecimento (base/) com inteligência artificial. Roda no Mac.

Fase 0: nada aqui mexe no site nem na rodada diária. Cada chamada ao `claude -p` fica registrada em
base/conferencia/uso.jsonl, que é a medida de quanto da assinatura uma pergunta-mãe consome.

Comandos:
  trechos   Para cada afirmação de documento sem trecho conferido, o agente abre a fonte (ou acha a versão
            original) e copia o trecho literal que sustenta a frase. Depois o código abre a mesma página e
            confere o trecho palavra por palavra (src/verifica_base.py). Trecho que o código não acha cai.
  advogado  Para cada leitura e cada degrau de consenso, outro agente tenta derrubar o texto: procura a evidência
            contrária mais forte (níveis 1 a 3), diz se o rótulo se sustenta e faz o teste da troca. As
            objeções novas também têm o trecho conferido pelo código.
  teste     Calcula o teste das moedas (t-real-vizinhos) com a Ptax do Banco Central. Sem IA.
  uso       Soma o consumo registrado.

Opções: --aplicar grava na base o que o código confirmou (trechos, status, resultado do teste);
        --limite N para só as N primeiras chamadas; --ids a,b,c para só essas afirmações ou leituras.

Uso: .venv/bin/python src/pesquisa_base.py trechos --aplicar
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import verifica_base as vb  # noqa: E402

CLAUDE = os.environ.get("CLAUDE_BIN", "/Users/pedrojahara/.local/bin/claude")
MODELO = os.environ.get("VDC_PESQUISA_MODELO", "opus")
USO = vb.CONF / "uso.jsonl"
HOJE = dt.date.today().isoformat()

NIVEIS = ("1 meta-análise ou revisão de estudos; 2 artigo revisado por pares ou capítulo de livro acadêmico; "
          "3 Banco Central, FMI, Tesouro, IBGE, IFI, Ipea, lei ou documento oficial; 4 tese ou dissertação; "
          "5 banco, gestora ou consultoria; 6 notícia; 7 coluna, comentarista ou podcast")

SYS_TRECHO = f"""Você confere fontes para um site brasileiro de economia que explica causas sem tomar lado.
Recebe uma frase do site e a fonte que deveria sustentá-la. Abra a fonte com WebFetch. Se ela não abrir,
estiver incompleta ou for uma notícia sobre um documento, procure com WebSearch a versão original ou oficial
(o estudo, a nota do Banco Central, a lei) e abra essa.

Copie da página, sem mudar uma letra, sem traduzir e sem juntar pedaços, um trecho de até 80 palavras que
sustente a frase. Se nenhum trecho da página sustentar a frase inteira, diga o que a página diz e o que falta.
Nunca invente nem reconstrua um trecho de memória: o código vai abrir a mesma página e procurar o trecho letra
por letra, e trecho que não estiver lá derruba a afirmação.

Níveis de fonte: {NIVEIS}. Responda só no esquema."""

ESQ_TRECHO = {
    "type": "object", "additionalProperties": False,
    "required": ["url_usada", "titulo", "nivel", "trecho", "lingua", "sustenta", "o_que_falta"],
    "properties": {
        "url_usada": {"type": "string"}, "titulo": {"type": "string"},
        "nivel": {"type": "integer", "minimum": 1, "maximum": 7},
        "trecho": {"type": ["string", "null"]}, "lingua": {"type": "string"},
        "sustenta": {"enum": ["sim", "em_parte", "nao", "nao_achei_a_fonte"]},
        "o_que_falta": {"type": "string"},
    },
}

SYS_ADVOGADO = f"""Você é o advogado do diabo de um site brasileiro de economia que explica causas sem tomar lado.
Recebe uma leitura (ou um degrau dado como consenso), com o que está a favor, a objeção que o site já mostra e
as fontes citadas. Seu trabalho é tentar derrubar o texto, com honestidade:

1. Procure com WebSearch e abra com WebFetch a evidência contrária mais forte que o texto ainda não mostra,
   de preferência dos níveis 1 a 3. Para cada uma, dê o endereço e copie da página, sem mudar uma letra, um
   trecho de até 80 palavras. O código vai conferir o trecho na página; trecho que não estiver lá é descartado.
2. Diga se a objeção que o site já mostra é mesmo a mais forte e, se não for, qual seria.
3. Diga se o rótulo (consenso, maioria, em disputa, minoria, pouco testada, testada e não confirmada) se
   sustenta com as fontes citadas.
4. Faça o teste da troca: com o governo do lado oposto no poder, alguma frase sairia diferente? Aponte a frase
   e o motivo. Aponte também palavra com lado ou de alarme.

Níveis de fonte: {NIVEIS}. Responda só no esquema."""

ESQ_ADVOGADO = {
    "type": "object", "additionalProperties": False,
    "required": ["objecoes_novas", "objecao_atual_e_a_mais_forte", "comentario_objecao", "rotulo_se_sustenta",
                 "comentario_rotulo", "teste_da_troca"],
    "properties": {
        "objecoes_novas": {"type": "array", "maxItems": 3, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["texto", "url", "titulo", "nivel", "trecho"],
            "properties": {"texto": {"type": "string"}, "url": {"type": "string"}, "titulo": {"type": "string"},
                           "nivel": {"type": "integer", "minimum": 1, "maximum": 7}, "trecho": {"type": "string"}}}},
        "objecao_atual_e_a_mais_forte": {"type": "boolean"}, "comentario_objecao": {"type": "string"},
        "rotulo_se_sustenta": {"type": "boolean"}, "comentario_rotulo": {"type": "string"},
        "teste_da_troca": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["frase", "problema"],
            "properties": {"frase": {"type": "string"}, "problema": {"type": "string"}}}},
    },
}


# ---------- chamada ao claude, com registro do consumo ----------

def claude_com_busca(system: str, prompt: str, schema: dict, budget_usd: float, comando: str, alvo: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_", "ANTHROPIC_"))}
    cmd = [CLAUDE, "-p", "--safe-mode", "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch", "WebFetch",
           "--output-format", "json", "--no-session-persistence", "--model", MODELO,
           "--max-budget-usd", str(budget_usd), "--system-prompt", system, "--json-schema", json.dumps(schema)]
    t0 = time.time()
    reg = {"em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "comando": comando, "alvo": alvo,
           "modelo_pedido": MODELO}
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1200, env=env, cwd=str(ROOT))
        res = json.loads(p.stdout)
    except Exception as e:  # noqa: BLE001
        reg.update({"ok": False, "erro": f"{type(e).__name__}: {str(e)[:200]}", "segundos": round(time.time() - t0)})
        _registrar(reg)
        return {"ok": False, "saida": None, "erro": reg["erro"]}
    mu = res.get("modelUsage") or {}
    reg.update({
        "ok": not res.get("is_error") and res.get("structured_output") is not None,
        "segundos": round(time.time() - t0), "custo_usd": res.get("total_cost_usd"), "turnos": res.get("num_turns"),
        "modelos": {m: {k: u.get(k) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens",
                                               "cacheCreationInputTokens", "webSearchRequests")} for m, u in mu.items()},
        "negadas": len(res.get("permission_denials") or []),
    })
    if not reg["ok"]:
        reg["erro"] = str(res.get("result"))[:300]
    _registrar(reg)
    return {"ok": reg["ok"], "saida": res.get("structured_output"), "erro": reg.get("erro")}


def _registrar(reg: dict) -> None:
    vb.CONF.mkdir(parents=True, exist_ok=True)
    with USO.open("a") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def _opcoes() -> tuple[bool, int | None, set[str] | None]:
    a = sys.argv
    limite = int(a[a.index("--limite") + 1]) if "--limite" in a else None
    ids = set(a[a.index("--ids") + 1].split(",")) if "--ids" in a else None
    return "--aplicar" in a, limite, ids


def _salvar(nome: str, dados: dict) -> Path:
    vb.CONF.mkdir(parents=True, exist_ok=True)
    out = vb.CONF / f"{HOJE}-{nome}.json"
    out.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
    return out


# ---------- trechos ----------

def trechos() -> None:
    aplicar, limite, ids = _opcoes()
    base = vb.carregar()
    feitos, n = [], 0
    for a in base["lista_afirmacoes"]:
        if a["tipo"] != "documento" or (ids and a["id"] not in ids):
            continue
        atual = vb.conferir_trecho(a, offline=False)
        if atual["status"] == "conferido" and a.get("trecho"):
            continue
        if limite is not None and n >= limite:
            break
        n += 1
        f = a["fonte"]
        prompt = (f"Frase do site: {a['texto']}\n\nFonte indicada: {f.get('quem')}, \"{f.get('titulo')}\""
                  f"{', ' + str(f['ano']) if f.get('ano') else ''}. Endereço: {f.get('url') or '(sem endereço: procure)'}\n"
                  + (f"Trecho que um resumo de busca sugeriu (pode estar errado): {a['trecho_candidato']}\n" if a.get("trecho_candidato") else "")
                  + (f"Nota: {a['nota']}\n" if a.get("nota") else "")
                  + "\nAche e copie o trecho literal que sustenta a frase.")
        r = claude_com_busca(SYS_TRECHO, prompt, ESQ_TRECHO, 1.5, "trechos", a["id"])
        item = {"id": a["id"], "antes": atual["status"], "agente": r.get("saida"), "erro": r.get("erro")}
        s = r.get("saida")
        if not r["ok"] or not s:
            item["resultado"] = "falha_do_agente"
        elif not s.get("trecho") or s["sustenta"] in ("nao", "nao_achei_a_fonte"):
            item["resultado"] = "agente_nao_sustenta"
        else:
            texto, erro = vb.abrir(s["url_usada"])
            if erro:
                item["resultado"] = "codigo_nao_abriu"
                item["erro_codigo"] = erro
            elif vb.normalizar(s["trecho"]) in vb.normalizar(texto):
                item["resultado"] = "confirmado" if s["sustenta"] == "sim" else "confirmado_em_parte"
            else:
                item["resultado"] = "trecho_nao_esta_na_pagina"
        feitos.append(item)
        print(f"{a['id']}: {item['resultado']}", flush=True)
    resumo: dict[str, int] = {}
    for x in feitos:
        resumo[x["resultado"]] = resumo.get(x["resultado"], 0) + 1
    out = _salvar("trechos", {"em": HOJE, "modelo": MODELO, "resumo": resumo, "itens": feitos})
    print("resumo:", resumo, "->", out.relative_to(ROOT))
    if aplicar:
        _aplicar_trechos(feitos)


def _aplicar_trechos(feitos: list[dict]) -> None:
    p = vb.BASE / "afirmacoes.json"
    d = json.loads(p.read_text())
    por_id = {x["id"]: x for x in feitos}
    for a in d["afirmacoes"]:
        x = por_id.get(a["id"])
        if not x:
            continue
        s = x.get("agente") or {}
        if x["resultado"] in ("confirmado", "confirmado_em_parte"):
            a["trecho"] = s["trecho"]
            a["trecho_lingua"] = s.get("lingua")
            if s.get("url_usada") and s["url_usada"] != a["fonte"].get("url"):
                a["fonte_original"] = dict(a["fonte"])
                a["fonte"].update({"url": s["url_usada"], "titulo": s.get("titulo") or a["fonte"].get("titulo"),
                                   "nivel": s.get("nivel") or a["fonte"]["nivel"]})
            a["conferencia"] = {"status": "conferido" if x["resultado"] == "confirmado" else "sustenta_em_parte",
                                "em": HOJE, "como": "trecho achado pelo agente e conferido pelo código na página",
                                "o_que_falta": s.get("o_que_falta") or None}
        else:
            a["conferencia"] = {"status": "derrubado" if x["resultado"] in ("agente_nao_sustenta", "trecho_nao_esta_na_pagina") else "pendente",
                                "em": HOJE, "como": x["resultado"], "o_que_falta": s.get("o_que_falta") or x.get("erro_codigo") or x.get("erro")}
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print("base/afirmacoes.json atualizado")


# ---------- advogado do diabo ----------

def _alvos_advogado(base: dict) -> list[tuple[str, dict]]:
    A = base["afirmacoes"]
    out = []
    for p in base["perguntas"]:
        for d in p["escada"]:
            if d.get("rotulo") == "consenso" and d.get("texto"):
                out.append((f"{p['id']}/{d['degrau']}", {"pergunta": d["pergunta"], "rotulo": "consenso", "texto": d["texto"],
                            "fontes": [A[i]["texto"] + f" ({A[i]['fonte']['quem']}, nível {A[i]['fonte']['nivel']})" for i in d.get("afirmacoes", []) if i in A]}))
            for lt in d.get("leituras", []):
                ids = [i for x in lt.get("a_favor", []) + lt.get("estudos", []) for i in x["afirmacoes"]]
                out.append((lt["id"], {"pergunta": d["pergunta"], "rotulo_da_pergunta": d["rotulo"], "leitura": lt["nome"],
                            "status": lt.get("status"), "o_que_diz": lt["o_que_diz"],
                            "a_favor": [x["texto"] for x in lt.get("a_favor", []) + lt.get("estudos", [])],
                            "objecao_atual": (lt.get("melhor_objecao") or {}).get("texto"),
                            "resposta": (lt.get("resposta") or {}).get("texto"),
                            "fontes": [A[i]["texto"] + f" ({A[i]['fonte']['quem']}, nível {A[i]['fonte']['nivel']})" for i in ids if i in A]}))
    return out


def advogado() -> None:
    _, limite, ids = _opcoes()
    base = vb.carregar()
    feitos = []
    for n, (alvo, conteudo) in enumerate(_alvos_advogado(base)):
        if ids and alvo not in ids:
            continue
        if limite is not None and len(feitos) >= limite:
            break
        r = claude_com_busca(SYS_ADVOGADO, json.dumps(conteudo, ensure_ascii=False, indent=1), ESQ_ADVOGADO, 3.0, "advogado", alvo)
        s = r.get("saida") or {}
        for o in s.get("objecoes_novas", []):
            texto, erro = vb.abrir(o["url"])
            o["conferencia_codigo"] = ("codigo_nao_abriu: " + erro) if erro else (
                "confirmado" if vb.normalizar(o["trecho"]) in vb.normalizar(texto) else "trecho_nao_esta_na_pagina")
        feitos.append({"alvo": alvo, "ok": r["ok"], "erro": r.get("erro"), "saida": s})
        print(f"{alvo}: {'ok' if r['ok'] else 'falhou'}; objeções novas confirmadas: "
              f"{sum(1 for o in s.get('objecoes_novas', []) if o.get('conferencia_codigo') == 'confirmado')}; "
              f"rótulo se sustenta: {s.get('rotulo_se_sustenta')}; troca: {len(s.get('teste_da_troca', []))} frase(s)", flush=True)
    out = _salvar("advogado", {"em": HOJE, "modelo": MODELO, "itens": feitos})
    print("->", out.relative_to(ROOT))


# ---------- teste das moedas ----------

def _ptax(moeda: str, inicio: str, fim: str) -> dict[str, float]:
    import requests
    i = dt.date.fromisoformat(inicio).strftime("%m-%d-%Y")
    f = dt.date.fromisoformat(fim).strftime("%m-%d-%Y")
    url = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoMoedaPeriodo(moeda=@moeda,"
           f"dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?@moeda='{moeda}'&@dataInicial='{i}'"
           f"&@dataFinalCotacao='{f}'&$top=1000&$format=json&$select=cotacaoVenda,dataHoraCotacao,tipoBoletim")
    r = requests.get(url, timeout=40)
    r.raise_for_status()
    out = {}
    for x in r.json()["value"]:
        if x["tipoBoletim"] == "Fechamento":
            out[x["dataHoraCotacao"][:10]] = float(x["cotacaoVenda"])
    return out


def teste() -> None:
    aplicar, _, _ = _opcoes()
    base = vb.carregar()
    resultados = []
    for p in base["perguntas"]:
        for t in p.get("testes", []):
            if t["id"] != "t-real-vizinhos":
                continue
            ini = t["dados"]["inicio"]
            for fim in t["conferir_em"]:
                if fim > HOJE:
                    continue
                reais = {m: _ptax(m, ini, fim) for m in ("USD", "MXN", "CLP")}  # reais por unidade da moeda
                dias = sorted(set(reais["USD"]) & set(reais["MXN"]) & set(reais["CLP"]))
                if not dias:
                    print("sem cotações em comum")
                    continue
                d0, d1 = dias[0], dias[-1]
                alta = {"real": 100 * (reais["USD"][d1] / reais["USD"][d0] - 1)}
                for m, nome in (("MXN", "peso_mexicano"), ("CLP", "peso_chileno")):
                    por_dolar0 = reais["USD"][d0] / reais[m][d0]
                    por_dolar1 = reais["USD"][d1] / reais[m][d1]
                    alta[nome] = 100 * (por_dolar1 / por_dolar0 - 1)
                dif = alta["real"] - (alta["peso_mexicano"] + alta["peso_chileno"]) / 2
                rg = t["regra"]
                if dif > rg["favorece_l_daqui_acima_de"]:
                    fav = "l-daqui"
                elif rg["favorece_l_fora_entre"][0] <= dif <= rg["favorece_l_fora_entre"][1]:
                    fav = "l-fora"
                else:
                    fav = "nenhuma"
                res = {"conferido_em": HOJE, "janela": [d0, d1], "alta_do_dolar_pct": {k: round(v, 2) for k, v in alta.items()},
                       "diferenca_pontos": round(dif, 2), "favorece": fav,
                       "fonte": "Ptax de fechamento do Banco Central (Olinda, CotacaoMoedaPeriodo)"}
                resultados.append({"teste": t["id"], "fim_pedido": fim, **res})
                print(json.dumps(res, ensure_ascii=False))
                if aplicar:
                    t.setdefault("resultados", [])
                    t["resultados"] = [x for x in t["resultados"] if x.get("janela", [None, None])[1] != d1] + [res]
            if aplicar:
                arq = vb.BASE / "perguntas" / f"{p['id']}.json"
                arq.write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n")
    _salvar("teste", {"em": HOJE, "resultados": resultados})


# ---------- consumo ----------

def uso() -> None:
    if not USO.exists():
        print("nenhuma chamada registrada")
        return
    linhas = [json.loads(x) for x in USO.read_text().splitlines() if x.strip()]
    por: dict[str, dict] = {}
    for r in linhas:
        c = por.setdefault(r["comando"], {"chamadas": 0, "ok": 0, "custo_usd": 0.0, "segundos": 0, "buscas": 0,
                                         "tokens_entrada": 0, "tokens_saida": 0, "tokens_cache": 0})
        c["chamadas"] += 1
        c["ok"] += 1 if r.get("ok") else 0
        c["custo_usd"] += r.get("custo_usd") or 0
        c["segundos"] += r.get("segundos") or 0
        for u in (r.get("modelos") or {}).values():
            c["buscas"] += u.get("webSearchRequests") or 0
            c["tokens_entrada"] += (u.get("inputTokens") or 0) + (u.get("cacheCreationInputTokens") or 0)
            c["tokens_saida"] += u.get("outputTokens") or 0
            c["tokens_cache"] += u.get("cacheReadInputTokens") or 0
    tot = {k: round(sum(c[k] for c in por.values()), 2) for k in next(iter(por.values()))}
    print(json.dumps({"por_comando": por, "total": tot}, ensure_ascii=False, indent=1))
    _salvar("uso", {"por_comando": por, "total": tot})


if __name__ == "__main__":
    cmds = {"trechos": trechos, "advogado": advogado, "teste": teste, "uso": uso}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    cmds[sys.argv[1]]()
