"""Baixa dados de vários países para testar o que antecipa recessão (estudo, fora do site).

Roda numa ação do GitHub, porque a nuvem de trabalho não alcança esses servidores.
Cada fonte que falhar fica registrada em pesquisa/dados/manifesto.json; o resto segue.
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent / "dados"
OUT.mkdir(parents=True, exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (pesquisa vaidarcrise)"
MANIFESTO: dict[str, dict] = {}

PAISES = ("AR AT AU BE BG BO BR CA CH CL CN CO CR CY CZ DE DK EC EE EG ES FI FR GB GR HK HR HU ID IE IL IN IS IT "
          "JP KR LT LU LV MA MT MX MY NG NL NO NZ PE PH PK PL PT PY RO RS RU SA SE SG SI SK TH TR TW UA US UY VN "
          "ZA").split()


def baixar(url: str, timeout: int = 120, tentativas: int = 3) -> bytes | None:
    for i in range(tentativas):
        try:
            r = S.get(url, timeout=timeout)
            if r.status_code == 200 and r.content:
                return r.content
            if r.status_code in (400, 404):
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (i + 1))
    return None


def registrar(nome: str, ok: bool, **extra) -> None:
    MANIFESTO[nome] = {"ok": ok, **extra}
    print(("OK   " if ok else "FALHA"), nome, extra.get("url", ""), extra.get("linhas", ""))


# ---------------------------------------------------------------- BIS: crédito, hiato, serviço da dívida
def bis() -> None:
    for fluxo in ("WS_TC", "WS_CREDIT_GAP", "WS_DSR", "WS_CBPOL", "WS_EER", "WS_SPP", "WS_DEBT_SEC2_PUB"):
        urls = [f"https://data.bis.org/static/bulk/{fluxo}_csv_flat.zip",
                f"https://stats.bis.org/api/v1/data/{fluxo}/all/all?format=csv",
                f"https://stats.bis.org/api/v2/data/dataflow/BIS/{fluxo}/1.0/*?format=csv"]
        feito = False
        for u in urls:
            b = baixar(u, timeout=600)
            if not b:
                continue
            if b[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(b))
                nome = z.namelist()[0]
                (OUT / f"bis_{fluxo}.csv").write_bytes(z.read(nome))
            else:
                (OUT / f"bis_{fluxo}.csv").write_bytes(b)
            registrar(f"bis_{fluxo}", True, url=u, bytes=(OUT / f"bis_{fluxo}.csv").stat().st_size)
            feito = True
            break
        if not feito:
            registrar(f"bis_{fluxo}", False, url=urls[0])


# ---------------------------------------------------------------- FRED (sem chave): PIB trimestral e outros
def fred_serie(sid: str) -> list[tuple[str, float]] | None:
    b = baixar(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=60, tentativas=2)
    if not b:
        return None
    linhas = b.decode("utf-8", "replace").strip().splitlines()[1:]
    out = []
    for ln in linhas:
        d, _, v = ln.partition(",")
        try:
            out.append((d, float(v)))
        except ValueError:
            continue
    return out or None


def fred() -> None:
    modelos = {
        "pib_real_sa": ["NGDPRSAXDC{c}Q", "CLVMNACSCAB1GQ{c}", "NAEXKP01{c}Q189S"],
        "credito_privado_pib": ["Q{c}PAM770A"],
        "credito_familias_pib": ["Q{c}HAM770A"],
        "credito_empresas_pib": ["Q{c}NAM770A"],
        "credito_governo_pib": ["Q{c}GAM770A"],
        "juro_curto": ["IR3TIB01{c}M156N", "INTDSR{c}M193N", "IRSTCI01{c}M156N"],
        "juro_longo": ["IRLTLT01{c}M156N"],
        "cambio_real_efetivo": ["RB{c}BIS"],
        "imovel_real": ["Q{c}R628BIS"],
        "cpi": ["{c3}CPIALLMINMEI", "FPCPITOTLZG{c3}"],
        "desemprego": ["LRHUTTTT{c}M156S", "LRUNTTTT{c}Q156S"],
    }
    iso3 = json.loads((Path(__file__).resolve().parent / "iso.json").read_text())
    dados: dict[str, dict[str, dict]] = {k: {} for k in modelos}
    for c in PAISES:
        for var, ids in modelos.items():
            for m in ids:
                sid = m.format(c=c, c3=iso3.get(c, c))
                s = fred_serie(sid)
                time.sleep(0.4)
                if s:
                    dados[var][c] = {"id": sid, "serie": s}
                    break
    for var, d in dados.items():
        (OUT / f"fred_{var}.json").write_text(json.dumps(d))
        registrar(f"fred_{var}", bool(d), paises=sorted(d))
    globais = {"vix": "VIXCLS", "fed_funds": "FEDFUNDS", "us_10a_3m": "T10Y3M", "us_recessao": "USREC",
               "commodities_fmi": "PALLFNFINDEXM", "petroleo_brent": "POILBREUSDM", "dolar_amplo": "DTWEXBGS",
               "dolar_amplo_antigo": "TWEXBMTH", "us_baa_10a": "BAA10YM", "pib_mundo_fmi": "NYGDPMKTPKDWLD",
               "us_juro_real_10a": "REAINTRATREARAT10Y", "embi_proxy_hy": "BAMLH0A0HYM2"}
    g = {}
    for k, sid in globais.items():
        s = fred_serie(sid)
        if s:
            g[k] = {"id": sid, "serie": s}
        time.sleep(0.4)
    (OUT / "fred_globais.json").write_text(json.dumps(g))
    registrar("fred_globais", bool(g), series=sorted(g))


# ---------------------------------------------------------------- Banco Mundial (anual)
def banco_mundial() -> None:
    ind = {"FS.AST.PRVT.GD.ZS": "credito_privado_pib", "FD.AST.PRVT.GD.ZS": "credito_bancos_pib",
           "FI.RES.TOTL.MO": "reservas_meses_importacao", "DT.DOD.DSTC.IR.ZS": "divida_curta_sobre_reservas",
           "TT.PRI.MRCH.XD.WD": "termos_de_troca", "FR.INR.RINR": "juro_real", "FR.INR.LEND": "juro_emprestimo",
           "FB.AST.NPER.ZS": "inadimplencia_bancos", "DT.DOD.DECT.GN.ZS": "divida_externa_rnb",
           "TX.VAL.FUEL.ZS.UN": "exporta_combustivel", "TX.VAL.MMTL.ZS.UN": "exporta_metais",
           "TX.VAL.FOOD.ZS.UN": "exporta_alimentos", "TX.VAL.AGRI.ZS.UN": "exporta_agro",
           "BN.KLT.DINV.CD.WD": "ied", "NY.GDP.MKTP.KD.ZG": "pib_cresc", "FP.CPI.TOTL.ZG": "inflacao",
           "GC.DOD.TOTL.GD.ZS": "divida_governo_central", "BN.CAB.XOKA.GD.ZS": "conta_corrente_pib",
           "FM.LBL.BMNY.GD.ZS": "m2_pib", "CM.MKT.LCAP.GD.ZS": "bolsa_pib"}
    tudo = {}
    for cod, nome in ind.items():
        u = f"https://api.worldbank.org/v2/country/all/indicator/{cod}?format=json&per_page=20000&date=1960:2025"
        b = baixar(u, timeout=180)
        try:
            j = json.loads(b) if b else None
            linhas = [{"iso3": x["countryiso3code"], "ano": int(x["date"]), "valor": x["value"]}
                      for x in (j[1] if j and len(j) > 1 and j[1] else []) if x["value"] is not None]
        except (ValueError, TypeError, KeyError):
            linhas = []
        tudo[nome] = linhas
        registrar(f"wb_{nome}", bool(linhas), url=u, linhas=len(linhas))
    (OUT / "banco_mundial.json").write_text(json.dumps(tudo))


# ---------------------------------------------------------------- FMI DataMapper (anual): dívida privada
def fmi() -> None:
    tudo = {}
    for cod in ("PVD_LS", "HH_LS", "NFC_LS", "GG_DEBT_GDP", "CG_DEBT_GDP", "PS_DEBT_GDP", "GGXWDG_NGDP",
                "GGXCNL_NGDP", "BCA_NGDPD", "NGDP_RPCH", "PCPIPCH"):
        u = f"https://www.imf.org/external/datamapper/api/v1/{cod}"
        b = baixar(u, timeout=180)
        try:
            j = json.loads(b) if b else None
            vals = j["values"][cod] if j and "values" in j and cod in j["values"] else {}
        except (ValueError, KeyError, TypeError):
            vals = {}
        tudo[cod] = vals
        registrar(f"fmi_{cod}", bool(vals), url=u, paises=len(vals))
    (OUT / "fmi_datamapper.json").write_text(json.dumps(tudo))


# ---------------------------------------------------------------- JST Macrohistory (anual, 18 países ricos)
def jst() -> None:
    for u in ("https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.xlsx",
              "https://www.macrohistory.net/app/download/9834512569/JSTdatasetR6.xlsx"):
        b = baixar(u, timeout=180)
        if b and b[:2] == b"PK":
            (OUT / "jst_R6.xlsx").write_bytes(b)
            registrar("jst_R6", True, url=u)
            return
    registrar("jst_R6", False)


if __name__ == "__main__":
    for f in (bis, fred, banco_mundial, fmi, jst):
        try:
            f()
        except Exception as e:  # uma fonte quebrada não derruba as outras
            registrar(f.__name__, False, erro=repr(e))
    (OUT / "manifesto.json").write_text(json.dumps(MANIFESTO, indent=1, ensure_ascii=False))
