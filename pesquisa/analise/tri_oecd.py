"""Painel trimestral (OECD, 48 países): o que antecipa recessão técnica em 1 ano e em 2 a 3 anos."""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
S = Path(__file__).resolve().parent.parent / "dados"
R = Path("/home/user/vaidarcrise/pesquisa/dados")

def kei():
    cache = S / "kei_q.pkl"
    if cache.exists(): return pd.read_pickle(cache)
    k = pd.read_csv(R / "oecd_kei_juro.csv", low_memory=False,
                    usecols=["REF_AREA", "FREQ", "MEASURE", "UNIT_MEASURE", "ADJUSTMENT", "TRANSFORMATION", "TIME_PERIOD", "OBS_VALUE"])
    k = k[k.MEASURE.isin(["IR3TIB", "IRSTCI", "IRLT", "CP", "SHARE", "UNEMP", "BCICP", "CCICP", "LI", "PRVM"])]
    k["data"] = pd.PeriodIndex(k.TIME_PERIOD.str.replace("-Q", "Q"), freq=None).to_timestamp() if False else None
    def per(s):
        if "Q" in s: return pd.Period(s.replace("-Q", "Q"), "Q")
        if len(s) == 7: return pd.Period(s, "M").asfreq("Q")
        return None
    k["q"] = k.TIME_PERIOD.map(per)
    k = k.dropna(subset=["q"])
    # escolhe uma variante por medida: a combinação de unidade, ajuste e transformação mais comum
    out = {}
    for m, sub in k.groupby("MEASURE"):
        combo = sub.groupby(["UNIT_MEASURE", "ADJUSTMENT", "TRANSFORMATION"]).size().sort_values(ascending=False)
        if m == "CP":
            ix = [c for c in combo.index if "IX" in c[0] and c[2] in ("_Z", "N")]
            u, a, t = ix[0] if ix else combo.index[0]
        elif m == "SHARE":
            u, a, t = ("GR", "_Z", "GY")
        else:
            nz = [c for c in combo.index if c[2] in ("_Z", "N")]
            u, a, t = nz[0] if nz else combo.index[0]
        sub = sub[(sub.UNIT_MEASURE == u) & (sub.ADJUSTMENT == a) & (sub.TRANSFORMATION == t)]
        # trimestral quando houver; senão, média dos meses
        tq = sub[sub.FREQ == "Q"].groupby(["REF_AREA", "q"]).OBS_VALUE.mean()
        tm = sub[sub.FREQ == "M"].groupby(["REF_AREA", "q"]).OBS_VALUE.mean()
        out[m] = tq.combine_first(tm)
    K = pd.DataFrame(out).reset_index().rename(columns={"REF_AREA": "pais"})
    K.to_pickle(cache)
    return K

