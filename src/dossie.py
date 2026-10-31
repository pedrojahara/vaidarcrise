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


def enxuto(x: float, d: int = 1) -> str:
    """Sem zeros que não dizem nada: 14,00 vira 14 e 29,0 vira 29; 13,75 fica."""
    s = num(x, d)
    return s.split(",")[0] if "," in s and set(s.split(",")[1]) == {"0"} else s


def pontos(x: float) -> str:
    """'0,6 ponto', '5,1 pontos': singular abaixo de 2."""
    return f"{num(abs(x))} ponto{'s' if round(abs(x), 1) >= 2 else ''}"


def faixa(lo: float, hi: float) -> str:
    """A faixa normal sem sinal de menos: 'de queda de 0,4% a alta de 4,1%' ou 'de 0,4% a 4,1%'."""
    if lo < 0:
        return f"de queda de {num(abs(lo))}% a alta de {num(hi)}%" if hi > 0 else f"de queda de {num(abs(lo))}% a {num(abs(hi))}%"
    return f"de {num(lo)}% a {num(hi)}%"


def alta_queda(x: float) -> str:
    return f"queda de {enxuto(abs(x))}%" if round(x, 1) < 0 else f"alta de {enxuto(x)}%"


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
    """'o maior desde março de 2016': o último mês antes de `mes` com valor pelo menos tão extremo.

    Devolve None quando o valor não é o mais extremo de pelo menos 12 meses."""
    anteriores = [(m, v) for m, v in serie.items() if m < mes]
    if not anteriores:
        return None
    for m, v in reversed(anteriores):
        if (v >= valor if maior else v <= valor):
            meses = (int(mes[:4]) - int(m[:4])) * 12 + int(mes[5:7]) - int(m[5:7])
            return f"desde {mes_extenso(m)}" if meses >= 12 else None
    return f"desde o início da série, em {anteriores[0][0][:4]}"


