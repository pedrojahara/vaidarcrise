"""Baixa o histórico longo dos indicadores para a calibração (src/calibra.py).

Grava data/historico/series.json com as séries mensais (e as diárias que o modelo
usa dia a dia) desde 2002, mais o PIB trimestral desde 1996. Roda de vez em quando,
não todo dia: a calibração só muda quando alguém decide recalibrar.

Uso: python src/historico.py              (baixa tudo de novo)
     python src/historico.py --faltando    (só as séries que faltam no arquivo)

O Banco Central às vezes devolve uma página vazia em vez do JSON: cada consulta é
repetida algumas vezes, e uma série que falha mantém a versão já gravada.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAIDA = ROOT / "data" / "historico" / "series.json"
INICIO = dt.date(2002, 1, 1)

# Mesmas séries da coleta diária. A Selic e o dólar são diários e muito longos: ficam por mês.
MENSAIS = {
    "ibcbr": 24364,
    "desocupacao": 24369,
    "comprometimento_renda": 29034,
    "divida_bruta": 13762,
    "primario_12m": 5793,
}
DIARIAS_POR_MES = {"selic_meta": 432, "dolar_ptax": 1}
# Preço mundial das commodities (FMI, via FRED): o fator Cenário externo.
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
FRED_SERIES = {"commodities": "PALLFNFINDEXM"}


def com_paciencia(f, tentativas: int = 4):
    """Repete a consulta com pausas crescentes (o SGS recusa rajadas)."""
    for i in range(tentativas):
        try:
            return f()
        except Exception:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            time.sleep(15 * (i + 1))


def sgs_longo(code: int, inicio: dt.date) -> list[dict]:
    """O SGS limita consultas diárias a 10 anos: busca em blocos."""
    out: list[dict] = []
    a = inicio
    hoje = dt.date.today()
    while a <= hoje:
        b = min(dt.date(a.year + 9, 12, 31), hoje)
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
        params = {"formato": "json", "dataInicial": a.strftime("%d/%m/%Y"), "dataFinal": b.strftime("%d/%m/%Y")}
        lote = com_paciencia(lambda: fetch_data._get(url, params).json())
        out += [{"data": dt.datetime.strptime(x["data"], "%d/%m/%Y").date().isoformat(), "valor": float(x["valor"])}
                for x in lote if x.get("valor") not in (None, "")]
        a = b + dt.timedelta(days=1)
        time.sleep(2)
    dedup = {x["data"]: x for x in out if x["data"] <= hoje.isoformat()}
    return [dedup[k] for k in sorted(dedup)]


def por_mes(diaria: list[dict]) -> list[dict]:
    """Último valor de cada mês."""
    ult: dict[str, dict] = {}
    for x in diaria:
        ult[x["data"][:7]] = x
    return [{"data": k + "-01", "valor": ult[k]["valor"], "dia": ult[k]["data"]} for k in sorted(ult)]


def olinda_todos(recurso: str, filtro: str, campos: str) -> list[dict]:
    """Pagina o Olinda (o serviço devolve no máximo alguns milhares por chamada)."""
    out: list[dict] = []
    skip = 0
    while True:
        r = fetch_data._get(fetch_data._odata(f"{fetch_data.OLINDA}/{recurso}", {
            "$top": 5000, "$skip": skip, "$format": "json", "$orderby": "Data asc",
            "$filter": filtro, "$select": campos}))
        lote = r.json()["value"]
        out += lote
        if len(lote) < 5000:
            return out
        skip += 5000
        time.sleep(0.5)


def focus_ipca_12m_historico() -> list[dict]:
    vals = olinda_todos("ExpectativasMercadoInflacao12Meses",
                        "Indicador eq 'IPCA' and Suavizada eq 'S' and baseCalculo eq 0", "Data,Mediana")
    return por_mes([{"data": v["Data"], "valor": v["Mediana"]} for v in vals])


def focus_pib_historico() -> list[dict]:
    """Mediana do PIB do ano corrente e do seguinte, no último dia de cada mês."""
    vals = olinda_todos("ExpectativasMercadoAnuais", "Indicador eq 'PIB Total' and baseCalculo eq 0",
                        "Data,DataReferencia,Mediana")
    por_dia: dict[str, dict[str, float]] = {}
    for v in vals:
        por_dia.setdefault(v["Data"], {})[str(v["DataReferencia"])] = v["Mediana"]
    ult: dict[str, tuple[str, dict]] = {}
    for dia in sorted(por_dia):
        ult[dia[:7]] = (dia, por_dia[dia])
    out = []
    for mes in sorted(ult):
        dia, refs = ult[mes]
        ano = int(mes[:4])
        if str(ano) in refs and str(ano + 1) in refs:
            out.append({"data": mes + "-01", "dia": dia, "ano": refs[str(ano)], "ano_seguinte": refs[str(ano + 1)]})
    return out


def pib_desde_1996() -> list[dict]:
    hoje = dt.date.today()
    periodos = "|".join(f"{a}0{q}" for a in range(1996, hoje.year + 1) for q in range(1, 5))
    r = fetch_data._get(fetch_data.IBGE_PIB.format(periodos=periodos))
    serie = r.json()[0]["resultados"][0]["series"][0]["serie"]
    return [{"trimestre": f"{int(p[-1])}T{p[:4]}", "var_qoq": float(v)} for p, v in sorted(serie.items())
            if v not in ("...", "-", "", None, "X")]


def fred(serie: str) -> list[dict]:
    r = fetch_data._get(FRED.format(id=serie))
    linhas = r.text.strip().splitlines()[1:]
    out = []
    for ln in linhas:
        d, v = ln.split(",")[:2]
        if v not in (".", ""):
            out.append({"data": d, "valor": float(v)})
    return out


def main() -> None:
    faltando = "--faltando" in sys.argv
    antigo = json.loads(SAIDA.read_text()) if SAIDA.exists() else {"series": {}}
    res: dict = {"coletado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                 "series": dict(antigo["series"]), "erros": []}

    def tenta(nome, f):
        if faltando and res["series"].get(nome):
            return
        try:
            res["series"][nome] = com_paciencia(f)
            print(f"{nome}: {len(res['series'][nome])} pontos", flush=True)
        except Exception as e:  # noqa: BLE001
            res["erros"].append(f"{nome}: {e}")
            print(f"ERRO {nome}: {e}" + (" (fica a versão anterior)" if nome in res["series"] else ""), flush=True)
        time.sleep(2)

    for nome, code in MENSAIS.items():
        tenta(nome, lambda code=code: fetch_data.sgs(code, INICIO))
    for nome, code in DIARIAS_POR_MES.items():
        tenta(nome, lambda code=code: por_mes(sgs_longo(code, INICIO)))
    tenta("dolar_ptax_diario", lambda: sgs_longo(1, INICIO))
    tenta("juro_real_longo", lambda: fetch_data.juro_real_longo(INICIO))
    tenta("focus_ipca_12m", focus_ipca_12m_historico)
    tenta("focus_pib", focus_pib_historico)
    tenta("pib", pib_desde_1996)
    for nome, sid in FRED_SERIES.items():
        tenta(nome, lambda sid=sid: fred(sid))

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    print(f"-> {SAIDA} ({SAIDA.stat().st_size // 1024} KB), {len(res['erros'])} erros")


if __name__ == "__main__":
    main()
