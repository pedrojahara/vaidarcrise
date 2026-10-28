"""Coleta os indicadores econômicos (BCB SGS, Focus/Olinda, IBGE) e grava um
snapshot com data de coleta em data/raw/<data>/indicadores.json.

Cada série é guardada como veio da fonte, com a data em que foi coletada, porque
PIB e IBC-Br são revisados e o backtest precisa saber o que se sabia em cada dia.
"""
from __future__ import annotations

import datetime as dt
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


def coletar() -> dict:
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=3 * 365)
    snap: dict = {"coletado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                  "series": {}, "focus": {}, "erros": []}
    for key, (code, nome) in SGS.items():
        try:
            snap["series"][key] = {"codigo_sgs": code, "nome": nome, "dados": sgs(code, inicio),
                                   "fonte": f"https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint?codigo={code}"}
        except Exception as e:  # noqa: BLE001
            snap["erros"].append(f"SGS {code}: {e}")
        time.sleep(0.5)
    for ind in ("PIB Total", "IPCA", "Selic"):
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
