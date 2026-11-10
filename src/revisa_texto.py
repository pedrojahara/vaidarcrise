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
                r"limite de alerta|nova regra|versão do (site|modelo)|vaivém normal|desvio (absoluto|padrão))\b", re.I),
     "explica a conta ao leitor"),
    # O leitor (PERSONA.md) tem curso superior, mas não estudou economia, e tem lado político.
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
     "'juro básico' troca jargão por jargão: escreva só Selic, que o site liga à Wikipédia"),
    # PERSONA.md, "O jeito de escrever do site": o termo técnico ganha link, e o texto não o define toda vez.
    (re.compile(r"(PIB, tudo o que o país produz|IPCA, a inflação oficial|Selic é o juro que o Banco Central decide|"
                r"\bIBC-Br\b)", re.I),
     "define termo que o link da Wikipédia já explica (PIB, IPCA, Selic) ou usa IBC-Br em vez de 'a prévia do PIB'"),
    (re.compile(r"\b(cenário ruim|inadimplência|(déficit|superávit) primário|crédito livre)\b", re.I),
     "palavra que o site trocou (num ano ruim, atraso nas dívidas, gasta mais do que arrecada)"),
    # PERSONA.md, "Os nomes do site": o juro de 10 anos se explica pelo que é; a pressão se chama Desconfiança de quem investe.
    (re.compile(r"\b(juros? longos?|juros futuros|prêmios? de risco|dólar e juro longo)\b", re.I),
     "palavra que o site trocou: diga o juro de 10 anos (o que o governo paga, acima da inflação, para pegar dinheiro "
     "emprestado por uns 10 anos) e, para a pressão, Desconfiança de quem investe"),
    # PERSONA.md, "Os nomes do site": cada pressão piorou, ficou igual ou melhorou, citada pelo nome, e só as
    # categorias do topo (as cinco pressões e Também acompanhamos).
    (re.compile(r"\b(apert(ou|aram|ava|avam|ando|a|am|ar|ad[oa]s?)|folg(ou|aram|ava|avam|ando|a|am|ar|ad[oa]s?))\b", re.I),
     "palavra que o site trocou: cada pressão piorou, ficou igual ou melhorou"),
    (re.compile(r"\bde (piorou|melhorou|igual) para (piorou|melhorou|igual)\b", re.I),
     "usa o rótulo da tabela como palavra: escreva a frase inteira ('tinha melhorado no fim de setembro e passou a piorar')"),
    (re.compile(r"\b(duas|três|quatro|cinco|nenhuma) das (cinco )?pressões\b", re.I),
     "conta as pressões em vez de citar cada uma pelo nome"),
    (re.compile(r"(?<=\w\s)(Contas do governo|Dívidas das famílias|Desconfiança de quem investe|Inflação esperada|Juro)\b"),
     "nome de pressão com maiúscula no meio da frase: use minúscula e artigo ('as contas do governo', 'o juro')"),
    # PERSONA.md, "O jeito de escrever do site": a comparação diz o mês, e produto de outro país é importado.
    (re.compile(r"\b((contra|que|de|com) 3 meses antes|há 3 meses|nos últimos 3 meses|3 meses atrás)\b", re.I),
     "compara com '3 meses antes' em vez de dizer o mês ('se compararmos com julho', 'mais caro que no fim de julho')"),
    (re.compile(r"\b(o|tudo o) que vem de fora\b", re.I),
     "diga 'os importados' (ou 'a importação') em vez de 'o que vem de fora'"),
    (re.compile(r"(?:^|(?<=[.!?:]\s))No bolso\b"),
     "categoria que o site não usa: use os nomes do topo (as cinco pressões e Também acompanhamos)"),
    # PERSONA.md, regra 11 do prompt: pessoas e partidos não, só o cargo ou a instituição.
    (re.compile(r"\b(Lula|Haddad|Bolsonaro|Galípolo|Campos Neto|Tarcísio|Alckmin|Tebet|Durigan|Hugo Motta|Alcolumbre|"
                r"Alexandre de Moraes|Gleisi|Trump|Powell|Xi Jinping|Milei)\b|\b(PT|PL|MDB|PSDB|PSOL|PSD|União Brasil)\b"),
     "nome de pessoa ou partido: use o cargo ou a instituição (o presidente, a Fazenda, o partido do governo)"),
    # A decisão pública se mede pelo objetivo de quem decidiu, sem juízo sobre o decisor (PERSONA.md, "Sem lado").
    # Pede a reescrita, mas não barra: a crítica de alguém, citada como fala dele, pode passar.
    (re.compile(r"\b(Banco Central|Copom|governo|Congresso|Senado|Câmara|Fazenda|Tesouro|ministr[oa]|presidente|"
                r"estados?|prefeituras?|TCU)\b[^.;]{0,50}\b(acertou|errou|acertaram|erraram|acerta|erra|deveria|"
                r"deveriam|devia|deviam)\b|\b(decisão|medida) (certa|errada|acertada|equivocada|correta|incorreta)\b",
                re.I),
     "julga quem decidiu: meça a decisão pelo objetivo que o decisor escreveu, com 'dá certo se' e 'dá errado se'"),
    # CARTA_EDITORIAL.md, "Cuidados para o redator": recorde tem a régua da série.
    (re.compile(r"\b(já (registrad|vist)[oa]s?|de todos os tempos|da história)\b", re.I),
     "recorde sem a régua: diga 'da série' ou desde quando a série existe, como a fonte diz"),
]

FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀÁÉÍÓÚÂÊÔÃÕÇ0-9\"“])")
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
    # A direção diz para que lado o risco andou; não é previsão de recessão.
    (re.compile(r"\b(vai|deve|irá) (ter|haver|entrar em) (uma )?recessão|recessão (vem|virá|é certa)|"
                r"(não|nem) (vai|deve) (ter|haver) (uma )?recessão\b", re.I), "prevê recessão"),
    # O site faz a análise do fato e para aí: não promete conferir, acompanhar nem testar depois (Pedro, 8/11/2026).
    (re.compile(r"\b(o site|n[óo]s|a gente)\s+(vai|vamos|voltar[áa]|volta|seguir[áa]|segue)\s+(a\s+)?"
                r"(conferir|acompanhar|olhar|observar|monitorar|testar|checar|verificar|dizer|mostrar se|voltar)\b|"
                r"\bvamos (conferir|acompanhar|ver se|testar|checar|monitorar)\b|o que o site vai conferir", re.I),
     "promete conferir ou acompanhar depois: o site faz a análise do fato e para aí"),
    # O risco de recessão é qualitativo: nunca vira número.
    (re.compile(r"(\d+(,\d+)?\s*(%|por cento)\s*de (chance|probabilidade|risco)|(chance|probabilidade|risco) "
                r"(de recessão )?(é |fica |sobe para |cai para |vai a |de )?(de )?\d+(,\d+)?\s*(%|por cento)|"
                r"\d+(,\d+)?\s*(×|vezes o normal|vezes a chance)|\bvezes o normal\b)", re.I), "dá número ao risco de recessão"),
]


# O post conta o fato; como a conta funciona fica na aba Como funciona. Uma frase só pode dizer que um
# fato fica fora da conta, quando ele parece contradizer a direção (regra 6 do prompt do post).
CONTA_FUNCIONA = re.compile(r"\b((não|nem) (entra|entram|mexe|mexem|move|movem|muda|mudam|altera|alteram) "
                            r"(n[oa] |o |a )?(número|conta|soma|direção)|entram? n[oa] (número|conta|soma|direção)|"
                            r"só se (mexe|move)|(fora|dentro) d[oa] (número|conta|soma|direção))\b", re.I)

