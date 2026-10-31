"""A direção do risco: as cinco pressões que costumam vir antes de uma recessão, cada uma contra 3 meses antes.

A regra (config/modelo.json, seção "direcao"; os cortes de cada pressão em config/calibracao.json):

1. Cinco pressões: contas do governo (dívida bruta; antes de 2007, o resultado sem juros), dívidas das
   famílias (parte da renda que vai para parcelas e juros), dólar e juro longo (contam como uma só),
   inflação esperada (Focus, 12 meses) e juro (Selic).
2. Cada uma é comparada com 3 meses antes. Apertou se andou para o lado ruim mais que três quartos do
   vaivém normal dela desde 2002 (1,4826 × desvio absoluto mediano das mudanças de 3 meses); folgou se
   andou isso para o lado bom; no resto, ficou igual.
3. A soma (as que apertaram menos as que folgaram) decide: 2 ou mais, subindo; −2 ou menos, caindo.
4. A direção só muda se o novo resultado se repetir no mês seguinte.
5. Se a prévia do PIB (IBC-Br, média de 3 meses contra os 3 anteriores) cair mais de 1,5%, o topo diz
   que a economia está encolhendo.

O ritmo da economia e o emprego aparecem, mas não entram na soma. Cada parte mostra também a folga: o
nível de hoje contra todos os meses desde o começo da série.

Nos meses passados, cada série entra com o atraso típico de divulgação (o mesmo do teste desde 2004).
No mês corrente, entra o último dado que já saiu, comparado com o de 3 meses antes dele.

Uso: python src/direcao.py --calibrar   (grava os cortes e o teste desde 2004 em config/calibracao.json)
     python src/direcao.py              (mostra a direção com o último registro de indicadores)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import indicadores  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
PIB = ROOT / "data" / "historico" / "pib.json"
MENSAL = ROOT / "data" / "historico" / "mensal.json"
CAL = ROOT / "config" / "calibracao.json"
CFG = ROOT / "config" / "modelo.json"

ESTADOS = {1: "subindo", 0: "igual", -1: "caindo", 2: "encolhendo"}
CODIGO = {"subindo": "S", "igual": "I", "caindo": "C", "encolhendo": "E"}

# Cada medida: a série, como se mede a mudança em 3 meses, o lado ruim (+1: subir é ruim) e o atraso de
# divulgação em meses, usado no teste e nos meses passados.
MEDIDAS = {
    "divida": {"serie": "divida_bruta", "como": "pontos", "ruim": 1, "atraso": 2},
    "primario": {"serie": "primario_12m", "como": "pontos", "ruim": 1, "atraso": 2},
    "parcelas": {"serie": "comprometimento_renda", "como": "pontos", "ruim": 1, "atraso": 3},
    "dolar": {"serie": "dolar_ptax", "como": "pct", "ruim": 1, "atraso": 0},
    "juro_longo": {"serie": "juro_real_longo", "como": "pontos", "ruim": 1, "atraso": 0},
    "inflacao": {"serie": "focus_ipca_12m", "como": "pontos", "ruim": 1, "atraso": 0},
    "juro": {"serie": "selic_meta", "como": "pontos", "ruim": 1, "atraso": 0},
    "ritmo": {"serie": "ibcbr", "como": "media", "ruim": -1, "atraso": 2},
    "emprego": {"serie": "desocupacao", "como": "pontos", "ruim": 1, "atraso": 1},
}
# As partes da página, na ordem do topo. As cinco primeiras entram na soma.
PARTES = ["contas", "parcelas", "mercado", "inflacao", "juro", "ritmo", "emprego"]
NA_SOMA = ["contas", "parcelas", "mercado", "inflacao", "juro"]
# A folga: a série cujo nível se compara com a história e o lado ruim. O juro usa o juro descontado da
# inflação esperada; o dólar não tem folga (o nível em reais não se compara entre décadas).
FOLGA = {"contas": ("divida_bruta", 1), "parcelas": ("comprometimento_renda", 1), "mercado": ("juro_real_longo", 1),
         "inflacao": ("focus_ipca_12m", 1), "juro": ("juro_real", 1), "emprego": ("desocupacao", 1)}


# ------------------------------------------------------------------ meses
def mnum(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def mstr(n: int) -> str:
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def mais(m: str, k: int) -> str:
    return mstr(mnum(m) + k)


# ------------------------------------------------------------------ séries
def _junta(destino: dict[str, tuple[str, float]], pontos: list[dict], dia_de=None) -> None:
    """Põe cada ponto no seu mês; vale o de dia mais recente (num dado mensal, a versão mais nova)."""
    for x in pontos:
        v = x.get("valor")
        if v is None:
            continue
        m = x["data"][:7]
        dia = (dia_de(x) if dia_de else None) or x.get("dia") or x["data"]
        if m not in destino or dia >= destino[m][0]:
            destino[m] = (dia, float(v))


def mensais(snap: dict | None = None, rodadas: list[dict] | None = None, hist: dict | None = None) -> dict[str, dict[str, tuple[str, float]]]:
    """As séries mês a mês, com o dia do dado: o histórico longo (data/historico/series.json), por cima o
    registro de indicadores do dia (que traz 4 anos de cada série e as revisões) e, para o Focus, que a
    coleta do dia traz só o último valor, o Focus guardado em cada rodada."""
    hist = hist if hist is not None else json.loads(HIST.read_text())["series"]
    out: dict[str, dict[str, tuple[str, float]]] = {}
    for m in MEDIDAS.values():
        k = m["serie"]
        d: dict[str, tuple[str, float]] = {}
        _junta(d, hist.get(k, []))
        if snap and k in snap.get("series", {}):
            _junta(d, snap["series"][k]["dados"])
        out[k] = d
    foc = out["focus_ipca_12m"]
    for r in rodadas or []:
        f = ((r.get("insumos") or {}).get("focus") or {}).get("IPCA 12m")
        if f and f.get("Mediana") is not None:
            _junta(foc, [{"data": f["Data"][:10], "valor": f["Mediana"]}])
    f = (snap or {}).get("focus", {}).get("IPCA 12m")
    if f and f.get("Mediana") is not None:
        _junta(foc, [{"data": f["Data"][:10], "valor": f["Mediana"]}])
    # Juro descontado da inflação esperada, mês a mês (só para a folga), com a mesma conta do resto do site.
    sel = out["selic_meta"]
    out["juro_real"] = {m: (max(sel[m][0], foc[m][0]), indicadores.juro_real(sel[m][1], foc[m][1])) for m in sel if m in foc}
    return out


def _valor(s: dict[str, tuple[str, float]], m: str) -> float | None:
    x = s.get(m)
    return x[1] if x else None


def mudanca(med: dict, s: dict[str, tuple[str, float]], ref: str, janela: int) -> float | None:
    """A mudança de uma medida entre o mês `ref` e `janela` meses antes, no lado do dado (positivo = subiu)."""
    if med["como"] == "media":
        a = [_valor(s, mais(ref, -i)) for i in range(janela)]
        b = [_valor(s, mais(ref, -janela - i)) for i in range(janela)]
        if None in a or None in b:
            return None
        return 100 * (sum(a) / sum(b) - 1)
    a, b = _valor(s, ref), _valor(s, mais(ref, -janela))
    if a is None or b is None:
        return None
    return 100 * (a / b - 1) if med["como"] == "pct" else a - b


def escala_robusta(xs: list[float]) -> float:
    """1,4826 × desvio absoluto mediano: o vaivém normal, sem deixar uma crise grande inflar a régua."""
    def mediana(v: list[float]) -> float:
        v = sorted(v)
        n = len(v)
        return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    med = mediana(xs)
    return 1.4826 * mediana([abs(x - med) for x in xs])


def lado(x: float | None, corte: float, ruim: int) -> int | None:
    """+1 apertou, −1 folgou, 0 igual (no lado ruim da medida)."""
    if x is None:
        return None
    x *= ruim
    return 1 if x > corte else -1 if x < -corte else 0


# ------------------------------------------------------------------ a regra
def referencias(series: dict, mes: str, ao_vivo: bool) -> dict[str, str | None]:
    """O mês de dado que cada medida usa no mês `mes`: com o atraso típico (meses passados) ou o último que
    saiu (mês corrente, ao vivo)."""
    out = {}
    for k, med in MEDIDAS.items():
        s = series[med["serie"]]
        if ao_vivo:
            ms = [m for m in s if m <= mes]
            out[k] = max(ms) if ms else None
        else:
            out[k] = mais(mes, -med["atraso"])
    return out


def mes_da_regra(series: dict, mes: str, cortes: dict, p: dict, ao_vivo: bool = False) -> dict:
    """As medidas, os lados de cada parte e a soma num mês."""
    j = p["janela_meses"]
    refs = referencias(series, mes, ao_vivo)
    mud = {k: mudanca(MEDIDAS[k], series[MEDIDAS[k]["serie"]], refs[k], j) if refs[k] else None for k in MEDIDAS}
    lados = {k: lado(mud[k], p["corte_vaivem"] * cortes[k], MEDIDAS[k]["ruim"]) for k in MEDIDAS}
    partes = {
        # Antes de 2007 não há série da dívida: vale o resultado sem juros.
        "contas": lados["divida"] if lados["divida"] is not None else lado(mud["primario"], p["corte_vaivem"] * cortes["divida"], 1),
        "parcelas": lados["parcelas"],
        "mercado": (None if lados["dolar"] is None else
                    lados["dolar"] if lados["juro_longo"] is None else
                    (lados["dolar"] + lados["juro_longo"] > 0) - (lados["dolar"] + lados["juro_longo"] < 0)),
        "inflacao": lados["inflacao"], "juro": lados["juro"], "ritmo": lados["ritmo"], "emprego": lados["emprego"],
    }
    soma_vals = [partes[k] for k in NA_SOMA if partes[k] is not None]
    soma = sum(soma_vals) if soma_vals else None
    bruto = 0 if soma is None else 1 if soma >= p["corte_soma"] else -1 if soma <= -p["corte_soma"] else 0
    return {"mes": mes, "refs": refs, "mudancas": mud, "lados": lados, "partes": partes, "soma": soma, "bruto": bruto,
            "encolhe": mud["ritmo"] is not None and mud["ritmo"] < -p["encolhe_pct"]}


def linha_do_tempo(series: dict, ate: str, cortes: dict, p: dict, ao_vivo_no_fim: bool = True) -> list[dict]:
    """O estado mês a mês desde o começo da amostra, com a confirmação de um mês e o 'encolhendo' por cima."""
    meses = [mstr(n) for n in range(mnum(p["amostra_inicio"]), mnum(ate) + 1)]
    out = []
    atual = cand = None
    n = 0
    for m in meses:
        x = mes_da_regra(series, m, cortes, p, ao_vivo=ao_vivo_no_fim and m == ate)
        c = x["bruto"]
        if atual is None:
            atual = c
        elif c != atual:
            if c == cand:
                n += 1
            else:
                cand, n = c, 1
            if n >= p["confirma_meses"]:
                atual, cand, n = c, None, 0
        else:
            cand, n = None, 0
        estado = 2 if x["encolhe"] else atual
        out.append({**x, "estado": estado, "pendente": c if (c != atual and not x["encolhe"]) else None})
    return out


def _folga(series: dict, k: str, ref_mes: str | None) -> dict | None:
    if k not in FOLGA or not ref_mes:
        return None
    nome, ruim = FOLGA[k]
    s = series[nome]
    if ref_mes not in s:
        ms = [m for m in s if m <= ref_mes]
        if not ms:
            return None
        ref_mes = max(ms)
    v = s[ref_mes][1]
    hist = [x[1] for m, x in s.items() if m <= ref_mes]
    melhores = sum(1 for h in hist if (h - v) * ruim < 0)
    return {"serie": nome, "valor": v, "ref": ref_mes, "desde": min(s)[:4], "meses": len(hist),
            "pior_que_pct": round(100 * melhores / len(hist)),
            "recorde_ruim": all((h - v) * ruim <= 0 for h in hist),
            "recorde_bom": all((h - v) * ruim >= 0 for h in hist)}


def calcular(snap: dict, cfg: dict, cal: dict, rodadas: list[dict] | None = None, hoje: dt.date | None = None) -> dict:
    """A direção de hoje, cada parte com o dado de agora e o de 3 meses antes, a folga e a linha do tempo."""
    hoje = hoje or dt.date.today()
    p, cortes = cfg["direcao"], cal["direcao"]["cortes"]
    series = mensais(snap, rodadas)
    mes = hoje.isoformat()[:7]
    linha = linha_do_tempo(series, mes, cortes, p)
    agora = linha[-1]
    j = p["janela_meses"]
    estado = agora["estado"]
    k = len(linha) - 1
    while k > 0 and linha[k - 1]["estado"] == estado:
        k -= 1
    medidas = {}
    for m, med in MEDIDAS.items():
        s = series[med["serie"]]
        ref = agora["refs"][m]
        if not ref:
            continue
        a, b = s.get(ref), s.get(mais(ref, -j))
        medidas[m] = {"agora": a[1] if a else None, "dia": a[0] if a else None, "ref": ref,
                      "antes": b[1] if b else None, "dia_antes": b[0] if b else None, "ref_antes": mais(ref, -j),
                      "mudanca": agora["mudancas"][m], "corte": p["corte_vaivem"] * cortes[m],
                      "lado": agora["lados"][m], "como": med["como"]}
    partes = []
    for nome in PARTES:
        quais = {"contas": ["divida", "primario"], "parcelas": ["parcelas"], "mercado": ["dolar", "juro_longo"],
                 "inflacao": ["inflacao"], "juro": ["juro"], "ritmo": ["ritmo"], "emprego": ["emprego"]}[nome]
        ref_folga = medidas.get(quais[0], {}).get("ref")
        if nome == "juro":
            ref_folga = min(medidas.get("juro", {}).get("ref") or "0000", medidas.get("inflacao", {}).get("ref") or "0000")
        partes.append({"id": nome, "lado": agora["partes"][nome], "na_soma": nome in NA_SOMA,
                       "medidas": {q: medidas[q] for q in quais if q in medidas},
                       "folga": _folga(series, nome, ref_folga if ref_folga != "0000" else None)})
    return {
        "estado": ESTADOS[estado] if estado is not None else None, "desde": linha[k]["mes"],
        "soma": agora["soma"], "bruto": ESTADOS[agora["bruto"]] if agora["bruto"] is not None else None,
        "pendente": ESTADOS[agora["pendente"]] if agora["pendente"] is not None else None,
        "apertaram": sum(1 for x in partes if x["na_soma"] and x["lado"] == 1),
        "folgaram": sum(1 for x in partes if x["na_soma"] and x["lado"] == -1),
        "partes": partes, "mes": mes,
        "linha": [{"mes": x["mes"], "estado": CODIGO[ESTADOS[x["estado"]]]} for x in linha
                  if x["estado"] is not None and x["mes"] >= p["teste_inicio"]],
    }


# ------------------------------------------------------------------ calibração e teste
def _pib_frente() -> dict[str, float]:
    """PIB nos 4 trimestres depois do trimestre de cada mês, em %."""
    q = {}
    for x in json.loads(PIB.read_text())["pib"]:
        t, a = int(x["trimestre"][0]), int(x["trimestre"][2:])
        q[a * 4 + t - 1] = x["var_qoq"]
    out = {}
    for n in range(mnum("2002-01"), mnum("2027-01")):
        tq = (n // 12) * 4 + (n % 12) // 3
        vals = [q.get(tq + i) for i in range(1, 5)]
        if None not in vals:
            prod = 1.0
            for v in vals:
                prod *= 1 + v / 100
            out[mstr(n)] = 100 * (prod - 1)
    return out


def calibrar(ate: str) -> dict:
    """Os cortes de cada medida (vaivém normal desde 2002) e o teste da regra desde 2004, até o mês `ate`."""
    cfg = json.loads(CFG.read_text())
    p = cfg["direcao"]
    series = mensais()
    j = p["janela_meses"]
    meses = [mstr(n) for n in range(mnum(p["amostra_inicio"]), mnum(ate) + 1)]
    cortes = {}
    for k, med in MEDIDAS.items():
        s = series[med["serie"]]
        xs = [mudanca(med, s, mais(m, -med["atraso"]), j) for m in meses]
        cortes[k] = [x for x in xs if x is not None]
    # Contas: dívida onde há, resultado sem juros antes (como no teste).
    div = {m: mudanca(MEDIDAS["divida"], series["divida_bruta"], mais(m, -2), j) for m in meses}
    pri = {m: mudanca(MEDIDAS["primario"], series["primario_12m"], mais(m, -2), j) for m in meses}
    contas = [div[m] if div[m] is not None else pri[m] for m in meses if div[m] is not None or pri[m] is not None]
    escalas = {k: escala_robusta(v) for k, v in cortes.items()}
    escalas["divida"] = escala_robusta(contas)
    linha = linha_do_tempo(series, ate, escalas, p, ao_vivo_no_fim=False)
    pib = _pib_frente()
    ra = {k: v for k, v in json.loads(MENSAL.read_text())["recessao_a_frente"].items() if v is not None}
    teste = [x for x in linha if x["mes"] >= p["teste_inicio"]]
    n = len(teste)

    def media(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 3) if xs else None  # 3 casas: o site arredonda para 1 sem erro de meio

    def parte(e: int) -> float:
        return round(sum(1 for x in teste if x["estado"] == e) / n, 3)

    trocas = sum(1 for a, b in zip(teste, teste[1:]) if a["estado"] != b["estado"])
    rec_ini = {"2008": "2008-10", "2014": "2014-04", "2020": "2020-01"}
    blocos = []
    for x in teste:
        c = CODIGO[ESTADOS[x["estado"]]]
        if blocos and blocos[-1]["estado"] == c:
            blocos[-1]["fim"] = x["mes"]
        else:
            blocos.append({"inicio": x["mes"], "fim": x["mes"], "estado": c})
    return {
        "cortes": {k: round(v, 4) for k, v in escalas.items()},
        "o_que_e": "Escala de cada medida: 1,4826 × desvio absoluto mediano das mudanças de 3 meses desde 2002, com o atraso de divulgação de cada série. A pressão aperta ou folga quando a mudança passa de corte_vaivem (config/modelo.json) vezes essa escala, o que a página chama de vaivém normal. Em 'divida', a régua das contas: dívida bruta desde 2007, resultado sem juros antes.",
        "teste": {
            "de": teste[0]["mes"], "ate": teste[-1]["mes"], "meses": n,
            "parte_dos_meses": {ESTADOS[e]: parte(e) for e in (1, 0, -1, 2)},
            "trocas_por_ano": round(trocas / (n / 12), 2),
            "pib_12m_depois": {ESTADOS[e]: media([pib[x["mes"]] for x in teste if x["estado"] == e and x["mes"] in pib]) for e in (1, 0, -1)},
            "recessao_a_frente": {ESTADOS[e]: media([ra[x["mes"]] for x in teste if x["estado"] == e and x["mes"] in ra]) for e in (1, 0, -1)},
            "subindo_antes_das_recessoes": {a: sum(1 for x in teste if mais(i, -12) <= x["mes"] < i and x["estado"] == 1)
                                           for a, i in rec_ini.items()},
            "blocos": blocos,
        },
    }


def main() -> None:
    if "--calibrar" in sys.argv:
        ate = sys.argv[sys.argv.index("--calibrar") + 1] if len(sys.argv) > sys.argv.index("--calibrar") + 1 else dt.date.today().isoformat()[:7]
        cal = json.loads(CAL.read_text())
        cal["direcao"] = calibrar(ate)
        CAL.write_text(json.dumps(cal, ensure_ascii=False, indent=1) + "\n")
        t = cal["direcao"]["teste"]
        print(json.dumps({k: v for k, v in t.items() if k != "blocos"}, ensure_ascii=False, indent=1))
        print("cortes:", cal["direcao"]["cortes"])
        return
    cfg, cal = json.loads(CFG.read_text()), json.loads(CAL.read_text())
    brutos = sorted((ROOT / "data" / "raw").glob("*/indicadores.json"))
    snap = json.loads(brutos[-1].read_text()) if brutos else None
    rodadas = [json.loads(x.read_text()) for x in sorted((ROOT / "runs").glob("*.json"))]
    hoje = dt.date.fromisoformat(brutos[-1].parent.name) if brutos else dt.date.today()
    d = calcular(snap, cfg, cal, rodadas, hoje)
    print(d["estado"], "desde", d["desde"], "| soma", d["soma"], "| pendente", d["pendente"])
    for x in d["partes"]:
        print(f"  {x['id']:9s} lado {x['lado']}  " + "; ".join(
            f"{k}: {m['antes']} ({m['ref_antes']}) -> {m['agora']} ({m['ref']}) mud {m['mudanca']:+.2f} corte {m['corte']:.2f}"
            for k, m in x["medidas"].items() if m["mudanca"] is not None) + (f" | folga {x['folga']['pior_que_pct']}%" if x["folga"] else ""))


if __name__ == "__main__":
    main()
