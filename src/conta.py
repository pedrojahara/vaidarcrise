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
A tradução do fato na vida de quem lê (as regras, as fontes e a força de cada uma estão em TRADUCAO.md):
  python src/conta.py traduz precos                       # o que custava R$ 100 um ano antes, pelo IPCA e pelo INPC,
                                                          # e daqui a um ano, pelo Focus
  python src/conta.py traduz dolar [PCT]                  # quanto uma alta (ou queda) de PCT% do dólar sobe o IPCA em
                                                          # um ano, pela conta do Banco Central; sem PCT, a dos 12 meses
  python src/conta.py traduz parcela VALOR MESES JURO [JURO ...]  # a parcela de um financiamento (SAC e Price) com
                                                          # cada juro ao ano; ex.: traduz parcela 300000 360 11.7 15
  python src/conta.py traduz credito                      # o juro de cada tipo de empréstimo às pessoas, agora e um
                                                          # ano antes, e quanto viram R$ 1.000 devidos por um ano
  python src/conta.py traduz guardado [VALOR]             # quanto rendem R$ 1.000 (ou VALOR) com a Selic e na poupança,
                                                          # e quanto sobra acima da inflação esperada
  python src/conta.py traduz minimo                       # o salário mínimo, o poder de compra perdido desde o último
                                                          # reajuste e o reajuste de janeiro pela lei; e o INSS
  python src/conta.py traduz renda                        # a renda média do trabalho, descontada a inflação, contra
                                                          # um ano antes
  python src/conta.py traduz emprego                      # o desemprego, quantas pessoas são 1 ponto e quanto ele
                                                          # subiu nas recessões desde 2012
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
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
    "inpc": ("INPC, a inflação das famílias com renda de 1 a 5 salários mínimos, que corrige o mínimo e o INSS",
             "% no mês", "IBGE, pelo Banco Central, série 188"),
    "salario_minimo": ("Salário mínimo", "R$ por mês", "Banco Central, série 1619"),
    "tr": ("Taxa referencial (TR), que corrige a poupança", "% ao mês", "Banco Central, série 7811"),
    "rendimento_real": ("Renda média do trabalho, descontada a inflação (PNAD Contínua, trimestre móvel que termina no mês)",
                        "R$ por mês, em reais do último trimestre", "IBGE, tabela 6390"),
    "forca_trabalho": ("Força de trabalho: quem trabalha ou procura trabalho (PNAD Contínua)", "mil pessoas",
                       "IBGE, pelo Banco Central, série 24378"),
    "juro_pf": ("Juro médio dos empréstimos às pessoas com juro definido pelo banco (todos os tipos)", "% ao ano", "Banco Central, série 20740"),
    "juro_rotativo": ("Juro médio do cartão de crédito rotativo", "% ao ano", "Banco Central, série 22022"),
    "juro_cheque_especial": ("Juro médio do cheque especial", "% ao ano", "Banco Central, série 20741"),
    "juro_pessoal": ("Juro médio do crédito pessoal não consignado", "% ao ano", "Banco Central, série 20742"),
    "juro_consignado_inss": ("Juro médio do consignado para aposentados e pensionistas do INSS", "% ao ano",
                             "Banco Central, série 20746"),
    "juro_veiculos": ("Juro médio do financiamento de veículos", "% ao ano", "Banco Central, série 20749"),
    "juro_imobiliario": ("Juro médio do financiamento imobiliário com taxas de mercado", "% ao ano",
                         "Banco Central, série 20772"),
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


