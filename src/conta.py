"""Contas com as séries do próprio site, para a pesquisa da leitura a fundo (src/fundo.py) e para quem quiser refazer.

A IA da pesquisa roda este programa pelo terminal com uma permissão que só aceita este comando, e cada número que
ela tira daqui vai para o caderno com o comando exato; a conferência roda o mesmo comando de novo e confere o número.
Por isso o programa só lê arquivos fixos do repositório (data/historico, data/raw e runs/), não abre rede, não
escreve nada e responde sempre igual para a mesma pergunta.

Uso (os meses em AAAA-MM):
  python src/conta.py series                              # o que existe, com unidade, fonte e o primeiro e último mês
  python src/conta.py valores SERIE [--de MES] [--ate MES]
  python src/conta.py variacao SERIE MES_A MES_B          # de MES_A para MES_B, em pontos e em %
  python src/conta.py recorde SERIE MES                   # maior ou menor desde quando, e a posição no histórico
  python src/conta.py depois MES [--meses N]              # as séries principais em MES e N meses depois
  python src/conta.py ciclos                              # cada ciclo de alta e de corte da Selic desde 2002
  python src/conta.py pausas                              # cada vez que o BC parou de cortar, e o que veio depois
  python src/conta.py parecidos MES SERIE [SERIE ...]     # os meses do passado mais parecidos e o que veio depois
  python src/conta.py episodios "SERIE>VALOR" ["SERIE<VALOR" ...]  # as vezes, contadas por episódio, em que as
                                                          # condições valeram juntas, e o que veio depois de cada uma
                                                          # (séries a mais: focus_menos_meta e ipca_menos_meta)
  python src/conta.py recessoes                           # o PIB trimestre a trimestre e as recessões desde 1996
  python src/conta.py focus [--de AAAA-MM-DD]             # as previsões dos bancos (Focus) que o site guardou, semana a semana
  python src/conta.py calc "EXPRESSAO"                    # a conta feita à mão: números, + - * / e parênteses,
                                                          # com ponto ou vírgula nos decimais e sem separador de milhar
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SERIES = {
    "selic_meta": ("Selic, a taxa básica de juros decidida pelo Copom", "% ao ano, valor no fim do mês", "Banco Central, série 432"),
    "ipca_12m": ("IPCA, a inflação oficial, acumulada em 12 meses", "%", "IBGE, pelo Banco Central, série 13522"),
    "focus_ipca_12m": ("Inflação que os bancos esperam para os 12 meses seguintes (Focus, mediana)", "%, último valor do mês",
                       "Banco Central, pesquisa Focus"),
    "juro_real": ("Selic descontada da inflação esperada para 12 meses (a mesma conta do topo do site)", "% ao ano",
                  "conta do site com a Selic e o Focus"),
    "juro_real_longo": ("Juro do título do Tesouro protegido da inflação (NTN-B de uns 10 anos), acima da inflação",
                        "% ao ano, último valor do mês", "Tesouro Direto, taxa de compra"),
    "dolar_ptax": ("Dólar comercial (Ptax de venda)", "R$, último valor do mês", "Banco Central, série 1"),
    "ibcbr": ("IBC-Br, a prévia mensal do PIB feita pelo Banco Central (índice com ajuste sazonal)", "índice",
              "Banco Central, série 24364"),
    "desocupacao": ("Desemprego (PNAD Contínua, trimestre móvel que termina no mês)", "% da força de trabalho",
                    "IBGE, pelo Banco Central, série 24369"),
    "divida_bruta": ("Dívida bruta do governo geral", "% do PIB", "Banco Central, série 13762"),
    "primario_12m": ("Resultado sem juros do setor público em 12 meses (positivo é déficit, quando o governo gasta mais do que arrecada sem contar os juros; negativo é sobra)", "% do PIB",
                     "Banco Central, série 5793"),
    "ibovespa": ("Ibovespa, o índice da bolsa", "pontos, média do mês", "B3"),
    "commodities": ("Índice de preços de commodities do Banco Central em dólar (IC-Br)", "índice", "Banco Central, série 29042"),
    "comprometimento_renda": ("Parte da renda das famílias que vai para pagar dívidas", "% da renda", "Banco Central, série 29034"),
    "reservas": ("Reservas internacionais do Banco Central", "US$ milhões", "Banco Central, série 3546"),
}
PRINCIPAIS = ["selic_meta", "ipca_12m", "focus_ipca_12m", "juro_real", "juro_real_longo", "dolar_ptax", "ibcbr",
              "desocupacao", "divida_bruta", "primario_12m"]


def _carregar() -> tuple[dict, dict]:
    """As séries mês a mês e dia a dia. Com VDC_ATE=AAAA-MM-DD (a leitura a fundo de um dia passado), só o que já se
    sabia naquele dia: os meses antes do mês da data e os dias até ela."""
    import os

    import verifica_base
    ate = os.environ.get("VDC_ATE")
    if ate in _CARREGADAS:
        return _CARREGADAS[ate]
    with contextlib.redirect_stdout(io.StringIO()):
        mensal, diario = verifica_base.series_do_site()
    if ate:
        mensal = {k: {m: v for m, v in s.items() if m < ate[:7]} for k, s in mensal.items()}
        diario = {k: {d: v for d, v in s.items() if d <= ate} for k, s in diario.items()}
    _CARREGADAS[ate] = ({k: v for k, v in mensal.items() if v}, diario)
    return _CARREGADAS[ate]


_CARREGADAS: dict = {}


def _mais(mes: str, n: int) -> str:
    a, m = int(mes[:4]), int(mes[5:7]) - 1 + n
    return f"{a + m // 12:04d}-{m % 12 + 1:02d}"


def _br(x: float | None, casas: int = 2) -> str:
    if x is None:
        return "sem dado"
    s = f"{x:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _casas(serie: str) -> int:
    return {"dolar_ptax": 4, "ibovespa": 0, "reservas": 0, "ibcbr": 2, "commodities": 1}.get(serie, 2)


def _serie(mensal: dict, nome: str) -> dict:
    if nome not in mensal:
        raise SystemExit(f"série desconhecida: {nome}. Rode 'series' para ver as que existem.")
    return mensal[nome]


def _mes_ok(m: str) -> str:
    if len(m) != 7 or m[4] != "-" or not (m[:4] + m[5:]).isdigit():
        raise SystemExit(f"mês fora do formato AAAA-MM: {m}")
    return m


def cmd_series(mensal: dict, _a) -> None:
    for k, (o_que, unidade, fonte) in SERIES.items():
        s = mensal.get(k)
        if not s:
            continue
        ks = sorted(s)
        print(f"{k}: {o_que}. Unidade: {unidade}. Fonte: {fonte}. De {ks[0]} a {ks[-1]} "
              f"(último: {_br(s[ks[-1]], _casas(k))}).")


def cmd_valores(mensal: dict, a) -> None:
    s = _serie(mensal, a.serie)
    meses = [m for m in sorted(s) if (not a.de or m >= a.de) and (not a.ate or m <= a.ate)]
    if len(meses) > 150:
        print(f"(são {len(meses)} meses; mostrando os 150 últimos do intervalo; use --de e --ate)")
        meses = meses[-150:]
    print(f"{a.serie} ({SERIES.get(a.serie, ('', '', ''))[1]}):")
    for m in meses:
        print(f"{m}: {_br(s[m], _casas(a.serie))}")


def cmd_variacao(mensal: dict, a) -> None:
    s = _serie(mensal, a.serie)
    x, y = s.get(_mes_ok(a.mes_a)), s.get(_mes_ok(a.mes_b))
    if x is None or y is None:
        print(f"sem dado em {a.mes_a if x is None else a.mes_b}")
        return
    print(f"{a.serie}: {_br(x, _casas(a.serie))} em {a.mes_a} e {_br(y, _casas(a.serie))} em {a.mes_b}; "
          f"diferença de {_br(y - x, _casas(a.serie))} (em pontos) e de {_br(100 * (y / x - 1), 1)}% (em %).")


def cmd_recorde(mensal: dict, a) -> None:
    s = _serie(mensal, a.serie)
    m = _mes_ok(a.mes)
    if m not in s:
        print(f"sem dado de {a.serie} em {m}")
        return
    v, c = s[m], _casas(a.serie)
    antes = [k for k in sorted(s) if k < m]
    if not antes:
        print(f"{a.serie} em {m}: {_br(v, c)}; é o primeiro mês da série.")
        return
    maior = next((k for k in reversed(antes) if s[k] >= v), None)
    menor = next((k for k in reversed(antes) if s[k] <= v), None)
    print(f"{a.serie} em {m}: {_br(v, c)}. A série começa em {antes[0]}.")
    if maior is None:
        print(f"É o maior valor da série: nenhum mês antes teve valor igual ou maior.")
    elif menor is None:
        print(f"É o menor valor da série: nenhum mês antes teve valor igual ou menor.")
    elif maior < menor:
        print(f"É o maior valor desde {maior}, quando foi {_br(s[maior], c)}.")
    else:
        print(f"É o menor valor desde {menor}, quando foi {_br(s[menor], c)}.")
    abaixo = sum(1 for k in antes if s[k] < v)
    print(f"Dos {len(antes)} meses antes de {m}, {abaixo} tiveram valor menor ({_br(100 * abaixo / len(antes), 0)}%).")


def _cresc12(mensal: dict, m: str) -> float | None:
    s = mensal.get("ibcbr", {})
    a, b = s.get(m), s.get(_mais(m, -12))
    return None if a is None or b is None else 100 * (a / b - 1)


def _linha_mes(mensal: dict, m: str) -> str:
    partes = []
    for k in PRINCIPAIS:
        v = mensal.get(k, {}).get(m)
        if v is not None:
            partes.append(f"{k} {_br(v, _casas(k))}")
    c = _cresc12(mensal, m)
    if c is not None:
        partes.append(f"ibcbr_12m {_br(c, 1)}%")
    return f"{m}: " + ("; ".join(partes) or "sem dado")


def cmd_depois(mensal: dict, a) -> None:
    m = _mes_ok(a.mes)
    print("Valores do mês e de depois (ibcbr_12m é o crescimento da prévia do PIB em 12 meses):")
    for n in [0, *range(a.passo, a.meses + 1, a.passo)]:
        print(_linha_mes(mensal, _mais(m, n)))
    print("Recessão (2 trimestres seguidos de queda do PIB) começando nos 12 meses seguintes: "
          + (", ".join(r["de"] for r in _recessoes() if m <= _tri_mes(r["de"]) <= _mais(m, 12)) or "nenhuma"))


def _ciclos(mensal: dict) -> list[dict]:
    s = mensal["selic_meta"]
    meses = sorted(s)
    out, atual = [], None
    for i in range(1, len(meses)):
        m0, m1 = meses[i - 1], meses[i]
        d = s[m1] - s[m0]
        if abs(d) < 1e-9:
            continue
        lado = "alta" if d > 0 else "corte"
        if atual and atual["lado"] == lado:
            atual.update({"ate": m1, "fim": s[m1]})
        else:
            atual = {"lado": lado, "de": m1, "ate": m1, "inicio": s[m0], "fim": s[m1]}
            out.append(atual)
    return out


def cmd_ciclos(mensal: dict, _a) -> None:
    print("Ciclos da Selic desde 2002, mês a mês (uma pausa no meio de um ciclo não o interrompe, se ele segue para o mesmo lado):")
    for c in _ciclos(mensal):
        print(f"{c['lado']} de {c['de']} a {c['ate']}: de {_br(c['inicio'])}% para {_br(c['fim'])}% "
              f"({'+' if c['fim'] > c['inicio'] else ''}{_br(c['fim'] - c['inicio'])} ponto(s))")


def _pausas(mensal: dict) -> list[dict]:
    s, foc = mensal["selic_meta"], mensal.get("focus_ipca_12m", {})
    meses = sorted(s)
    out = []
    for i in range(1, len(meses)):
        m = meses[i]
        if not s[m] < s[meses[i - 1]] - 1e-9:
            continue
        # Pausa: a Selic fica igual nos 2 meses seguintes (ou até o fim da série, se ele vem antes).
        seguintes = meses[i + 1:i + 3]
        if not seguintes or any(abs(s[x] - s[m]) > 1e-9 for x in seguintes):
            continue
        prox = next((x for x in meses[i + 1:] if abs(s[x] - s[m]) > 1e-9), None)
        parado = len([x for x in meses[i + 1:] if x < (prox or "9999")])
        p = {"ultimo_corte": m, "selic": s[m], "meses_parado": parado, "aberta": prox is None,
             "expectativa": foc.get(m), "juro_real": mensal.get("juro_real", {}).get(m), "ipca_12m": mensal.get("ipca_12m", {}).get(m)}
        f1, f3 = foc.get(_mais(m, 1)), foc.get(_mais(m, 3))
        p["exp_1m"] = None if f1 is None or p["expectativa"] is None else f1 - p["expectativa"]
        p["exp_3m"] = None if f3 is None or p["expectativa"] is None else f3 - p["expectativa"]
        if prox:
            p["depois"] = "alta" if s[prox] > s[m] else "corte"
            p["meses_ate"] = (int(prox[:4]) - int(m[:4])) * 12 + int(prox[5:]) - int(m[5:])
            # O ciclo que começa (ou continua, se o BC voltou a cortar) no mês da próxima mudança.
            ciclo = next(c for c in _ciclos(mensal) if c["de"] <= prox <= c["ate"])
            p["ciclo"] = {"ate": ciclo["ate"], "fim": ciclo["fim"], "total": ciclo["fim"] - s[m]}
        out.append(p)
    return out


def cmd_pausas(mensal: dict, _a) -> None:
    print("Cada vez que o Banco Central cortou a Selic e a deixou parada pelo menos nos 2 meses seguintes "
          "(ou até o último mês da série). 'Expectativa' é a inflação que os bancos esperam para os 12 meses seguintes "
          "(Focus), no fim do mês; 'meta' é o centro da meta de inflação desses mesmos 12 meses (a média das metas de "
          "cada ano, pelo número de meses); a distância é expectativa menos meta.")
    for p in _pausas(mensal):
        meta = _meta(p["ultimo_corte"])
        linha = (f"último corte em {p['ultimo_corte']} (Selic {_br(p['selic'])}%): expectativa {_br(p['expectativa'])}% "
                 f"(meta {_br(meta, 2)}%, distância {_br(p['expectativa'] - meta) if p['expectativa'] is not None else 'sem dado'}), "
                 f"IPCA 12 meses {_br(p['ipca_12m'])}%, juro real {_br(p['juro_real'], 1)}%; "
                 f"expectativa 1 mês depois {'+' if (p['exp_1m'] or 0) > 0 else ''}{_br(p['exp_1m'])} ponto, "
                 f"3 meses depois {'+' if (p['exp_3m'] or 0) > 0 else ''}{_br(p['exp_3m'])} ponto; ")
        if p["aberta"]:
            linha += f"ainda parada ({p['meses_parado']} mês(es) com dado depois do corte)."
        else:
            linha += (f"depois: {p['depois']} {p['meses_ate']} meses depois do último corte; o ciclo foi até {p['ciclo']['ate']} "
                      f"e levou a Selic a {_br(p['ciclo']['fim'])}% ({'+' if p['ciclo']['total'] > 0 else ''}{_br(p['ciclo']['total'])} ponto(s)).")
        print(linha)


# O centro da meta de inflação (CMN), ano a ano; 2002 e 2003 com as metas ajustadas que o BC passou a perseguir.
METAS = {2002: 3.5, 2003: 4.0, 2004: 5.5, 2005: 4.5, 2006: 4.5, 2007: 4.5, 2008: 4.5, 2009: 4.5, 2010: 4.5, 2011: 4.5,
         2012: 4.5, 2013: 4.5, 2014: 4.5, 2015: 4.5, 2016: 4.5, 2017: 4.5, 2018: 4.5, 2019: 4.25, 2020: 4.0, 2021: 3.75,
         2022: 3.5, 2023: 3.25, 2024: 3.0, 2025: 3.0, 2026: 3.0, 2027: 3.0}


def _meta(mes: str) -> float:
    """O centro da meta para os 12 meses depois de `mes`: a meta de cada ano, pesada pelos meses que caem nele."""
    a, m = int(mes[:4]), int(mes[5:7])
    return ((12 - m) * METAS.get(a, 3.0) + m * METAS.get(a + 1, 3.0)) / 12


def _recessoes() -> list[dict]:
    pib = json.loads((ROOT / "data" / "historico" / "pib.json").read_text())["pib"]
    out, i = [], 0
    while i < len(pib):
        if pib[i]["var_qoq"] < 0 and i + 1 < len(pib) and pib[i + 1]["var_qoq"] < 0:
            j = i
            while j + 1 < len(pib) and pib[j + 1]["var_qoq"] < 0:
                j += 1
            out.append({"de": pib[i]["trimestre"], "ate": pib[j]["trimestre"], "quedas": [p["var_qoq"] for p in pib[i:j + 1]]})
            i = j + 1
        else:
            i += 1
    return out


def _tri_mes(tri: str) -> str:
    """'3T2014' -> '2014-09' (o último mês do trimestre)."""
    return f"{tri[2:]}-{int(tri[0]) * 3:02d}"


def cmd_recessoes(_m: dict, _a) -> None:
    pib = json.loads((ROOT / "data" / "historico" / "pib.json").read_text())
    print(f"PIB contra o trimestre anterior, com ajuste sazonal ({pib['nota']}). Último: {pib['pib'][-1]['trimestre']} "
          f"({_br(pib['pib'][-1]['var_qoq'], 1)}%).")
    print("Recessões, contadas como 2 ou mais trimestres seguidos de queda:")
    for r in _recessoes():
        print(f"de {r['de']} a {r['ate']}: quedas de " + ", ".join(_br(q, 1) + "%" for q in r["quedas"]))
    print("Últimos 8 trimestres: " + ", ".join(f"{p['trimestre']} {_br(p['var_qoq'], 1)}%" for p in pib["pib"][-8:]))


def _escala(v: list[float]) -> float:
    import direcao
    return direcao.escala_robusta(v) or 1.0


def cmd_parecidos(mensal: dict, a) -> None:
    m = _mes_ok(a.mes)
    series = a.series
    for k in series:
        _serie(mensal, k)
        if m not in mensal[k]:
            raise SystemExit(f"sem dado de {k} em {m}")
    esc = {k: _escala(list(mensal[k].values())) for k in series}
    cand = []
    for x in sorted(set.intersection(*[set(mensal[k]) for k in series])):
        if x > _mais(m, -24):
            continue
        d = sum(((mensal[k][x] - mensal[k][m]) / esc[k]) ** 2 for k in series) ** 0.5
        cand.append((d, x))
    escolhidos = []
    for d, x in sorted(cand):
        if all(abs((int(x[:4]) - int(y[:4])) * 12 + int(x[5:]) - int(y[5:])) > 6 for _, y in escolhidos):
            escolhidos.append((d, x))
        if len(escolhidos) == 5:
            break
    print(f"Os 5 meses mais parecidos com {m} em {', '.join(series)} (distância em vaivéns normais de cada série; "
          "meses a menos de 6 meses um do outro contam uma vez; só meses até 2 anos antes):")
    print("referência " + _linha_mes(mensal, m))
    for d, x in escolhidos:
        print(f"\ndistância {_br(d, 2)}: " + _linha_mes(mensal, x))
        for n in (6, 12):
            print(f"  {n} meses depois, " + _linha_mes(mensal, _mais(x, n)))
        rec = [r["de"] for r in _recessoes() if x <= _tri_mes(r["de"]) <= _mais(x, 12)]
        print("  recessão começando nos 12 meses seguintes: " + (", ".join(rec) or "nenhuma"))


# Séries que só existem como conta de outras: a distância da inflação (esperada ou passada) até o centro da meta.
DERIVADAS = {
    "focus_menos_meta": "inflação esperada para 12 meses (Focus) menos o centro da meta desses 12 meses, em pontos",
    "ipca_menos_meta": "IPCA em 12 meses menos o centro da meta do ano, em pontos",
}
CONDICAO = __import__("re").compile(r"^\s*([a-z_0-9]+)\s*(>=|<=|>|<)\s*(-?\d+(?:[.,]\d+)?)\s*$")


def _derivada(mensal: dict, nome: str) -> dict:
    if nome == "focus_menos_meta":
        return {m: v - _meta(m) for m, v in mensal.get("focus_ipca_12m", {}).items()}
    if nome == "ipca_menos_meta":
        return {m: v - METAS.get(int(m[:4]), 3.0) for m, v in mensal.get("ipca_12m", {}).items()}
    return _serie(mensal, nome)


def _episodios(mensal: dict, conds: list[tuple[str, str, float]], folga: int = 2) -> list[dict]:
    """Os trechos de meses seguidos em que todas as condições valem. Até `folga` meses fora da condição no meio não
    quebram o trecho, para que um mês de vaivém não faça um episódio virar dois."""
    import operator as op
    ops = {">": op.gt, "<": op.lt, ">=": op.ge, "<=": op.le}
    series = {k: _derivada(mensal, k) for k, _, _ in conds}
    meses = sorted(set.intersection(*[set(s) for s in series.values()]))
    vale = [m for m in meses if all(ops[o](series[k][m], v) for k, o, v in conds)]
    out = []
    for m in vale:
        if out and (int(m[:4]) - int(out[-1]["ate"][:4])) * 12 + int(m[5:]) - int(out[-1]["ate"][5:]) <= folga + 1:
            out[-1]["ate"] = m
            out[-1]["meses"].append(m)
        else:
            out.append({"de": m, "ate": m, "meses": [m]})
    return out


def cmd_episodios(mensal: dict, a) -> None:
    conds = []
    for c in a.condicoes:
        x = CONDICAO.match(c)
        if not x:
            raise SystemExit(f"condição fora do formato SERIE>VALOR (ou <, >=, <=): {c}")
        nome = x.group(1)
        if nome not in DERIVADAS:
            _serie(mensal, nome)
        conds.append((nome, x.group(2), float(x.group(3).replace(",", "."))))
    eps = _episodios(mensal, conds)
    s = mensal["selic_meta"]
    nomes = [k for k, _, _ in conds]
    print("Episódios em que " + " e ".join(f"{k} {o} {_br(v)}" for k, o, v in conds)
          + " (meses seguidos; até 2 meses fora da condição no meio não quebram o episódio). Conte por episódio, e não "
          "por mês: um episódio longo não vale mais que um curto.")
    for k in nomes:
        if k in DERIVADAS:
            print(f"{k}: {DERIVADAS[k]}.")
    subiu = caiu = igual = 0
    for e in eps:
        ser = {k: _derivada(mensal, k) for k in nomes}
        vals = "; ".join(f"{k} de {_br(ser[k][e['de']])} a {_br(ser[k][e['ate']])} (o maior: {_br(max(ser[k][m] for m in e['meses']))})"
                         for k in nomes)
        s0, s1 = s.get(e["de"]), s.get(e["ate"])
        if s0 is not None and s1 is not None:
            subiu, caiu, igual = subiu + (s1 > s0 + 1e-9), caiu + (s1 < s0 - 1e-9), igual + (abs(s1 - s0) <= 1e-9)
        n = (int(e["ate"][:4]) - int(e["de"][:4])) * 12 + int(e["ate"][5:]) - int(e["de"][5:]) + 1
        print(f"\nde {e['de']} a {e['ate']} ({n} meses): {vals}; Selic de {_br(s0)}% no começo a {_br(s1)}% no fim.")
        print("  no começo, " + _linha_mes(mensal, e["de"]))
        print("  12 meses depois do fim, " + _linha_mes(mensal, _mais(e["ate"], 12)))
        rec = [r["de"] for r in _recessoes() if e["de"] <= _tri_mes(r["de"]) <= _mais(e["ate"], 12)]
        print("  recessão começando no episódio ou nos 12 meses seguintes: " + (", ".join(rec) or "nenhuma"))
    print(f"\n{len(eps)} episódio(s). Do começo ao fim de cada um, a Selic subiu em {subiu}, caiu em {caiu} e ficou "
          f"igual em {igual}.")


def cmd_focus(_m: dict, a) -> None:
    import os
    ate = os.environ.get("VDC_ATE") or "9999"
    vistos = {}
    for arq in sorted((ROOT / "data" / "raw").glob("*/indicadores.json")):
        try:
            f = json.loads(arq.read_text()).get("focus") or {}
        except (OSError, json.JSONDecodeError):
            continue
        for nome, v in f.items():
            for x in v if isinstance(v, list) else [v]:
                if not isinstance(x, dict) or x.get("Mediana") is None:
                    continue
                if x["Data"][:10] > ate:
                    continue
                chave = (x["Data"][:10], nome, str(x.get("DataReferencia") or ""))
                vistos[chave] = x["Mediana"]
    print("Previsões dos bancos (Focus, mediana) na data da pesquisa, como o site guardou:")
    for (data, nome, ref), v in sorted(vistos.items()):
        if a.de and data < a.de:
            continue
        print(f"{data}: {nome}{' ' + ref if ref else ''}: {_br(v, 2)}")


def calcular(expr: str) -> float:
    """A conta de `calc`, sem eval: só números, + - * / e parênteses."""
    import ast
    import operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.USub: op.neg, ast.UAdd: op.pos}

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        raise SystemExit("calc aceita só números, + - * / e parênteses")
    if len(expr) > 300:
        raise SystemExit("calc: expressão longa demais")
    try:
        return ev(ast.parse(expr.replace(",", "."), mode="eval").body)
    except (SyntaxError, ZeroDivisionError) as e:
        raise SystemExit(f"calc: {type(e).__name__}") from None


def cmd_calc(_mensal, a) -> None:
    v = calcular(a.expr)
    print(f"{a.expr} = {_br(v, 4)} (com 3 casas: {_br(v, 3)}; com 2 casas: {_br(v, 2)}; com 1 casa: {_br(v, 1)})")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("series")
    p = sub.add_parser("valores")
    p.add_argument("serie")
    p.add_argument("--de")
    p.add_argument("--ate")
    p = sub.add_parser("variacao")
    p.add_argument("serie")
    p.add_argument("mes_a")
    p.add_argument("mes_b")
    p = sub.add_parser("recorde")
    p.add_argument("serie")
    p.add_argument("mes")
    p = sub.add_parser("depois")
    p.add_argument("mes")
    p.add_argument("--meses", type=int, default=12)
    p.add_argument("--passo", type=int, default=3)
    sub.add_parser("ciclos")
    sub.add_parser("pausas")
    p = sub.add_parser("parecidos")
    p.add_argument("mes")
    p.add_argument("series", nargs="+")
    p = sub.add_parser("episodios")
    p.add_argument("condicoes", nargs="+")
    sub.add_parser("recessoes")
    p = sub.add_parser("focus")
    p.add_argument("--de")
    p = sub.add_parser("calc")
    p.add_argument("expr")
    a = ap.parse_args(argv)
    if a.cmd == "calc":
        cmd_calc(None, a)
        return
    if getattr(a, "meses", 1) > 60 or getattr(a, "passo", 1) < 1:
        raise SystemExit("--meses vai até 60 e --passo é de pelo menos 1")
    mensal, _ = _carregar()
    {"series": cmd_series, "valores": cmd_valores, "variacao": cmd_variacao, "recorde": cmd_recorde,
     "depois": cmd_depois, "ciclos": cmd_ciclos, "pausas": cmd_pausas, "parecidos": cmd_parecidos,
     "recessoes": cmd_recessoes, "focus": cmd_focus, "episodios": cmd_episodios}[a.cmd](mensal, a)


def rodar(comando: str) -> str:
    """Roda um comando do caderno ("python src/conta.py pausas" ou só "pausas") e devolve a saída, para a conferência."""
    import shlex
    partes = shlex.split(comando)
    if "conta.py" in " ".join(partes):
        partes = partes[next(i for i, x in enumerate(partes) if x.endswith("conta.py")) + 1:]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            main(partes)
    except SystemExit as e:
        return buf.getvalue() + (str(e.code) if e.code not in (None, 0) else "")
    return buf.getvalue()


if __name__ == "__main__":
    main()
