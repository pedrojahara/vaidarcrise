import numpy as np, pandas as pd, warnings, sys
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from tri_oecd import S
P = pd.read_pickle(S / "painel_tri.pkl")
P["ano"] = P.q.dt.year
EM = ["ARG","BRA","CHL","COL","CRI","IDN","IND","MEX","RUS","SAU","TUR","ZAF","CHN","HUN","POL","CZE","SVK","EST","LVA","LTU","SVN","ISR","KOR"]
B = {"momento_mercado": ["g", "d4_conf_cons", "d2_cli", "acoes_4t", "prod_ind_4t"],
     "juros_inflacao": ["d4_juro", "d8_juro", "inclinacao", "d4_infl", "juro_real"],
     "fiscal": ["divida", "deficit", "d3_divida", "perm_deficit3", "perm_divida_sobe"],
     "credito_externo": ["credito_gap", "d3_credito", "d3_reer", "cc", "reservas"],
     "global": ["g_oecd", "g_eua"]}
CONJ = [("momento_mercado", ["momento_mercado"]), ("juros_inflacao", ["juros_inflacao"]), ("fiscal", ["fiscal"]),
        ("credito_externo", ["credito_externo"]), ("momento+juros", ["momento_mercado", "juros_inflacao"]),
        ("momento+juros+fiscal", ["momento_mercado", "juros_inflacao", "fiscal"]),
        ("momento+juros+credito_ext", ["momento_mercado", "juros_inflacao", "credito_externo"]),
        ("tudo", list(B))]
def modelo(tipo):
    if tipo == "logit":
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), LogisticRegression(C=0.1, max_iter=3000))
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=50, l2_regularization=1.0)
def temporal(a, X, y, alvo, tipo):
    lag = 1 if alvo == "h4" else 3
    p = pd.Series(np.nan, index=a.index)
    for ano in (2002, 2006, 2010, 2014, 2018, 2022):
        tr = a.ano <= ano - lag; te = (a.ano > ano) & (a.ano <= ano + 4)
        if te.sum() == 0 or y[tr].nunique() < 2: continue
        p[te] = modelo(tipo).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p
def avaliar(a0, tipo):
    out = []
    for alvo in ("h4", "m5_12"):
        a = a0.dropna(subset=[alvo]); y = a[alvo].astype(int)
        for nome, bl in CONJ:
            vs = sum((B[b] for b in bl), [])
            X = a[vs].astype(float); X = X.clip(X.quantile(.01), X.quantile(.99), axis=1)
            p = temporal(a, X, y, alvo, tipo); ok = p.notna()
            base = y[a.ano <= a.ano.max()][ok].mean()
            # referência justa: taxa média conhecida até a data (frequência histórica)
            ref = pd.Series(np.nan, index=a.index)
            lag = 1 if alvo == "h4" else 3
            for ano in (2002, 2006, 2010, 2014, 2018, 2022):
                te = (a.ano > ano) & (a.ano <= ano + 4); ref[te] = y[a.ano <= ano - lag].mean()
            bs = brier_score_loss(y[ok], p[ok]); b0 = brier_score_loss(y[ok], ref[ok])
            out.append({"alvo": alvo, "modelo": nome, "auc": round(roc_auc_score(y[ok], p[ok]), 3),
                        "ganho_brier_%": round(100 * (1 - bs / b0), 1), "n": int(ok.sum())})
    return pd.DataFrame(out).pivot_table(index="modelo", columns="alvo", values=["auc", "ganho_brier_%"])
if __name__ == "__main__":
    tipo = sys.argv[1] if len(sys.argv) > 1 else "logit"
    pd.set_option("display.width", 250)
    for nome, a in (("todos", P), ("emergentes", P[P.pais.isin(EM)])):
        print(nome, tipo, "(teste fora do tempo: cada bloco de 4 anos previsto só com o passado)")
        print(avaliar(a, tipo).to_string())
