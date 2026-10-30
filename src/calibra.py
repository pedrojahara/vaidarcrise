"""Calibração do nível: o cenário ruim do PIB (crescimento em risco), os cortes dos níveis e a validação.

Segue as regras de config/modelo.json. Lê o painel de países em data/historico/painel_ocde.csv
e as séries do Brasil em data/historico/series.json (src/historico.py), e grava:
- config/calibracao.json: o que a conta do dia usa (coeficientes, cortes, faixas normais);
- data/historico/mensal.json: os indicadores e as entradas do Brasil mês a mês, como eram
  conhecidos em cada mês, o alvo e o nível fora da amostra, para quem quiser refazer a conta.

Precisa de pandas e statsmodels, que a atualização diária não usa: pip install pandas statsmodels.
Uso: python src/calibra.py
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from statistics import pstdev

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gar  # noqa: E402
import indicadores as ind  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
SAIDA = ROOT / "config" / "calibracao.json"
MENSAL = ROOT / "data" / "historico" / "mensal.json"
PAINEL = ROOT / "data" / "historico" / "painel_ocde.csv"


def carregar_config() -> dict:
    return json.loads((ROOT / "config" / "modelo.json").read_text())


# ------------------------------------------------------------------- meses
def mes_num(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def num_mes(n: int) -> str:
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def fim_do_mes(m: str) -> str:
    n = mes_num(m) + 1
    return (dt.date(n // 12, n % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()


# ------------------------------------------------------------- trimestres
def tri_num(t: str) -> int:
    """'3T2026' -> número sequencial do trimestre."""
    q, a = t.split("T")
    return int(a) * 4 + int(q) - 1


def num_tri(n: int) -> str:
    return f"{n % 4 + 1}T{n // 4}"


def primeiro_nao_divulgado(m: str) -> int:
    """O trimestre que termina no mês e conta como divulgado no fim do mês e+3 (o IBGE leva uns 60 dias)."""
    n = mes_num(m)
    # O último trimestre divulgado é o último cujo mês final e satisfaz e + 3 <= n.
    e = n - 3
    ultimo = (e // 12) * 4 + (e % 12 + 1) // 3 - 1  # trimestres completos até o mês e
    return ultimo + 1


def episodios(pib: dict[str, float], juntar: bool) -> list[tuple[int, int]]:
    """Recessões técnicas: 2 ou mais trimestres seguidos de queda; quedas separadas por um só trimestre
    sem queda viram um episódio só."""
    tris = sorted(tri_num(t) for t in pib)
    neg = {t for t in tris if pib[num_tri(t)] < 0}
    corridas, i = [], 0
    while i < len(tris):
        t = tris[i]
        if t in neg:
            j = t
            while j + 1 in neg:
                j += 1
            if j > t:
                corridas.append([t, j])
            i = tris.index(j) + 1
        else:
            i += 1
    if juntar:
        juntas: list[list[int]] = []
        for c in corridas:
            if juntas and c[0] - juntas[-1][1] == 2:
                juntas[-1][1] = c[1]
            else:
                juntas.append(c)
        corridas = juntas
    return [tuple(c) for c in corridas]


def alvo(m: str, eps: list[tuple[int, int]], ultimo_pib: int, h: int) -> int | None:
    """1 se uma recessão começa no horizonte do mês, 0 se não, None se fora da amostra ou ainda sem resposta."""
    fu = primeiro_nao_divulgado(m)
    for ini, fim in eps:
        if ini < fu <= fim:
            return None
    if any(fu <= ini < fu + h for ini, _ in eps):
        return 1
    # Para saber que nenhuma começou, o trimestre seguinte ao último do horizonte precisa ter saído.
    return 0 if fu + h <= ultimo_pib else None


# ---------------------------------------------------------- indicadores
def cortar(serie: list[dict], ate: str) -> list[dict]:
    return [x for x in serie if x["data"] <= ate]


def mensal(series: dict, cfg: dict, inicio: str, fim: str) -> dict[str, dict[str, float]]:
    """Cada indicador mês a mês, com o que já tinha sido divulgado no fim de cada mês."""
    defas = {k: v["defasagem_meses"] for k, v in cfg["indicadores"].items()}
    focus_ipca = {x["data"][:7]: x for x in series.get("focus_ipca_12m", [])}
    focus_pib = {x["data"][:7]: x for x in series.get("focus_pib", [])}
    selic = {x["data"][:7]: x for x in series.get("selic_meta", [])}
    tesouro = series.get("juro_real_longo", [])
    out: dict[str, dict[str, float]] = {k: {} for k in cfg["indicadores"]}
    for n in range(mes_num(inicio), mes_num(fim) + 1):
        m = num_mes(n)

        def ate(k: str) -> str:
            return num_mes(n - defas[k]) + "-31"

        v = {
            "ibcbr": ind.ibcbr(cortar(series.get("ibcbr", []), ate("ibcbr"))),
            "comprometimento": ind.comprometimento(cortar(series.get("comprometimento_renda", []), ate("comprometimento"))),
            "divida": ind.divida(cortar(series.get("divida_bruta", []), ate("divida"))),
            "sahm": ind.sahm(cortar(series.get("desocupacao", []), ate("sahm"))),
            "commodities": ind.commodities(cortar(series.get("commodities", []), ate("commodities"))),
            "dolar": ind.dolar(cortar(series.get("dolar_ptax", []), m + "-31")),
        }
        t = ind.tesouro(cortar(tesouro, fim_do_mes(m)))
        v["tesouro"] = t[0] if t else None
        if m in focus_pib:
            f = focus_pib[m]
            v["focus_pib"] = ind.focus_pib(f["ano"], f["ano_seguinte"], f["dia"])
        if m in selic and m in focus_ipca:
            v["juro_real"] = ind.juro_real(selic[m]["valor"], focus_ipca[m]["valor"])
        for k, x in v.items():
            if x is not None:
                out[k][m] = x
    return out


# ------------------------------------------------------------- estatística
def percentil(xs: list[float], p: float) -> float:
    """Interpolação linear, como o padrão do numpy."""
    s = sorted(xs)
    if not s:
        raise ValueError("sem dados")
    pos = (len(s) - 1) * p / 100
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def auc(pontos: list[tuple[float, int]]) -> float | None:
    """Chance de um mês com recessão à frente ter nota maior que um mês sem (empate vale meio)."""
    pos = [x for x, y in pontos if y == 1]
    neg = [x for x, y in pontos if y == 0]
    if not pos or not neg:
        return None
    ganha = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return ganha / (len(pos) * len(neg))


def nivel_de(g: float, cortes: list[float]) -> int:
    """Índice do nível (0 = Muito abaixo, 4 = Muito acima): quanto pior o cenário ruim, mais alto."""
    return sum(1 for c in cortes if g <= c)


# ------------------------------------------------------- crescimento em risco
def entradas_brasil(series: dict, pib: list[tuple[int, float]], m: str, defas: dict) -> dict[str, float] | None:
    """As quatro entradas do Brasil com o que já tinha sido divulgado no fim do mês m."""
    n = mes_num(m)

    def ate(k: str) -> str:
        return num_mes(n - defas[k]) + "-31"

    selic = {x["data"][:7]: x["valor"] for x in series.get("selic_meta", [])}
    fu = primeiro_nao_divulgado(m)
    e = {
        "tendencia": gar.tendencia([(t, v) for t, v in pib if t < fu]),
        "crescimento": gar.crescimento(cortar(series.get("ibcbr", []), ate("crescimento"))),
        "juro": selic[m] - selic[num_mes(n - 12)] if m in selic and num_mes(n - 12) in selic else None,
        "inflacao": gar.variacao_mensal(cortar(series.get("ipca_12m", []), ate("inflacao"))),
    }
    return None if any(v is None for v in e.values()) else e


def realizado(pib: dict[int, float], m: str) -> float | None:
    """O crescimento que de fato veio nos 4 trimestres a partir do primeiro não divulgado no mês m."""
    fu = primeiro_nao_divulgado(m)
    if not all(t in pib for t in range(fu, fu + 4)):
        return None
    return sum(100 * math.log(1 + pib[t] / 100) for t in range(fu, fu + 4))


def calibrar_gar(cfg: dict, series: dict, pib: dict[int, float], y: dict, meses: list[str]) -> tuple[dict, dict]:
    """Estima o cenário ruim (quantil 10%) no painel, valida fora da amostra e monta o histórico do Brasil.
    Devolve (bloco 'gar' da calibração, histórico mês a mês)."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm

    g = cfg["gar"]
    col = [gar.NO_PAINEL[k] for k in gar.ENTRADAS]
    painel = pd.read_csv(PAINEL)
    painel["t"] = painel.q.map(lambda q: int(q[:4]) * 4 + int(q[-1]) - 1)
    treino_total = painel.dropna(subset=["y4"])

    def ajustar(df: pd.DataFrame, tau: float) -> dict[str, float]:
        r = sm.QuantReg(df.y4, sm.add_constant(df[col])).fit(q=tau, max_iter=5000).params
        return {"const": float(r["const"]), **{k: float(r[gar.NO_PAINEL[k]]) for k in gar.ENTRADAS}}

    def prever(df: pd.DataFrame, c: dict) -> np.ndarray:
        return c["const"] + sum(c[k] * df[gar.NO_PAINEL[k]].to_numpy() for k in gar.ENTRADAS)

    tau = g["quantil"]
    q10 = ajustar(treino_total, tau)

    # Fora da amostra no painel: cada ano é previsto só com os trimestres cujo PIB 4 trimestres à frente
    # já tinha saído no começo daquele ano. Mede o ganho sobre a conta só com a média do país e a cobertura.
    def pinball(u: np.ndarray) -> float:
        return float(np.mean(np.maximum(tau * u, (tau - 1) * u)))

    oos, oos0, coef_ano, coef_ano0, coef_bolsa = [], [], {}, {}, {}
    com_bolsa = treino_total.dropna(subset=["acoes_4t"])
    for ano in range(g["validacao_desde"], int(meses[-1][:4]) + 1):
        corte = (ano - 2) * 4 + 3  # até o 3º trimestre de dois anos antes
        tr = treino_total[treino_total.t < corte]
        c = ajustar(tr, tau)
        c0 = sm.QuantReg(tr.y4, sm.add_constant(tr[["media_pais"]])).fit(q=tau, max_iter=5000).params
        coef_ano[ano], coef_ano0[ano] = c, c0
        r5 = com_bolsa[com_bolsa.t < corte]
        coef_bolsa[ano] = sm.QuantReg(r5.y4, sm.add_constant(r5[col + ["acoes_4t"]])).fit(q=tau, max_iter=5000).params
        te = treino_total[(treino_total.t >= ano * 4) & (treino_total.t < ano * 4 + 4)]
        if len(te):
            oos.append(te.y4.to_numpy() - prever(te, c))
            oos0.append(te.y4.to_numpy() - (c0["const"] + c0["media_pais"] * te.media_pais.to_numpy()))
    u, u0 = np.concatenate(oos), np.concatenate(oos0)
    ajuste = float(np.quantile(u, tau))

    # Candidatas a quinta entrada: cada uma somada às quatro, com a mesma validação, na amostra em que
    # ela existe. O número é quanto o erro fora da amostra cai (positivo) ou sobe (negativo).
    def erro_fora(df: pd.DataFrame, xs: list[str]) -> float:
        us = []
        for ano in range(g["validacao_desde"], int(meses[-1][:4]) + 1):
            tr = df[df.t < (ano - 2) * 4 + 3]
            te = df[(df.t >= ano * 4) & (df.t < ano * 4 + 4)]
            if len(te) and len(tr) > 200:
                r = sm.QuantReg(tr.y4, sm.add_constant(tr[xs])).fit(q=tau, max_iter=5000).params
                us.append(te.y4.to_numpy() - (r["const"] + te[xs].to_numpy() @ r[xs].to_numpy()))
        return pinball(np.concatenate(us))

    candidatas = {}
    for nome, coluna in g["candidatas"].items():
        df = treino_total.dropna(subset=[coluna])
        candidatas[nome] = round(1 - erro_fora(df, col + [coluna]) / erro_fora(df, col), 4)

    # O Brasil mês a mês: entradas, cenário ruim com os coeficientes finais e fora da amostra.
    defas = g["defasagem_meses"]
    pib_lista = sorted(pib.items())
    hist, fora = {}, {}
    for m in meses:
        e = entradas_brasil(series, pib_lista, m, defas)
        if e is None:
            continue
        hist[m] = {"entradas": e, "ruim": gar.cenario(e, q10), "realizado": realizado(pib, m),
                   "recessao_a_frente": y.get(m)}
        a = int(m[:4])
        if a in coef_ano:
            fora[m] = gar.cenario(e, coef_ano[a])
    ruins = [h["ruim"] for h in hist.values()]
    cortes = [percentil(ruins, p) for p in g["percentis_dos_cortes"]]
    normal = percentil(ruins, 50)
    referencia = {k: percentil([h["entradas"][k] for h in hist.values()], 50) for k in gar.ENTRADAS}
    faixas = {}
    for k in gar.ENTRADAS:
        vals = [h["entradas"][k] for h in hist.values()]
        faixas[k] = {"faixa_normal": [round(percentil(vals, p), 4) for p in cfg["faixa_normal_percentis"]],
                     "escala": [round(percentil(vals, 2), 4), round(percentil(vals, 98), 4)]}

    # No Brasil, fora da amostra: a conta contra só a média do país, e com a bolsa como quinta entrada
    # (retorno real do Ibovespa em 12 meses: média dos 3 últimos meses, menos o IPCA de 12 meses).
    ibov = {x["data"][:7]: x["valor"] for x in series.get("ibovespa", [])}
    ipca = {x["data"][:7]: x["valor"] for x in series.get("ipca_12m", [])}

    def bolsa(m: str) -> float | None:
        n = mes_num(m)
        meses_ = [(num_mes(n - k), num_mes(n - k - 12)) for k in range(3)]
        if not all(a in ibov and b in ibov for a, b in meses_) or num_mes(n - 1) not in ipca:
            return None
        return sum(100 * (ibov[a] / ibov[b] - 1) for a, b in meses_) / 3 - ipca[num_mes(n - 1)]

    b4, b0, b5 = [], [], []
    for m, v in fora.items():
        r, a, h = hist[m]["realizado"], int(m[:4]), hist[m]["entradas"]
        b = bolsa(m)
        if r is None or b is None:
            continue
        c0, c5 = coef_ano0[a], coef_bolsa[a]
        b4.append(r - v)
        b0.append(r - (c0["const"] + c0["media_pais"] * h["tendencia"]))
        b5.append(r - (c5["const"] + sum(c5[gar.NO_PAINEL[k]] * h[k] for k in gar.ENTRADAS) + c5["acoes_4t"] * b))
    b4, b0, b5 = np.array(b4), np.array(b0), np.array(b5)

    # O nível fora da amostra: o cenário ruim de cada mês com coeficientes que não viram o ano dele,
    # nos cortes da própria série fora da amostra.
    vals = list(fora.values())
    cortes_fora = [percentil(vals, p) for p in g["percentis_dos_cortes"]]
    nivel_fora = {m: nivel_de(v, cortes_fora) for m, v in fora.items()}
    com_y = [(m, hist[m]["recessao_a_frente"]) for m in fora if hist[m]["recessao_a_frente"] is not None]
    cobertos = [(fora[m], hist[m]["realizado"]) for m in fora if hist[m]["realizado"] is not None]
    altos = [hist[m]["realizado"] for m in fora if nivel_fora[m] >= 3 and hist[m]["realizado"] is not None]
    outros = [hist[m]["realizado"] for m in fora if nivel_fora[m] < 3 and hist[m]["realizado"] is not None]
    rec_altos = [y for m, y in com_y if nivel_fora[m] >= 3]
    rec_outros = [y for m, y in com_y if nivel_fora[m] < 3]
    validacao = {
        "painel_ganho_sobre_a_media_do_pais": round(1 - pinball(u) / pinball(u0), 4),
        "painel_cobertura_fora_da_amostra": round(float(np.mean(u < 0)), 4),
        "painel_trimestres_fora_da_amostra": int(len(u)),
        "candidatas_ganho_fora_da_amostra": candidatas,
        "brasil_ganho_sobre_a_media_do_pais": round(1 - pinball(b4) / pinball(b0), 4),
        "brasil_bolsa_ganho_fora_da_amostra": round(1 - pinball(b5) / pinball(b4), 4),
        "brasil_meses_fora_da_amostra": len(fora),
        "brasil_auc_recessao_a_frente": round(auc([(-fora[m], yy) for m, yy in com_y]), 4),
        "brasil_auc_nivel": round(auc([(nivel_fora[m], yy) for m, yy in com_y]), 4),
        "brasil_meses_com_resposta": len(com_y),
        "brasil_cobertura_sem_ajuste": round(sum(r < v for v, r in cobertos) / len(cobertos), 4),
        "brasil_cobertura_com_ajuste": round(sum(r < v + ajuste for v, r in cobertos) / len(cobertos), 4),
        "brasil_meses_com_pib_realizado": len(cobertos),
        "acima_crescimento_medio_seguinte": round(gar.pct(sum(altos) / len(altos)), 2) if altos else None,
        "demais_crescimento_medio_seguinte": round(gar.pct(sum(outros) / len(outros)), 2) if outros else None,
        "acima_meses_com_recessao_a_frente": round(sum(rec_altos) / len(rec_altos), 4) if rec_altos else None,
        "demais_meses_com_recessao_a_frente": round(sum(rec_outros) / len(rec_outros), 4) if rec_outros else None,
        "acima_pior_crescimento_seguinte": round(gar.pct(min(altos)), 2) if altos else None,
        "demais_pior_crescimento_seguinte": round(gar.pct(min(outros)), 2) if outros else None,
    }
    bloco = {
        "painel": {"paises": int(painel.pais.nunique()), "trimestres": int(len(treino_total)),
                   "inicio": str(treino_total.q.min()), "fim": str(treino_total.q.max())},
        "coeficientes": q10, "ajuste": ajuste,
        "referencia": referencia, "faixas": faixas, "cortes": cortes, "normal": normal,
        "historico": {"inicio": min(hist), "fim": max(hist), "meses": len(hist)},
        "validacao": validacao,
    }
    mensal_gar = {m: {"ruim": round(h["ruim"], 3),
                      "fora_da_amostra": round(fora[m], 3) if m in fora else None,
                      "nivel_fora_da_amostra": nivel_fora.get(m),
                      **{k: round(v, 3) for k, v in h["entradas"].items()}} for m, h in hist.items()}
    return bloco, mensal_gar