def montar():
    pib = pd.read_pickle(S / "oecd_pib_qq.pkl")
    pib.index = pd.PeriodIndex(pib.index.str.replace("-Q", "Q"), freq="Q")
    agreg = ["USMCA", "EU", "EA", "G20", "G7", "OECDE", "OECD"]
    mundo = pib["OECD"].rename("g_oecd")
    eua = pib["USA"].rename("g_eua")
    P = pib.drop(columns=agreg).stack().rename("g").reset_index().rename(columns={"TIME_PERIOD": "q", "REF_AREA": "pais"})
    P = P.merge(kei(), on=["pais", "q"], how="left").sort_values(["pais", "q"])
    P = P.merge(mundo, left_on="q", right_index=True, how="left").merge(eua, left_on="q", right_index=True, how="left")
    g = P.groupby("pais")
    P["juro"] = P.IR3TIB.fillna(P.IRSTCI)
    P["infl"] = 100 * g.CP.pct_change(4)
    g = P.groupby("pais")
    P["juro_real"] = P.juro - P.infl
    P["d4_juro"] = g.juro.diff(4); P["d8_juro"] = g.juro.diff(8)
    P["inclinacao"] = P.IRLT - P.juro
    P["d4_infl"] = g.infl.diff(4)
    P["acoes_4t"] = P.SHARE - P.infl
    P["d4_desemp"] = g.UNEMP.diff(4)
    P["conf_emp"] = P.BCICP; P["conf_cons"] = P.CCICP
    P["d4_conf_cons"] = g.CCICP.diff(4)
    P["cli"] = P.LI; P["d2_cli"] = g.LI.diff(2)
    P["g_4t"] = g.g.transform(lambda s: s.rolling(4).sum())
    P["prod_ind_4t"] = 100 * g.PRVM.pct_change(4)
    # anuais (GMD e Banco Mundial), com um ano de defasagem para estarem publicados
    d = pd.read_pickle(S / "painel_anual.pkl")
    ex = pd.read_pickle(S / "extra_anual.pkl")
    A = d.merge(ex, on=["ISO3", "year"], how="left")
    gA = A.groupby("ISO3")
    A["rel_divida"] = A.divida - gA.divida.transform(lambda s: s.shift(1).rolling(10, min_periods=6).mean())
    cols = ["divida", "deficit", "d3_divida", "rel_divida", "perm_deficit3", "perm_divida_sobe", "cc", "reer_gap10", "d3_reer",
            "credito", "credito_gap", "d3_credito", "reservas", "curta_res"]
    A = A[["ISO3", "year"] + cols].copy(); A["year"] = A.year + 1
    P["year"] = P.q.dt.year
    P = P.merge(A.rename(columns={"ISO3": "pais"}), on=["pais", "year"], how="left")
    # alvos: recessão técnica
    out = []
    for c, df in P.groupby("pais"):
        df = df.sort_values("q").copy()
        gg = df.g.values; n = len(gg)
        neg = gg < 0
        rec = np.zeros(n, bool)
        for i in range(n - 1):
            if neg[i] and neg[i + 1]: rec[i] = rec[i + 1] = True
        for i in range(1, n):
            if rec[i - 1] and neg[i]: rec[i] = True
        for i in range(1, n - 1):
            if not rec[i] and rec[i - 1] and rec[i + 1]: rec[i] = True
        ini = (rec & ~np.r_[False, rec[:-1]]).astype(float)
        ini[np.isnan(gg)] = np.nan
        df["rec"] = rec.astype(float); df["inicio"] = ini
        for nome, (a, b) in {"h4": (1, 4), "h12": (1, 12), "m5_12": (5, 12)}.items():
            v = np.full(n, np.nan)
            for i in range(n):
                if i + b >= n: break
                jan = ini[i + a: i + b + 1]
                if np.isnan(jan).any(): continue
                v[i] = float(np.nanmax(jan) > 0)
            df[nome] = v
        df.loc[df.rec == 1, ["h4", "h12", "m5_12"]] = np.nan
        # médio prazo puro: sem início nos 4 primeiros trimestres
        df.loc[df.h4 == 1, "m5_12"] = np.nan
        out.append(df)
    P = pd.concat(out)
    P.to_pickle(S / "painel_tri.pkl")
    return P

if __name__ == "__main__":
    P = montar()
    EM = ["ARG","BRA","CHL","COL","CRI","IDN","IND","MEX","RUS","SAU","TUR","ZAF","CHN","HUN","POL","CZE","SVK","EST","LVA","LTU","SVN","ISR","KOR"]
    print("países:", P.pais.nunique(), "| inícios de recessão:", int(P.inicio.sum()), "| em emergentes:", int(P[P.pais.isin(EM)].inicio.sum()))
    for c in ["h4", "m5_12"]:
        print(c, "taxa", round(P[c].mean(), 3), "n", int(P[c].notna().sum()))
    b = P[P.pais == "BRA"].set_index("q")
    print(b.loc["2012Q1":, ["g", "rec", "inicio", "h4", "m5_12", "juro", "infl", "juro_real", "inclinacao", "acoes_4t", "conf_cons", "credito_gap"]].round(2).tail(20).to_string())
    print("inícios BRA:", b.index[b.inicio == 1].astype(str).tolist())
