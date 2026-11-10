"""As decisões de órgãos públicos que os posts contam, e quanto cada uma é analisada.

Quem decide a profundidade é o código, com o que o classificador de notícias marca (estágio, quem decidiu, tipo de
decisão e tamanho), e não a IA do dia: assim o site não aprofunda mais as decisões de um lado do que as do outro.

O site analisa a decisão pelo objetivo que o próprio decisor escreveu (o meio, nunca o fim), com a evidência da
biblioteca (EVIDENCIA.md), escrita antes e igual para qualquer governo. O site não guarda placar de acertos, não volta
depois para conferir e não diz o que o decisor deveria ter feito (decisão do Pedro em 8/11/2026).

Níveis (nivel()):
- "analise": decisão tomada ou em votação, de órgão público do Brasil que decide sobre a economia (Banco Central,
  governo federal, Congresso, estados e municípios, agências), de tamanho 2 ou 3, de um tipo com entrada na
  biblioteca: as oito perguntas.
- "basico": outra decisão pública do Brasil (tamanho 1, tribunal, órgão de controle, tipo sem entrada): as perguntas
  1 a 4.
- "anuncio": anúncio de órgão público do Brasil: o básico e o que falta para virar ato.
- None: dado, previsão, rumor, decisão de empresa ou de fora do país, que o site conta pelo efeito.

Uso:
  python src/decisoes.py [--de AAAA-MM-DD] [--ate AAAA-MM-DD]   # as decisões de data/eventos.json e o nível de cada uma
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIBLIOTECA = ROOT / "EVIDENCIA.md"

# Quem decidiu (classificador de notícias, campo "decisor").
DECISORES = {
    "banco_central": "Banco Central",
    "governo_federal": "governo federal (Presidência, ministérios, Tesouro, BNDES, Caixa)",
    "congresso": "Congresso (Câmara ou Senado)",
    "estados_municipios": "governos estaduais ou municipais",
    "agencia": "agência reguladora (Aneel, ANP, Anatel, ANS...)",
    "orgao_de_controle": "órgão de controle (TCU, CGU), que propõe ou fiscaliza, mas não fixa a regra",
    "tribunal": "tribunal (STF, STJ...)",
    "empresa": "empresa (inclusive estatal agindo como empresa, como a Petrobras no preço do dia)",
    "fora": "decisor de fora do Brasil (Fed, governo dos EUA, Opep, China)",
    "nenhum": "não é decisão (dado, previsão, notícia de mercado)",
}
# O tipo de decisão (campo "instrumento"): cada um tem uma entrada na biblioteca, menos "outro" e "nenhum".
INSTRUMENTOS = {
    "juros_cambio": "juros e câmbio (Selic, compra e venda de dólares pelo Banco Central)",
    "gasto": "gasto e transferência (orçamento, programas, benefícios, investimento público)",
    "imposto": "imposto e renúncia (alta ou corte de imposto, isenção, desconto para um setor)",
    "credito_publico": "crédito público (BNDES, Caixa, Banco do Brasil, crédito com dinheiro ou garantia do governo)",
    "preco_regulacao": "preço administrado e regulação (combustível da Petrobras, energia, salário mínimo, regras de agência)",
    "regra_fiscal": "regra fiscal e instituição (arcabouço, meta das contas, Lei de Responsabilidade Fiscal, dívida de estados)",
    "divida_publica": "gestão da dívida pública (leilões, recompras e prazos dos títulos do Tesouro)",
    "outro": "outra decisão, sem entrada na biblioteca",
    "nenhum": "não é decisão",
}
PUBLICOS = {"banco_central", "governo_federal", "congresso", "estados_municipios", "agencia"}
SO_BASICO = {"orgao_de_controle", "tribunal"}
# Para os eventos de antes destes campos (até 8/11/2026): o Banco Central se reconhece pela origem.
_DA_ORIGEM = {"banco_central": ("banco_central", "juros_cambio"), "mundo": ("fora", "nenhum")}

PERGUNTAS_BASICO = [
    "Quem decidiu, com que poder e quem pode desfazer? (o Senado aprovar não é lei; o Tribunal de Contas da União "
    "propor não é o Congresso fixar; anunciar não é fazer)",
    "Qual objetivo o decisor escreveu, e em que documento? (o comunicado e a ata do Copom; a exposição de motivos de "
    "medida provisória, decreto ou projeto; a estimativa de impacto que o artigo 113 do ADCT e o artigo 14 da Lei de "
    "Responsabilidade Fiscal exigem de quem cria gasto obrigatório ou abre mão de imposto; a análise de impacto "
    "regulatório das agências, pelo Decreto 10.411/2020; a nota do Tesouro). Se o objetivo não está escrito, ou é "
    "vago, diga isso: já é informação",
    "Qual é o tamanho? (em reais, em fatia do PIB, em reais por brasileiro e perto do problema que a decisão diz "
    "resolver; quando o decisor estima o próprio impacto e outro órgão também, como a IFI, as consultorias da Câmara "
    "e do Senado ou o TCU, as duas contas entram)",
    "Em que pressão do site e em que porta da leitora ela mexe: o emprego, o preço, a parcela ou o dólar?",
]
PERGUNTAS_ANALISE = [
    "Por que caminho a decisão chega ao objetivo que o decisor escreveu, e o que a evidência da biblioteca diz desse "
    "caminho, com a força (forte, média ou fraca) e o estudo que discorda?",
    "O que aconteceu das outras vezes, no Brasil, desde 2002, em todos os governos, contadas por episódio e não por "
    "mês (src/conta.py episodios, pausas e ciclos; o episódio longo não vale mais que o curto)? Sem casos parecidos, "
    "diga isso e não dê chance",
    "Dá certo se, dá errado se: até duas condições de cada lado, cada uma com o sinal que a mostra e o corte (a "
    "inflação esperada parar de subir; a arrecadação ficar abaixo da estimativa do próprio governo), e qual lado os "
    "casos parecidos e a evidência deixam mais provável. Quando a evidência não deixa dizer, a resposta é que ainda "
    "não dá para dizer",
    "Quem ganha, quem paga e quando; a melhor objeção de cada lado, com o número dela; e o espelho: a mesma régua "
    "numa decisão parecida de outro governo, para mostrar que o critério não muda com quem decide",
]


def campos(ev: dict) -> tuple[str, str]:
    """(decisor, instrumento) de um evento, com a origem para os eventos de antes desses campos."""
    d, i = ev.get("decisor"), ev.get("instrumento")
    if d and i:
        return d, i
    dd, ii = _DA_ORIGEM.get(ev.get("origem") or "", (None, None))
    return d or dd or "nenhum", i or ii or "outro"


def biblioteca(tipo: str) -> str | None:
    """A entrada da biblioteca de um tipo de decisão (do título "## " com a marca <!-- tipo: X --> até o próximo)."""
    try:
        txt = BIBLIOTECA.read_text()
    except OSError:
        return None
    for parte in re.split(r"\n(?=## )", txt):
        if re.search(rf"<!--\s*tipo:\s*{re.escape(tipo)}\s*-->", parte):
            return parte.strip()
    return None


def regras_gerais() -> str:
    """A parte da biblioteca que vale para todos os tipos (antes da primeira entrada)."""
    try:
        txt = BIBLIOTECA.read_text()
    except OSError:
        return ""
    m = re.search(r"\n## .*\n\s*<!--\s*tipo:", txt)
    return txt[:m.start()].strip() if m else ""


def nivel(ev: dict | None) -> str | None:
    if not ev:
        return None
    dec, ins = campos(ev)
    est = ev.get("estagio")
    if dec not in PUBLICOS | SO_BASICO:
        return None
    if est == "anuncio":
        return "anuncio" if dec in PUBLICOS else None
    if est not in ("decidido", "em_votacao"):
        return None
    if dec in PUBLICOS and (ev.get("magnitude") or 1) >= 2 and ins in INSTRUMENTOS and biblioteca(ins):
        return "analise"
    return "basico"


def _quem(ev: dict) -> str:
    dec, ins = campos(ev)
    return f"{DECISORES.get(dec, dec)}; tipo: {INSTRUMENTOS.get(ins, ins)}"


def bloco_pesquisa(ev: dict | None) -> str:
    """O que a pesquisa, a redação e o revisor do texto do dia recebem quando o fato do dia é uma decisão pública: as
    perguntas do nível e, na análise, a entrada da biblioteca do tipo."""
    nv = nivel(ev)
    if not nv:
        return ""
    dec, ins = campos(ev)
    cab = [f"<decisao>\nO fato do dia é uma decisão pública: {ev['titulo_evento']} ({_quem(ev)}; estágio: "
           f"{ev.get('estagio')}; tamanho {ev.get('magnitude')} de 3)."]
    if ev.get("objetivo"):
        cab.append(f"O objetivo que as manchetes atribuem a quem decidiu: {ev['objetivo']} (confira no documento oficial).")
    if nv == "anuncio":
        cab.append("É um anúncio, e não um ato: responda às perguntas do básico com o que já se sabe e diga o que falta "
                   "para virar ato (o documento, o tamanho e a data). Não analise o mérito.")
        perguntas = PERGUNTAS_BASICO
    elif nv == "basico":
        cab.append("Nível: básico (o código decide pelo estágio, por quem decidiu e pelo tamanho). Responda às quatro "
                   "perguntas do básico, cada uma com linhas do caderno.")
        perguntas = PERGUNTAS_BASICO
    else:
        cab.append("Nível: análise completa (o código decide pelo estágio, por quem decidiu e pelo tamanho). Responda "
                   "às oito perguntas, nesta ordem, cada uma com linhas do caderno. O caminho e a força da evidência "
                   "vêm só da entrada da biblioteca abaixo: cite-a no caderno com o tipo \"biblioteca\", com o trecho "
                   "copiado como está nela e o link do estudo.")
        perguntas = PERGUNTAS_BASICO + PERGUNTAS_ANALISE
    cab += [f"{k}. {p}" for k, p in enumerate(perguntas, 1)]
    cab.append("Escreva cada pergunta em \"perguntas\" com estas palavras, na mesma ordem, antes das suas outras perguntas.")
    if nv == "analise":
        cab += ["", regras_gerais(), "", biblioteca(ins) or ""]
    return "\n".join(cab).strip() + "\n</decisao>"


def do_periodo(eventos: dict, ini: str, fim: str) -> list[dict]:
    """As decisões públicas do Brasil do período (de data/eventos.json), com o nível de cada uma."""
    out = []
    for ev in sorted(eventos.values(), key=lambda e: (e["data"], e["id"])):
        if ini <= ev["data"] <= fim:
            nv = nivel(ev)
            if nv:
                dec, ins = campos(ev)
                out.append({"id": ev["id"], "data": ev["data"], "titulo": ev["titulo_evento"], "nivel": nv,
                            "decisor": dec, "instrumento": ins, "estagio": ev.get("estagio"),
                            "objetivo": ev.get("objetivo") or ""})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--de", default="0000")
    ap.add_argument("--ate", default="9999")
    a = ap.parse_args()
    evs = {e["id"]: e for e in json.loads((ROOT / "data" / "eventos.json").read_text())}
    for d in do_periodo(evs, a.de, a.ate):
        print(f"{d['data']} {d['nivel']:8} {d['decisor']:18} {d['instrumento']:16} {d['titulo']}")


if __name__ == "__main__":
    main()
