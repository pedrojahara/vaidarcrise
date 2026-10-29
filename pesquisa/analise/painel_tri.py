"""Painel trimestral: recessão técnica (dois trimestres seguidos de queda do PIB) em ~60 países."""
import json, numpy as np, pandas as pd
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "dados" / "gh"

def serie_tri(js, agreg="last"):
    out = {}
    for c, v in js.items():
        s = pd.Series({pd.Timestamp(d): x for d, x in v["serie"]}).sort_index()
        s = s[~s.index.duplicated()]
        q = s.resample("QE").last() if agreg == "last" else s.resample("QE").mean()
        out[c] = q
    return pd.DataFrame(out)

def carregar():
    L = lambda n: json.loads((D / f"fred_{n}.json").read_text()) if (D / f"fred_{n}.json").exists() else {}
    pib = serie_tri(L("pib_real_sa"))
    cred = serie_tri(L("credito_privado_pib"))
    cred_f = serie_tri(L("credito_familias_pib"))
    cred_e = serie_tri(L("credito_empresas_pib"))
    juro = serie_tri(L("juro_curto"), "mean")
    juro_l = serie_tri(L("juro_longo"), "mean")
    reer = serie_tri(L("cambio_real_efetivo"), "mean")
    imov = serie_tri(L("imovel_real"))
    cpi = serie_tri(L("cpi"), "mean")
    des = serie_tri(L("desemprego"), "mean")
    G = json.loads((D / "fred_globais.json").read_text()) if (D / "fred_globais.json").exists() else {}
    glob = pd.DataFrame({k: serie_tri({k: v}, "mean")[k] for k, v in G.items()}) if G else pd.DataFrame()
    linhas = []
    for c in pib.columns:
        y = pib[c].dropna()
        if len(y) < 40: continue
        df = pd.DataFrame({"pib": y})
        df["g"] = 100 * np.log(df.pib).diff()
        for nome, tab in (("cred", cred), ("cred_f", cred_f), ("cred_e", cred_e), ("juro", juro), ("juro_l", juro_l),
                          ("reer", reer), ("imov", imov), ("cpi", cpi), ("des", des)):
            if c in tab.columns: df[nome] = tab[c]
        df["pais"] = c
        linhas.append(df)
    P = pd.concat(linhas).reset_index().rename(columns={"index": "data"})
    if not glob.empty:
        P = P.merge(glob, left_on="data", right_index=True, how="left")
    return P

def alvos(P, juntar=True):
    out = []
    for c, df in P.groupby("pais"):
        df = df.sort_values("data").copy()
        g = df.g.values
        neg = g < 0
        rec = np.zeros(len(g), bool)
        for i in range(len(g) - 1):
            if neg[i] and neg[i + 1]:
                rec[i] = rec[i + 1] = True
        # estender: quedas seguidas dentro de um episódio
        for i in range(1, len(g)):
            if rec[i - 1] and neg[i]: rec[i] = True
        if juntar:  # um trimestre de alta entre quedas não separa episódios
            for i in range(1, len(g) - 1):
                if not rec[i] and rec[i - 1] and rec[i + 1]: rec[i] = True
        inicio = rec & ~np.r_[False, rec[:-1]]
        df["rec"] = rec.astype(float); df["inicio"] = inicio.astype(float)
        df.loc[df.g.isna(), ["rec", "inicio"]] = np.nan
        n = len(df)
        for nome, (a, b) in {"h4": (1, 4), "h8": (1, 8), "h12": (1, 12), "m5_12": (5, 12)}.items():
            v = np.full(n, np.nan)
            ini = df.inicio.values
            for i in range(n):
                if i + b >= n: break
                jan = ini[i + a: i + b + 1]
                if np.isnan(jan).any(): continue
                v[i] = float(jan.max() > 0)
            df[nome] = v
            df.loc[df.rec == 1, nome] = np.nan   # só prever a partir de expansão
        out.append(df)
    return pd.concat(out)