# Fato do dia com a direção parada: o topo da página já mostra a direção e o que cada pressão fez em 3 meses.
DIRECAO_REPETIDA = re.compile(r"\b(risco( de recessão)?[^.]{0,30}\b(segue|seguiu|continua|continuou|está|fica|ficou|"
                              r"permanece|permaneceu)\b[^.]{0,12}\b(subindo|igual|caindo|em alta|em queda)|"
                              r"direção (do risco )?(segue|continua|está|fica|permanece|é|de)\b|"
                              r"(uma|duas|três|quatro|cinco|\d) das cinco pressões)", re.I)

LIMITE_PALAVRAS = {"dia": 120, "semana": 300, "mes": 360}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
DATA_BARRA = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}))?(?![\d/])")
DATA_EXTENSO = re.compile(r"\b(\d{1,2})(?:º)? de (" + "|".join(MESES) + r")\b", re.I)
NUM = re.compile(r"(?<![A-Za-z0-9_,.])(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(?![\d])")
# Números que o prompt dá ao modelo fora dos dados: desde 2004, 3 meses, 12 meses, cinco pressões.
CONSTANTES = "2004 3 12 5"


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
    if CONTA_FUNCIONA.search(post["titulo"]):
        out.append("título: explica como a conta da direção funciona")
    n = sum(1 for f in _frases(post["paragrafos"]) if CONTA_FUNCIONA.search(f))
    if n > 1:
        out.append(f"{n} frases explicam como a conta funciona (o post pode ter uma, quando o fato parece contradizer a direção)")
    if dados is not None:
        fora = numeros_fora(textos, dados)
        if fora:
            out.append("número ou data que não está nos dados: " + ", ".join(fora[:6])
                       + " (use só os números dos dados, sem recalcular)")
    return out


def _nomes_do_site() -> set[str]:
    """Os nomes das pressões, das linhas do topo e dos assuntos das notícias (config/modelo.json)."""
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config" / "modelo.json").read_text())
    return {*cfg["direcao"]["nomes"].values(), *cfg["fatores"].values()}


# Siglas que todo mundo conhece; as outras vão por extenso ou com link (glossario em config/modelo.json).
SIGLAS_CONHECIDAS = {"PIB", "IBGE", "EUA", "INSS", "FGTS", "SUS", "STF", "ONU", "US", "PIX", "CPF", "MEI", "IPVA", "IPTU"}
SIGLA = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")


def _glossario() -> list[re.Pattern]:
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config" / "modelo.json").read_text())
    return [re.compile(g["rx"]) for g in (cfg.get("glossario") or {}).get("termos", [])]


def siglas_soltas(texto: str) -> list[str]:
    """Siglas que a leitora não conhece e que o site não liga à Wikipédia (PERSONA.md, "O jeito de escrever do site")."""
    com_link = {m.group(0) for rx in _glossario() for m in rx.finditer(texto)}
    # A sigla com link no próprio texto ([PMI](https://...)) está explicada; o endereço do link não tem sigla.
    com_link |= set(re.findall(r"\[([^\]]+)\]\([^)]*\)", texto))
    texto = re.sub(r"\]\([^)]*\)", "]", texto)
    return sorted({s for s in SIGLA.findall(texto) if s not in SIGLAS_CONHECIDAS and not any(s in c for c in com_link)})


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
        sig = siglas_soltas(t)
        if sig:
            out.append(f"sigla que a leitora não conhece ({', '.join(sig)}): escreva o nome por extenso, se ele explica: {t[:60]}")
    out += _aberturas([ev["porque"] for ev in saida.get("eventos", [])])
    return out


