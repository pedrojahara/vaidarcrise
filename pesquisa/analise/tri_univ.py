import numpy as np, pandas as pd, warnings, sys
warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
from tri_oecd import S
P = pd.read_pickle(S / "painel_tri.pkl")
EM = ["ARG","BRA","CHL","COL","CRI","IDN","IND","MEX","RUS","SAU","TUR","ZAF","CHN","HUN","POL","CZE","SVK","EST","LVA","LTU","SVN","ISR","KOR"]
VARS = {"momento": ["g", "g_4t", "prod_ind_4t", "d4_desemp", "cli", "d2_cli", "conf_emp", "conf_cons", "d4_conf_cons"],
        "juros_inflacao": ["juro", "juro_real", "d4_juro", "d8_juro", "inclinacao", "infl", "d4_infl"],
        "mercado": ["acoes_4t"],
        "fiscal": ["divida", "rel_divida", "d3_divida", "deficit", "perm_deficit3", "perm_divida_sobe"],
        "credito_externo": ["credito", "credito_gap", "d3_credito", "cc", "reer_gap10", "d3_reer", "reservas", "curta_res"],
        "global": ["g_oecd", "g_eua"]}
def tabela(a):
    rows = []
    for bloco, vs in VARS.items():
        for v in vs:
            r = {"bloco": bloco, "var": v}
            for alvo in ("h4", "m5_12"):
                s = a[[v, alvo]].dropna()
                if len(s) < 300 or s[alvo].nunique() < 2: continue
                x = s[v].clip(s[v].quantile(.01), s[v].quantile(.99))
                q = pd.qcut(x.rank(method="first"), 5, labels=False); base = s[alvo].mean()
                r[f"auc_{alvo}"] = round(roc_auc_score(s[alvo], x), 3)
                r[f"q5/base_{alvo}"] = round(s[alvo][q == 4].mean() / base, 2); r[f"q1/base_{alvo}"] = round(s[alvo][q == 0].mean() / base, 2)
                r[f"n_{alvo}"] = len(s)
            rows.append(r)
    return pd.DataFrame(rows)
pd.set_option("display.width", 250)
for nome, a in (("todos", P), ("emergentes", P[P.pais.isin(EM)])):
    print(nome, "| h4 = recessão técnica começa nos próximos 4 trimestres; m5_12 = começa entre o 5º e o 12º trimestre (sem início antes)",
          "| taxas:", round(a.h4.mean(), 3), round(a.m5_12.mean(), 3))
    print(tabela(a).to_string(index=False))
