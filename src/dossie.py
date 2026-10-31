"""Os fatos de dados de cada parte da economia: o valor de hoje contra a história desde 2002.

Saem de código, todo dia, para nunca ficarem velhos, e vão para o post (src/escreve_post.py) como
contexto, com a mesma frase em todas as atualizações. O site não faz previsão para os próximos meses.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def _ler(p: Path, padrao):
    return json.loads(p.read_text()) if p.exists() else padrao




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
