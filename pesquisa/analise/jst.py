"""JST (17 países ricos, 1870–2020): crédito, dívida pública e juros antecipam recessão em 1–3 anos?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss
j = pd.read_excel("../dados/jst_R6.xlsx").sort_values(["iso", "year"])
j = j[~j.year.between(1914, 1919) & ~j.year.between(1939, 1947)]   # fora as guerras mundiais
g = j.groupby("iso")
j["cresc"] = 100 * g.rgdpbarro.pct_change()
j["infl"] = 100 * g.cpi.pct_change()
j["cred"] = 100 * j.tloans / j.gdp
j["cred_hh"] = 100 * j.thh / j.gdp
g = j.groupby("iso")
j["d5_cred"] = g.cred.diff(5); j["d3_cred"] = g.cred.diff(3); j["d5_cred_hh"] = g.cred_hh.diff(5)
j["d3_divida"] = g.debtgdp.diff(3)
j["juro_real"] = j.stir - j.infl
j["d1_juro"] = g.stir.diff(1)
j["inclinacao"] = j.ltrate - j.stir
j["d3_casa"] = 100 * g.hpnom.pct_change(3) - 3 * j.infl
j["d1_infl"] = g.infl.diff(1)
j["cc"] = 100 * j.ca / j.gdp
j["deficit"] = 100 * (j.expenditure - j.revenue) / j.gdp
j["queda"] = (j.cresc < 0).astype(float).where(j.cresc.notna())
j["inicio"] = ((j.queda == 1) & (g.queda.shift(1) == 0)).astype(float).where(j.queda.notna() & g.queda.shift(1).notna())
g = j.groupby("iso")
for h in (1, 2, 3):
    F = pd.concat([g.inicio.shift(-k) for k in range(1, h + 1)], axis=1)
    j[f"y{h}"] = F.max(axis=1).where(F.notna().all(axis=1)); j.loc[j.queda != 0, f"y{h}"] = np.nan
    F = pd.concat([g.crisisJST.shift(-k) for k in range(1, h + 1)], axis=1)
    j[f"c{h}"] = F.max(axis=1).where(F.notna().all(axis=1))
VARS = ["d5_cred", "d3_cred", "cred", "d5_cred_hh", "d3_casa", "debtgdp", "d3_divida", "deficit", "juro_real", "d1_juro", "inclinacao", "infl", "d1_infl", "cc", "cresc"]
pd.set_option("display.width", 250)
for periodo, a in (("1950–2020", j[j.year >= 1950]), ("1870–2020", j)):
    rows = []
    for v in VARS:
        r = {"var": v}
        for alvo in ("y1", "y3", "c3"):
            s = a[[v, alvo]].dropna()
            if len(s) < 200 or s[alvo].nunique() < 2: continue
            x = s[v].clip(s[v].quantile(.01), s[v].quantile(.99))
            q = pd.qcut(x.rank(method="first"), 5, labels=False); base = s[alvo].mean()
            r[f"auc_{alvo}"] = round(roc_auc_score(s[alvo], x), 3); r[f"q5/base_{alvo}"] = round(s[alvo][q == 4].mean() / base, 2)
        rows.append(r)
    print(periodo, "| y = início de recessão em 1 ou 3 anos; c3 = crise financeira em 3 anos | taxas:",
          {k: round(a[k].mean(), 3) for k in ("y1", "y3", "c3")})
    print(pd.DataFrame(rows).to_string(index=False))
