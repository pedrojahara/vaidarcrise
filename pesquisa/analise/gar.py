"""Crescimento em risco: os indicadores deslocam a cauda ruim (10% piores) do crescimento futuro?"""
import numpy as np, pandas as pd, warnings, sys
warnings.filterwarnings("ignore")
import statsmodels.api as sm
import multivariada as M
d = M.d
g = d.groupby("ISO3")
for h in (1, 2, 3):
    F = pd.concat([g.cresc.shift(-k) for k in range(1, h + 1)], axis=1)
    d[f"min{h}"] = F.min(axis=1).where(F.notna().all(axis=1))
    d[f"med{h}"] = F.mean(axis=1).where(F.notna().all(axis=1))
def pinball(y, q, tau):
    e = y - q
    return np.mean(np.maximum(tau * e, (tau - 1) * e))
nome = sys.argv[1] if len(sys.argv) > 1 else "emergentes"
a0 = M.amostra(nome)
tau = 0.10
vars_ = [v for v in sum(M.BLOCOS.values(), []) if v != "cresc"]
rows = []
for v in vars_:
    r = {"var": v}
    for alvo in ("med1", "med3"):
        a = a0[[v, alvo, "ISO3", "cresc"]].dropna()
        if len(a) < 400: continue
        x = a[v].clip(a[v].quantile(.01), a[v].quantile(.99))
        z = (x - x.mean()) / x.std()
        X = sm.add_constant(pd.DataFrame({"z": z, "cresc": a.cresc.clip(-15, 20)}))
        res = sm.QuantReg(a[alvo].clip(-30, 30), X).fit(q=tau)
        # fora da amostra: 10 grupos de países
        paises = a.ISO3.unique(); rng = np.random.default_rng(0); rng.shuffle(paises)
        perdas_m, perdas_0 = [], []
        for gs in np.array_split(paises, 10):
            te = a.ISO3.isin(gs).values
            yt = a[alvo].clip(-30, 30).values
            rm = sm.QuantReg(yt[~te], X.values[~te]).fit(q=tau)
            r0 = sm.QuantReg(yt[~te], X[["const", "cresc"]].values[~te]).fit(q=tau)
            perdas_m.append(pinball(yt[te], X.values[te] @ rm.params, tau) * te.sum())
            perdas_0.append(pinball(yt[te], X[["const", "cresc"]].values[te] @ r0.params, tau) * te.sum())
        r[f"{alvo}_coef"] = round(res.params["z"], 2); r[f"{alvo}_t"] = round(res.tvalues["z"], 1)
        r[f"{alvo}_ganho_oos_%"] = round(100 * (1 - sum(perdas_m) / sum(perdas_0)), 1)
    rows.append(r)
pd.set_option("display.width", 250)
print(nome, "| cauda de 10% do crescimento médio no ano seguinte (med1) e nos 3 anos seguintes (med3); coef = efeito de 1 desvio-padrão, em p.p.; ganho fora da amostra sobre modelo só com o crescimento atual")
print(pd.DataFrame(rows).to_string(index=False))
