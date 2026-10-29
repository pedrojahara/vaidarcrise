import numpy as np, pandas as pd, sys
from pathlib import Path
from sklearn.metrics import roc_auc_score
from painel_anual import PRED, D
d = pd.read_pickle(D / "painel_anual.pkl")
print("pop exemplo BRA 2020:", d[(d.ISO3=='BRA')&(d.year==2020)]['pop'].values)
# relativos ao próprio histórico (média dos 10 anos anteriores, sem olhar o futuro)
g = d.groupby("ISO3")
for k in ["log_infl", "juro_real", "divida", "deficit", "cc", "desemp"]:
    d[f"rel_{k}"] = d[k] - g[k].transform(lambda s: s.shift(1).rolling(10, min_periods=6).mean())
PRED["relativo"] = [f"rel_{k}" for k in ["log_infl", "juro_real", "divida", "deficit", "cc", "desemp"]]
amostra = sys.argv[1] if len(sys.argv) > 1 else "todos"
a = d[(d.year >= 1980) & (d.year <= 2024)]
a = a[a["pop"] >= 1]
if amostra == "emergentes":
    a = a[a.income_group.isin(["Upper middle income", "Lower middle income"]) | a.ISO3.isin(["CHL","URY","POL","HUN","CZE","KOR","SAU","PAN","HRV","ROU","SVK","LTU","LVA","EST","ISR","TWN","SGP","HKG"])]
elif amostra == "sem_baixa":
    a = a[a.income_group != "Low income"]
rows = []
for bloco, vs in PRED.items():
    for v in vs:
        r = {"bloco": bloco, "var": v}
        for h in (1, 2, 3):
            s = a[[v, f"y{h}"]].dropna()
            if len(s) < 300 or s[f"y{h}"].nunique() < 2:
                continue
            x = s[v].clip(s[v].quantile(.01), s[v].quantile(.99))
            auc = roc_auc_score(s[f"y{h}"], x)
            q = pd.qcut(x.rank(method="first"), 5, labels=False)
            top = s[f"y{h}"][q == 4].mean(); bot = s[f"y{h}"][q == 0].mean(); base = s[f"y{h}"].mean()
            r[f"auc{h}"] = round(auc, 3); r[f"q5/base{h}"] = round(top / base, 2); r[f"q1/base{h}"] = round(bot / base, 2); r[f"n{h}"] = len(s)
        rows.append(r)
t = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(amostra, "| taxa base:", {h: round(a[f'y{h}'].mean(), 3) for h in (1,2,3)})
print(t.to_string(index=False))
