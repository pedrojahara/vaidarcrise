"""O que causa recessão: os números da aba /causas/.

Duas partes:
- O que veio antes das altas da Selic no Brasil desde 2002, refeito aqui a partir de
  data/historico/series.json. Os números dos 44 países vêm do painel da pesquisa e ficam
  fixos em config/causas.json.
- O Brasil de hoje em cada elo da cadeia: o dado mais recente contra os meses desde 2004.

Uso: python src/causas.py   (imprime a chance de cada sinal vir antes de uma alta da Selic)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
CONFIG = ROOT / "config" / "causas.json"
INICIO_AUC, INICIO_HOJE = "2002-01", "2004-01"
# Atenção: fora da metade do meio dos meses desde 2004, para o lado que pressiona (como no Resumo).
CORTE = 75


def mes_num(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def num_mes(n: int) -> str:
    a, m = divmod(n, 12)
    return f"{a:04d}-{m + 1:02d}"


def mensal(serie: list[dict]) -> dict[str, float]:
    """Média de cada mês (as séries diárias viram mensais)."""
    soma: dict[str, list[float]] = {}
    for p in serie:
        if p.get("valor") is not None:
            soma.setdefault(p["data"][:7], []).append(p["valor"])
    return {m: sum(v) / len(v) for m, v in soma.items()}


def desloca(x: dict[str, float], k: int) -> dict[str, float]:
    """O valor de k meses antes em cada mês (k > 0) ou de k meses depois (k < 0)."""
    return {num_mes(mes_num(m) + k): v for m, v in x.items()}


def var(x: dict[str, float], k: int, pct: bool = False) -> dict[str, float]:
    antes = desloca(x, k)
    return {m: (100 * (v / antes[m] - 1) if pct else v - antes[m]) for m, v in x.items() if m in antes}


def auc(x: dict[str, float], y: dict[str, int]) -> float | None:
    """Chance de um mês antes de uma alta ter o sinal mais alto que um mês sem alta (0,5 = cara ou coroa)."""
    pos = [v for m, v in x.items() if y.get(m) == 1]
    neg = [v for m, v in x.items() if y.get(m) == 0]
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def series_brasil(series: dict) -> dict[str, dict[str, float]]:
    return {k: mensal(series[k]) for k in ("selic_meta", "ipca_12m", "focus_ipca_12m", "ibcbr", "primario_12m",
                                           "divida_bruta", "commodities", "comprometimento_renda") if k in series}


def sinais_selic(s: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Cada sinal com o que já tinha sido divulgado no mês (IBC-Br, primário e dívida saem com 2 meses de atraso)."""
    selic, foc = s["selic_meta"], s["focus_ipca_12m"]
    return {
        "economia": desloca(var(s["ibcbr"], 12, pct=True), 2),
        "preco_fora": desloca(var(s["commodities"], 12, pct=True), 1),
        "deficit_sobe": desloca(var(s["primario_12m"], 12), 2),
        "expectativa_sobe": var(foc, 6),
        "juro_real_baixo": {m: v - selic[m] for m, v in foc.items() if m in selic},
        "divida": desloca(s["divida_bruta"], 2),
    }


def alta_selic(selic: dict[str, float]) -> dict[str, int]:
    """1 se a Selic subir 1 ponto ou mais nos 12 meses seguintes."""
    depois = desloca(selic, -12)
    return {m: int(depois[m] - v >= 1) for m, v in selic.items() if m in depois and m >= INICIO_AUC}


def aucs_brasil(series: dict) -> dict:
    s = series_brasil(series)
    y = alta_selic(s["selic_meta"])
    out = {}
    for k, x in sinais_selic(s).items():
        a = auc({m: v for m, v in x.items() if m in y}, y)
        out[k] = round(a, 2) if a is not None else None
    return {"aucs": out, "altas": sum(y.values()), "meses": len(y)}


# -------------------------------------------------------------- Brasil hoje
def percentil(hist: dict[str, float], v: float) -> int:
    xs = [x for m, x in hist.items() if m >= INICIO_HOJE]
    return round(100 * sum(1 for x in xs if x <= v) / len(xs)) if xs else 50


def num(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 and round(abs(x), d) != 0 else "") + s


