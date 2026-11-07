# Base de conhecimento (fase 0)

Esta pasta é a fase 0 da ideia que veio do leitor Bruno: ligar cada notícia à causa de fundo dela, com fontes que alguém pode conferir. A fase 0 constrói uma pergunta-mãe só, "Por que o juro do Brasil é tão alto?", e reescreve com a escada de porquês os fatos do dia de 3 a 7 de novembro de 2026.

**O que o site mostra daqui** (desde 7/11/2026, a pedido do Pedro): o "Entenda a fundo" dos fatos do dia que têm `post.escada` em `runs/`, e a página de cada pergunta-mãe em `/perguntas/<id>/`. Quem monta é `src/base_site.py`, chamado por `src/build_site.py`; um erro na base não derruba a atualização do dia. A rodada diária (`run.sh`) ainda não escreve escadas: os posts novos saem como antes até o Pedro decidir a fase 1.

A fase 0 mede três coisas:

1. quanto da assinatura uma pergunta-mãe consome (`base/conferencia/uso.jsonl`);
2. quantas afirmações o verificador derruba, e se uma conferência à mão concorda com ele;
3. se a leitora entende e confia (teach-back com o Bruno e mais três ou quatro pessoas; parte do Pedro).

## Arquivos

| Arquivo | O que guarda |
|---|---|
| `afirmacoes.json` | Cada frase que a base pode dizer, com a prova dela. Três tipos: `dado` (número de uma série do site, com data e tolerância), `documento` (fonte com nível, endereço e trecho literal) e `site` (trecho de uma página do próprio site). |
| `episodios.json` | Episódios do passado (2002 a 2026), com números das séries do site, de onde veio a causa (`daqui`, `de fora`, `as duas`) e o passo da aba O que causa recessão em que caem. `governo` serve só ao teste da troca. |
| `perguntas/<id>.json` | Uma pergunta-mãe: resposta curta, escada de porquês, leituras, testes registrados antes do resultado, episódios e registro de mudanças. |
| `conferencia/` | Relatórios do verificador e dos agentes, e o registro de consumo. Ficam no git porque são a medição da fase 0. |
| `cache/` | Cópia das páginas que o código abriu. Fora do git. |
| `runs/<dia>.json`, `post.escada` | A escada de um fato do dia: cada degrau com pergunta, rótulo (`fato`, `consenso`, `maioria_com_dissenso`, `em_disputa`), texto, afirmações e, se houver, `liga` (degrau da pergunta-mãe), `link` e `teste`. `post.paragrafos_afirmacoes` diz que afirmações sustentam cada parágrafo, e `post.versao_anterior` guarda o texto que saiu no dia. |

## A escada

Cada pergunta tem os degraus `fato`, `causa_imediata`, `mecanismo`, `divisao`, `raiz` e `o_que_vem_depois`. Todo degrau tem um rótulo:

- `consenso`: as fontes de nível 1 a 3 concordam;
- `maioria_com_dissenso`: há uma leitura dominante e leituras minoritárias sérias;
- `em_disputa`: a evidência ainda não decide.

Um degrau com divisão ou raiz traz `leituras`. Cada leitura tem nome pelo mecanismo (nunca pelo partido), o que diz, o que pesa a favor, a melhor objeção com fonte, a resposta a ela, quem defende e um status: `em_pe`, `maioria`, `em_disputa`, `minoria`, `pouco_testada` ou `testada_e_nao_confirmada`.

Divisões que dados futuros podem decidir têm um `teste` registrado antes do resultado: medida, regra, datas de conferência e o que cada leitura espera. O resultado entra em `resultados` sem apagar a regra. Não há placar somado de acertos (decisão do Pedro, 7/11/2026).

## Níveis de fonte

1 metanálise; 2 artigo revisado por pares ou capítulo de livro acadêmico; 3 Banco Central, FMI, Tesouro, IBGE, IFI, Ipea ou lei; 4 tese ou dissertação; 5 banco ou consultoria; 6 notícia; 7 comentarista. Comentarista pode aparecer em `quem_defende`, nunca como prova. Consenso não pode se apoiar só em nível 5 ou pior, e uma leitura `maioria` precisa de fonte de nível 1 a 3.

## O que o verificador confere (`src/verifica_base.py`)

- Afirmação `dado`: o valor bate com a série do site na data, dentro da tolerância.
- Afirmação `documento`: o código abre o endereço (HTML ou PDF) e procura o trecho literal, palavra por palavra, depois de normalizar acentos e espaços. Resultado: `conferido`, `trecho_nao_achado`, `sem_trecho`, `sem_endereco`, `fonte_inacessivel` ou `nao_aberta` (modo `--offline`).
- Afirmação `site`: o trecho está no arquivo do repositório.
- Todo número de um texto da pergunta aparece numa afirmação que o texto cita.
- Ligações: toda afirmação citada existe, todo episódio e teste aponta para algo que existe, e nenhuma afirmação fica sem uso.
- Escrita: frase de até 30 palavras, sem os moldes de efeito de `src/revisa_texto.py`, sigla com link ou por extenso, nenhum nome de partido ou presidente nos textos.
- Leituras: todas têm melhor objeção e algo a favor; os testes cobrem as leituras da divisão; os episódios cobrem pelo menos três governos e causas daqui e de fora.
- Fatos do dia com escada: até 100 palavras, 3 parágrafos de até 50, título de até 70 caracteres, todo número numa afirmação citada, e cada degrau ligado a algo que existe na pergunta-mãe.

## Como rodar (no Mac)

A nuvem não abre as fontes (o proxy recusa), então a conferência de verdade e os agentes rodam no Mac, numa cópia separada do repositório para não mexer na rodada diária.

```sh
cd /Users/pedrojahara/Development/Pessoal/vaidarcrise
git fetch origin claude/project-thread-iwulvz
git worktree add ../vaidarcrise-fase0 origin/claude/project-thread-iwulvz
cd ../vaidarcrise-fase0
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt pypdf

.venv/bin/python src/verifica_base.py                    # confere dados, trechos e regras
.venv/bin/python src/pesquisa_base.py teste --aplicar    # teste das moedas com a Ptax (sem IA)
.venv/bin/python src/pesquisa_base.py trechos --aplicar  # agente acha o trecho; código confere
.venv/bin/python src/verifica_base.py                    # de novo, com os trechos novos
.venv/bin/python src/pesquisa_base.py advogado           # agente tenta derrubar cada leitura
.venv/bin/python src/pesquisa_base.py uso                # consumo somado
```

`pesquisa_base.py` usa `CLAUDE_BIN` (padrão `claude`) e `VDC_PESQUISA_MODELO` (padrão `opus`). Toda chamada fica em `conferencia/uso.jsonl` com tokens, buscas, segundos e o custo que o `claude -p` informa. Com assinatura, esse custo é uma estimativa do que a chamada gastaria na API, útil para comparar perguntas entre si.