def main() -> None:
    cfg = carregar_config()
    hist = json.loads(HIST.read_text())
    series = hist["series"]
    # O IBGE recusa conexões de fora do Brasil: sem o PIB no arquivo, vale a cópia em data/historico/pib.json.
    pib_lista = series.get("pib") or json.loads((ROOT / "data" / "historico" / "pib.json").read_text())["pib"]
    pib = {x["trimestre"]: x["var_qoq"] for x in pib_lista}
    eps = episodios(pib, cfg["recessao"]["juntar_quedas_separadas_por_um_trimestre"])
    ultimo_pib = max(tri_num(t) for t in pib)
    h = cfg["recessao"]["horizonte_trimestres"]
    inicio = cfg["amostra_inicio"]
    hoje = dt.date.today()
    fim_dados = num_mes(hoje.year * 12 + hoje.month - 1)
    xs = mensal(series, cfg, inicio, fim_dados)
    todos_meses = [num_mes(n) for n in range(mes_num(inicio), mes_num(fim_dados) + 1)]
    y = {m: alvo(m, eps, ultimo_pib, h) for m in todos_meses}
    amostra = [m for m in todos_meses if y[m] is not None]

    # Os indicadores do Resumo: faixa normal (metade dos meses desde 2002) e a régua de cada um.
    indicadores = {}
    for k, s in xs.items():
        vals = [s[m] for m in sorted(s)]
        if not vals:
            indicadores[k] = {"meses": 0}
            continue
        indicadores[k] = {"meses": len(vals), "amostra": [min(s), max(s)],
                          "faixa_normal": [round(percentil(vals, p), 6) for p in cfg["faixa_normal_percentis"]],
                          "escala": [round(percentil(vals, 2), 6), round(percentil(vals, 98), 6)]}

    bloco_gar, mensal_gar = calibrar_gar(cfg, series, {tri_num(t): v for t, v in pib.items()}, y, todos_meses)

    # Desvio das variações de 6 meses de cada medida do placar: a tolerância de "estável".
    def nivel_mensal(nome: str) -> dict[str, float]:
        if nome == "ibcbr_3m":
            return xs["ibcbr"]
        if nome == "juro_real":
            return xs["juro_real"]
        fonte = {"comprometimento_nivel": "comprometimento_renda", "divida_nivel": "divida_bruta",
                 "desocupacao": "desocupacao", "commodities_nivel": "commodities"}.get(nome)
        if fonte:
            return {x["data"][:7]: x["valor"] for x in series.get(fonte, [])}
        if nome == "tesouro_nivel":
            out = {}
            for x in series.get("juro_real_longo", []):
                out[x["data"][:7]] = x["valor"]
            return out
        return {}

    placar = {}
    for fator, med in cfg["placar"]["medidas"].items():
        s = nivel_mensal(med["serie"])
        ms = sorted(s)
        if med["serie"] == "commodities_nivel":
            dif = [100 * (s[m] / s[num_mes(mes_num(m) - 6)] - 1) for m in ms if num_mes(mes_num(m) - 6) in s]
        else:
            dif = [s[m] - s[num_mes(mes_num(m) - 6)] for m in ms if num_mes(mes_num(m) - 6) in s]
        placar[fator] = {"desvio_6m": pstdev(dif) if len(dif) > 2 else None,
                         "tolerancia": cfg["placar"]["tolerancia_desvios"] * pstdev(dif) if len(dif) > 2 else None}

    res = {
        "calibrado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dados_de": hist["coletado_em"],
        "recessoes": [{"inicio": num_tri(a), "fim": num_tri(b)} for a, b in eps],
        "amostra": {"inicio": amostra[0], "fim": amostra[-1], "meses": len(amostra),
                    "meses_com_recessao_a_frente": sum(y[m] for m in amostra)},
        "gar": bloco_gar,
        "indicadores": indicadores,
        "placar": placar,
    }
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    historico = [{"mes": m, "nivel": v["nivel_fora_da_amostra"], "recessao_a_frente": y.get(m)}
                 for m, v in sorted(mensal_gar.items()) if v["nivel_fora_da_amostra"] is not None]
    MENSAL.write_text(json.dumps({
        "gerado_em": res["calibrado_em"],
        "indicadores": {k: {m: round(v, 4) for m, v in sorted(s.items())} for k, s in xs.items()},
        "recessao_a_frente": {m: y[m] for m in todos_meses if y[m] is not None},
        "crescimento_em_risco": mensal_gar,
        "nivel_fora_da_amostra": historico,
    }, ensure_ascii=False, separators=(",", ":")))

    gb = bloco_gar
    print(f"recessões: {', '.join(f'{num_tri(a)}–{num_tri(b)}' for a, b in eps)}")
    print(f"painel: {gb['painel']} | q10 {({k: round(v, 4) for k, v in gb['coeficientes'].items()})} | ajuste {gb['ajuste']:.3f}")
    print(f"Brasil {gb['historico']} | cortes {[round(c, 3) for c in gb['cortes']]} | normal {gb['normal']:.3f}")
    print(f"referência {({k: round(v, 3) for k, v in gb['referencia'].items()})}")
    print("validação:", json.dumps(gb["validacao"], ensure_ascii=False))


if __name__ == "__main__":
    main()
