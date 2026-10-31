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
    # O leitor (PERSONA.md) não estudou economia e tem lado político.
    (re.compile(r"\b(política monetária|aperto monetário|interanual|dessazonalizad\w*|commodities|pontos?[- ]base|"
                r"hiato do produto|PIB potencial|quantil|desancorad\w*|curva de juros|estagflação|spread)\b", re.I),
     "jargão que o leitor não conhece"),
    (re.compile(r"\b(despenc\w*|explod\w*|explos\w*|derret\w*|colaps\w*|tomb[oa]s?|sangria)\b", re.I), "palavra de alarme"),
    (re.compile(r"\b(rombo|gastança|farra|herança maldita|austericídio|desgoverno)\b", re.I), "palavra com lado"),
    (re.compile(r"(^|[\s(])[−-]\d"), "queda com sinal de menos em vez de verbo"),
    # PERSONA.md, "Como explicar um mecanismo": nada do vocabulário e do bastidor da nossa pesquisa.
    (re.compile(r"\b(gatilhos?|fragilidades?|segunda derivada|AUC|fora da amostra|\d+ países)\b", re.I),
     "termo da pesquisa do site que o leitor não conhece"),
    # PERSONA.md, regra 11: causa e efeito por extenso, sem frase de efeito no lugar da explicação.
    (re.compile(r"(,\s*(sim|não)\.(\s|$)|,\s+não\s+(?:[ao]s?\s+)?\w+\.(\s|$)|\b(\w{4,}) (puxa|chama|gera|traz) \5\b|"
                r"ninguém controla|\bna dose certa\b)", re.I),
     "frase de efeito no lugar de causa e efeito ('X, sim.', 'isto, não aquilo', 'aumento puxa aumento')"),
    # PERSONA.md, "Jargões": a Selic se explica pelo que faz, não por outro termo.
    (re.compile(r"\bjuro básico\b", re.I),
     "'juro básico' troca jargão por jargão: diga que é o juro que o Banco Central decide e que serve de base para os juros dos bancos"),
    (re.compile(r"\b(cenário ruim|inadimplência|(déficit|superávit) primário|crédito livre)\b", re.I),
     "palavra que o site trocou (num ano ruim, atraso nas dívidas, gasta mais do que arrecada)"),
]

FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\"“])")
NUMERO = re.compile(r"\d+(?:,\d+)?\s*(?:%|pontos?\b)|R\$\s*\d")
# "A inflação recuou" soa como preço caindo; o leitor precisa ler que os preços sobem mais devagar.
INFLACAO_CAI = re.compile(r"\b(inflação|IPCA)\b[^.]{0,60}\b(recu\w*|ca(i|iu|ía|indo|em|ir)|diminu\w*)\b", re.I)


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
]


# O post conta o fato; como a conta funciona fica na página da conta. Uma frase só pode dizer que um
# fato fica fora da conta do nível, quando ele parece contradizer o nível (PERSONA.md, regra 6 do prompt).
NIVEL_FUNCIONA = re.compile(r"\b((não|nem) (entra|entram|mexe|mexem|move|movem) "
                            r"(n[oa] |o |a )?(número|conta|nível)|entram? n[oa] (número|conta|nível)|só se (mexe|move)|"
                            r"(fora|dentro) d[oa] (número|conta|nível))\b", re.I)

# Fato do dia com o nível parado: a placa do topo já mostra o nível e o PIB num ano ruim.
NIVEL_REPETIDO = re.compile(r"\b(num ano ruim|em tempos normais|risco( de recessão)?[^.]{0,30}\b(segue|seguiu|continua|"
                            r"continuou|está|fica|ficou|permanece|permaneceu)\b[^.]{0,12}\b(normal|acima|abaixo)|"
                            r"nível (segue|continua|está|fica|permanece|é|de) (o )?(muito )?(normal|acima|abaixo))", re.I)

LIMITE_PALAVRAS = {"dia": 120, "semana": 300, "mes": 360}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
DATA_BARRA = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}))?(?![\d/])")
DATA_EXTENSO = re.compile(r"\b(\d{1,2})(?:º)? de (" + "|".join(MESES) + r")\b", re.I)
NUM = re.compile(r"(?<![A-Za-z0-9_,.])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?![\d])")
# Números que o prompt dá ao modelo fora dos dados: desde 2004, 1 chance em 10, 12 meses, cinco níveis.
CONSTANTES = "2004 10 12 5"


def _datas(texto: str) -> set[tuple[int, int]]:
    out = {(int(d), int(m)) for d, m, _ in DATA_BARRA.findall(texto)}
    out |= {(int(d), MESES.index(m.lower()) + 1) for d, m in DATA_EXTENSO.findall(texto)}
    return {(d, m) for d, m in out if 1 <= d <= 31 and 1 <= m <= 12}


def _sem_datas(texto: str) -> str:
    return DATA_EXTENSO.sub(" ", DATA_BARRA.sub(" ", texto))


def _numeros(texto: str) -> list[tuple[str, float, int]]:
    """(como está escrito, valor, casas decimais) de cada número do texto, sem as datas."""
    out = []
    for m in NUM.finditer(_sem_datas(texto)):
        inteiro, dec = m.group(1), m.group(2) or ""
        out.append((m.group(0), float(inteiro.replace(".", "") + ("." + dec if dec else "")), len(dec)))
    return out


