"""AUC com sinal fixado pela teoria antes de olhar (risco = valor alto, salvo indicado), em 3 painéis e 2 prazos."""
import numpy as np, pandas as pd, warnings, json
warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
from painel_anual import D
EM_EXTRA = ["CHL","URY","POL","HUN","CZE","KOR","SAU","PAN","HRV","ROU","SVK","LTU","LVA","EST","ISR","TWN","SGP","HKG"]
d = pd.read_pickle(D/"painel_anual.pkl").merge(pd.read_pickle(D/"extra_anual.pkl"), on=["ISO3","year"], how="left").sort_values(["ISO3","year"])
g = d.groupby("ISO3")
d["rel_log_infl"] = d.log_infl - g.log_infl.transform(lambda s: s.shift(1).rolling(10, min_periods=6).mean())
F = pd.concat([g.inicio.shift(-k) for k in range(1, 6)], axis=1)
d["y5"] = F.max(axis=1).where(F.notna().all(axis=1)); d.loc[d.queda != 0, "y5"] = np.nan
F = pd.concat([g.inicio.shift(-k) for k in range(2, 4)], axis=1)
d["y23"] = F.max(axis=1).where(F.notna().all(axis=1)); d.loc[(d.queda != 0) | (d.y1 == 1), "y23"] = np.nan
a = d[(d.year>=1980)&(d.year<=2024)&(d["pop"]>=1)]
em = a[a.income_group.isin(["Upper middle income","Lower middle income"])|a.ISO3.isin(EM_EXTRA)]
def auc(df, v, alvo, sinal=1):
    s = df[[v, alvo]].dropna()
    if len(s) < 150 or s[alvo].nunique() < 2: return None
    return round(roc_auc_score(s[alvo], sinal * s[v]), 3)
rows = []
A = [("Dívida pública, nível", "divida", 1, "fiscal"), ("Déficit, nível", "deficit", 1, "fiscal"), ("Juro real, nível", "juro_real", 1, "juro"),
     ("Inflação, nível", "log_infl", 1, "inflacao"), ("Déficit >3% em 5 anos (permanência)", "perm_deficit3", 1, "fiscal"),
     ("Juro real >5% em 5 anos (permanência)", "perm_juro5", 1, "juro"), ("Inflação >10% em 5 anos (permanência)", "perm_infl10", 1, "inflacao"),
     ("Dívida subindo em 5 anos (permanência)", "perm_divida_sobe", 1, "fiscal"), ("Dívida, alta em 3 anos", "d3_divida", 1, "fiscal"),
     ("Inflação acima da média do país", "rel_log_infl", 1, "inflacao"), ("Câmbio real acima da média de 10 anos", "reer_gap10", 1, "externo"),
     ("Dívida externa curta / reservas", "curta_res", 1, "externo"), ("Déficit em conta corrente", "cc", -1, "externo"),
     ("Crédito, alta em 3 anos", "d3_credito", 1, "credito"), ("Hiato de crédito", "credito_gap", 1, "credito")]
for nome, v, s, fam in A:
    rows.append({"painel": "emergentes anual", "indicador": nome, "familia": fam, "curto": auc(em, v, "y1", s), "medio": auc(em, v, "y23", s), "longo5": auc(em, v, "y5", s)})
# JST
j = pd.read_excel("../dados/jst_R6.xlsx").sort_values(["iso","year"])
j = j[~j.year.between(1914,1919) & ~j.year.between(1939,1947) & (j.year >= 1950)]
gj = j.groupby("iso"); j["cresc"] = 100*gj.rgdpbarro.pct_change(); j["infl"] = 100*gj.cpi.pct_change()
j["cred_hh"] = 100*j.thh/j.gdp; gj = j.groupby("iso"); j["d5_cred_hh"] = gj.cred_hh.diff(5); j["d1_juro"] = gj.stir.diff(1); j["incl"] = j.ltrate - j.stir
j["d1_infl"] = gj.infl.diff(1); j["juro_real"] = j.stir - j.infl
j["queda"] = (j.cresc<0).astype(float).where(j.cresc.notna()); gj = j.groupby("iso")
j["inicio"] = ((j.queda==1)&(gj.queda.shift(1)==0)).astype(float).where(j.queda.notna()&gj.queda.shift(1).notna()); gj = j.groupby("iso")
F = pd.concat([gj.inicio.shift(-1)], axis=1); j["y1"] = F.max(axis=1).where(F.notna().all(axis=1)); j.loc[j.queda!=0,"y1"] = np.nan
F = pd.concat([gj.inicio.shift(-k) for k in (2,3)], axis=1); j["y23"] = F.max(axis=1).where(F.notna().all(axis=1)); j.loc[(j.queda!=0)|(j.y1==1),"y23"] = np.nan
for nome, v, s, fam in [("Dívida pública, nível", "debtgdp", 1, "fiscal"), ("Crédito às famílias, alta em 5 anos", "d5_cred_hh", 1, "credito"),
                        ("Juro subindo no ano", "d1_juro", 1, "juro"), ("Curva de juros (longo menos curto)", "incl", -1, "juro"),
                        ("Inflação acelerando", "d1_infl", 1, "inflacao"), ("Juro real, nível", "juro_real", 1, "juro")]:
    rows.append({"painel": "ricos anual (JST)", "indicador": nome, "familia": fam, "curto": auc(j, v, "y1", s), "medio": auc(j, v, "y23", s)})
# OECD trimestral
t = pd.read_pickle(D/"painel_tri.pkl")
for nome, v, s, fam in [("Juro subindo em 4 trimestres", "d4_juro", 1, "juro"), ("Juro subindo em 8 trimestres", "d8_juro", 1, "juro"),
                        ("Curva de juros (longo menos curto)", "inclinacao", -1, "juro"), ("Inflação acelerando", "d4_infl", 1, "inflacao"),
                        ("Indicador antecedente da OCDE acima da tendência", "cli", 1, "atividade"), ("Bolsa, queda real em 4 trimestres", "acoes_4t", -1, "mercado"),
                        ("Dívida pública, nível", "divida", 1, "fiscal"), ("Déficit >3% em 5 anos (permanência)", "perm_deficit3", 1, "fiscal"),
                        ("Hiato de crédito", "credito_gap", 1, "credito"), ("Câmbio real acima da média de 10 anos", "reer_gap10", 1, "externo")]:
    rows.append({"painel": "OCDE trimestral", "indicador": nome, "familia": fam, "curto": auc(t, v, "h4", s), "medio": auc(t, v, "m5_12", s)})
r = pd.DataFrame(rows); pd.set_option("display.width", 250); print(r.to_string(index=False))
r.to_json("../dados/tabela_auc.json", orient="records", force_ascii=False)
