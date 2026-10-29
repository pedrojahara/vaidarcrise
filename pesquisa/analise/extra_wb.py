import json, numpy as np, pandas as pd
from painel_anual import D
wb = json.loads((D / "banco_mundial.json").read_text())
frames = []
for nome, linhas in wb.items():
    if not linhas: continue
    f = pd.DataFrame(linhas).rename(columns={"iso3": "ISO3", "ano": "year", "valor": nome})
    f = f[f.ISO3.astype(str).str.len() == 3].drop_duplicates(["ISO3", "year"])
    frames.append(f.set_index(["ISO3", "year"])[[nome]])
X = pd.concat(frames, axis=1).reset_index().sort_values(["ISO3", "year"])
X = X[X.ISO3.str.len() == 3]
g = X.groupby("ISO3")
cred = X.credito_privado_pib.fillna(X.credito_bancos_pib)
X["credito"] = cred
g = X.groupby("ISO3")
X["d3_credito"] = g.credito.diff(3)
X["d1_credito"] = g.credito.diff(1)
X["credito_gap"] = X.credito - g.credito.transform(lambda s: s.shift(1).rolling(10, min_periods=6).mean())
X["log_tt"] = np.log(X.termos_de_troca.where(X.termos_de_troca > 0))
g = X.groupby("ISO3")
X["d1_tt"] = 100 * g.log_tt.diff(1); X["d3_tt"] = 100 * g.log_tt.diff(3)
X["reservas"] = X.reservas_meses_importacao
X["curta_res"] = X.divida_curta_sobre_reservas
X["div_ext"] = X.divida_externa_rnb
X["commodities_exp"] = X[["exporta_combustivel", "exporta_metais", "exporta_alimentos", "exporta_agro"]].sum(axis=1, min_count=1)
X["npl"] = X.inadimplencia_bancos
keep = ["ISO3", "year", "credito", "d3_credito", "d1_credito", "credito_gap", "d1_tt", "d3_tt", "reservas", "curta_res", "div_ext", "commodities_exp", "npl"]
X[keep].to_pickle(D / "extra_anual.pkl")
b = X[X.ISO3 == "BRA"].set_index("year")[keep[2:]]
print(b.loc[2000:2025].round(1).to_string())
