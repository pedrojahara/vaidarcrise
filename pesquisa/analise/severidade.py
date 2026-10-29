"""Fragilidade em três ângulos que o teste de 'quando começa' não pega:
1) profundidade da queda quando ela vem; 2) choque x fragilidade; 3) horizonte de 5 anos e crescimento médio à frente."""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from painel_anual import D
import statsmodels.formula.api as smf

d = pd.read_pickle(D / "painel_anual.pkl").merge(pd.read_pickle(D / "extra_anual.pkl"), on=["ISO3", "year"], how="left")
EM_EXTRA = ["CHL","URY","POL","HUN","CZE","KOR","SAU","PAN","HRV","ROU","SVK","LTU","LVA","EST","ISR","TWN","SGP","HKG"]
d = d.sort_values(["ISO3", "year"])
g = d.groupby("ISO3")
# profundidade: queda acumulada do PIB do ano anterior ao início até o fundo em 4 anos (%)
fut_min = pd.concat([g.log_pib.shift(-k) for k in range(0, 4)], axis=1).min(axis=1)
d["prof"] = 100 * (g.log_pib.shift(1) - fut_min)
# perda contra a tendência: crescimento médio dos 5 anos anteriores menos o de t..t+3, somado
tend = g.cresc.transform(lambda s: s.shift(1).rolling(5, min_periods=4).mean())
real = pd.concat([g.cresc.shift(-k) for k in range(0, 4)], axis=1).sum(axis=1, min_count=4)
d["perda"] = 4 * tend - real
d["cresc_5a_frente"] = pd.concat([g.cresc.shift(-k) for k in range(1, 6)], axis=1).mean(axis=1)
F = pd.concat([g.inicio.shift(-k) for k in range(1, 6)], axis=1)
d["y5"] = F.max(axis=1).where(F.notna().all(axis=1)); d.loc[d.queda != 0, "y5"] = np.nan
Q = pd.concat([g.queda.shift(-k) for k in range(1, 6)], axis=1)
d["anos_queda_5"] = Q.sum(axis=1, min_count=5)
# variáveis do ano anterior ao início (o que se via antes)
VARS = ["divida", "deficit", "log_infl", "juro_real", "cc", "perm_deficit3", "perm_juro5", "perm_infl10", "perm_divida_sobe",
        "d3_divida", "d1_log_infl", "credito", "d3_credito", "credito_gap", "curta_res", "reservas", "div_ext", "reer_gap10"]
for v in VARS:
    d[f"L_{v}"] = g[v].shift(1)

a = d[(d.year >= 1980) & (d.year <= 2024) & (d["pop"] >= 1)]
em = a[a.income_group.isin(["Upper middle income", "Lower middle income"]) | a.ISO3.isin(EM_EXTRA)]
pd.set_option("display.width", 250)

