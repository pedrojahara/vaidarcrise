"""A camada de tendência: o que o site acha que cada fator vai fazer nos próximos 6 meses.

- data/dossie.json guarda, por fator, a tendência, os fatos de notícia que a sustentam,
  o que outras instituições projetam e o que melhoraria ou pioraria o fator.
- Os fatos de dados (valor de hoje contra a história desde 2002) saem de código, todo dia,
  para nunca ficarem velhos.
- O LLM só propõe revisões; este módulo decide o que entra. Uma troca de tendência só
  vale com fato divulgado ou decisão tomada, noticiado por pelo menos 2 jornais.
- data/placar.json registra cada leitura com a data de conferir (6 meses depois) e o
  resultado contra o dado.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIE = ROOT / "data" / "dossie.json"
PLACAR = ROOT / "data" / "placar.json"
HIST = ROOT / "data" / "historico" / "series.json"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
TENDENCIAS = {"piora": ("mais", "↑", "Tende a piorar"), "estavel": ("igual", "→", "Estável"),
              "melhora": ("menos", "↓", "Tende a melhorar"), "sem_direcao": ("igual", "→", "Sem direção clara")}
MAX_NOTICIAS = 2
VALIDADE_NOTICIA_DIAS = 180


def _ler(p: Path, padrao):
    return json.loads(p.read_text()) if p.exists() else padrao


def carregar() -> dict:
    return _ler(DOSSIE, {"fatores": {}})


def carregar_placar() -> list[dict]:
    return _ler(PLACAR, [])


# ------------------------------------------------------------------ formatos
def num(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 and round(abs(x), d) != 0 else "") + s


def sinal(x: float, d: int = 1) -> str:
    return num(0, d) if round(x, d) == 0 else ("+" if x > 0 else "−") + num(abs(x), d)


def mes_ano(m: str) -> str:
    return f"{MESES[int(m[5:7]) - 1][:3]}/{m[2:4]}"


def mes_extenso(m: str) -> str:
    return f"{MESES[int(m[5:7]) - 1]} de {m[:4]}"


def dia_mes(iso: str) -> str:
    return f"{int(iso[8:10])}/{int(iso[5:7])}"


# ---------------------------------------------------------- fatos de dados
def _historia(hist: dict, chave: str, snap_serie: list[dict] | None = None, por_mes: bool = True) -> dict[str, float]:
    """Série mês a mês: o histórico desde 2002 completado pelo que a coleta do dia trouxe."""
    out: dict[str, float] = {}
    for x in hist.get("series", {}).get(chave, []):
        out[x["data"][:7]] = x["valor"]
    for x in snap_serie or []:
        out[x["data"][:7]] = x["valor"]
    return dict(sorted(out.items()))


def desde(serie: dict[str, float], mes: str, valor: float, maior: bool) -> str | None:
    """'o maior desde mar/16': o último mês antes de `mes` com valor pelo menos tão extremo.

    Devolve None quando o valor não é o mais extremo de pelo menos 12 meses."""
    anteriores = [(m, v) for m, v in serie.items() if m < mes]
    if not anteriores:
        return None
    for m, v in reversed(anteriores):
        if (v >= valor if maior else v <= valor):
            meses = (int(mes[:4]) - int(m[:4])) * 12 + int(mes[5:7]) - int(m[5:7])
            return f"desde {mes_ano(m)}" if meses >= 12 else None
    return f"da série, que começa em {anteriores[0][0][:4]}"


def fatos_de_dados(res: dict, snap: dict, mensal: dict | None = None, hist: dict | None = None) -> dict[str, list[dict]]:
    """Um ou dois fatos de dados por fator, com o contexto da história. Cada fato: {texto, fonte}."""
    hist = hist if hist is not None else _ler(HIST, {"series": {}})
    mensal = mensal or {}
    ind = {x["id"]: x for x in res["indicadores"]}
    ser = snap.get("series", {})
    out: dict[str, list[dict]] = {k: [] for k in ("atividade", "juro", "credito", "mercado", "contas", "emprego", "externo")}

    def hist_ind(k: str) -> dict[str, float]:
        return (mensal.get("indicadores") or {}).get(k, {})

    x = ind.get("ibcbr")
    if x and x.get("valor") is not None:
        m = x["ref"]
        txt = f"IBC-Br {sinal(x['valor'])}% no trimestre até {MESES[int(m[5:7]) - 1]}, contra os 3 meses anteriores"
        if x["valor"] < 0:
            # A série mensal da calibração é indexada pelo mês da conta (2 meses depois do dado).
            h = {_mais_meses(k, -2): v for k, v in hist_ind("ibcbr").items()}
            ctx = desde(h, m, x["valor"], maior=False)
            if ctx:
                txt += f", a maior queda {ctx}"
        out["atividade"].append({"texto": txt + ".", "fonte": "BC"})
    x = ind.get("focus_pib")
    if x and x.get("valor") is not None:
        ano = int(x["ref"][:4])
        txt = f"Focus espera PIB de {num(x['ano'])}% em {ano} e {num(x['ano_seguinte'])}% em {ano + 1}"
        antes = {f["data"][:7]: f for f in hist.get("series", {}).get("focus_pib", [])}.get(_mais_meses(x["ref"][:7], -3))
        # Com a comparação de 3 meses, o Focus aparece no quadro de quem projeta (focus_outros), não aqui.
        if not antes:
            out["atividade"].append({"texto": txt + ".", "fonte": "Focus"})

    x = ind.get("juro_real")
    if x and x.get("valor") is not None:
        txt = f"Juro real em {num(x['valor'])}% ao ano: Selic de {num(x['selic'], 2)}% menos a inflação esperada de {num(x['inflacao_esperada'])}%"
        h = dict(hist_ind("juro_real"))
        mes = x["ref"][:7]
        h.pop(mes, None)
        lo, hi = x["faixa_normal"] or (None, None)
        if hi is not None and x["valor"] > hi:
            ctx = desde(h, mes, x["valor"], maior=True)
            if ctx:
                txt += f", o maior {ctx}"
        out["juro"].append({"texto": txt + ".", "fonte": "BC e Focus"})
        selic = ser.get("selic_meta", {}).get("dados", [])
        if selic:
            ult = selic[-1]["valor"]
            mudou = next((s for s in reversed(selic) if s["valor"] != ult), None)
            if mudou:
                ini = next(s for s in selic if s["data"] > mudou["data"])
                txt = f"Selic em {num(ult, 2)}% desde {dia_mes(ini['data'])}/{ini['data'][2:4]}; antes, {num(mudou['valor'], 2)}%"
                pico = max(s["valor"] for s in selic if s["data"] >= _mais_meses(selic[-1]["data"][:7], -12))
                if pico > ult:
                    txt += f". Em 12 meses, chegou a {num(pico, 2)}%"
                out["juro"].append({"texto": txt + ".", "fonte": "BC"})

    x = ind.get("comprometimento")
    if x and x.get("valor") is not None:
        h = _historia(hist, "comprometimento_renda", ser.get("comprometimento_renda", {}).get("dados"))
        mes = x["ref"][:7]
        txt = f"{num(x['nivel'])}% da renda das famílias vai para dívidas ({mes_ano(mes)})"
        ctx = desde({k: v for k, v in h.items() if k != mes}, mes, x["nivel"], maior=True)
        if ctx:
            txt += f", o maior nível {ctx}"
        ant = h.get(_mais_meses(mes, -12))
        if ant is not None:
            txt += f"; eram {num(ant)}% um ano antes"
        out["credito"].append({"texto": txt + ".", "fonte": "BC"})

    x = ind.get("tesouro")
    if x and x.get("valor") is not None:
        venc = (x.get("vencimento") or "")[:4]
        txt = (f"Tesouro IPCA+ {venc} a {num(x['nivel'], 2)}% ao ano em {dia_mes(x['ref'])}, "
               f"{num(abs(x['valor']), 2)} ponto {'acima' if x['valor'] >= 0 else 'abaixo'} da mediana de 3 anos")
        h = {}
        for p in hist.get("series", {}).get("juro_real_longo", []):
            h[p["data"][:7]] = max(h.get(p["data"][:7], -99), p["valor"])
        mes = x["ref"][:7]
        h.pop(mes, None)
        ctx = desde(h, mes, x["nivel"], maior=True)
        if ctx:
            txt += f"; a taxa mais alta {ctx}"
        out["mercado"].append({"texto": txt + ".", "fonte": "Tesouro Direto"})
    x = ind.get("dolar")
    if x and x.get("valor") is not None:
        out["mercado"].append({"texto": f"Dólar a R$ {num(x['nivel'], 2)} em {dia_mes(x['ref'])}, {sinal(x['valor'])}% em 3 meses.",
                               "fonte": "BC"})

    x = ind.get("divida")
    if x and x.get("valor") is not None:
        mes = x["ref"][:7]
        txt = f"Dívida bruta em {num(x['nivel'])}% do PIB ({mes_ano(mes)}), {sinal(x['valor'])} pontos em 12 meses"
        h = {_mais_meses(k, -2): v for k, v in hist_ind("divida").items()}
        h.pop(mes, None)
        if x["valor"] > 0:
            ctx = desde(h, mes, x["valor"], maior=True)
            if ctx:
                txt += f", a maior alta {ctx}"
        out["contas"].append({"texto": txt + ".", "fonte": "BC"})
    prim = ser.get("primario_12m", {}).get("dados", [])
    if len(prim) >= 13:
        a, b = prim[-1], next((p for p in reversed(prim) if p["data"][:7] == _mais_meses(prim[-1]["data"][:7], -12)), None)
        if b:
            def lado(v: float) -> str:
                return f"déficit de {num(abs(v))}%" if v > 0 else f"superávit de {num(abs(v))}%"
            out["contas"].append({"texto": f"Setor público (União, estados e municípios): {lado(a['valor'])} do PIB em 12 meses até "
                                           f"{mes_ano(a['data'][:7])}, contra {lado(b['valor'])} um ano antes.", "fonte": "BC"})

    x = ind.get("sahm")
    if x and x.get("valor") is not None:
        h = _historia(hist, "desocupacao", ser.get("desocupacao", {}).get("dados"))
        mes = x["ref"][:7]
        mn_m = min((k for k in h if k < mes), key=lambda k: (h[k], k), default=None)
        txt = f"Desemprego em {num(x['nivel'])}% no trimestre até {MESES[int(mes[5:7]) - 1]}"
        if mn_m:
            txt += f"; a mínima da série, que começa em 2012, foi {num(h[mn_m])}% ({mes_ano(mn_m)})"
        out["emprego"].append({"texto": txt + ".", "fonte": "IBGE"})
        lim = x.get("limite")
        txt = f"Regra de Sahm em {sinal(x['valor'])} ponto"
        txt += f", abaixo do alerta de {sinal(lim)}" if lim is not None and x["peso"] else ": o desemprego médio de 3 meses contra a mínima de 12 meses"
        out["emprego"].append({"texto": txt + ".", "fonte": "IBGE"})

    x = ind.get("commodities")
    if x and x.get("valor") is not None:
        mes = x["ref"][:7]
        out["externo"].append({"texto": f"Preço das commodities {sinal(x['valor'])}% em 6 meses até {MESES[int(mes[5:7]) - 1]} "
                                        f"(índice do FMI).", "fonte": "FMI"})
    return out


def _mais_meses(m: str, n: int) -> str:
    a, mm = divmod(int(m[:4]) * 12 + int(m[5:7]) - 1 + n, 12)
    return f"{a:04d}-{mm + 1:02d}"


# --------------------------------------------------------------- o que outros projetam
def focus_outros(res: dict, snap: dict, dossie: dict, hist: dict | None = None) -> dict[str, dict]:
    """O Focus em igual destaque, onde ele projeta o fator. A posição sai por regra: concorda quando a
    projeção aponta para o mesmo lado da tendência do site."""
    hist = hist if hist is not None else _ler(HIST, {"series": {}})
    ind = {x["id"]: x for x in res["indicadores"]}
    focus = snap.get("focus", {})
    fat = dossie.get("fatores", {})
    out = {}

    def posicao(lado_focus: str, fid: str) -> str:
        nossa = fat.get(fid, {}).get("tendencia")
        if nossa in (None, "sem_direcao"):
            return "neutro"
        return "concorda" if nossa == lado_focus else "discorda"

    x = ind.get("focus_pib")
    if x and x.get("valor") is not None:
        antes = {f["data"][:7]: f for f in hist.get("series", {}).get("focus_pib", [])}.get(_mais_meses(x["ref"][:7], -3))
        if antes:
            import indicadores as I
            v0 = I.focus_pib(antes["ano"], antes["ano_seguinte"], antes["dia"])
            d = x["valor"] - v0
            lado = "piora" if d <= -0.2 else "melhora" if d >= 0.2 else "estavel"
            verbo = {"piora": "cortou", "melhora": "subiu", "estavel": "manteve perto de"}[lado]
            ano = int(x["ref"][:4])
            txt = (f"Focus {verbo} a projeção de PIB em 3 meses: {num(x['ano'])}% em {ano} e {num(x['ano_seguinte'])}% em {ano + 1}"
                   f" (eram {num(antes['ano'])}% e {num(antes['ano_seguinte'])}%).")
            out["atividade"] = {"tipo": posicao(lado, "atividade"), "texto": txt, "fonte": {"veiculo": f"Focus {dia_mes(x['ref'])}", "url": "https://www.bcb.gov.br/publicacoes/focus"}}
    sel = focus.get("Selic") or []
    jr = ind.get("juro_real")
    if sel and jr and jr.get("valor") is not None:
        data = sel[0]["Data"]
        ano = int(data[:4])
        por_ano = {str(r["DataReferencia"]): float(r["Mediana"]) for r in sel}
        if str(ano) in por_ano and str(ano + 1) in por_ano:
            d = por_ano[str(ano + 1)] - jr["selic"]
            lado = "melhora" if d <= -1.0 else "piora" if d >= 0.5 else "estavel"
            txt = (f"Focus espera Selic de {num(por_ano[str(ano)], 2)}% no fim de {ano} e {num(por_ano[str(ano + 1)], 2)}% no fim de {ano + 1}"
                   + (", ou seja, juro em queda." if lado == "melhora" else "."))
            out["juro"] = {"tipo": posicao(lado, "juro"), "texto": txt, "fonte": {"veiculo": f"Focus {dia_mes(data)}", "url": "https://www.bcb.gov.br/publicacoes/focus"}}
    cam = focus.get("Câmbio") or []
    dol = ind.get("dolar")
    if cam and dol and dol.get("valor") is not None:
        data = cam[0]["Data"]
        ano = int(data[:4])
        por_ano = {str(r["DataReferencia"]): float(r["Mediana"]) for r in cam}
        if str(ano) in por_ano:
            alvo = por_ano[str(ano)]
            rel = alvo / dol["nivel"] - 1
            lado = "melhora" if rel <= -0.03 else "piora" if rel >= 0.03 else "estavel"
            txt = f"Focus espera dólar a R$ {num(alvo, 2)} no fim de {ano}, contra R$ {num(dol['nivel'], 2)} hoje."
            out["mercado"] = {"tipo": posicao(lado, "mercado"), "texto": txt, "fonte": {"veiculo": f"Focus {dia_mes(data)}", "url": "https://www.bcb.gov.br/publicacoes/focus"}}
    return out


# ------------------------------------------------------------- revisões do LLM
def aplicar_revisoes(dossie: dict, revisoes: list[dict], eventos_por_noticia: dict[str, dict],
                     fontes_por_noticia: dict[str, dict], hoje: dt.date) -> list[dict]:
    """Aplica o que as regras permitem e devolve a lista do que mudou (e do que foi recusado, com motivo)."""
    log = []
    for rv in revisoes:
        f = dossie["fatores"].get(rv["fator"])
        if f is None:
            continue
        evs = [eventos_por_noticia[i] for i in rv["noticia_ids"] if i in eventos_por_noticia]
        fontes = [fontes_por_noticia[i] for i in rv["noticia_ids"] if i in fontes_por_noticia]
        if rv["tipo"] == "noticia":
            if not fontes:
                log.append({**rv, "aplicada": False, "motivo": "sem manchete"})
                continue
            f.setdefault("noticias", []).insert(0, {"texto": rv["texto"], "data": hoje.isoformat(),
                                                   "fonte": {"veiculo": fontes[0]["veiculo"], "url": fontes[0]["url"]}})
            f["noticias"] = f["noticias"][:MAX_NOTICIAS]
            log.append({**rv, "aplicada": True})
        elif rv["tipo"] == "outros":
            if not fontes or rv.get("posicao") not in ("concorda", "discorda"):
                log.append({**rv, "aplicada": False, "motivo": "sem manchete ou sem posição"})
                continue
            if f.get("outros_automatico"):
                log.append({**rv, "aplicada": False, "motivo": "fator com projeção do Focus calculada por código"})
                continue
            f["outros"] = {"tipo": rv["posicao"], "texto": rv["texto"], "data": hoje.isoformat(),
                           "fonte": {"veiculo": fontes[0]["veiculo"], "url": fontes[0]["url"]}}
            log.append({**rv, "aplicada": True})
        elif rv["tipo"] == "tendencia":
            nova = rv.get("tendencia")
            fortes = [e for e in evs if e.get("estagio") in ("dado", "decidido")]
            veiculos = {v for e in fortes for v in e.get("veiculos", [])}
            if nova not in TENDENCIAS or nova == f.get("tendencia"):
                log.append({**rv, "aplicada": False, "motivo": "tendência igual ou inválida"})
            elif not fortes or len(veiculos) < 2:
                log.append({**rv, "aplicada": False, "motivo": "troca exige fato divulgado ou decisão em 2 jornais"})
            else:
                f.setdefault("leituras", []).append({"tendencia": f.get("tendencia"), "ate": hoje.isoformat()})
                f["tendencia"], f["desde"], f["motivo_troca"] = nova, hoje.isoformat(), rv["texto"]
                log.append({**rv, "aplicada": True})
    corte = (hoje - dt.timedelta(days=VALIDADE_NOTICIA_DIAS)).isoformat()
    for f in dossie["fatores"].values():
        f["noticias"] = [n for n in f.get("noticias", []) if n.get("data", "9999") >= corte]
    return log


# ------------------------------------------------------------------- placar
MEDIDAS_NIVEL = {"comprometimento_nivel": ("comprometimento", "nivel"), "tesouro_nivel": ("tesouro", "nivel"),
                 "divida_nivel": ("divida", "nivel"), "desocupacao": ("sahm", "nivel"),
                 "commodities_nivel": ("commodities", "nivel"), "ibcbr_3m": ("ibcbr", "valor"),
                 "juro_real": ("juro_real", "valor")}


def medida(res: dict, serie: str) -> dict | None:
    ind = {x["id"]: x for x in res["indicadores"]}
    k, campo = MEDIDAS_NIVEL[serie]
    x = ind.get(k)
    if not x or x.get(campo) is None:
        return None
    return {"valor": x[campo], "ref": x["ref"]}


def registrar(placar: list[dict], dossie: dict, res: dict, cfg: dict, hoje: dt.date) -> list[dict]:
    """Registra a leitura de cada fator que ainda não tem leitura aberta igual. Devolve as novas."""
    novas = []
    meses = cfg["placar"]["meses"]
    for fid, f in dossie["fatores"].items():
        t = f.get("tendencia")
        if t not in ("piora", "estavel", "melhora"):
            continue
        aberta = next((p for p in placar if p["fator"] == fid and p.get("resultado") is None), None)
        if aberta and aberta["leitura"] == t:
            continue
        med = cfg["placar"]["medidas"][fid]
        m = medida(res, med["serie"])
        if m is None:
            continue
        a, mm = divmod(hoje.year * 12 + hoje.month - 1 + meses, 12)
        dia = min(hoje.day, 28)
        p = {"fator": fid, "leitura": t, "data": hoje.isoformat(), "conferir_em": dt.date(a, mm + 1, dia).isoformat(),
             "medida": med["serie"], "inicial": m, "resultado": None}
        if aberta:
            # Leitura trocada antes do prazo: a antiga fica registrada como substituída, sem resultado.
            aberta["resultado"] = "substituida"
            aberta["substituida_em"] = hoje.isoformat()
        placar.append(p)
        novas.append(p)
    return novas


def conferir(placar: list[dict], res: dict, cfg: dict, cal: dict, hoje: dt.date) -> list[dict]:
    """Confere as leituras vencidas contra o dado: piora acerta se a medida andou para o lado ruim mais que a
    tolerância; estável, se ficou dentro dela; melhora, se andou para o lado bom."""
    feitas = []
    for p in placar:
        if p.get("resultado") is not None or p["conferir_em"] > hoje.isoformat():
            continue
        med = cfg["placar"]["medidas"][p["fator"]]
        m = medida(res, med["serie"])
        tol = (cal.get("placar", {}).get(p["fator"]) or {}).get("tolerancia")
        if m is None or tol is None:
            continue
        if med["serie"] == "commodities_nivel":
            delta = 100 * (m["valor"] / p["inicial"]["valor"] - 1)
        else:
            delta = m["valor"] - p["inicial"]["valor"]
        ruim = delta * med["direcao"]
        certo = {"piora": ruim > tol, "estavel": abs(ruim) <= tol, "melhora": ruim < -tol}[p["leitura"]]
        p.update({"final": m, "variacao": delta, "tolerancia": tol, "resultado": "acertou" if certo else "errou",
                  "conferido_em": hoje.isoformat()})
        feitas.append(p)
    return feitas