def fatos_de_dados(res: dict, snap: dict, mensal: dict | None = None, hist: dict | None = None) -> dict[str, list[dict]]:
    """Um ou dois fatos de dados por fator, com o contexto da história. Cada fato: {texto, fonte}.

    Os textos seguem PERSONA.md: queda no verbo, uma comparação por frase, sem sigla solta."""
    hist = hist if hist is not None else _ler(HIST, {"series": {}})
    mensal = mensal or {}
    ind = {x["id"]: x for x in res["indicadores"]}
    ser = snap.get("series", {})
    out: dict[str, list[dict]] = {k: [] for k in ("atividade", "juro", "credito", "mercado", "contas", "emprego", "externo")}

    def hist_ind(k: str) -> dict[str, float]:
        return (mensal.get("indicadores") or {}).get(k, {})

    # As entradas da conta do nível vêm primeiro no fator delas.
    ent = {x["id"]: x for x in (res.get("gar") or {}).get("entradas", [])}
    x = ent.get("crescimento")
    if x:
        m = x["ref"]
        ini = _mais_meses(m, -2)
        v = x["valor"]
        verbo = "ficou parada" if round(v, 1) == 0 else f"cresceu {num(v)}%" if v > 0 else f"encolheu {num(abs(v))}%"
        out["atividade"].append({"texto": f"A economia {verbo} em um ano (prévia do PIB, de {MESES[int(ini[5:7]) - 1]} a "
                                          f"{MESES[int(m[5:7]) - 1]}). O normal desde 2004 vai "
                                          f"{faixa(*x['faixa_normal'])}.", "fonte": "BC"})
    x = ent.get("inflacao")
    if x:
        m = x["ref"]
        ritmo = ("no mesmo ritmo" if round(x["valor"], 1) == 0 else "mais devagar" if x["valor"] < 0 else "mais rápido")
        out["juro"].append({"texto": f"Os preços subiram {num(x['nivel'])}% em um ano até {MESES[int(m[5:7]) - 1]} (IPCA). "
                                     f"Um ano antes, a alta era de {num(x['antes'])}%: os preços sobem {ritmo}.", "fonte": "IBGE"})

    x = ind.get("ibcbr")
    if x and x.get("valor") is not None:
        m = x["ref"]
        v = x["valor"]
        verbo = "ficou parada" if round(v, 1) == 0 else f"cresceu {num(v)}%" if v > 0 else f"caiu {num(abs(v))}%"
        txt = f"A prévia do PIB {verbo} no trimestre até {MESES[int(m[5:7]) - 1]}, contra os 3 meses anteriores"
        if x["valor"] < 0:
            # A série mensal da calibração é indexada pelo mês da conta (2 meses depois do dado).
            h = {_mais_meses(k, -2): v for k, v in hist_ind("ibcbr").items()}
            ctx = desde(h, m, x["valor"], maior=False)
            if ctx:
                txt += f". É a maior queda {ctx}"
        out["atividade"].append({"texto": txt + ".", "fonte": "BC"})
    x = ind.get("focus_pib")
    if x and x.get("valor") is not None:
        ano = int(x["ref"][:4])
        txt = f"Os bancos (Focus) esperam {alta_queda(x['ano'])} do PIB em {ano} e {alta_queda(x['ano_seguinte'])} em {ano + 1}"
        antes = {f["data"][:7]: f for f in hist.get("series", {}).get("focus_pib", [])}.get(_mais_meses(x["ref"][:7], -3))
        # Com a comparação de 3 meses, o Focus aparece no quadro de quem projeta (focus_outros), não aqui.
        if not antes:
            out["atividade"].append({"texto": txt + ".", "fonte": "Focus"})

    x = ind.get("juro_real")
    if x and x.get("valor") is not None:
        txt = (f"Descontada a inflação esperada ({num(x['inflacao_esperada'])}%), a Selic de {enxuto(x['selic'], 2)}% "
               f"rende {num(x['valor'])}% ao ano")
        h = dict(hist_ind("juro_real"))
        mes = x["ref"][:7]
        h.pop(mes, None)
        lo, hi = x["faixa_normal"] or (None, None)
        if hi is not None and x["valor"] > hi:
            ctx = desde(h, mes, x["valor"], maior=True)
            if ctx:
                txt += f". É o maior {ctx}"
        out["juro"].append({"texto": txt + ".", "fonte": "BC e Focus"})
        selic = ser.get("selic_meta", {}).get("dados", [])
        if selic:
            ult = selic[-1]["valor"]
            mudou = next((s for s in reversed(selic) if s["valor"] != ult), None)
            if mudou:
                ini = next(s for s in selic if s["data"] > mudou["data"])
                quando = dia_mes(ini["data"]) + ("" if ini["data"][:4] == selic[-1]["data"][:4] else f"/{ini['data'][:4]}")
                txt = f"Selic em {enxuto(ult, 2)}% desde {quando}. Antes, era {enxuto(mudou['valor'], 2)}%"
                pico = max(s["valor"] for s in selic if s["data"] >= _mais_meses(selic[-1]["data"][:7], -12))
                if pico > ult:
                    txt += f". Nos últimos 12 meses, chegou a {enxuto(pico, 2)}%"
                out["juro"].append({"texto": txt + ".", "fonte": "BC"})

    x = ind.get("comprometimento")
    if x and x.get("valor") is not None:
        h = _historia(hist, "comprometimento_renda", ser.get("comprometimento_renda", {}).get("dados"))
        mes = x["ref"][:7]
        txt = f"{enxuto(x['nivel'])}% da renda das famílias vai para parcelas e juros ({MESES[int(mes[5:7]) - 1]})"
        ctx = desde({k: v for k, v in h.items() if k != mes}, mes, x["nivel"], maior=True)
        if ctx:
            txt += f", o maior {ctx}"
        ant = h.get(_mais_meses(mes, -12))
        if ant is not None:
            txt += f". Um ano antes, eram {enxuto(ant)}%"
        out["credito"].append({"texto": txt + ".", "fonte": "BC"})

    x = ind.get("tesouro")
    if x and x.get("valor") is not None:
        venc = (x.get("vencimento") or "")[:4]
        txt = (f"O governo paga {num(x['nivel'])}% ao ano acima da inflação para pegar dinheiro até {venc} ({dia_mes(x['ref'])}). "
               f"É {pontos(x['valor'])} {'acima' if x['valor'] >= 0 else 'abaixo'} do normal dos últimos 3 anos")
        h = {}
        for p in hist.get("series", {}).get("juro_real_longo", []):
            h[p["data"][:7]] = max(h.get(p["data"][:7], -99), p["valor"])
        mes = x["ref"][:7]
        h.pop(mes, None)
        ctx = desde(h, mes, x["nivel"], maior=True)
        if ctx:
            txt += f", a taxa mais alta {ctx}"
        out["mercado"].append({"texto": txt + ".", "fonte": "Tesouro Direto"})
    x = ind.get("dolar")
    if x and x.get("valor") is not None:
        v = x["valor"]
        quanto = "o mesmo preço de 3 meses atrás" if round(v, 1) == 0 else f"{num(abs(v))}% mais {'caro' if v > 0 else 'barato'} que há 3 meses"
        out["mercado"].append({"texto": f"Dólar a R$ {num(x['nivel'], 2)} em {dia_mes(x['ref'])}, {quanto}.",
                               "fonte": "BC"})

    x = ind.get("divida")
    if x and x.get("valor") is not None:
        mes = x["ref"][:7]
        v = x["valor"]
        txt = (f"Dívida do governo em {num(x['nivel'])}% do PIB ({MESES[int(mes[5:7]) - 1]}). "
               + ("Igual a um ano antes" if round(v, 1) == 0 else f"{'Subiu' if v > 0 else 'Caiu'} {pontos(v)} em um ano"))
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
            # + é déficit: o governo gasta mais do que arrecada, sem contar juros.
            def lado(v: float, passado: bool) -> str:
                g, r = ("gastavam", "arrecadavam") if passado else ("gastaram", "arrecadaram")
                return f"{g} {num(abs(v))}% do PIB a mais do que {r}" if v > 0 else f"{r} {num(abs(v))}% do PIB a mais do que {g}"
            antes = (f"Um ano antes, eram {num(abs(b['valor']))}%" if (a["valor"] > 0) == (b["valor"] > 0)
                     else f"Um ano antes, {lado(b['valor'], True)}")
            out["contas"].append({"texto": f"União, estados e municípios {lado(a['valor'], False)} nos 12 meses até "
                                           f"{MESES[int(a['data'][5:7]) - 1]}, sem contar juros. {antes}.", "fonte": "BC"})

    x = ind.get("sahm")
    if x and x.get("valor") is not None:
        h = _historia(hist, "desocupacao", ser.get("desocupacao", {}).get("dados"))
        mes = x["ref"][:7]
        mn_m = min((k for k in h if k < mes), key=lambda k: (h[k], k), default=None)
        txt = f"Desemprego em {num(x['nivel'])}% no trimestre até {MESES[int(mes[5:7]) - 1]}"
        if mn_m:
            txt += f". O menor desde 2012 foi {num(h[mn_m])}%, em {mes_extenso(mn_m)}"
        out["emprego"].append({"texto": txt + ".", "fonte": "IBGE"})
        v = x["valor"]
        quanto = "igual ao" if round(v, 1) == 0 else f"{pontos(v)} {'acima' if v > 0 else 'abaixo'} do"
        out["emprego"].append({"texto": f"O desemprego médio de 3 meses está {quanto} menor do último ano.", "fonte": "IBGE"})

    x = ind.get("commodities")
    if x and x.get("valor") is not None:
        mes = x["ref"][:7]
        v = x["valor"]
        quanto = "ficaram com o mesmo preço" if round(v, 1) == 0 else f"ficaram {num(abs(v))}% mais {'caros' if v > 0 else 'baratos'}"
        out["externo"].append({"texto": f"Soja, minério, petróleo e outros produtos básicos {quanto} em 6 meses até "
                                        f"{MESES[int(mes[5:7]) - 1]} (FMI).", "fonte": "FMI"})
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
            verbo = {"piora": "reduziram", "melhora": "aumentaram", "estavel": "mantiveram"}[lado]
            ano = int(x["ref"][:4])
            txt = (f"Os bancos (Focus) {verbo} a previsão do PIB: {enxuto(x['ano'])}% em {ano} e {enxuto(x['ano_seguinte'])}% em {ano + 1}."
                   f" Há 3 meses, eram {enxuto(antes['ano'])}% e {enxuto(antes['ano_seguinte'])}%.")
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
            txt = (f"Os bancos (Focus) esperam a Selic em {enxuto(por_ano[str(ano)], 2)}% no fim de {ano} e em "
                   f"{enxuto(por_ano[str(ano + 1)], 2)}% no fim de {ano + 1}"
                   + {"melhora": ": juro caindo.", "piora": ": juro subindo.", "estavel": "."}[lado])
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
            txt = f"Os bancos (Focus) esperam o dólar a R$ {num(alvo, 2)} no fim de {ano}. Hoje está em R$ {num(dol['nivel'], 2)}."
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
