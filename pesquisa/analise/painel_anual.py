"""Painel anual (Global Macro Database): o que antecipa o início de anos de queda do PIB em 1, 2 e 3 anos."""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "dados"

def carregar(extra=None):
    d = pd.read_stata(D / "GMD_2026_03.dta", convert_categoricals=False)
    d = d[(d.year >= 1960) & (d.year <= 2025)].copy()
    d["year"] = d.year.astype(int)
    d = d.sort_values(["ISO3", "year"])
    # população em milhões (GMD pop em milhões)
    g = d.groupby("ISO3")
    d["cresc"] = 100 * g.rGDP.pct_change()
    # mundo: média ponderada pelo PIB em dólar
    w = d.dropna(subset=["cresc", "rGDP_USD"])
    mundo = w.groupby("year").apply(lambda x: np.average(x.cresc, weights=x.rGDP_USD), include_groups=False)
    d["cresc_mundo"] = d.year.map(mundo)
    eua = d[d.ISO3 == "USA"].set_index("year")
    d["cresc_eua"] = d.year.map(eua.cresc)
    d["juro_real_eua"] = d.year.map(eua.cbrate - eua.infl)
    d["d_juro_real_eua"] = d.year.map((eua.cbrate - eua.infl).diff())
    g = d.groupby("ISO3")
    d["infl_c"] = d.infl.clip(-5, 200)
    d["log_infl"] = np.log1p(d.infl_c.clip(lower=-0.99*100) / 100)
    juro = d.cbrate.fillna(d.strate)
    d["juro_real"] = (juro - d.infl_c).clip(-50, 50)
    d["divida"] = d.gen_govdebt_GDP.fillna(d.govdebt_GDP)
    d["deficit"] = -d.gen_govdef_GDP.fillna(d.govdef_GDP)   # positivo = déficit
    d["cc"] = d.CA_GDP
    d["desemp"] = d.unemp
    g = d.groupby("ISO3")
    for k, n in (("divida", 3), ("cc", 3), ("log_infl", 1), ("juro_real", 1), ("deficit", 3), ("desemp", 1)):
        d[f"d{n}_{k}"] = g[k].diff(n)
    d["d2_log_infl"] = g["log_infl"].diff(2)
    d["deprec_1a"] = 100 * g.USDfx.pct_change().clip(-0.9, 10)
    d["log_reer"] = np.log(d.REER.where(d.REER > 0))
    g = d.groupby("ISO3")
    d["reer_gap10"] = d.log_reer - g.log_reer.transform(lambda s: s.rolling(10, min_periods=6).mean().shift(0))
    d["d3_reer"] = g.log_reer.diff(3)
    d["cresc_3a"] = g.cresc.transform(lambda s: s.rolling(3).mean())
    d["log_pib"] = np.log(d.rGDP.where(d.rGDP > 0))
    g = d.groupby("ISO3")
    # hiato: desvio do PIB em relação à tendência linear dos 10 anos anteriores (sem olhar o futuro)
    def hiato(s):
        out = np.full(len(s), np.nan); v = s.values
        for i in range(10, len(v)):
            y = v[i-10:i]
            if np.isnan(y).any() or np.isnan(v[i]): continue
            x = np.arange(10); b = np.polyfit(x, y, 1)
            out[i] = 100 * (v[i] - (b[0]*10 + b[1]))
        return pd.Series(out, index=s.index)
    d["hiato"] = g.log_pib.transform(hiato)
    # permanência: anos dos últimos 5 com a condição
    def anos(cond, n=5):
        return cond.astype(float).where(cond.notna()).groupby(d.ISO3).transform(lambda s: s.rolling(n, min_periods=n).sum())
    d["perm_deficit3"] = anos(d.deficit > 3)
    d["perm_juro5"] = anos(d.juro_real > 5)
    d["perm_infl10"] = anos(d.infl_c > 10)
    d["perm_divida_sobe"] = anos(d.groupby("ISO3").divida.diff() > 0)
    d["perm_cc_neg3"] = anos(d.cc < -3)
    # alvo: início de queda do PIB (ano com cresc < 0 depois de ano com cresc >= 0)
    d["queda"] = (d.cresc < 0).astype(float).where(d.cresc.notna())
    d["inicio"] = ((d.queda == 1) & (d.groupby("ISO3").queda.shift(1) == 0)).astype(float).where(d.queda.notna() & d.groupby("ISO3").queda.shift(1).notna())
    g = d.groupby("ISO3")
    for h in (1, 2, 3):
        fut = [g.inicio.shift(-k) for k in range(1, h+1)]
        F = pd.concat(fut, axis=1)
        y = F.max(axis=1).where(F.notna().all(axis=1))
        d[f"y{h}"] = y
    # só anos em expansão podem "começar" recessão à frente
    for h in (1, 2, 3):
        d.loc[d.queda != 0, f"y{h}"] = np.nan
    if extra is not None:
        d = d.merge(extra, on=["ISO3", "year"], how="left")
    return d

PRED = {
  "nivel": ["log_infl", "juro_real", "divida", "deficit", "cc", "desemp"],
  "tendencia": ["d3_divida", "d3_deficit", "d3_cc", "d1_log_infl", "d2_log_infl", "d1_juro_real", "deprec_1a", "d3_reer", "reer_gap10", "cresc", "cresc_3a", "hiato", "d1_desemp"],
  "permanencia": ["perm_deficit3", "perm_juro5", "perm_infl10", "perm_divida_sobe", "perm_cc_neg3"],
  "global": ["cresc_mundo", "cresc_eua", "juro_real_eua", "d_juro_real_eua"],
}

if __name__ == "__main__":
    d = carregar()
    d.to_pickle(D / "painel_anual.pkl")
    a = d[(d.year >= 1980) & (d.year <= 2024)]
    for h in (1, 2, 3):
        s = a[f"y{h}"].dropna()
        print(f"h={h}: {len(s)} país-anos, {int(s.sum())} inícios, taxa {s.mean():.3f}, países {a.loc[s.index,'ISO3'].nunique()}")
    b = d[d.ISO3 == "BRA"].set_index("year")
    print(b.loc[2010:2025, ["cresc","inicio","y1","y2","y3","juro_real","divida","deficit","hiato","perm_deficit3","perm_juro5"]].round(2).to_string())
