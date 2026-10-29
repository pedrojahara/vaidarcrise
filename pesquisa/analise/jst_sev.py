"""JST: profundidade das recessões em países ricos x crédito e dívida pública antes (Jordà-Schularick-Taylor 2013, 2016)."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
from scipy.stats import spearmanr
j = pd.read_excel("../dados/jst_R6.xlsx").sort_values(["iso", "year"])
j = j[~j.year.between(1914, 1919) & ~j.year.between(1939, 1947)]
g = j.groupby("iso")
j["lp"] = np.log(j.rgdpbarro); j["cresc"] = 100 * g.lp.diff()
j["cred"] = 100 * j.tloans / j.gdp; g = j.groupby("iso")
j["d5_cred"] = g.cred.diff(5); j["infl"] = 100 * g.cpi.pct_change(); j["juro_real"] = j.stir - j.infl
j["queda"] = (j.cresc < 0).astype(float).where(j.cresc.notna()); g = j.groupby("iso")
j["inicio"] = (j.queda == 1) & (g.queda.shift(1) == 0)
fm = pd.concat([g.lp.shift(-k) for k in range(0, 5)], axis=1).min(axis=1)
j["prof"] = 100 * (g.lp.shift(1) - fm)
j["crise"] = pd.concat([g.crisisJST.shift(-k) for k in range(-1, 3)], axis=1).max(axis=1)
for v in ("debtgdp", "d5_cred", "cred", "juro_real", "infl"):
    j[f"L_{v}"] = g[v].shift(1)
e = j[j.inicio & (j.year >= 1950)].dropna(subset=["prof"])
print(f"recessões desde 1950: {len(e)}, com crise financeira: {int(e.crise.sum())}; profundidade mediana {e.prof.median():.1f}% (normal {e.prof[e.crise==0].median():.1f}, com crise {e.prof[e.crise==1].median():.1f})")
for v in ("debtgdp", "d5_cred", "cred", "juro_real", "infl"):
    s = e[[f"L_{v}", "prof", "crise"]].dropna(); t = pd.qcut(s[f"L_{v}"].rank(method="first"), 3, labels=False)
    r = spearmanr(s[f"L_{v}"], s.prof)
    print(f"{v:10s} n={len(s)} rho={r.statistic:+.2f} p={r.pvalue:.3f}  prof terço baixo {s.prof[t==0].median():.1f}% alto {s.prof[t==2].median():.1f}%  | só crises: rho={spearmanr(s[s.crise==1][f'L_{v}'], s[s.crise==1].prof).statistic:+.2f} (n={int(s.crise.sum())})")
