import numpy as np, pandas as pd, sys, warnings
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from painel_anual import D

d = pd.read_pickle(D / "painel_anual.pkl")
g = d.groupby("ISO3")
for k in ["log_infl", "juro_real", "divida", "deficit", "cc"]:
    d[f"rel_{k}"] = d[k] - g[k].transform(lambda s: s.shift(1).rolling(10, min_periods=6).mean())
if (D / "extra_anual.pkl").exists():
    d = d.merge(pd.read_pickle(D / "extra_anual.pkl"), on=["ISO3", "year"], how="left")

EM_EXTRA = ["CHL","URY","POL","HUN","CZE","KOR","SAU","PAN","HRV","ROU","SVK","LTU","LVA","EST","ISR","TWN","SGP","HKG"]
def amostra(nome):
    a = d[(d.year >= 1980) & (d.year <= 2024) & (d["pop"] >= 1)]
    if nome == "emergentes":
        a = a[a.income_group.isin(["Upper middle income", "Lower middle income"]) | a.ISO3.isin(EM_EXTRA)]
    elif nome == "sem_baixa":
        a = a[a.income_group != "Low income"]
    return a

BLOCOS = {
  "momento": ["cresc", "cresc_3a", "hiato"],
  "niveis_fiscais_juro": ["divida", "deficit", "juro_real", "log_infl", "cc"],
  "tendencias": ["d1_log_infl", "rel_log_infl", "d3_reer", "reer_gap10", "deprec_1a", "d3_divida", "rel_divida", "d3_cc", "d1_juro_real"],
  "permanencia": ["perm_deficit3", "perm_juro5", "perm_infl10", "perm_divida_sobe", "perm_cc_neg3"],
  "global": ["cresc_mundo", "juro_real_eua", "d_juro_real_eua", "cresc_eua"],
}
EXTRA = [c for c in ("d3_credito", "credito", "credito_gap", "d1_tt", "d3_tt", "reservas", "d3_credito_fmi") if c in d.columns]
if EXTRA:
    BLOCOS["credito_externo"] = EXTRA

def modelo(tipo):
    if tipo == "logit":
        return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=40, l2_regularization=1.0)

def loco(a, X, y, tipo):
    p = pd.Series(np.nan, index=a.index)
    paises = a.ISO3.unique()
    rng = np.random.default_rng(0); rng.shuffle(paises)
    grupos = np.array_split(paises, 10)
    for gset in grupos:
        te = a.ISO3.isin(gset)
        m = modelo(tipo).fit(X[~te], y[~te])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p

def temporal(a, X, y, tipo, h):
    p = pd.Series(np.nan, index=a.index)
    for ano in range(2000, 2025, 5):
        tr = a.year <= ano - h   # só alvos já conhecidos na data
        te = (a.year > ano) & (a.year <= ano + 5)
        if te.sum() == 0: continue
        m = modelo(tipo).fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p

def avaliar(nome_amostra, tipo="logit"):
    a0 = amostra(nome_amostra)
    out = []
    for h in (1, 2, 3):
        a = a0.dropna(subset=[f"y{h}"]).copy()
        y = a[f"y{h}"].astype(int)
        cum = []
        for bloco, vs in BLOCOS.items():
            for conj, nome in ((vs, f"só {bloco}"), (None, None)):
                pass
        conjuntos = [("momento", BLOCOS["momento"]),
                     ("momento+niveis", BLOCOS["momento"] + BLOCOS["niveis_fiscais_juro"]),
                     ("momento+tendencias", BLOCOS["momento"] + BLOCOS["tendencias"]),
                     ("momento+permanencia", BLOCOS["momento"] + BLOCOS["permanencia"]),
                     ("momento+global", BLOCOS["momento"] + BLOCOS["global"]),
                     ("so_niveis", BLOCOS["niveis_fiscais_juro"]),
                     ("so_permanencia", BLOCOS["permanencia"]),
                     ("tudo", sum(BLOCOS.values(), []))]
        if EXTRA:
            conjuntos.insert(5, ("momento+credito_externo", BLOCOS["momento"] + BLOCOS["credito_externo"]))
        for nome, vs in conjuntos:
            X = a[vs].astype(float)
            X = X.clip(X.quantile(.01), X.quantile(.99), axis=1)
            for esquema in ("loco", "temporal"):
                p = loco(a, X, y, tipo) if esquema == "loco" else temporal(a, X, y, tipo, h)
                ok = p.notna()
                base = y[ok].mean()
                bs = brier_score_loss(y[ok], p[ok]); b0 = brier_score_loss(y[ok], np.full(ok.sum(), base))
                out.append({"h": h, "modelo": nome, "teste": esquema, "auc": round(roc_auc_score(y[ok], p[ok]), 3),
                            "ganho_brier_%": round(100 * (1 - bs / b0), 1), "n": int(ok.sum())})
    t = pd.DataFrame(out)
    return t.pivot_table(index=["modelo"], columns=["h", "teste"], values=["auc", "ganho_brier_%"])

if __name__ == "__main__":
    nome = sys.argv[1] if len(sys.argv) > 1 else "emergentes"
    tipo = sys.argv[2] if len(sys.argv) > 2 else "logit"
    pd.set_option("display.width", 250)
    print(nome, tipo)
    print(avaliar(nome, tipo).to_string())
