"""Calibração do nível: limites, faixas normais, pesos e a regressão, com validação fora da amostra.

Segue as regras de config/modelo.json, registradas antes de olhar o histórico. Lê
data/historico/series.json (src/historico.py) e grava:
- config/calibracao.json: o que a conta do dia usa (limites, pesos, regressão, k);
- data/historico/mensal.json: os indicadores mês a mês, como eram conhecidos em cada mês,
  o alvo e o nível fora da amostra, para quem quiser refazer a conta.

Uso: python src/calibra.py
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
from statistics import mean, pstdev

sys.path.insert(0, str(Path(__file__).resolve().parent))

import indicadores as ind  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
SAIDA = ROOT / "config" / "calibracao.json"
MENSAL = ROOT / "data" / "historico" / "mensal.json"


def carregar_config() -> dict:
    cfg = json.loads((ROOT / "config" / "modelo.json").read_text())
    if os.environ.get("VDC_PESOS"):  # para comparar regras de peso sem mexer no arquivo
        cfg["sinais"]["pesos"] = os.environ["VDC_PESOS"]
    return cfg


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


def sinal(x: float, limite: float, direcao: int) -> int:
    return int(x >= limite) if direcao > 0 else int(x <= limite)


def klr(x: dict[str, float], y: dict[str, int], meses: set[str], direcao: int, cfg: dict,
        janelas: list[set[str]]) -> dict:
    """Melhor limite de um indicador pela razão ruído/sinal, só com os meses de treino."""
    usa = sorted(m for m in meses if m in x and y.get(m) is not None)
    if not usa:
        return {"peso": 0.0, "motivo": "sem dado"}
    vals = [x[m] for m in usa]
    eps = [j & set(usa) for j in janelas]
    eps = [j for j in eps if any(y[m] == 1 for m in j)]
    regra = cfg["sinais"]
    base = {"meses": len(usa), "episodios_na_amostra": len(eps), "amostra": [usa[0], usa[-1]],
            "faixa_normal": [percentil(vals, p) for p in cfg["faixa_normal_percentis"]],
            "escala": [percentil(vals, 2), percentil(vals, 98)]}
    melhor = None
    for p in regra["percentis"]:
        lim = percentil(vals, p if direcao > 0 else 100 - p)
        a = b = c = d = 0
        for m in usa:
            s = sinal(x[m], lim, direcao)
            if y[m] == 1:
                a += s
                c += 1 - s
            else:
                b += s
                d += 1 - s
        avisados = sum(1 for j in eps if any(sinal(x[m], lim, direcao) for m in j if y[m] == 1))
        if a == 0 or avisados < regra["minimo_episodios_avisados"]:
            continue
        # Um indicador que nunca deu alarme falso é tratado como se tivesse dado um: o peso não fica infinito.
        nsr = (max(b, 1) / (b + d)) / (a / (a + c)) if b + d else 1.0
        cand = {"percentil": p, "limite": lim, "nsr": nsr, "episodios_avisados": avisados,
                "acertos": a, "falsos": b, "perdidos": c}
        if melhor is None or nsr < melhor["nsr"] - 1e-12 or (abs(nsr - melhor["nsr"]) <= 1e-12 and p > melhor["percentil"]):
            melhor = cand
    if melhor is None:
        return {**base, "peso": 0.0, "motivo": "não avisou pelo menos 2 recessões"}
    if melhor["nsr"] >= 1:
        peso = 0.0
    elif regra.get("pesos", "inverso") == "iguais":
        peso = 1.0
    else:
        peso = 1 / melhor["nsr"]
    return {**base, **melhor, "peso": peso,
            "motivo": None if peso else "deu mais alarme falso que aviso certo"}


def composto(xs: dict[str, dict[str, float]], params: dict, cfg: dict, m: str) -> tuple[float, int] | None:
    num = den = 0.0
    n = 0
    for k, p in params.items():
        if p["peso"] <= 0 or m not in xs[k]:
            continue
        den += p["peso"]
        num += p["peso"] * sinal(xs[k][m], p["limite"], cfg["indicadores"][k]["direcao"])
        n += 1
    if n < cfg["minimo_indicadores_no_mes"] or not den:
        return None
    return num / den, n


def logistica(pares: list[tuple[float, int]], pen: float) -> tuple[float, float]:
    """Máxima verossimilhança penalizada (pen × b²) por Newton-Raphson."""
    a = b = 0.0
    ybar = mean(y for _, y in pares)
    a = math.log(ybar / (1 - ybar))
    for _ in range(100):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in pares:
            p = 1 / (1 + math.exp(-(a + b * x)))
            w = p * (1 - p)
            ga += y - p
            gb += (y - p) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        gb -= 2 * pen * b
        hbb += 2 * pen
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a + da, b + db
        if abs(da) + abs(db) < 1e-10:
            break
    return a, b


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def sigm(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def prever(c: float, a: float, b: float, pbar: float, k: float) -> float:
    return sigm(logit(pbar) + k * (a + b * c - logit(pbar)))


def ajustar(xs: dict, y: dict, meses: set[str], cfg: dict, janelas: list[set[str]], fora: str | None = None) -> dict:
    """Tudo o que se estima, só com os meses dados: limites, pesos, regressão e a média.
    `fora` zera o peso de um indicador, para medir quanto do acerto depende dele."""
    params = {k: klr(xs[k], y, meses, v["direcao"], cfg, janelas) for k, v in cfg["indicadores"].items()}
    if fora:
        params[fora] = {**params[fora], "peso": 0.0}
    pares = []
    for m in sorted(meses):
        if y.get(m) is None:
            continue
        c = composto(xs, params, cfg, m)
        if c is not None:
            pares.append((c[0], y[m]))
    if not pares or all(yy == pares[0][1] for _, yy in pares):
        return {"params": params, "a": 0.0, "b": 0.0, "pbar": mean(yy for _, yy in pares) if pares else 0.0, "n": len(pares)}
    pbar = mean(yy for _, yy in pares)
    if not any(p["peso"] > 0 for p in params.values()):
        return {"params": params, "a": logit(pbar), "b": 0.0, "pbar": pbar, "n": len(pares)}
    a, b = logistica(pares, cfg["probabilidade"]["penalidade"])
    return {"params": params, "a": a, "b": b, "pbar": pbar, "n": len(pares)}


def nivel_de(r: float, cortes: list[float]) -> int:
    """Índice do nível (0 a 4) pela razão."""
    return sum(1 for c in cortes if r >= c)


def blocos(meses: list[str], janelas: list[set[str]], anos: int = 3) -> list[set[str]]:
    """Blocos de 3 anos; um corte dentro da janela de aviso de uma recessão vai para o fim dela."""
    if not meses:
        return []
    ini_ano = int(meses[0][:4])
    cortes = []
    a = ini_ano + anos
    while a <= int(meses[-1][:4]):
        corte = f"{a:04d}-01"
        for j in janelas:
            if j and min(j) < corte <= max(j):
                corte = num_mes(mes_num(max(j)) + 1)
        cortes.append(corte)
        a += anos
    cortes = sorted(set(cortes))
    out, atual = [], set()
    i = 0
    for m in meses:
        while i < len(cortes) and m >= cortes[i]:
            if atual:
                out.append(atual)
            atual = set()
            i += 1
        atual.add(m)
    if atual:
        out.append(atual)
    return out


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
    # Janela de aviso de cada recessão: os meses com y = 1 que apontam para ela.
    janelas = [{m for m in amostra if y[m] == 1 and primeiro_nao_divulgado(m) <= ini < primeiro_nao_divulgado(m) + h}
               for ini, _ in eps]

    final = ajustar(xs, y, set(amostra), cfg, janelas)

    # Validação: cada bloco é previsto por um modelo que nunca viu os meses dele.
    grade = cfg["probabilidade"]["grade_k"]
    bl = blocos(amostra, janelas)

    def validar(fora: str | None = None) -> tuple[dict, dict]:
        oof: dict[str, dict] = {}
        for b in bl:
            fit = ajustar(xs, y, set(amostra) - b, cfg, janelas, fora)
            for m in sorted(b):
                c = composto(xs, fit["params"], cfg, m)
                if c is None:
                    continue
                oof[m] = {"c": c[0], "y": y[m], "pbar": fit["pbar"],
                          "p": {k: prever(c[0], fit["a"], fit["b"], fit["pbar"], k) for k in grade}}
        return oof, {k: mean((o["p"][k] - o["y"]) ** 2 for o in oof.values()) for k in grade}

    def ganho(br: dict) -> tuple[float, float]:
        kb = min(grade, key=lambda k: (round(br[k], 12), k))
        return kb, (round(1 - br[kb] / br[0], 4) if br[0] else 0.0)

    oof, brier = validar()
    k_best = min(grade, key=lambda k: (round(brier[k], 12), k))
    # O mesmo teste sem o indicador de maior peso: quanto do acerto depende dele.
    maior = max(final["params"], key=lambda k: final["params"][k]["peso"])
    k_sem, ganho_sem = ganho(validar(maior)[1])

    # O nível fora da amostra, mês a mês (a conta de cada mês; a confirmação diária não se aplica aqui).
    cortes = cfg["niveis"]["cortes_razao"]
    historico = []
    for m in sorted(oof):
        o = oof[m]
        r = o["p"][k_best] / o["pbar"] if o["pbar"] else 1.0
        historico.append({"mes": m, "nivel": nivel_de(r, cortes), "recessao_a_frente": o["y"]})

    # Também o nível dos meses ainda sem resposta (de setembro de 2025 até hoje), com o modelo final.
    recentes = []
    for m in todos_meses:
        if m in oof or m < (amostra[-1] if amostra else m):
            continue
        c = composto(xs, final["params"], cfg, m)
        if c is None:
            continue
        p = prever(c[0], final["a"], final["b"], final["pbar"], k_best)
        recentes.append({"mes": m, "nivel": nivel_de(p / final["pbar"], cortes)})

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

    def limpo(p: dict) -> dict:
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in p.items()}

    res = {
        "calibrado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dados_de": hist["coletado_em"],
        "recessoes": [{"inicio": num_tri(a), "fim": num_tri(b)} for a, b in eps],
        "amostra": {"inicio": amostra[0], "fim": amostra[-1], "meses": len(amostra),
                    "meses_com_recessao_a_frente": sum(y[m] for m in amostra),
                    "meses_na_regressao": final["n"]},
        "indicadores": {k: limpo(p) for k, p in final["params"].items()},
        "regressao": {"a": final["a"], "b": final["b"]},
        "media": final["pbar"],
        "k": k_best,
        "validacao": {
            "blocos": [[min(b), max(b)] for b in bl],
            "meses": len(oof),
            "brier_por_k": {str(k): round(v, 6) for k, v in brier.items()},
            "brier_media": round(brier[0], 6),
            "brier_escolhido": round(brier[k_best], 6),
            "ganho_sobre_a_media": round(1 - brier[k_best] / brier[0], 4) if brier[0] else None,
            "sem_o_maior_peso": {"indicador": maior, "k": k_sem, "ganho_sobre_a_media": ganho_sem},
        },
        "placar": placar,
    }
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    MENSAL.write_text(json.dumps({
        "gerado_em": res["calibrado_em"],
        "indicadores": {k: {m: round(v, 4) for m, v in sorted(s.items())} for k, s in xs.items()},
        "recessao_a_frente": {m: y[m] for m in todos_meses if y[m] is not None},
        "nivel_fora_da_amostra": historico,
        "nivel_meses_recentes": recentes,
    }, ensure_ascii=False, separators=(",", ":")))

    print(f"recessões: {', '.join(f'{num_tri(a)}–{num_tri(b)}' for a, b in eps)}")
    print(f"amostra {amostra[0]}..{amostra[-1]}: {len(amostra)} meses, {res['amostra']['meses_com_recessao_a_frente']} com recessão à frente")
    for k, p in final["params"].items():
        if p.get("peso"):
            print(f"  {k:16s} limite {p['limite']:8.3f} (p{p['percentil']}) NSR {p['nsr']:.3f} peso {p['peso']:.2f} "
                  f"avisou {p['episodios_avisados']}/{p['episodios_na_amostra']} | normal {p['faixa_normal'][0]:.2f}..{p['faixa_normal'][1]:.2f}")
        else:
            print(f"  {k:16s} peso 0: {p.get('motivo')} | {p.get('amostra')} {p.get('episodios_na_amostra')} episódios")
    print(f"regressão a={final['a']:.3f} b={final['b']:.3f} média={final['pbar']:.4f} | k={k_best}")
    print("Brier por k:", {k: round(v, 4) for k, v in brier.items()})
    print(f"ganho fora da amostra sobre a média: {res['validacao']['ganho_sobre_a_media']} "
          f"(sem {maior}: {ganho_sem}, k={k_sem})")


if __name__ == "__main__":
    main()
