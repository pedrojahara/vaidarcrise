"""O crescimento da economia que fica logo abaixo da placa: quanto a economia cresceu em 12 meses, quanto
crescia um ano antes e quanto os bancos esperam para os próximos 12 meses.

Só mostra. Não entra na direção do risco (src/direcao.py): o "encolhendo" continua saindo da média de 3 meses
da prévia do PIB. A previsão é de fora (Focus) e fica só na tela, nunca na conta.

As contas:
- Crescimento em 12 meses: prévia do PIB do Banco Central (IBC-Br dessazonalizado, BCB 24364), soma dos 12 meses
  até o último dado contra a soma dos 12 meses anteriores. O número de um ano antes é a mesma conta 12 meses antes. A página mostra
  cada número com os 12 meses que ele cobre ("set/2025 a ago/2026"), e a previsão também (janela_previsao).
- Acelerando ou desacelerando: compara "agora" com "antes", os dois com uma casa, como a página mostra. Diferença
  de até 0,1 ponto é "no mesmo ritmo". É descrição, não sinal: o crescimento do Brasil varia muito de um ano para
  o outro, e a direção do risco não usa esta conta.
- Faixa normal: percentis 25 e 75 do crescimento em 12 meses desde 2004.
- Previsão: mediana do Focus para o PIB do ano corrente e do seguinte, ponderada pelos meses que faltam em cada
  um (indicadores.focus_pib). O erro é o erro médio absoluto dessa previsão contra o PIB do IBGE que veio,
  com a mesma ponderação, desde 2004.

Uso: python src/ritmo.py --calibrar   (grava a faixa e o erro em config/calibracao.json, seção "ritmo")
     python src/ritmo.py              (mostra o bloco com o último registro)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import indicadores  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico" / "series.json"
PIB = ROOT / "data" / "historico" / "pib.json"
RAW = ROOT / "data" / "raw"
CAL = ROOT / "config" / "calibracao.json"
CFG = ROOT / "config" / "modelo.json"
INICIO = "2004-01"


def _mn(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(n: int) -> str:
    return f"{n // 12:04d}-{n % 12 + 1:02d}"


def serie_ibcbr(dia: str | None = None) -> dict[str, float]:
    """O IBC-Br mês a mês: o histórico longo e, por cima, o registro de indicadores do dia (ou o último antes dele)."""
    s = {x["data"][:7]: float(x["valor"]) for x in json.loads(HIST.read_text())["series"].get("ibcbr", [])
         if x.get("valor") is not None}
    brutos = sorted(p for p in RAW.glob("*/indicadores.json") if dia is None or p.parent.name <= dia)
    if brutos:
        snap = json.loads(brutos[-1].read_text())
        for x in snap.get("series", {}).get("ibcbr", {}).get("dados", []):
            if x.get("valor") is not None:
                s[x["data"][:7]] = float(x["valor"])
    return s


def cresc_12m(s: dict[str, float], ref: str) -> float | None:
    """Crescimento em %: soma dos 12 meses até `ref` contra a soma dos 12 anteriores."""
    n = _mn(ref)
    a = [s.get(_ms(n - i)) for i in range(12)]
    b = [s.get(_ms(n - 12 - i)) for i in range(12)]
    if None in a or None in b:
        return None
    return 100 * (sum(a) / sum(b) - 1)


def _percentil(xs: list[float], p: float) -> float:
    v = sorted(xs)
    k = (len(v) - 1) * p / 100
    f = int(k)
    return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)


def _anual_ibge() -> dict[int, float]:
    """Crescimento anual do PIB pelo IBGE (média do ano contra a do ano anterior), encadeando as taxas trimestrais."""
    q = {}
    for x in json.loads(PIB.read_text())["pib"]:
        t, a = int(x["trimestre"][0]), int(x["trimestre"][2:])
        q[a * 4 + t - 1] = x["var_qoq"]
    ts = sorted(q)
    idx = {ts[0] - 1: 100.0}
    for t in ts:
        idx[t] = idx[t - 1] * (1 + q[t] / 100)
    out = {}
    for a in range(ts[0] // 4 + 1, ts[-1] // 4 + 1):
        este, ant = [idx.get(a * 4 + k) for k in range(4)], [idx.get((a - 1) * 4 + k) for k in range(4)]
        if None not in este and None not in ant:
            out[a] = 100 * (sum(este) / sum(ant) - 1)
    return out


def calibrar() -> dict:
    """A faixa normal do crescimento em 12 meses desde 2004 e o erro do Focus desde 2004."""
    s = serie_ibcbr()
    meses = [m for m in sorted(s) if m >= INICIO]
    g = {m: cresc_12m(s, m) for m in meses}
    g = {m: v for m, v in g.items() if v is not None}
    anual = _anual_ibge()
    erros = []
    for x in json.loads(HIST.read_text())["series"].get("focus_pib", []):
        m = x["data"][:7]
        if m < INICIO or x.get("ano") is None or x.get("ano_seguinte") is None:
            continue
        a, mes = int(m[:4]), int(m[5:7])
        if a not in anual or a + 1 not in anual:
            continue
        prev = indicadores.focus_pib(x["ano"], x["ano_seguinte"], x.get("dia") or x["data"])
        veio = ((12 - mes) * anual[a] + mes * anual[a + 1]) / 12
        erros.append((m, prev - veio))
    return {
        "o_que_e": "Crescimento em 12 meses pela prévia do PIB (IBC-Br): soma de 12 meses contra os 12 anteriores. "
                   "faixa: percentis 25 e 75 desde 2004. erro_focus: erro médio absoluto da previsão de 12 meses do Focus contra o PIB do IBGE que veio, com a mesma ponderação dos anos, desde 2004 (src/ritmo.py).",
        "de": min(g), "ate": max(g),
        "faixa": [round(_percentil(list(g.values()), 25), 3), round(_percentil(list(g.values()), 75), 3)],
        "mediana": round(_percentil(list(g.values()), 50), 3),
        "erro_focus": round(sum(abs(e) for _, e in erros) / len(erros), 3),
        "erro_focus_ate_1_ponto": round(sum(1 for _, e in erros if abs(e) <= 1) / len(erros), 3),
        "erro_focus_meses": [erros[0][0], erros[-1][0], len(erros)],
    }


def janela(ate: str) -> tuple[str, str]:
    """Os 12 meses que terminam em `ate` (AAAA-MM): de setembro de 2025 a agosto de 2026 para agosto de 2026."""
    return _ms(_mn(ate) - 11), ate


def janela_previsao(data_focus: str) -> tuple[str, str]:
    """Os 12 meses da previsão do Focus, pela mesma ponderação de indicadores.focus_pib: com a pesquisa no mês m, o ano
    corrente pesa 12 − m meses e o seguinte, m, que são os 12 meses do mês seguinte ao da pesquisa até o mesmo mês do
    ano que vem (pesquisa de novembro de 2026: de dezembro de 2026 a novembro de 2027)."""
    n = _mn(data_focus[:7])
    return _ms(n + 1), _ms(n + 12)


def bloco(dia: str, rodada: dict, cal: dict) -> dict | None:
    """Os números do bloco para um dia: agora, um ano antes, a previsão dos bancos e o rótulo da mudança."""
    c = cal.get("ritmo")
    if not c:
        return None
    s = serie_ibcbr(dia)
    ms = [m for m in s if m <= dia[:7]]
    if not ms:
        return None
    ref = max(ms)
    agora = cresc_12m(s, ref)
    ref_antes = _ms(_mn(ref) - 12)
    antes = cresc_12m(s, ref_antes)
    if agora is None or antes is None:
        return None
    dif = round(agora, 1) - round(antes, 1)
    muda = "acelerando" if dif > 0.15 else "desacelerando" if dif < -0.15 else "no mesmo ritmo"
    f = next((x for x in rodada["resultado"].get("indicadores", []) if x.get("id") == "focus_pib" and x.get("valor") is not None), None)
    return {"agora": agora, "ref": ref, "antes": antes, "ref_antes": ref_antes, "muda": muda,
            "janela": janela(ref), "janela_antes": janela(ref_antes),
            "previsao": f["valor"] if f else None, "previsao_data": f["ref"] if f else None,
            "janela_previsao": janela_previsao(f["ref"]) if f else None,
            "faixa": c["faixa"], "erro": c["erro_focus"]}


def main() -> None:
    if "--calibrar" in sys.argv:
        cal = json.loads(CAL.read_text())
        cal["ritmo"] = calibrar()
        CAL.write_text(json.dumps(cal, ensure_ascii=False, indent=1) + "\n")
        print(json.dumps(cal["ritmo"], ensure_ascii=False, indent=1))
        return
    cal = json.loads(CAL.read_text())
    rodada = json.loads(sorted((ROOT / "runs").glob("*.json"))[-1].read_text())
    print(json.dumps(bloco(rodada["gerado_em"][:10], rodada, cal), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
