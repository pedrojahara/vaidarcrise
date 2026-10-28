"""Taxa-base: o risco de uma recessão começar num trimestre, antes de qualquer dado ou notícia.

Calcula a âncora pela mediana de nove métodos que não escolhem o período a dedo,
a partir de data/cronologia.json (Brasil) e data/emergentes.json (vizinhos).
O resultado fica congelado em config/modelo.json a cada versão; este script só
existe para que qualquer pessoa refaça a conta.

Uso: python src/taxa_base.py          (tabela)
     python src/taxa_base.py --json   (bloco para colar em config/modelo.json)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
INICIOS_NA_JANELA = 17  # 3T26 a 3T30: um início no trimestre t exige t e t+1 dentro da janela


def idx(rotulo: str) -> int:
    """'2T99' -> índice contínuo de trimestres (anos de 70 a 99 são 1900)."""
    q, a = rotulo.split("T")
    ano = int(a) + (1900 if int(a) >= 70 else 2000)
    return 4 * ano + int(q) - 1


class Cronologia:
    def __init__(self, dados: dict, comeco: str = "1T80"):
        self.t0, self.t1 = idx(comeco), idx(dados["observado_ate"])
        self.recessao, self.inicios = set(), set()
        for r in dados["recessoes"]:
            a, b = idx(r["inicio"]), idx(r["fim"])
            self.recessao.update(range(a, b + 1))
            self.inicios.add(a)

    def contagem(self, de: str | int, peso=None) -> tuple[float, float]:
        """Inícios e trimestres em expansão (ponderados) de `de` até o último trimestre observado."""
        f = idx(de) if isinstance(de, str) else de
        s = e = 0.0
        for i in range(max(f, self.t0), self.t1 + 1):
            w = 1.0 if peso is None else peso(i)
            if i not in self.recessao:
                e += w
            if i in self.inicios:
                s += w
        return s, e

    def risco(self, de: str | int, peso=None) -> float:
        s, e = self.contagem(de, peso)
        return s / e


def acumulado(h: float, n: int = INICIOS_NA_JANELA) -> float:
    return 1 - (1 - h) ** n


def _logml(s: float, e: float, a: float, b: float) -> float:
    return a * math.log(b) + math.lgamma(a + s) - math.lgamma(a) - (a + s) * math.log(b + e)


def quebra_desconhecida(c: Cronologia, prior_medio: float = 0.06) -> float:
    """Média bayesiana entre 'nada mudou' e 'mudou numa data qualquer de 1988 a 2022'.

    Risco de Poisson com priori Gama (forma 1 e 2, média de 6% por trimestre); a data da
    quebra tem priori uniforme. Devolve o risco trimestral equivalente à chance preditiva
    de recessão nos 17 inícios da janela, na média das duas prioris.
    """
    n, ps = INICIOS_NA_JANELA, []
    for a in (1.0, 2.0):
        b = a / prior_medio
        s, e = c.contagem(c.t0)
        lm0, pc0 = _logml(s, e, a, b), 1 - ((b + e) / (b + e + n)) ** (a + s)
        lms, pcs = [], []
        for q in range(idx("1T88"), idx("4T22") + 1):
            s1, e1 = s - c.contagem(q)[0], e - c.contagem(q)[1]
            s2, e2 = c.contagem(q)
            lms.append(_logml(s1, e1, a, b) + _logml(s2, e2, a, b))
            pcs.append(1 - ((b + e2) / (b + e2 + n)) ** (a + s2))
        m = max(lms + [lm0])
        ws = [math.exp(x - m) for x in lms]
        l1, l0 = sum(ws) / len(ws), math.exp(lm0 - m)
        pc1 = sum(w * p for w, p in zip(ws, pcs)) / sum(ws)
        w1 = l1 / (l0 + l1)
        ps.append(w1 * pc1 + (1 - w1) * pc0)
    p = sum(ps) / len(ps)
    return 1 - (1 - p) ** (1 / n)


def metodos(c: Cronologia, viz: dict) -> list[dict]:
    meia_vida = lambda anos: (lambda i: 0.5 ** ((c.t1 - i) / 4 / anos))  # noqa: E731
    s_v = sum(p["inicios"] for p in viz["paises"])
    e_v = sum(p["trimestres_expansao"] for p in viz["paises"])
    m_v = s_v / e_v
    s_t, e_t = c.contagem("2T99")
    janelas = [c.risco(q) for q in range(idx("1T95"), idx("4T12") + 1)]
    out = [
        ("Desde 2T99: metas de inflação e câmbio flutuante", c.risco("2T99")),
        ("Desde 1T00: com a Lei de Responsabilidade Fiscal", c.risco("1T00")),
        ("1980 em diante, peso cai à metade a cada 10 anos", c.risco(c.t0, meia_vida(10))),
        ("1980 em diante, peso cai à metade a cada 15 anos", c.risco(c.t0, meia_vida(15))),
        ("1980 em diante, peso cai à metade a cada 20 anos", c.risco(c.t0, meia_vida(20))),
        ("Média das janelas iniciadas entre 1T95 e 4T12", sum(janelas) / len(janelas)),
        ("Quebra estrutural em data desconhecida (bayesiano)", quebra_desconhecida(c)),
        ("Brasil desde 2T99 + 8 emergentes, peso de 10 anos", (m_v * 40 + s_t) / (40 + e_t)),
        ("Brasil desde 2T99 + 8 emergentes, peso de 25 anos", (m_v * 100 + s_t) / (100 + e_t)),
    ]
    return [{"nome": n, "risco_trimestral": round(h, 4)} for n, h in out]


def calcular() -> dict:
    c = Cronologia(json.loads((ROOT / "data" / "cronologia.json").read_text()))
    viz = json.loads((ROOT / "data" / "emergentes.json").read_text())
    ms = metodos(c, viz)
    hs = [m["risco_trimestral"] for m in ms]
    return {
        "risco_trimestral": round(median(hs), 3),
        "faixa": {"min": min(hs), "max": max(hs)},
        "metodos": ms,
        "alternativas": [
            {"nome": "2004–2026", "risco_trimestral": round(c.risco("1T04"), 4),
             "leitura": "para quem acha que o Brasil mudou depois de 2004"},
            {"nome": "1980–2026", "risco_trimestral": round(c.risco(c.t0), 4),
             "leitura": "para quem acha que não mudou"},
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    r = calcular()
    if ap.parse_args().json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    for m in r["metodos"]:
        h = m["risco_trimestral"]
        print(f"{m['nome']:<55} {100 * h:5.2f}%  até 4T30: {100 * acumulado(h):4.1f}")
    h = r["risco_trimestral"]
    print(f"{'Âncora (mediana)':<55} {100 * h:5.2f}%  até 4T30: {100 * acumulado(h):4.1f}")
    print(f"Faixa: {100 * r['faixa']['min']:.2f}% a {100 * r['faixa']['max']:.2f}% "
          f"({100 * acumulado(r['faixa']['min']):.0f} a {100 * acumulado(r['faixa']['max']):.0f})")
    for a in r["alternativas"]:
        print(f"Alternativa {a['nome']}: {100 * a['risco_trimestral']:.2f}%  até 4T30: {100 * acumulado(a['risco_trimestral']):.1f}")


if __name__ == "__main__":
    main()
