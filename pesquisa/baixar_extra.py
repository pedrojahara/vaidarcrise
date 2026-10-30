"""Estudo: câmbio e bolsa da OCDE para o painel trimestral, e teste das séries do Banco Central e da bolsa
que a conta diária passaria a usar. Grava em pesquisa/dados/."""
import datetime as dt
import gzip
import json
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent / "dados"
OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "vaidarcrise.com.br (+https://github.com/pedrojahara/vaidarcrise)"}
R = {}


def get(url, timeout=120, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            R.setdefault("http", []).append(f"{r.status_code} {url[:120]}")
        except Exception as e:  # noqa: BLE001
            R.setdefault("erros", []).append(f"{url[:120]}: {e!r}"[:300])
        time.sleep(5 * (i + 1))
    return None


# OCDE: indicadores financeiros mensais (bolsa, juros, câmbio), todos os países
for nome, q in {
    "oecd_finmark": "OECD.SDD.STES,DSD_STES@DF_FINMARK,/all?startPeriod=1990-01&format=csv",
}.items():
    r = get("https://sdmx.oecd.org/public/rest/data/" + q, timeout=600)
    if r is not None and len(r.content) > 1000:
        (OUT / f"{nome}.csv.gz").write_bytes(gzip.compress(r.content))
        R[nome] = {"ok": True, "bytes": len(r.content), "cabecalho": r.text[:400]}
    else:
        R[nome] = {"ok": False}

# Banco Central: séries candidatas
hoje = dt.date.today()
for code in (13522, 433, 20622, 7, 11752, 4189, 1178, 12):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    ini = dt.date(2002, 1, 1) if code in (13522, 433, 20622, 11752) else hoje - dt.timedelta(days=400)
    r = get(url, params={"formato": "json", "dataInicial": ini.strftime("%d/%m/%Y"), "dataFinal": hoje.strftime("%d/%m/%Y")})
    try:
        d = r.json() if r is not None else []
        R[f"sgs_{code}"] = {"n": len(d), "primeiro": d[:1], "ultimos": d[-3:]}
        if code in (13522, 433, 20622, 11752):
            (OUT / f"sgs_{code}.json").write_text(json.dumps(d))
    except Exception as e:  # noqa: BLE001
        R[f"sgs_{code}"] = {"erro": repr(e)[:200], "texto": r.text[:200] if r is not None else None}
    time.sleep(1)

# Bolsa brasileira: fontes candidatas para a conta diária
for nome, url in {
    "stooq_bvp_m": "https://stooq.com/q/d/l/?s=%5Ebvp&i=m",
    "stooq_bvp_d": "https://stooq.com/q/d/l/?s=%5Ebvp&i=d",
    "yahoo_chart": "https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?range=2y&interval=1mo",
}.items():
    r = get(url, timeout=60)
    R[nome] = {"ok": r is not None, "inicio": (r.text[:300] if r is not None else None),
               "fim": (r.text[-300:] if r is not None else None)}

(OUT / "manifesto_extra.json").write_text(json.dumps(R, indent=1, ensure_ascii=False))
print(json.dumps(R, indent=1, ensure_ascii=False)[:4000])