def _contagem(mensal: dict, conds: list[tuple[str, str, float]]) -> tuple[int, int, int, int]:
    """(encerrados, subiu, caiu, igual): a Selic do começo ao fim de cada episódio encerrado, sem o que ainda vale."""
    eps = _episodios(mensal, conds)
    if not eps:
        return 0, 0, 0, 0
    s = mensal["selic_meta"]
    ultimo = max(set.intersection(*[set(_derivada(mensal, k)) for k, _, _ in conds]))
    n = subiu = caiu = igual = 0
    for e in eps:
        if (int(ultimo[:4]) - int(e["ate"][:4])) * 12 + int(ultimo[5:]) - int(e["ate"][5:]) <= 2:
            continue
        s0, s1 = s.get(e["de"]), s.get(e["ate"])
        if s0 is None or s1 is None:
            continue
        n, subiu, caiu, igual = n + 1, subiu + (s1 > s0 + 1e-9), caiu + (s1 < s0 - 1e-9), igual + (abs(s1 - s0) <= 1e-9)
    return n, subiu, caiu, igual


def _frase_frequencia(n: int, subiu: int, caiu: int, igual: int) -> str:
    partes = [(subiu, "terminou mais alta"), (igual, "ficou igual"), (caiu, "terminou mais baixa")]
    ditas = [f"{'todas as ' + str(n) if q == n else str(q) + ' das ' + str(n)} vezes, a Selic {o}" if i == 0
             else f"em {q}, {o.replace('terminou ', '')}" for i, (q, o) in enumerate(x for x in partes if x[0])]
    return "em " + "; ".join(ditas) if ditas else "nenhuma vez encerrada"


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
    # O episódio que ainda vale no fim da série (ou que parou há 2 meses ou menos, o que a folga ainda junta) não
    # terminou: o que a Selic fez nele até agora não é o fim dele, e ele fica fora da conta. No texto de 11/11/2026, o
    # "subiu em 5 e caiu em 1" contava como queda o episódio de agora, em que a Selic foi de 14% para 13,75%; nos 5 que
    # terminaram, ela subiu em todos.
    ultimo = max(set.intersection(*[set(_derivada(mensal, k)) for k in nomes])) if eps else None

    def _aberto(e: dict) -> bool:
        return ultimo is not None and (int(ultimo[:4]) - int(e["ate"][:4])) * 12 + int(ultimo[5:]) - int(e["ate"][5:]) <= 2

    print("Episódios em que " + " e ".join(f"{k} {o} {_br(v)}" for k, o, v in conds)
          + " (meses seguidos; até 2 meses fora da condição no meio não quebram o episódio). Conte por episódio, e não "
          "por mês: um episódio longo não vale mais que um curto. O episódio que ainda não terminou fica fora da conta.")
    for k in nomes:
        if k in DERIVADAS:
            print(f"{k}: {DERIVADAS[k]}.")
    subiu = caiu = igual = 0
    abertos = []
    for e in eps:
        ser = {k: _derivada(mensal, k) for k in nomes}
        vals = "; ".join(f"{k} de {_br(ser[k][e['de']])} a {_br(ser[k][e['ate']])} (o maior: {_br(max(ser[k][m] for m in e['meses']))})"
                         for k in nomes)
        s0, s1 = s.get(e["de"]), s.get(e["ate"])
        aberto = _aberto(e)
        if aberto:
            abertos.append((e, s0, s1))
        elif s0 is not None and s1 is not None:
            subiu, caiu, igual = subiu + (s1 > s0 + 1e-9), caiu + (s1 < s0 - 1e-9), igual + (abs(s1 - s0) <= 1e-9)
        n = (int(e["ate"][:4]) - int(e["de"][:4])) * 12 + int(e["ate"][5:]) - int(e["de"][5:]) + 1
        if aberto:
            print(f"\nde {e['de']} até agora, ainda aberto ({n} meses com dado): {vals}; Selic de {_br(s0)}% no começo a "
                  f"{_br(s1)}% no último mês com dado. Fica fora da conta, porque ainda não terminou.")
        else:
            print(f"\nde {e['de']} a {e['ate']} ({n} meses): {vals}; Selic de {_br(s0)}% no começo a {_br(s1)}% no fim.")
        print("  no começo, " + _linha_mes(mensal, e["de"]))
        print("  12 meses depois do fim, " + _linha_mes(mensal, _mais(e["ate"], 12)))
        rec = [r["de"] for r in _recessoes() if e["de"] <= _tri_mes(r["de"]) <= _mais(e["ate"], 12)]
        print("  recessão começando no episódio ou nos 12 meses seguintes: " + (", ".join(rec) or "nenhuma"))
    fechados = len(eps) - len(abertos)
    print(f"\n{len(eps)} episódio(s): {fechados} encerrado(s) e {len(abertos)} ainda aberto(s). Do começo ao fim de cada "
          f"episódio encerrado, a Selic subiu em {subiu}, caiu em {caiu} e ficou igual em {igual}.")
    contados = subiu + caiu + igual  # os encerrados com a Selic do começo e do fim
    if contados:
        print(f"Por frequência, do começo ao fim de cada vez encerrada: {_frase_frequencia(contados, subiu, caiu, igual)}.")
    for e, s0, s1 in abertos:
        print(f"O episódio aberto começou em {e['de']}: até agora, a Selic foi de {_br(s0)}% para {_br(s1)}%.")
    # O corte da condição muda a conta: com a inflação esperada mais de 1,4 ponto acima do centro, a Selic terminou mais
    # alta em todas as 5 vezes; com o teto da meta (1,5 ponto), em 4 das 6, e ficou igual nas outras 2. Os cortes
    # vizinhos mostram quanto a conta depende do corte; o texto usa o corte da biblioteca (EVIDENCIA.md), escrito antes.
    if len(conds) == 1 and contados:
        k, o, v = conds[0]
        outros = []
        for alt in sorted({round(v - 0.5, 2), round(v + 0.5, 2)} | ({1.5} if k == "focus_menos_meta" else set())):
            if abs(alt - v) < 1e-9:
                continue
            outros.append(f"com {k} {o} {_br(alt)}, " + _frase_frequencia(*_contagem(mensal, [(k, o, alt)])))
        print("Outros cortes, para saber quanto a conta depende do corte: " + "; ".join(outros) + ". O texto usa o "
              "corte da biblioteca (EVIDENCIA.md), escrito antes, e não o que deixa a conta mais limpa.")


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


