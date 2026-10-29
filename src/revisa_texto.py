"""Confere o texto do LLM contra os moldes que denunciam piloto automático.

Devolve a lista de problemas, que o post usa para pedir uma reescrita e a rodada
grava no registro. Os problemas graves (afirmações que o texto não pode fazer)
barram o post se sobrarem depois da reescrita; os moldes só pedem a reescrita.
"""
from __future__ import annotations

import re
from collections import Counter

MOLDES = [
    (re.compile(r"^(Aumenta|Reduz)\b"), "abre com Aumenta/Reduz"),
    (re.compile(r"\bpelo canal\b", re.I), "usa 'pelo canal'"),
    (re.compile(r"[—–]"), "travessão"),
    (re.compile(r"\b(vale (destacar|ressaltar|notar|lembrar)|é importante|além disso|nesse sentido|em suma|crucial|"
                r"robust[oa]s?|desafiador[ae]?s?)\b", re.I), "expressão de piloto automático"),
    (re.compile(r"\bnão (só|apenas)\b[^.]*\bmas\b", re.I), "não só X, mas Y"),
    (re.compile(r"\bgrande banco\b", re.I), "empresa sem nome"),
    (re.compile(r"!"), "ponto de exclamação"),
    (re.compile(r"\b(metodologia|log-?odds|Shapley|taxa-base|pesam? pouco|composto|regressão|calibra\w*|"
                r"limite de alerta|nova regra|versão do (site|modelo))\b", re.I), "explica a conta ao leitor"),
]


# Afirmações erradas por construção: o post não sabe por que um nome faltou nem tem motivo para dar
# sobre o que ficou fora da conta.
GRAVES = [
    (re.compile(r"\b(cujo nome|sem (o )?nome|nome não (aparece|foi|é|vem)|não (traz|trazem|cita|citam|informa|"
                r"informam|divulga|divulgam|revela|revelam|identifica|identificam) o nome|não identificad[oa]s?|"
                r"não nomead[oa]s?)\b", re.I), "comenta a falta de um nome"),
    (re.compile(r"\bindicadores já (a |o |as |os )?med", re.I), "dá motivo para notícia fora da conta"),
    # O risco de recessão é qualitativo: nunca vira número.
    (re.compile(r"(\d+(,\d+)?\s*(%|por cento)\s*de (chance|probabilidade|risco)|(chance|probabilidade|risco) "
                r"(de recessão )?(é |fica |sobe para |cai para |vai a |de )?(de )?\d+(,\d+)?\s*(%|por cento)|"
                r"\d+(,\d+)?\s*(×|vezes o normal|vezes a chance)|\bvezes o normal\b)", re.I), "dá número ao risco de recessão"),
    # O post conta o dia; como a conta funciona fica na página da conta.
    (re.compile(r"\b((não|nem) (entra|entram|mexe|mexem|move|movem) "
                r"(n[oa] |o |a )?(número|conta|nível)|entram? n[oa] (número|conta|nível)|só se (mexe|move)|"
                r"(fora|dentro) d[oa] (número|conta|nível))\b", re.I), "explica como o nível funciona"),
]


def graves_post(post: dict) -> list[str]:
    textos = [post["titulo"], *post["paragrafos"]]
    return [f"{'título' if i == 0 else f'parágrafo {i}'}: {nome}"
            for i, t in enumerate(textos) for rx, nome in GRAVES if rx.search(t)]


def _moldes(texto: str) -> list[str]:
    return [nome for rx, nome in MOLDES if rx.search(texto)]


def _aberturas(textos: list[str], limite: int = 2) -> list[str]:
    """Aberturas repetidas: mais de `limite` textos começando com as mesmas duas palavras."""
    ab = Counter(" ".join(t.lower().split()[:2]) for t in textos if t.strip())
    return [f"{n} textos abrem com '{a}'" for a, n in ab.items() if n > limite]


def problemas_classificacao(saida: dict) -> list[str]:
    out = []
    for ev in saida.get("eventos", []):
        t = ev["titulo_evento"]
        if len(t) > 80:
            out.append(f"título com {len(t)} caracteres: {t[:60]}")
        if ";" in t:
            out.append(f"título com ponto e vírgula: {t[:60]}")
        out += [f"{m}: {t[:60]}" for m in sorted(set(_moldes(t)) | set(_moldes(ev["porque"])))]
    out += _aberturas([ev["porque"] for ev in saida.get("eventos", [])])
    return out


def problemas_post(post: dict) -> list[str]:
    out = []
    t = post["titulo"]
    if len(t) > 80:
        out.append(f"título com {len(t)} caracteres")
    if t.rstrip().endswith("?"):
        out.append("título em forma de pergunta")
    for i, p in enumerate(post["paragrafos"], 1):
        out += [f"parágrafo {i}: {m}" for m in _moldes(p)]
        if len(p.split()) > 110:
            out.append(f"parágrafo {i} com {len(p.split())} palavras")
        if re.search(r"\b(eu|nós|nosso|nossa)\b", p, flags=re.IGNORECASE):
            out.append(f"parágrafo {i} em primeira pessoa")
    out += _aberturas(post["paragrafos"], limite=1)
    return out + graves_post(post)