def numeros_fora(textos: list[str], dados: str) -> list[str]:
    """Números e datas do texto que não estão nos dados, com a folga de arredondamento da casa decimal usada."""
    base = sorted({v for _, v, _ in _numeros(dados + " " + CONSTANTES)})
    datas = _datas(dados)
    out = []
    for t in textos:
        for d, m in sorted(_datas(t) - datas):
            out.append(f"{d}/{m}")
        for bruto, v, casas in _numeros(t):
            if casas == 0 and v <= 12:
                continue
            folga = 0.5 * 10 ** -casas + 1e-9
            if not any(abs(v - b) <= folga for b in base):
                out.append(bruto)
    return list(dict.fromkeys(out))


def _prosa(post: dict) -> list[str]:
    return [post["titulo"], *post["paragrafos"]]


def _frases(textos: list[str]) -> list[str]:
    return [f.strip() for t in textos for f in FRASE.split(t) if f.strip()]


def graves_post(post: dict, tipo: str = "dia", dados: str | None = None, **_) -> list[str]:
    textos = _prosa(post)
    out = [f"{'título' if i == 0 else f'parágrafo {i}'}: {nome}"
           for i, t in enumerate(textos) for rx, nome in GRAVES if rx.search(t)]
    if NIVEL_FUNCIONA.search(post["titulo"]):
        out.append("título: explica como o nível funciona")
    n = sum(1 for f in _frases(post["paragrafos"]) if NIVEL_FUNCIONA.search(f))
    if n > 1:
        out.append(f"{n} frases explicam como o nível funciona (o post pode ter uma, quando o fato parece contradizer o nível)")
    if dados is not None:
        fora = numeros_fora(textos, dados)
        if fora:
            out.append("número ou data que não está nos dados: " + ", ".join(fora[:6])
                       + " (use só os números dos dados, sem recalcular)")
    return out


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


def problemas_post(post: dict, tipo: str = "dia", dados: str | None = None, hoje=None, anterior: dict | None = None,
                   nivel_mudou: bool = True, **_) -> list[str]:
    """Moldes de texto e, nos posts, o que repete a página: nível parado, data da lateral, frase do post anterior."""
    import datetime as dt
    from difflib import SequenceMatcher

    out = []
    t = post["titulo"]
    if len(t) > 80:
        out.append(f"título com {len(t)} caracteres")
    if t.rstrip().endswith("?"):
        out.append("título em forma de pergunta")
    out += [f"título: {m}" for m in _moldes(t) if m in ("travessão", "ponto de exclamação", "palavra de alarme", "palavra com lado")]
    for i, p in enumerate(post["paragrafos"], 1):
        out += [f"parágrafo {i}: {m}" for m in _moldes(p)]
        if len(p.split()) > 65:
            out.append(f"parágrafo {i} com {len(p.split())} palavras")
        longas = [len(f.split()) for f in FRASE.split(p) if len(f.split()) > 25]
        if longas:
            out.append(f"parágrafo {i} com frase de {max(longas)} palavras")
        if len(NUMERO.findall(p)) > 4:
            out.append(f"parágrafo {i} com {len(NUMERO.findall(p))} números")
        if any(INFLACAO_CAI.search(f) and "mais devagar" not in f for f in FRASE.split(p)):
            out.append(f"parágrafo {i}: inflação que 'cai' ou 'recua' sem dizer que os preços sobem mais devagar")
        if re.search(r"\b(eu|nós|nosso|nossa)\b", p, flags=re.IGNORECASE):
            out.append(f"parágrafo {i} em primeira pessoa")
    out += _aberturas(post["paragrafos"], limite=1)
    palavras = sum(len(p.split()) for p in post["paragrafos"])
    if palavras > LIMITE_PALAVRAS.get(tipo, 10**6):
        out.append(f"texto com {palavras} palavras (o limite é {LIMITE_PALAVRAS[tipo] * 5 // 6})")
    if tipo == "dia" and not nivel_mudou:
        rep = [f for f in _frases(_prosa(post)) if NIVEL_REPETIDO.search(f)]
        if rep:
            out.append("repete o nível ou o PIB num ano ruim, que não mudaram e já estão na placa: " + rep[0][:70])
    if tipo == "dia" and hoje is not None:
        hoje = hoje if isinstance(hoje, dt.date) else dt.date.fromisoformat(str(hoje)[:10])
        futuras = []
        for d, m in _datas(" ".join(_prosa(post))):
            ano = hoje.year + (1 if m < hoje.month - 6 else 0)
            try:
                if dt.date(ano, m, d) > hoje:
                    futuras.append(f"{d}/{m}")
            except ValueError:
                pass
        if futuras:
            out.append("data futura (as próximas datas ficam na lateral): " + ", ".join(sorted(futuras)))
    if anterior and anterior.get("paragrafos"):
        velhas = [f for f in _frases([anterior.get("titulo", ""), *anterior["paragrafos"]]) if len(f.split()) >= 6]
        for f in _frases(_prosa(post)):
            # A frase da regra 6 ("Isso não muda o risco de recessão, porque...") é fórmula: pode repetir.
            if len(f.split()) >= 6 and not NIVEL_FUNCIONA.search(f) and any(SequenceMatcher(None, f.lower(), v.lower()).ratio() > 0.8 for v in velhas):
                out.append(f"frase copiada do post anterior: {f[:70]}")
    return out + graves_post(post, tipo=tipo, dados=dados)