def problemas_post(post: dict, tipo: str = "dia", dados: str | None = None, hoje=None, anterior: dict | None = None,
                   direcao_mudou: bool = True, **_) -> list[str]:
    """Moldes de texto e, nos posts, o que repete a página: direção parada, data da lateral, frase do post anterior."""
    import datetime as dt
    from difflib import SequenceMatcher

    out = []
    t = post["titulo"]
    if len(t) > 80:
        out.append(f"título com {len(t)} caracteres")
    if t.rstrip().endswith("?"):
        out.append("título em forma de pergunta")
    out += [f"título: {m}" for m in _moldes(t) if m in ("travessão", "ponto de exclamação", "palavra de alarme", "palavra com lado")
            or m.startswith(("palavra que o site trocou", "conta as pressões"))]
    # Os rótulos do resumo da semana usam os nomes do site: uma pressão ou um assunto das notícias.
    nomes = _nomes_do_site()
    for sec in post.get("secoes") or []:
        for it in sec.get("itens") or []:
            if it.get("rotulo") and it["rotulo"] not in nomes:
                out.append(f"rótulo \"{it['rotulo']}\" não é nome do site: use o nome de uma pressão ou de um assunto das notícias")
    for i, p in enumerate(post["paragrafos"], 1):
        out += [f"parágrafo {i}: {m}" for m in _moldes(p)]
        if len(p.split()) > 65:
            out.append(f"parágrafo {i} com {len(p.split())} palavras")
        longas = [len(f.split()) for f in FRASE.split(p) if len(f.split()) > 32]
        if longas:
            out.append(f"parágrafo {i} com frase de {max(longas)} palavras")
        if len(NUMERO.findall(p)) > 4:
            out.append(f"parágrafo {i} com {len(NUMERO.findall(p))} números")
        if any(INFLACAO_CAI.search(f) and "mais devagar" not in f for f in FRASE.split(p)):
            out.append(f"parágrafo {i}: inflação que 'cai' ou 'recua' sem dizer que os preços sobem mais devagar")
        if re.search(r"\b(eu|nós|nosso|nossa)\b", p, flags=re.IGNORECASE):
            out.append(f"parágrafo {i} em primeira pessoa")
    # Regra 9 do prompt do fato do dia e src/verifica_base.py: até 100 palavras no total.
    total = sum(len(p.split()) for p in post["paragrafos"])
    if tipo == "dia" and total > 100:
        out.append(f"fato do dia com {total} palavras (até 100): corte o que não é o fato, sem mudar os números")
    sig = siglas_soltas(" ".join(_prosa(post)))
    if sig:
        out.append(f"sigla que a leitora não conhece ({', '.join(sig)}): escreva o nome por extenso quando ele explica "
                   "(Confederação Nacional da Indústria, Tribunal de Contas da União); IFI e BNDES podem ficar, porque o site liga")
    dez = len(re.findall(r"\bpor (uns |cerca de )?10 anos\b", " ".join(post["paragrafos"])))
    if dez > 1:
        out.append("repete 'por 10 anos': depois da primeira vez, 'quando o governo paga mais para pegar dinheiro emprestado' basta")
    out += _aberturas(post["paragrafos"], limite=1)
    palavras = sum(len(p.split()) for p in post["paragrafos"])
    if palavras > LIMITE_PALAVRAS.get(tipo, 10**6):
        out.append(f"texto com {palavras} palavras (o limite é {LIMITE_PALAVRAS[tipo] * 5 // 6})")
    if tipo == "dia" and not direcao_mudou:
        rep = [f for f in _frases(_prosa(post)) if DIRECAO_REPETIDA.search(f) and not CONTA_FUNCIONA.search(f)]
        if rep:
            out.append("repete a direção do risco, que não mudou e já está no topo da página: " + rep[0][:70])
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
            # A frase da regra 6 ("Isso não muda a direção do risco, porque...") é fórmula: pode repetir.
            if len(f.split()) >= 6 and not CONTA_FUNCIONA.search(f) and any(SequenceMatcher(None, f.lower(), v.lower()).ratio() > 0.8 for v in velhas):
                out.append(f"frase copiada do post anterior: {f[:70]}")
    return out + graves_post(post, tipo=tipo, dados=dados)