print("=== 1) PROFUNDIDADE: quando a queda vem, é pior se a fragilidade era maior? (emergentes, inícios de queda)")
ep = em[em.inicio == 1].copy()
print(f"episódios: {len(ep)}; profundidade mediana {ep.prof.median():.1f}%, perda mediana contra tendência {ep.perda.median():.1f} p.p.")
rows = []
for v in VARS:
    s = ep[[f"L_{v}", "prof", "perda"]].dropna()
    if len(s) < 60: continue
    r1 = spearmanr(s[f"L_{v}"], s.prof); r2 = spearmanr(s[f"L_{v}"], s.perda)
    t = pd.qcut(s[f"L_{v}"].rank(method="first"), 3, labels=False)
    rows.append({"var": v, "n": len(s), "rho_prof": round(r1.statistic, 2), "p": round(r1.pvalue, 3),
                 "rho_perda": round(r2.statistic, 2), "p2": round(r2.pvalue, 3),
                 "prof_terço_baixo": round(s.prof[t == 0].median(), 1), "prof_terço_alto": round(s.prof[t == 2].median(), 1),
                 "perda_baixo": round(s.perda[t == 0].median(), 1), "perda_alto": round(s.perda[t == 2].median(), 1)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== 2) CHOQUE x FRAGILIDADE: chance de começar queda no ano seguinte (emergentes)")
x = em.copy()
x["choque_global"] = (x.cresc_mundo < 2) | (x.d_juro_real_eua > 1.5)
x["choque_tt"] = x.d1_tt < -10
x["choque"] = x.choque_global | x.choque_tt
FRAG = {"dívida>60": x.divida > 60, "inflação>10": x.infl_c > 10, "juro real>5": x.juro_real > 5,
        "déficit>3 em 4+ de 5 anos": x.perm_deficit3 >= 4, "dív. curta/reservas>100": x.curta_res > 100,
        "crédito +10pp em 3a": x.d3_credito > 10, "câmbio real 10% acima da média": x.reer_gap10 > 0.10,
        "conta corrente<-4": x.cc < -4}
rows = []
for nome, f in FRAG.items():
    r = {"fragilidade": nome}
    for ch, cm in (("sem choque", ~x.choque), ("com choque", x.choque)):
        for fr, fm in (("baixa", f == False), ("alta", f == True)):
            s = x.loc[cm & fm & f.notna(), "y1"].dropna()
            r[f"{ch}|{fr}"] = f"{s.mean():.2f} ({len(s)})"
    rows.append(r)
print("taxa base y1:", round(x.y1.mean(), 3))
print(pd.DataFrame(rows).to_string(index=False))
# logit com interação, efeitos padronizados, erro agrupado por país
print("\nlogit y1 ~ choque * fragilidade (coef. da interação; >0 = fragilidade amplifica o choque)")
for nome, f in FRAG.items():
    z = x.assign(fr=f.astype(float).where(f.notna()), ch=x.choque.astype(float)).dropna(subset=["y1", "fr", "ch"])
    try:
        m = smf.logit("y1 ~ ch * fr", z).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(z.ISO3)[0]})
        print(f"  {nome:32s} choque {m.params['ch']:+.2f}  frag {m.params['fr']:+.2f}  interação {m.params['ch:fr']:+.2f} (p={m.pvalues['ch:fr']:.2f}) n={len(z)}")
    except Exception as e:
        print(nome, e)

print("\n=== 3) HORIZONTE LONGO: queda nos próximos 5 anos, anos em queda e crescimento médio à frente (emergentes)")
rows = []
for v in ["divida", "deficit", "log_infl", "juro_real", "perm_deficit3", "perm_juro5", "perm_infl10", "perm_divida_sobe", "d3_divida",
          "credito", "d3_credito", "curta_res", "reservas", "div_ext", "cc", "reer_gap10"]:
    r = {"var": v}
    s = x[[v, "y5"]].dropna()
    if len(s) > 200: r["auc_y5"] = round(roc_auc_score(s.y5, s[v]), 3); r["n5"] = len(s)
    s = x[[v, "anos_queda_5", "cresc_5a_frente", "ISO3"]].dropna()
    if len(s) > 200:
        r["rho_anos_queda"] = round(spearmanr(s[v], s.anos_queda_5).statistic, 2)
        # dentro do país: tira a média de cada país (o que muda quando o MESMO país piora?)
        w = s.copy(); w[v] = w[v] - w.groupby("ISO3")[v].transform("mean")
        w["c"] = w.cresc_5a_frente - w.groupby("ISO3").cresc_5a_frente.transform("mean")
        r["rho_cresc5_entre"] = round(spearmanr(s[v], s.cresc_5a_frente).statistic, 2)
        r["rho_cresc5_dentro"] = round(spearmanr(w[v], w.c).statistic, 2)
    rows.append(r)
print("taxa base y5:", round(x.y5.mean(), 3), "| anos em queda (média de 5):", round(x.anos_queda_5.mean(), 2))
print(pd.DataFrame(rows).to_string(index=False))

b = d[d.ISO3 == "BRA"].set_index("year")
print("\nBrasil, episódios:")
print(b.loc[b.inicio == 1, ["prof", "perda", "L_divida", "L_log_infl", "L_juro_real", "L_d3_credito", "L_curta_res", "L_cc"]].round(1).to_string())