# ------------------------------------------------------------------ a tradução na vida (TRADUCAO.md)
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
            "novembro", "dezembro"]
# O repasse do dólar para o IPCA em quatro trimestres, pelas contas do Banco Central (Relatório de Política Monetária
# de março de 2026; a-repasse-bc em base/afirmacoes.json).
REPASSE_DOLAR = 0.10
# Os tipos de crédito de `traduz credito`, na ordem em que saem.
CREDITOS = ["juro_pf", "juro_rotativo", "juro_cheque_especial", "juro_pessoal", "juro_consignado_inss", "juro_veiculos",
            "juro_imobiliario"]


# Quantos dias depois do fim do mês o dado sai, em média: numa tradução de um dia passado (VDC_ATE), o mês que ainda
# não tinha saído naquele dia fica de fora. O IPCA e o INPC saem por volta do dia 10 do mês seguinte; a PNAD, uns 30
# dias depois do fim do trimestre; o juro por tipo de crédito, no fim do mês seguinte.
DIAS_ATE_SAIR = {"ipca_12m": 12, "inpc": 12, "rendimento_real": 32, "desocupacao": 32, "forca_trabalho": 32,
                 **{k: 30 for k in CREDITOS}}


def _publicada(mensal: dict, serie: str) -> dict:
    """A série só com os meses que já tinham saído no dia da tradução (VDC_ATE); sem VDC_ATE, inteira."""
    import os
    s = mensal.get(serie, {})
    ate = os.environ.get("VDC_ATE")
    lag = DIAS_ATE_SAIR.get(serie)
    if not ate or not lag or not s:
        return s
    lim = dt.date.fromisoformat(ate)

    def saiu(m: str) -> bool:
        a, b = int(m[:4]), int(m[5:7])
        fim = dt.date(a + b // 12, b % 12 + 1, 1) - dt.timedelta(days=1)
        return fim + dt.timedelta(days=lag) <= lim
    return {m: v for m, v in s.items() if saiu(m)}


def _mes_pt(m: str) -> str:
    return f"{MESES_PT[int(m[5:7]) - 1]} de {m[:4]}"


def _dia_pt(d: str) -> str:
    return f"{int(d[8:10])}/{int(d[5:7])}/{d[:4]}"


def _ultimo(s: dict) -> str | None:
    return max(s) if s else None


def _reais(x: float, casas: int = 2) -> str:
    return "R$ " + _br(x, casas)


def _num_arg(x: str, nome: str, lo: float, hi: float) -> float:
    try:
        v = float(x.replace(",", "."))
    except ValueError:
        raise SystemExit(f"traduz: {nome} tem de ser um número (recebi {x!r})") from None
    if not lo <= v <= hi:
        raise SystemExit(f"traduz: {nome} fora do intervalo de {_br(lo, 0)} a {_br(hi, 0)}")
    return v


def _falta(serie: str) -> None:
    print(f"Sem dado de {serie} no site ({SERIES.get(serie, (serie,))[0]}): esta tradução não sai hoje.")


def _inpc_acumulado(mensal: dict, de: str, ate: str) -> float | None:
    """O INPC acumulado do mês `de` ao mês `ate`, inclusive, em %; None se falta algum mês."""
    s = mensal.get("inpc", {})
    f, m = 1.0, de
    while m <= ate:
        if m not in s:
            return None
        f *= 1 + s[m] / 100
        m = _mais(m, 1)
    return 100 * (f - 1)


def tr_precos(mensal: dict, _d: dict, _a) -> None:
    s = mensal.get("ipca_12m")
    if not s:
        return _falta("ipca_12m")
    m = _ultimo(s)
    v = s[m]
    print(f"IPCA, a inflação oficial, em 12 meses até {_mes_pt(m)}: {_br(v)}%. O que custava R$ 100 em "
          f"{_mes_pt(_mais(m, -12))} passou a custar cerca de {_reais(100 * (1 + v / 100))} em {_mes_pt(m)}.")
    mi = _ultimo(mensal.get("inpc", {}))
    if mi:
        i12 = _inpc_acumulado(mensal, _mais(mi, -11), mi)
        if i12 is not None:
            print(f"INPC, que mede a cesta das famílias com renda de 1 a 5 salários mínimos e corrige o mínimo e o INSS, "
                  f"em 12 meses até {_mes_pt(mi)}: {_br(i12)}%. Por ele, R$ 100 de compras de {_mes_pt(_mais(mi, -12))} "
                  f"viraram cerca de {_reais(100 * (1 + i12 / 100))}.")
    f = mensal.get("focus_ipca_12m", {})
    mf = _ultimo(f)
    if mf:
        print(f"Para os 12 meses seguintes, os bancos (Focus) esperam IPCA de {_br(f[mf])}% (último dado de {_mes_pt(mf)}): "
              f"R$ 100 de compras de hoje custariam cerca de {_reais(100 * (1 + f[mf] / 100))} daqui a um ano. É previsão, "
              "e os bancos erram.")
    print("Fonte: IBGE (IPCA e INPC) e Banco Central (Focus). O passado é medida, não estimativa.")


def tr_dolar(_m: dict, diario: dict, a) -> None:
    d = diario.get("dolar_ptax", {})
    if a.args:
        pct = _num_arg(a.args[0], "PCT", -80, 300)
        print(f"Mudança do dólar dada: {'+' if pct > 0 else ''}{_br(pct, 1)}%.")
    else:
        if not d:
            return _falta("dolar_ptax")
        fim = max(d)
        alvo = (dt.date.fromisoformat(fim) - dt.timedelta(days=365)).isoformat()
        ini = max((x for x in d if x <= alvo), default=None)
        if not ini:
            return _falta("dolar_ptax")
        pct = 100 * (d[fim] / d[ini] - 1)
        print(f"O dólar foi de {_reais(d[ini], 4)} em {_dia_pt(ini)} para {_reais(d[fim], 4)} em {_dia_pt(fim)}: "
              f"{'alta' if pct > 0 else 'queda'} de {_br(abs(pct), 1)}% em 12 meses.")
    efeito = round(REPASSE_DOLAR * pct, 1)
    sobe = pct > 0
    print(f"Pelas contas do Banco Central (repasse de 0,10 para o IPCA em quatro trimestres, Relatório de Política "
          f"Monetária de março de 2026), cada 10% de {'alta' if sobe else 'queda'} do dólar {'sobe' if sobe else 'baixa'} "
          f"o IPCA em cerca de 1 ponto em um ano. Uma {'alta' if sobe else 'queda'} de {_br(abs(pct), 1)}%, se não voltar, "
          f"{'sobe' if sobe else 'baixa'} o IPCA em cerca de {_br(abs(efeito), 1)} ponto em 12 meses: R$ 100 de compras "
          f"ficam cerca de {_reais(abs(efeito), 2)} {'mais caros' if sobe else 'mais baratos'} do que ficariam sem essa "
          "mudança do dólar.")
    print("Força: média. É a estimativa do próprio Banco Central, uma média de muitos anos; o repasse muda com o momento "
          "da economia e com quanto a mudança do dólar parece durar. Pesa mais nos importados e no combustível.")


def _mensal_de(j: float) -> float:
    return (1 + j / 100) ** (1 / 12) - 1


def tr_parcela(_m: dict, _d: dict, a) -> None:
    if len(a.args) < 3:
        raise SystemExit("traduz parcela VALOR MESES JURO [JURO ...] (juro em % ao ano; ex.: 300000 360 11.7 15)")
    v = _num_arg(a.args[0], "VALOR", 100, 50_000_000)
    n = int(_num_arg(a.args[1], "MESES", 1, 480))
    juros = [_num_arg(x, "JURO", 0, 1000) for x in a.args[2:6]]
    res = []
    # O exemplo dito como a leitora diz: R$ 300 mil em 30 anos.
    rotulo = _reais(v, 0) + (f" (R$ {_br(v / 1000, 0)} mil)" if v >= 1000 and v % 1000 == 0 else "")
    prazo = f"{n} meses" + (f" ({n // 12} anos)" if n % 12 == 0 else "")
    for j in juros:
        i = _mensal_de(j)
        sac = v / n + v * i
        price = v / n if i == 0 else v * i / (1 - (1 + i) ** -n)
        res.append((j, i, sac, price))
        print(f"{rotulo} em {prazo} com juro de {_br(j)}% ao ano ({_br(100 * i)}% ao mês): primeira parcela de "
              f"{_reais(sac)} na tabela SAC, que começa mais alta e cai todo mês, ou parcela fixa de {_reais(price)} na "
              f"tabela Price, com {_reais(price * n, 0)} pagos no total.")
    if len(res) >= 2:
        (j0, _, s0, p0), (j1, _, s1, p1) = res[0], res[-1]
        print(f"De {_br(j0)}% para {_br(j1)}% ao ano, a primeira parcela na SAC vai de {_reais(s0)} para {_reais(s1)} "
              f"({'+' if s1 >= s0 else ''}{_reais(s1 - s0)}, {'+' if s1 >= s0 else ''}{_br(100 * (s1 / s0 - 1), 1)}%), "
              f"e a parcela fixa na Price vai de {_reais(p0)} para {_reais(p1)} "
              f"({'+' if p1 >= p0 else ''}{_br(100 * (p1 / p0 - 1), 1)}%).")
    print("A conta não tem seguro, taxas nem a correção pela TR. Vale para quem pede o crédito com esse juro; quem já "
          "tem financiamento com juro fixo continua com a mesma parcela.")


def tr_credito(mensal: dict, _d: dict, _a) -> None:
    algum = False
    for k in CREDITOS:
        s = mensal.get(k)
        if not s:
            continue
        algum = True
        m = _ultimo(s)
        v, antes = s[m], s.get(_mais(m, -12))
        txt = f"{SERIES[k][0]}: {_br(v)}% ao ano em {_mes_pt(m)}"
        if antes is not None:
            txt += f", contra {_br(antes)}% em {_mes_pt(_mais(m, -12))}"
        txt += f". R$ 1.000 devidos por um ano, sem pagar nada no meio, viram cerca de {_reais(1000 * (1 + v / 100), 0)}"
        if antes is not None:
            txt += f" (um ano antes, {_reais(1000 * (1 + antes / 100), 0)})"
        print(txt + ".")
    if not algum:
        return _falta("juro_pf")
    print("Fonte: Banco Central, juro médio das operações de crédito para pessoas físicas, com um a dois meses de "
          "atraso. A Selic não passa inteira nem logo para esses juros.")


def tr_guardado(mensal: dict, diario: dict, a) -> None:
    v = _num_arg(a.args[0], "VALOR", 1, 10_000_000) if a.args else 1000.0
    ds = diario.get("selic_meta", {})
    if ds:
        dia = max(ds)
        selic, quando = ds[dia], f"em {_dia_pt(dia)}"
    else:
        s = mensal.get("selic_meta", {})
        m = _ultimo(s)
        if not m:
            return _falta("selic_meta")
        selic, quando = s[m], f"no fim de {_mes_pt(m)}"
    i = _mensal_de(selic)
    print(f"Com a Selic em {_br(selic)}% ao ano ({quando}), {_reais(v, 0)} numa aplicação que rende o mesmo que a Selic "
          f"rendem cerca de {_reais(v * i)} por mês, ou {_reais(v * selic / 100)} em um ano, antes do imposto de renda.")
    f = mensal.get("focus_ipca_12m", {})
    mf = _ultimo(f)
    if mf:
        real = (1 + selic / 100) / (1 + f[mf] / 100) - 1
        print(f"Os bancos (Focus) esperam IPCA de {_br(f[mf])}% para os 12 meses seguintes: descontada essa inflação, "
              f"sobram cerca de {_reais(v * real)} em um ano ({_br(100 * real)}% acima da inflação), antes do imposto.")
    tr = mensal.get("tr", {})
    mt = _ultimo(tr)
    if selic > 8.5:
        regra, ao_mes = "0,5% ao mês mais a TR", 0.005
    else:
        regra, ao_mes = "70% da Selic mais a TR", _mensal_de(0.7 * selic)
    txt = (f"Na poupança, pela Lei 12.703, de 2012, com a Selic {'acima de' if selic > 8.5 else 'em ou abaixo de'} 8,5%, "
           f"o rendimento é de {regra}, sem imposto: {_reais(v * ao_mes)} por mês mais a TR")
    if mt:
        tot = (1 + ao_mes) * (1 + tr[mt] / 100) - 1
        txt += (f"; com a TR de {_mes_pt(mt)} ({_br(tr[mt], 4)}% ao mês), {_reais(v * tot)} no mês, ou cerca de "
                f"{_reais(v * ((1 + tot) ** 12 - 1))} em um ano se a TR ficar igual")
    print(txt + ".")
    print("O juro alto que encarece a parcela de quem pega empréstimo aumenta o rendimento de quem tem dinheiro guardado.")


def tr_minimo(mensal: dict, _d: dict, _a) -> None:
    sm, inpc = mensal.get("salario_minimo", {}), mensal.get("inpc", {})
    if not sm:
        return _falta("salario_minimo")
    m = _ultimo(sm)
    v = sm[m]
    m0 = m
    while _mais(m0, -1) in sm and abs(sm[_mais(m0, -1)] - v) < 1e-9:
        m0 = _mais(m0, -1)
    print(f"O salário mínimo é de {_reais(v)} desde {_mes_pt(m0)}.")
    mi = _ultimo(inpc)
    if not mi or mi < m0:
        return _falta("inpc")
    ac = _inpc_acumulado(mensal, m0, mi)
    if ac is not None:
        print(f"De {_mes_pt(m0)} a {_mes_pt(mi)}, o INPC, a inflação das famílias com renda de 1 a 5 salários mínimos, "
              f"somou {_br(ac)}%: {_reais(v)} compram hoje o que {_reais(v / (1 + ac / 100))} compravam em {_mes_pt(m0)}, "
              f"uma perda de {_br(100 * (1 - 1 / (1 + ac / 100)), 1)}% no poder de compra até agora, que o reajuste de "
              "janeiro repõe.")
    print("Em janeiro, a lei (Lei 14.663, de 2023, com o limite da Lei 15.077, de 2024) corrige o mínimo pelo INPC dos "
          "12 meses até novembro mais o crescimento do PIB de dois anos antes, com ganho acima da inflação de até 2,5%.")
    i12 = _inpc_acumulado(mensal, _mais(mi, -11), mi)
    if i12 is not None:
        nov = f"{mi[:4]}-11"
        faltam = (int(nov[:4]) - int(mi[:4])) * 12 + int(nov[5:]) - int(mi[5:])
        print(f"O INPC dos 12 meses até {_mes_pt(mi)} foi de {_br(i12)}%. Só a correção pela inflação levaria o mínimo a "
              f"cerca de {_reais(v * (1 + i12 / 100))}; com o ganho máximo de 2,5%, a cerca de "
              f"{_reais(v * (1 + i12 / 100) * 1.025)}."
              + (f" Ainda {'falta 1 mês' if faltam == 1 else f'faltam {faltam} meses'} de INPC até novembro, e o número muda com eles."
                 if faltam > 0 else ""))
        print(f"Os benefícios do INSS acima do mínimo são corrigidos em janeiro só pelo INPC do ano anterior: com o INPC dos "
              f"12 meses até {_mes_pt(mi)}, uma aposentadoria de R$ 3.000 iria para cerca de "
              f"{_reais(3000 * (1 + i12 / 100))}.")
    print("Fonte: Banco Central (salário mínimo, série 1619; INPC, série 188) e as leis do mínimo. É regra de lei: só "
          "muda se o Congresso mudar a lei.")


def tr_renda(mensal: dict, _d: dict, _a) -> None:
    s = mensal.get("rendimento_real")
    if not s:
        return _falta("rendimento_real")
    m = _ultimo(s)
    v, antes = s[m], s.get(_mais(m, -12))
    print(f"A renda média do trabalho foi de {_reais(v, 0)} por mês no trimestre até {_mes_pt(m)}, já descontada a "
          "inflação (PNAD Contínua, do IBGE, em reais do último trimestre).")
    if antes is not None:
        pct = 100 * (v / antes - 1)
        print(f"No trimestre até {_mes_pt(_mais(m, -12))}, ela foi de {_reais(antes, 0)}, nos mesmos reais de hoje: "
              + (f"alta de {_br(pct, 1)}% em um ano, já descontada a inflação." if pct >= 0 else
                 f"queda de {_br(-pct, 1)}% em um ano, já descontada a inflação: a renda subiu menos que os preços."))
    ks = sorted(s)
    topo = max(ks, key=lambda k: s[k])
    print(f"A série começa em {_mes_pt(ks[0])}. " + ("É o maior valor da série." if topo == m else
                                                     f"O maior valor da série é de {_reais(s[topo], 0)}, no trimestre até "
                                                     f"{_mes_pt(topo)}."))
    print("É uma média: quando quem ganha menos perde o emprego, ela pode subir mesmo com a vida piorando, como em 2020.")


def tr_emprego(mensal: dict, _d: dict, _a) -> None:
    s = mensal.get("desocupacao")
    if not s:
        return _falta("desocupacao")
    m = _ultimo(s)
    print(f"O desemprego foi de {_br(s[m], 1)}% no trimestre até {_mes_pt(m)} (PNAD Contínua, do IBGE).")
    ft = mensal.get("forca_trabalho", {})
    mf = _ultimo(ft)
    if mf:
        um = ft[mf] / 100  # mil pessoas
        um_txt = f"{_br(um / 1000, 1)} milhão de pessoas" if um >= 950 else f"{_br(um, 0)} mil pessoas"
        print(f"A força de trabalho (quem trabalha ou procura trabalho) era de {_br(ft[mf] / 1000, 1)} milhões de pessoas "
              f"no trimestre até {_mes_pt(mf)}: cada ponto de desemprego são cerca de {um_txt} sem trabalho, e o "
              f"desemprego de hoje são cerca de {_br(ft[mf] * s[m] / 100 / 1000, 1)} milhões de pessoas.")
    ks = sorted(s)
    # As quedas do PIB com até 4 trimestres entre uma e outra contam como uma recessão só, como a de 2014 a 2016,
    # porque o desemprego de uma ainda está subindo quando a outra começa.
    juntas: list[dict] = []
    for r in _recessoes():
        if juntas and _tri_mes(r["de"]) <= _mais(_tri_mes(juntas[-1]["ate"]), 12):
            juntas[-1] = {**juntas[-1], "ate": r["ate"]}
        else:
            juntas.append(dict(r))
    for r in juntas:
        ini = _tri_mes(r["de"])
        if ini < ks[0]:
            continue
        janela = [k for k in ks if ini <= k <= _mais(_tri_mes(r["ate"]), 12)]
        if not janela or ini not in s:
            continue
        pico = max(janela, key=lambda k: s[k])
        print(f"Nas quedas do PIB de {r['de']} a {r['ate']}, o desemprego foi de {_br(s[ini], 1)}% no trimestre até "
              f"{_mes_pt(ini)} para {_br(s[pico], 1)}% no trimestre até {_mes_pt(pico)}, o maior até 12 meses depois do "
              f"fim da recessão: {_br(s[pico] - s[ini], 1)} {'ponto' if abs(s[pico] - s[ini]) < 2 else 'pontos'} a mais.")
    print(f"A série começa em {_mes_pt(ks[0])}. O desemprego costuma subir depois que a recessão começa e cair devagar "
          "depois que ela acaba.")


TRADUZ = {"precos": tr_precos, "dolar": tr_dolar, "parcela": tr_parcela, "credito": tr_credito,
          "guardado": tr_guardado, "minimo": tr_minimo, "renda": tr_renda, "emprego": tr_emprego}
# As traduções que o código faz toda manhã e põe no caderno da pesquisa (src/fundo.py, traducoes_do_dia()).
TRADUZ_DO_DIA = ["precos", "dolar", "credito", "guardado", "minimo", "renda", "emprego"]


def cmd_traduz(mensal: dict, a) -> None:
    _, diario = _carregar()
    mensal = {**mensal, **{k: _publicada(mensal, k) for k in DIAS_ATE_SAIR}}
    TRADUZ[a.qual](mensal, diario, a)


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
    p = sub.add_parser("traduz")
    p.add_argument("qual", choices=list(TRADUZ))
    p.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "calc":
        cmd_calc(None, a)
        return
    if getattr(a, "meses", 1) > 60 or getattr(a, "passo", 1) < 1:
        raise SystemExit("--meses vai até 60 e --passo é de pelo menos 1")
    mensal, _ = _carregar()
    {"series": cmd_series, "valores": cmd_valores, "variacao": cmd_variacao, "recorde": cmd_recorde,
     "depois": cmd_depois, "ciclos": cmd_ciclos, "pausas": cmd_pausas, "parecidos": cmd_parecidos,
     "recessoes": cmd_recessoes, "focus": cmd_focus, "episodios": cmd_episodios, "traduz": cmd_traduz}[a.cmd](mensal, a)


def rodar(comando: str) -> str:
    """Roda um comando do caderno ("python src/conta.py pausas" ou só "pausas") e devolve a saída, para a conferência."""
    import shlex
    partes = shlex.split(comando)
    # A pesquisa às vezes corta a saída no terminal ("... | tail -5"): a conferência roda só a conta, e a saída inteira
    # contém as linhas que o corte mostrava.
    if "|" in partes:
        partes = partes[:partes.index("|")]
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