def pct(x: float, d: int = 2) -> str:
    """13,75 e 15 (sem os zeros do fim)."""
    s = num(x, d)
    return s.rstrip("0").rstrip(",") if "," in s else s


def rumo(v: float, parado: float = 0.25) -> str:
    return "subiu" if v >= parado else "caiu" if v <= -parado else "ficou parado"


def brasil_hoje(series: dict, res: dict, bruto: dict | None, runs: list[dict], cfg: dict) -> dict:
    """Cada elo da cadeia com o dado de hoje e a leitura (Atenção ou Calmo).

    Atenção quando o dado sai da metade do meio dos meses desde 2004 para o lado que pressiona,
    como no Resumo: pela faixa normal da calibração, quando o dado já está na conta ou no Resumo;
    pelos meses de data/historico/series.json, quando não está.
    """
    s = series_brasil(series)
    ind = {x["id"]: x for x in res["indicadores"]}
    ent = {x["id"]: x for x in (res.get("gar") or {}).get("entradas", [])}
    foc = dict(s["focus_ipca_12m"])
    for r in runs:  # a expectativa mês a mês continua nas atualizações diárias
        jr = next((x for x in r["resultado"]["indicadores"] if x["id"] == "juro_real"), None)
        if jr and jr.get("inflacao_esperada") is not None and jr.get("focus_data"):
            foc[jr["focus_data"][:7]] = jr["inflacao_esperada"]

    def linha(nome, hoje, atencao, o_que, nota=""):
        return {"nome": nome, "hoje": hoje, "nota": nota, "atencao": atencao, "o_que": o_que,
                "leitura": "Atenção" if atencao else "Calmo"}

    def acima(x, v):
        return v > x["faixa_normal"][1] if x.get("faixa_normal") else False

    def alto(hist, v):
        return percentil(hist, v) > CORTE

    def mudou(v, unidade="ponto"):
        """A mudança no verbo: 'subiu 0,2 ponto', 'caiu 1,3 ponto'."""
        if round(v, 1) == 0:
            return "igual"
        u = unidade if round(abs(v), 1) < 2 else unidade + "s"
        return f"{'subiu' if v > 0 else 'caiu'} {num(abs(v))} {u}"

    g, r, f = [], [], []
    rumos = {}
    if "juro" in ent:
        x = ent["juro"]
        rumos["Selic"] = rumo(x["valor"])
        g.append(linha("Selic", f"{pct(x['nivel'])}%", acima(x, x["valor"]), "Selic subindo",
                       f"o juro básico; era {pct(x['antes'])}% um ano antes"))
    if "inflacao" in ent:
        x = ent["inflacao"]
        rumos["Inflação"] = rumo(x["valor"])
        g.append(linha("Inflação", f"{num(x['nivel'])}%", acima(x, x["valor"]), "inflação acelerando",
                       f"IPCA em 12 meses; era {num(x['antes'])}% um ano antes"))
    prim = {p["data"][:7]: p["valor"] for p in ((bruto or {}).get("series", {}).get("primario_12m", {}).get("dados") or [])}
    if prim:
        m = max(prim)
        antes = prim.get(num_mes(mes_num(m) - 12))
        if antes is not None:
            v, z = prim[m] - antes, prim[m]
            # + é déficit: subir é piorar
            r.append(linha("Contas do governo", f"déficit de {num(z)}% do PIB" if z > 0 else f"superávit de {num(-z)}% do PIB",
                           alto(var(s["primario_12m"], 12), v), "contas do governo piorando",
                           ("igual a um ano antes" if round(v, 1) == 0 else
                            f"{'piorou' if v > 0 else 'melhorou'} {num(abs(v))} ponto{'s' if round(abs(v), 1) >= 2 else ''} em 12 meses")
                           + "; sem contar juros da dívida"))
    jr = ind.get("juro_real") or {}
    if jr.get("inflacao_esperada") is not None:
        e, m = jr["inflacao_esperada"], (jr.get("focus_data") or jr["ref"])[:7]
        antes = foc.get(num_mes(mes_num(m) - 6))
        teto = cfg["meta_inflacao"] + cfg["tolerancia_meta"]
        if antes is not None:
            v = e - antes
            sobe = alto(var(foc, 6), v)
            o_que = ("inflação esperada acima do teto da meta" if round(e, 1) > teto else
                     "inflação esperada no teto da meta" if e > teto else "inflação esperada subindo")
            r.append(linha("Inflação esperada", f"{num(e)}%", sobe or e > teto, o_que,
                           f"o que bancos e empresas esperam em 12 meses; meta de {pct(cfg['meta_inflacao'])}%, "
                           f"teto de {pct(teto, 1)}%; {mudou(v)} em 6 meses"))
    if jr.get("valor") is not None:
        lo, hi = jr.get("faixa_normal") or (None, None)
        baixo = lo is not None and jr["valor"] < lo
        nota = ("Selic menos a inflação esperada; baixo: o Banco Central está atrás da inflação" if baixo else
                "Selic menos a inflação esperada; alto: freia a economia e deixa espaço para cortar" if hi is not None and jr["valor"] > hi else
                f"Selic menos a inflação esperada; normal no Brasil: de {num(lo)}% a {num(hi)}%" if lo is not None else "")
        r.append(linha("Juro descontado da inflação", f"{num(jr['valor'])}% ao ano", baixo, "juro baixo perto da inflação", nota))
    if (ind.get("divida") or {}).get("valor") is not None:
        x = ind["divida"]
        r.append(linha("Dívida pública", f"{num(x['nivel'])}% do PIB", acima(x, x["valor"]), "dívida subindo",
                       f"{mudou(x['valor'])} em 12 meses"))
    if (ind.get("comprometimento") or {}).get("nivel") is not None:
        x, hist = ind["comprometimento"], s["comprometimento_renda"]
        recorde = x["nivel"] >= max(hist.values())
        f.append(linha("Famílias endividadas", f"{num(x['nivel'])}% da renda", alto(hist, x["nivel"]), "famílias endividadas",
                       "vai para pagar dívidas" + (f"; o maior desde {min(hist)[:4]}" if recorde else "")))
    return {"grupos": [{"nome": "Gatilhos", "linhas": g},
                       {"nome": "O que pode fazer o juro subir", "linhas": r},
                       {"nome": "Fragilidade", "linhas": f}],
            "resumo": resumo(g, r, f, rumos)}


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " e " + xs[-1]


