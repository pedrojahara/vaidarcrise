"""Verificador da base de conhecimento (base/), a parte do código.

Fase 0: a base fica fora do site; nada aqui é lido por build_site.py nem pela rodada diária.

Confere, sem inteligência artificial:
  1. ligações: toda afirmação, episódio e teste citado existe;
  2. dados: cada número de uma afirmação do tipo "dado" bate com as séries do próprio site
     (data/historico e data/raw), com a mesma conta do topo (direcao.mensais);
  3. números do texto: todo número de um texto da pergunta-mãe está nas afirmações que ele cita;
  4. trechos: o trecho literal de cada afirmação do tipo "documento" está na página da fonte
     (precisa de rede: no Mac; na nuvem a rede bloqueia esses sites), e o do tipo "site" está no arquivo;
  5. regras de leitura: toda leitura tem a melhor objeção com fonte; nenhuma leitura leva nome de partido
     ou de presidente; consenso não se apoia só em notícia; episódios cobrem governos e causas diferentes;
     todo teste diz antes o que cada leitura espera e como se decide;
  6. escrita: frase de até 30 palavras, moldes de piloto automático, sigla sem link (src/revisa_texto.py).

O agente que tenta derrubar cada afirmação (advogado do diabo, teste da troca) fica em src/pesquisa_base.py.

Uso:
  .venv/bin/python src/verifica_base.py              # tudo, com rede
  .venv/bin/python src/verifica_base.py --offline    # sem abrir as fontes
  .venv/bin/python src/verifica_base.py --json       # o relatório inteiro em JSON
O relatório vai para base/conferencia/<data>-verifica.json.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import html
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import direcao  # noqa: E402
import revisa_texto  # noqa: E402

BASE = ROOT / "base"
CACHE = BASE / "cache"
CONF = BASE / "conferencia"
ROTULOS = {"consenso", "maioria_com_dissenso", "em_disputa"}
# Nome de empresa que se escreve em maiúsculas e não é sigla: o texto diz o que ela é ("a corretora XP").
NOMES_DE_EMPRESA = {"XP"}
STATUS_LEITURA = {"em_pe", "maioria", "em_disputa", "minoria", "pouco_testada", "testada_e_nao_confirmada"}
# O texto para a leitora diz o mecanismo, nunca o lado (PERSONA.md, teste da troca).
NOMES_COM_LADO = re.compile(r"\b(PT|PL|PSDB|MDB|PSOL|Novo|União Brasil|Lula|Bolsonaro|Dilma|Temer|FHC|Fernando Henrique|"
                            r"Haddad|Tarcísio|esquerda|direita|petista|bolsonarista|oposição|governista)\b")
UA = "Mozilla/5.0 (compatible; vaidarcrise-verificador/0.1; +https://vaidarcrise.com.br)"


# ---------- carga ----------

def carregar() -> dict:
    afs = json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]
    eps = json.loads((BASE / "episodios.json").read_text())["episodios"]
    perguntas = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(BASE / "perguntas" / "*.json")))]
    # Os fatos do dia com a escada de porquês ficam nos registros do dia (runs/), como os outros posts.
    posts = []
    for arq in sorted((ROOT / "runs").glob("*.json")):
        post = json.loads(arq.read_text()).get("post") or {}
        if post.get("escada"):
            posts.append({"dia": arq.stem[:10], "arquivo": f"runs/{arq.name}", **post})
    return {"afirmacoes": {a["id"]: a for a in afs}, "lista_afirmacoes": afs,
            "episodios": {e["id"]: e for e in eps}, "perguntas": perguntas, "posts": posts}


def series_do_site() -> tuple[dict, dict]:
    """(mensal, diário). Mensal: {serie: {"AAAA-MM": valor}}, com a conta do topo (direcao.mensais) para as
    séries do topo e o juro descontado da inflação esperada; as outras, o último valor de cada mês.
    Diário: {serie: {"AAAA-MM-DD": valor}} do histórico longo e de todas as coletas em data/raw."""
    hist = json.loads((ROOT / "data" / "historico" / "series.json").read_text())["series"]
    brutos = sorted((ROOT / "data" / "raw").glob("*/indicadores.json"))
    snaps = [json.loads(b.read_text()) for b in brutos]
    rodadas = [json.loads(x.read_text()) for x in sorted((ROOT / "runs").glob("*.json"))]
    m = direcao.mensais(snaps[-1] if snaps else None, rodadas, hist)
    mensal = {k: {mes: v for mes, (_, v) in d.items()} for k, d in m.items()}
    diario: dict[str, dict[str, float]] = {}

    def junta(k: str, pontos: list[dict]) -> None:
        d = diario.setdefault(k, {})
        for x in pontos:
            if x.get("valor") is not None:
                d[x.get("dia") or x["data"]] = float(x["valor"])

    for k, pts in hist.items():
        junta("dolar_ptax" if k == "dolar_ptax_diario" else k, pts)
    for s in snaps:
        for k, v in s.get("series", {}).items():
            junta(k, v.get("dados", []))
    for k, d in diario.items():
        if k not in mensal:
            mm: dict[str, float] = {}
            for dia in sorted(d):
                mm[dia[:7]] = d[dia]
            mensal[k] = mm
    return mensal, diario


def valor_em(serie: str, quando: str, mensal: dict, diario: dict) -> float | None:
    if len(quando) == 7:
        return mensal.get(serie, {}).get(quando)
    return diario.get(serie, {}).get(quando)


# ---------- texto das fontes ----------

def normalizar(t: str) -> str:
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t).replace("­", "")
    t = re.sub(r"[‘’´`]", "'", t)
    t = re.sub(r"[“”«»]", '"', t)
    t = re.sub(r"[‐-―−]", "-", t)
    t = re.sub(r"-\s*\n\s*", "", t)  # palavra quebrada no fim da linha do PDF
    return re.sub(r"\s+", " ", t).strip().lower()


def texto_da_pagina(conteudo: bytes, tipo: str) -> str:
    if b"%PDF" in conteudo[:1024] or "pdf" in tipo:
        try:
            from pypdf import PdfReader  # opcional: pip install pypdf
            return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(conteudo)).pages)
        except Exception:  # noqa: BLE001
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(conteudo)
                f.flush()
                try:
                    return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, timeout=120).stdout
                except Exception:  # noqa: BLE001
                    return ""
    t = conteudo.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    return re.sub(r"(?s)<[^>]+>", " ", t)


def abrir(url: str) -> tuple[str | None, str | None]:
    """(texto, erro). Guarda a página em base/cache para não abrir de novo."""
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".txt")
    if arq.exists():
        return arq.read_text(), None
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": UA}, timeout=40, allow_redirects=True)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        t = texto_da_pagina(r.content, r.headers.get("content-type", ""))
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:120]}"
    if len(t.strip()) < 200:
        return None, "página sem texto (talvez só JavaScript ou paywall)"
    arq.write_text(t)
    return t, None


def conferir_trecho(a: dict, offline: bool) -> dict:
    """Status do trecho de uma afirmação: conferido, trecho_nao_achado, sem_trecho, sem_endereco,
    fonte_inacessivel, nao_aberta (modo offline)."""
    if a["tipo"] == "site":
        alvo = (ROOT / a["arquivo"]).read_text()
        faltam = [t for t in (a.get("trecho"), a.get("trecho_2")) if t and normalizar(t) not in normalizar(alvo)]
        return {"status": "trecho_nao_achado" if faltam else "conferido", "onde": a["arquivo"]}
    trecho = a.get("trecho") or a.get("trecho_candidato")
    url = (a.get("fonte") or {}).get("url")
    if not url:
        return {"status": "sem_endereco"}
    if not trecho:
        return {"status": "sem_trecho"}
    if offline:
        return {"status": "nao_aberta"}
    # O endereço principal primeiro; depois as cópias da mesma fonte (repositório, PDF da revista).
    tentativas = []
    for u in [url, *((a.get("fonte") or {}).get("urls_alternativas") or [])]:
        texto, erro = abrir(u)
        if erro:
            tentativas.append({"url": u, "erro": erro})
            continue
        if normalizar(trecho) in normalizar(texto):
            return {"status": "conferido", "url": u, "era_candidato": not a.get("trecho")}
        tentativas.append({"url": u, "erro": "trecho não está na página"})
    abriu_alguma = any(t["erro"] == "trecho não está na página" for t in tentativas)
    return {"status": "trecho_nao_achado" if abriu_alguma else "fonte_inacessivel", "tentativas": tentativas,
            "era_candidato": not a.get("trecho")}


# ---------- regras ----------

def textos_da_pergunta(p: dict) -> list[tuple[str, str, list[str]]]:
    """(onde, texto, afirmações citadas) de cada texto que a leitora lê."""
    out = [("resposta_curta", p["resposta_curta"]["texto"], p["resposta_curta"]["afirmacoes"])]
    for d in p["escada"]:
        nome = d.get("id") or d["degrau"]
        if d.get("texto"):
            out.append((nome, d["texto"], d.get("afirmacoes", [])))
        if d.get("consenso"):
            out.append((f"{nome}/consenso", d["consenso"]["texto"], d["consenso"]["afirmacoes"]))
        if d.get("em_disputa"):
            out.append((f"{nome}/em_disputa", d["em_disputa"], d.get("em_disputa_afirmacoes", [])))
        if d.get("peso_da_evidencia") and d.get("peso_afirmacoes"):
            out.append((f"{nome}/peso", d["peso_da_evidencia"], d["peso_afirmacoes"]))
        for lt in d.get("leituras", []):
            base = f"{nome}/{lt['id']}"
            out.append((f"{base}/o_que_diz", lt["o_que_diz"], lt.get("o_que_diz_afirmacoes", [])))
            for i, x in enumerate(lt.get("a_favor", []) + lt.get("estudos", [])):
                out.append((f"{base}/a_favor{i}", x["texto"], x["afirmacoes"]))
            for parte in ("melhor_objecao", "resposta"):
                if lt.get(parte):
                    out.append((f"{base}/{parte}", lt[parte]["texto"], lt[parte]["afirmacoes"]))
    return out


def _texto_ok(onde: str, texto: str, ids: list[str], A: dict, pe: list[str], pa: list[str]) -> None:
    """Regras 1, 3 e 6 num texto que a leitora lê: afirmações citadas existem, todo número está nelas, e a escrita
    segue o guia (frase de até 30 palavras, sem molde, sigla com link, sem nome de lado)."""
    for i in ids:
        if i not in A:
            pe.append(f"{onde}: cita afirmação que não existe ({i})")
    if ids:
        fontes = " ".join(A[i]["texto"] for i in ids if i in A)
        fora = [n for n in revisa_texto.numeros_fora([texto], fontes) if not re.fullmatch(r"(19|20)\d\d", n)]
        if fora:
            pe.append(f"{onde}: número sem afirmação que o sustente ({', '.join(fora)})")
    elif re.search(r"\d", revisa_texto._sem_datas(texto)) and not onde.endswith("o_que_diz"):
        pa.append(f"{onde}: texto com número e sem afirmação citada")
    for f in revisa_texto.FRASE.split(texto):
        if len(f.split()) > 30:
            pa.append(f"{onde}: frase com {len(f.split())} palavras: {f[:60]}")
    pa += [f"{onde}: {m}" for m in revisa_texto._moldes(texto)]
    sig = [x for x in revisa_texto.siglas_soltas(texto) if x not in NOMES_DE_EMPRESA]
    if sig:
        pa.append(f"{onde}: sigla sem link ({', '.join(sig)})")
    if NOMES_COM_LADO.search(texto):
        pe.append(f"{onde}: nome de partido, presidente ou lado no texto ({NOMES_COM_LADO.search(texto).group(0)})")


def checar_posts(posts: list[dict], perguntas: dict, A: dict) -> tuple[list[str], list[str], set[str]]:
    """Os fatos do dia com escada (runs/): o tamanho do fato do dia (até 100 palavras, 3 parágrafos de até 50, título
    de até 70 caracteres), as regras de texto em cada parágrafo e degrau, e as ligações com a pergunta-mãe."""
    pe: list[str] = []
    pa: list[str] = []
    citadas: set[str] = set()
    for x in posts:
        dia = x["dia"]
        p = perguntas.get(x.get("pergunta"))
        if not p:
            pe.append(f"{dia}: aponta para pergunta que não existe ({x.get('pergunta')})")
            continue
        alvos = {"teste"} | {d["degrau"] for d in p["escada"]} | {d["id"] for d in p["escada"] if d.get("id")}
        divisoes = {d["id"] for d in p["escada"] if d.get("leituras")}
        testes = {t["id"] for t in p.get("testes", [])}
        ids_par = x.get("paragrafos_afirmacoes") or []
        if len(ids_par) != len(x["paragrafos"]):
            pe.append(f"{dia}: paragrafos_afirmacoes não tem uma lista por parágrafo")
            ids_par = (ids_par + [[]] * len(x["paragrafos"]))[:len(x["paragrafos"])]
        if len(x["titulo"]) > 70:
            pa.append(f"{dia}: título com {len(x['titulo'])} caracteres")
        _texto_ok(f"{dia}/titulo", x["titulo"], [i for ids in ids_par for i in ids], A, pe, pa)
        total = 0
        for k, (t, ids) in enumerate(zip(x["paragrafos"], ids_par)):
            n = len(t.split())
            total += n
            if n > 50:
                pa.append(f"{dia}/p{k + 1}: parágrafo com {n} palavras")
            citadas |= set(ids)
            _texto_ok(f"{dia}/p{k + 1}", t, ids, A, pe, pa)
        if total > 100:
            pe.append(f"{dia}: fato do dia com {total} palavras (até 100)")
        if len(x["paragrafos"]) > 3:
            pe.append(f"{dia}: fato do dia com {len(x['paragrafos'])} parágrafos (até 3)")
        for k, d in enumerate(x["escada"]):
            onde = f"{dia}/degrau{k + 1}"
            if d["rotulo"] not in ROTULOS | {"fato"}:
                pe.append(f"{onde}: rótulo desconhecido {d['rotulo']}")
            if d.get("liga") and d["liga"] not in alvos:
                pe.append(f"{onde}: liga a degrau que não existe ({d['liga']})")
            if d.get("leituras") and d["leituras"] not in divisoes:
                pe.append(f"{onde}: leituras de divisão que não existe ({d['leituras']})")
            if d.get("teste") and d["teste"] not in testes:
                pe.append(f"{onde}: teste que não existe ({d['teste']})")
            if d["rotulo"] == "consenso":
                niveis = [A[i]["fonte"]["nivel"] for i in d["afirmacoes"] if i in A]
                if niveis and min(niveis) >= 5:
                    pa.append(f"{onde}: consenso apoiado só em notícia ou banco (nível {min(niveis)} ou pior)")
            citadas |= set(d["afirmacoes"])
            _texto_ok(onde, d["pergunta"] + " " + d["texto"], d["afirmacoes"], A, pe, pa)
    return pe, pa, citadas


def checar(base: dict, offline: bool) -> dict:
    A, E = base["afirmacoes"], base["episodios"]
    mensal, diario = series_do_site()
    erros: list[str] = []
    avisos: list[str] = []
    afirm: dict[str, dict] = {}

    # 2 e 4: cada afirmação
    for a in base["lista_afirmacoes"]:
        r: dict = {"tipo": a["tipo"], "nivel": a["fonte"]["nivel"]}
        if a["tipo"] == "dado":
            ruins = []
            for c in a["dados"]:
                v = valor_em(c["serie"], c["quando"], mensal, diario)
                if v is None or abs(v - c["valor"]) > c["tol"] + 1e-9:
                    ruins.append(f"{c['serie']} em {c['quando']}: texto {c['valor']}, dado {None if v is None else round(v, 4)}")
            nums_dados = " ".join(str(c["valor"]).replace(".", ",") for c in a["dados"])
            # As datas dos dados no jeito do texto (26/10) e os números que saem da conta dos dados (0,25).
            datas = " ".join(f"{int(c['quando'][8:])}/{int(c['quando'][5:7])}" for c in a["dados"] if len(c["quando"]) == 10)
            extra = " ".join(a.get("numeros_derivados", []))
            fora = revisa_texto.numeros_fora([a["texto"]], f"{nums_dados} {datas} {extra}")
            fora = [n for n in fora if not re.fullmatch(r"(19|20)\d\d", n)]
            r["status"] = "conferido" if not ruins else "dado_errado"
            if ruins:
                r["problemas"] = ruins
                erros.append(f"{a['id']}: dado não bate ({'; '.join(ruins)})")
            if fora:
                avisos.append(f"{a['id']}: número do texto sem conferência no campo dados ({', '.join(fora)})")
        else:
            r.update(conferir_trecho(a, offline))
            if r["status"] in ("trecho_nao_achado",) and a["tipo"] == "site":
                erros.append(f"{a['id']}: trecho não está em {a['arquivo']}")
        afirm[a["id"]] = r

    perguntas = []
    for p in base["perguntas"]:
        pe: list[str] = []
        pa: list[str] = []
        citadas: set[str] = set()
        # 1 e 3: ligações e números
        for onde, texto, ids in textos_da_pergunta(p):
            citadas |= set(ids)
            _texto_ok(onde, texto, ids, A, pe, pa)
        for e in p.get("episodios", []):
            if e not in E:
                pe.append(f"episódio que não existe: {e}")
        # 5: regras de leitura
        testes = {t["id"]: t for t in p.get("testes", [])}
        for d in p["escada"]:
            if d.get("rotulo") and d["rotulo"] not in ROTULOS:
                pe.append(f"{d['degrau']}: rótulo desconhecido {d['rotulo']}")
            if d.get("rotulo") == "consenso" and d["degrau"] != "fato" and d.get("afirmacoes"):
                niveis = [A[i]["fonte"]["nivel"] for i in d["afirmacoes"] if i in A]
                if niveis and min(niveis) >= 5:
                    pa.append(f"{d['degrau']}: consenso apoiado só em notícia ou banco (nível {min(niveis)} ou pior)")
            if d.get("leituras"):
                if not d.get("peso_da_evidencia"):
                    pe.append(f"{d.get('id')}: divisão sem peso da evidência")
                for lt in d["leituras"]:
                    if lt.get("status") not in STATUS_LEITURA:
                        pe.append(f"{lt['id']}: status desconhecido {lt.get('status')}")
                    if NOMES_COM_LADO.search(lt["nome"]):
                        pe.append(f"{lt['id']}: leitura com nome de lado ({lt['nome']})")
                    mo = lt.get("melhor_objecao") or {}
                    if not mo.get("afirmacoes"):
                        pe.append(f"{lt['id']}: leitura sem a melhor objeção com fonte")
                    apoio = [i for x in lt.get("a_favor", []) + lt.get("estudos", []) for i in x["afirmacoes"]]
                    if not apoio:
                        pe.append(f"{lt['id']}: leitura sem nada a favor")
                    if any(A[i]["fonte"]["nivel"] == 7 for i in apoio if i in A):
                        pe.append(f"{lt['id']}: comentarista (nível 7) usado como prova")
                    if lt.get("status") == "maioria" and not any(A[i]["fonte"]["nivel"] <= 3 for i in apoio if i in A):
                        pe.append(f"{lt['id']}: leitura de maioria sem estudo ou fonte oficial (níveis 1 a 3)")
                    if (lt.get("resposta") or {}).get("fonte_pendente"):
                        pa.append(f"{lt['id']}: resposta com fonte pendente: {lt['resposta']['fonte_pendente']}")
                if d.get("teste"):
                    t = testes.get(d["teste"])
                    if not t:
                        pe.append(f"{d.get('id')}: teste {d['teste']} não existe")
                    else:
                        faltam = {lt["id"] for lt in d["leituras"]} - set(t.get("o_que_cada_leitura_espera", {}))
                        if faltam:
                            pe.append(f"{t['id']}: não diz o que esperam {', '.join(sorted(faltam))}")
                        if not t.get("regra") or not t.get("conferir_em"):
                            pe.append(f"{t['id']}: teste sem regra ou sem data")
                        if t.get("registrado_em") and max(t["conferir_em"]) < t["registrado_em"]:
                            pe.append(f"{t['id']}: registrado depois da conferência")
        eps = [E[e] for e in p.get("episodios", []) if e in E]
        governos = {g for e in eps for g in e.get("governo", [])}
        causas = {e.get("causa") for e in eps}
        if len(governos) < 3:
            pa.append(f"episódios de só {len(governos)} governos: o teste da troca pede mais")
        if not {"daqui", "de fora"} <= causas:
            pa.append("episódios sem caso daqui e caso de fora")
        for e in eps:
            fontes = " ".join(A[i]["texto"] for i in e["afirmacoes"] if i in A)
            fora = [n for n in revisa_texto.numeros_fora([e["resumo"]], fontes) if not re.fullmatch(r"(19|20)\d\d", n)]
            if fora:
                pe.append(f"{e['id']}: número do resumo sem afirmação ({', '.join(fora)})")
            if NOMES_COM_LADO.search(e["resumo"]):
                pe.append(f"{e['id']}: nome de presidente ou partido no resumo")
            for i in e["afirmacoes"]:
                citadas.add(i)
        cont: dict[str, int] = {}
        for i in sorted(citadas):
            if i in afirm:
                cont[afirm[i]["status"]] = cont.get(afirm[i]["status"], 0) + 1
        perguntas.append({"id": p["id"], "erros": pe, "avisos": pa, "afirmacoes_citadas": len(citadas), "status": cont})
        erros += [f"{p['id']}: {x}" for x in pe]
        avisos += [f"{p['id']}: {x}" for x in pa]

    por_id = {p["id"]: p for p in base["perguntas"]}
    me, ma, citadas_posts = checar_posts(base.get("posts", []), por_id, A)
    posts = {"dias": [x["dia"] for x in base.get("posts", [])], "erros": me, "avisos": ma}
    erros += [f"posts: {x}" for x in me]
    avisos += [f"posts: {x}" for x in ma]

    soltas = sorted(set(A) - citadas_posts - {i for _, _, ids in
                    (t for p in base["perguntas"] for t in textos_da_pergunta(p)) for i in ids}
                    - {i for e in E.values() for i in e["afirmacoes"]})
    if soltas:
        avisos.append(f"afirmações que nenhum texto cita: {', '.join(soltas)}")
    resumo: dict[str, int] = {}
    for r in afirm.values():
        resumo[r["status"]] = resumo.get(r["status"], 0) + 1
    return {"em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "offline": offline,
            "resumo": resumo, "erros": erros, "avisos": avisos, "perguntas": perguntas, "posts": posts,
            "afirmacoes": afirm}


def main() -> None:
    offline = "--offline" in sys.argv
    rel = checar(carregar(), offline)
    CONF.mkdir(parents=True, exist_ok=True)
    out = CONF / f"{dt.date.today().isoformat()}-verifica{'-offline' if offline else ''}.json"
    out.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n")
    if "--json" in sys.argv:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
        return
    print(f"afirmações: {sum(rel['resumo'].values())} | " + ", ".join(f"{k} {v}" for k, v in sorted(rel["resumo"].items())))
    print(f"erros: {len(rel['erros'])}")
    for e in rel["erros"]:
        print("  ERRO", e)
    print(f"avisos: {len(rel['avisos'])}")
    for a in rel["avisos"]:
        print("  aviso", a)
    print(f"relatório: {out.relative_to(ROOT)}")
    sys.exit(1 if rel["erros"] else 0)


if __name__ == "__main__":
    main()
