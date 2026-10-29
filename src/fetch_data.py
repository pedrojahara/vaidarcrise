"""Coleta os indicadores econômicos (BCB SGS, Focus/Olinda, IBGE, Tesouro Direto e FMI via FRED)
e grava um snapshot com data de coleta em data/raw/<data>/indicadores.json.

Cada série é guardada como veio da fonte, com a data em que foi coletada, porque
PIB e IBC-Br são revisados e o backtest precisa saber o que se sabia em cada dia.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import time
from pathlib import Path

import requests
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "vaidarcrise.com.br (+https://github.com/pedrojahara/vaidarcrise)"}

SGS = {
    "ibcbr": (24364, "IBC-Br dessazonalizado (índice)"),
    "desocupacao": (24369, "Taxa de desocupação, PNAD Contínua (%)"),
    "selic_meta": (432, "Selic meta (% a.a.)"),
    "comprometimento_renda": (29034, "Comprometimento de renda das famílias com dívidas, dessazonalizado (%)"),
    "divida_bruta": (13762, "Dívida bruta do governo geral (% do PIB)"),
    "primario_12m": (5793, "Resultado primário do setor público, 12 meses (% do PIB, + = déficit)"),
    "dolar_ptax": (1, "Dólar PTAX venda (R$)"),
}
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
# Taxas do Tesouro Direto, todos os títulos, desde 2002 (Tesouro Transparente). Sai em D-1.
TESOURO = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
           "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
TESOURO_CACHE = ROOT / "data" / "raw" / "tesouro_direto.csv"
# Índice de preços de todas as commodities do FMI, mensal (fator Cenário externo).
FRED_COMMODITIES = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PALLFNFINDEXM"
IBGE_PIB = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/5932/periodos/{periodos}"
    "/variaveis/6564?localidades=N1[all]&classificacao=11255[90707]"
)


def _odata(url: str, params: dict) -> str:
    # O Olinda recusa "+" como espaço: monta a query com %20.
    safe = "',"
    return url + "?" + "&".join(f"{k}={quote(str(v), safe=safe)}" for k, v in params.items())


def _get(url: str, params: dict | None = None, tries: int = 3) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=40)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} em {r.url}")
        except requests.RequestException as e:  # noqa: PERF203
            last = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"falha ao buscar {url}: {last}")


def sgs(code: int, inicio: dt.date) -> list[dict]:
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    r = _get(url, {"formato": "json", "dataInicial": inicio.strftime("%d/%m/%Y"),
                   "dataFinal": dt.date.today().strftime("%d/%m/%Y")})
    rows = [{"data": dt.datetime.strptime(x["data"], "%d/%m/%Y").date().isoformat(),
             "valor": float(x["valor"])} for x in r.json() if x.get("valor") not in (None, "")]
    rows.sort(key=lambda x: x["data"])
    # SGS repete a Selic meta para datas futuras até a próxima reunião: corta no dia da coleta.
    hoje = dt.date.today().isoformat()
    return [x for x in rows if x["data"] <= hoje]


def focus_anual(indicador: str) -> list[dict]:
    r = _get(_odata(f"{OLINDA}/ExpectativasMercadoAnuais", {
        "$top": 40, "$format": "json", "$orderby": "Data desc",
        "$filter": f"Indicador eq '{indicador}' and baseCalculo eq 0",
        "$select": "Data,DataReferencia,Mediana,numeroRespondentes"}))
    vals = r.json()["value"]
    ultima = vals[0]["Data"]
    return [v for v in vals if v["Data"] == ultima]


def focus_ipca_12m() -> dict:
    r = _get(_odata(f"{OLINDA}/ExpectativasMercadoInflacao12Meses", {
        "$top": 1, "$format": "json", "$orderby": "Data desc",
        "$filter": "Indicador eq 'IPCA' and Suavizada eq 'S' and baseCalculo eq 0",
        "$select": "Data,Mediana,numeroRespondentes"}))
    return r.json()["value"][0]


def pib_trimestral() -> list[dict]:
    hoje = dt.date.today()
    periodos = "|".join(f"{a}0{q}" for a in range(2023, hoje.year + 1) for q in range(1, 5))
    r = _get(IBGE_PIB.format(periodos=periodos))
    serie = r.json()[0]["resultados"][0]["series"][0]["serie"]
    out = []
    for per, val in sorted(serie.items()):
        if val in ("...", "-", "", None, "X"):
            continue
        out.append({"trimestre": f"{int(per[-1])}T{per[2:4]}", "periodo": per, "var_qoq": float(val)})
    return out


def juro_real_longo(inicio: dt.date) -> list[dict]:
    """Taxa de venda (manhã) do Tesouro IPCA+ com vencimento mais perto de 10 anos, dia a dia.

    O arquivo tem uns 15 MB e fica numa cópia local fora do git: se o download falhar, a
    cópia de até 5 dias vale; mais velha que isso, o indicador sai da conta naquele dia.
    """
    try:
        texto = _get(TESOURO).content.decode("latin-1")
        TESOURO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TESOURO_CACHE.write_text(texto, encoding="latin-1")
    except Exception:  # noqa: BLE001
        idade = (dt.datetime.now().timestamp() - TESOURO_CACHE.stat().st_mtime) / 86400 if TESOURO_CACHE.exists() else 99
        if idade > 5:
            raise
        texto = TESOURO_CACHE.read_text(encoding="latin-1")
    por_dia: dict[dt.date, list[tuple[dt.date, float]]] = {}
    for linha in csv.DictReader(io.StringIO(texto), delimiter=";"):
        if linha.get("Tipo Titulo", "").strip() != "Tesouro IPCA+":
            continue
        try:
            base = dt.datetime.strptime(linha["Data Base"], "%d/%m/%Y").date()
            venc = dt.datetime.strptime(linha["Data Vencimento"], "%d/%m/%Y").date()
            taxa = float(linha["Taxa Venda Manha"].replace(",", "."))
        except (KeyError, ValueError):
            continue
        if base >= inicio and taxa > 0:
            por_dia.setdefault(base, []).append((venc, taxa))
    out = []
    for base in sorted(por_dia):
        alvo = base + dt.timedelta(days=3652)
        venc, taxa = min(por_dia[base], key=lambda t: abs((t[0] - alvo).days))
        out.append({"data": base.isoformat(), "valor": taxa, "vencimento": venc.isoformat()})
    return out


def commodities(inicio: dt.date) -> list[dict]:
    r = _get(FRED_COMMODITIES)
    out = []
    for linha in r.text.strip().splitlines()[1:]:
        d, v = linha.split(",")[:2]
        if v not in (".", "") and d >= inicio.isoformat():
            out.append({"data": d, "valor": float(v)})
    return out


def coletar() -> dict:
    hoje = dt.date.today()
    # 4 anos: a média de 36 meses do comprometimento de renda precisa de 37 meses de dado, com folga.
    inicio = hoje - dt.timedelta(days=4 * 365)
    snap: dict = {"coletado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                  "series": {}, "focus": {}, "erros": []}
    for key, (code, nome) in SGS.items():
        try:
            snap["series"][key] = {"codigo_sgs": code, "nome": nome, "dados": sgs(code, inicio),
                                   "fonte": f"https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint?codigo={code}"}
        except Exception as e:  # noqa: BLE001
            snap["erros"].append(f"SGS {code}: {e}")
        time.sleep(0.5)
    # Três anos de mediana para hoje e para a rodada de 30 dias atrás, com folga.
    try:
        snap["series"]["juro_real_longo"] = {
            "nome": "Tesouro IPCA+ de cerca de 10 anos, taxa de venda pela manhã (% a.a.)",
            "dados": juro_real_longo(hoje - dt.timedelta(days=3 * 365 + 90)),
            "fonte": "https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto"}
    except Exception as e:  # noqa: BLE001
        snap["erros"].append(f"Tesouro Direto: {e}")
    try:
        snap["series"]["commodities"] = {"nome": "Índice de preços de todas as commodities do FMI (2016 = 100)",
                                         "dados": commodities(inicio),
                                         "fonte": "https://fred.stlouisfed.org/series/PALLFNFINDEXM"}
    except Exception as e:  # noqa: BLE001
        snap["erros"].append(f"FRED commodities: {e}")
    for ind in ("PIB Total", "IPCA", "Selic", "Câmbio"):
        try:
            snap["focus"][ind] = focus_anual(ind)
        except Exception as e:  # noqa: BLE001
            snap["erros"].append(f"Focus {ind}: {e}")
    try:
        snap["focus"]["IPCA 12m"] = focus_ipca_12m()
    except Exception as e:  # noqa: BLE001
        snap["erros"].append(f"Focus IPCA 12m: {e}")
    try:
        snap["pib"] = pib_trimestral()
    except Exception as e:  # noqa: BLE001
        snap["erros"].append(f"IBGE PIB: {e}")
    return snap


def main() -> Path:
    snap = coletar()
    out = ROOT / "data" / "raw" / dt.date.today().isoformat() / "indicadores.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    print(f"indicadores: {len(snap['series'])} séries, {len(snap['erros'])} erros -> {out}")
    for e in snap["erros"]:
        print("  ERRO", e)
    return out


if __name__ == "__main__":
    main()