SELIC = {"subiu": "a Selic subiu", "caiu": "a Selic caiu", "ficou parado": "a Selic ficou parada"}
PRECOS = {"subiu": "os preços sobem mais rápido", "caiu": "os preços sobem mais devagar",
          "ficou parado": "os preços sobem no mesmo ritmo"}


def resumo(g: list[dict], r: list[dict], f: list[dict], rumos: dict[str, str]) -> list[str]:
    out = []
    ligados = [x["o_que"] for x in g if x["atencao"]]
    if ligados:
        out.append(f"Gatilho ligado: {_lista(ligados)}.")
    elif rumos:
        partes = ([SELIC[rumos["Selic"]]] if "Selic" in rumos else []) + ([PRECOS[rumos["Inflação"]]] if "Inflação" in rumos else [])
        out.append(f"Gatilhos calmos: em 12 meses, {', e '.join(partes)}.")
    pressao = [x["o_que"] for x in r if x["atencao"]]
    out.append(f"Pode puxar o juro para cima: {_lista(pressao)}." if pressao else "Nada empurra o juro para cima agora.")
    frag = [x["o_que"] for x in f if x["atencao"]]
    out.append(f"Fragilidade: {_lista(frag)}." if frag else "Sem fragilidade acima do normal.")
    return out


def carregar_config() -> dict:
    return json.loads(CONFIG.read_text())


def main() -> None:
    series = json.loads(HIST.read_text())["series"]
    cfg = carregar_config()
    b = aucs_brasil(series)
    print(f"Selic subiu 1 ponto ou mais nos 12 meses seguintes em {b['altas']} de {b['meses']} meses desde {INICIO_AUC}")
    for s in cfg["sinais"]:
        print(f"  {s['nome']:45s} 44 países {s.get('paises') or '—'}  Brasil {b['aucs'].get(s['id'])}")


if __name__ == "__main__":
    main()
