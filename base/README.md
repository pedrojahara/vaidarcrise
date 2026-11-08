# Base de conhecimento (fase 0)

Esta pasta é a fase 0 da ideia que veio do leitor Bruno: ligar cada notícia à causa de fundo dela, com fontes que alguém pode conferir. A fase 0 publica uma pergunta-mãe, "Por que o juro do Brasil é tão alto?", guarda como rascunho a do dólar, "Por que o dólar sobe tanto no Brasil?". Os fatos do dia de 3 a 7 de novembro de 2026 tiveram uma escada de porquês, trocada em 8/11 pela leitura a fundo (abaixo).

**O que o site mostra daqui**: a página de cada pergunta publicada em `/perguntas/<id>/` e, no topo, o link de cada pressão para a sua página. Desde 8/11/2026, a escada de porquês dos fatos do dia saiu: no lugar dela, cada fato do dia tem a leitura a fundo (`post.fundo` em `runs/`), um texto corrido com tese, feito por `src/fundo.py` com o guia [FUNDO.md](../FUNDO.md), e a rodada das 06h30 a faz sozinha depois do post. A leitura a fundo leva à página da pressão onde a corrente termina (`post.termina_em`, `post.pergunta`). Quem monta a página é `src/base_site.py`, chamado por `src/build_site.py`; um erro aqui não derruba a atualização do dia.

**As memórias da leitura a fundo** ficam em `memoria/` (`src/memoria.py`): `longa.json` (episódios do passado, além dos 8 de `episodios.json`), `momento/AAAA-MM.json` (o que aconteceu mês a mês desde maio de 2025, com fonte; a rodada junta os fatos do dia) e `historias.json` (as histórias abertas, revistas no domingo). A memória do site sai de `runs/`.

## Uma página por pressão (decisão do Pedro, 7/11/2026)

Cada pergunta-mãe pertence a uma das pressões do topo (`pressao`, uma chave de `direcao.nomes` em `config/modelo.json`), e cada pressão tem no máximo uma página. As regras:

- **Um fato liga a uma página só**: a da pressão onde a corrente de porquês termina (`post.termina_em`). Se essa pressão ainda não tem página publicada, o "Entenda a fundo" leva ao passo da aba O que causa recessão (`direcao.causas` em `config/modelo.json`). O fato do petróleo de 3/11 termina na inflação e vai para a aba; o do dólar de 4/11 termina na desconfiança de quem investe e usa o teste guardado no rascunho do dólar.
- **Ordem das páginas novas**: a pressão com mais fatos do dia ligados nos últimos 30 dias. O Pedro decide no resumo do mês, e sai no máximo uma página nova por mês.
- **Rascunho** (`publicada: false`): não vira página nem aparece no topo, mas guarda a disputa e o teste, que o post que os cita mostra.
- **Disputa só se existe**: a página mostra leituras em disputa apenas quando os estudos de fato divergem.
- **A página nunca some**: o bloco "O que está em jogo agora" só aparece quando um fato ligado saiu nos últimos 30 dias; sem isso, a página fica como referência.

A fase 0 mede três coisas:

1. quanto da assinatura uma pergunta-mãe consome (`base/conferencia/uso.jsonl`);
2. quantas afirmações o verificador derruba, e se uma conferência à mão concorda com ele;
3. se a leitora entende e confia (teach-back com o Bruno e mais três ou quatro pessoas; parte do Pedro).

## Arquivos

| Arquivo | O que guarda |
|---|---|
| `afirmacoes.json` | Cada frase que a base pode dizer, com a prova dela. Três tipos: `dado` (número de uma série do site, com data e tolerância), `documento` (fonte com nível, endereço e trecho literal) e `site` (trecho de uma página do próprio site). |
| `episodios.json` | Episódios do passado (2002 a 2026), com números das séries do site, de onde veio a causa (`daqui`, `de fora`, `as duas`) e o passo da aba O que causa recessão em que caem. `governo` serve só ao teste da troca. |
| `perguntas/<id>.json` | Uma pergunta-mãe: `pressao`, `publicada`, resposta curta, `governo` (se a causa é de um governo só, com a linha do tempo dos episódios), `agora` (o que está em jogo), escada de porquês com as leituras, testes registrados antes do resultado, episódios e registro de mudanças. |
| `conferencia/` | Relatórios do verificador e dos agentes, e o registro de consumo. Ficam no git porque são a medição da fase 0. |
| `cache/` | Cópia das páginas que o código abriu. Fora do git. |
| `runs/<dia>.json`, `post.fundo` | A leitura a fundo de um fato do dia (`src/fundo.py`): `titulo` (a tese, no botão), `texto` (Markdown com até 3 intertítulos `###` e as marcas `[c3]` do caderno), `previsao`, `caderno` (cada linha com a conferência do código), `voltas` (as teses e o veredito do editor-chefe), `conferencia` e `meta` (modelo, custo e tempo de cada etapa). `post.termina_em` e `post.pergunta` dizem a página da pressão do fim. |

## A escada

A pergunta-mãe guarda só o que dura anos: a `raiz` (as explicações, com as leituras) e `o_que_vem_depois` (o que muda para a leitora). Uma divisão que não é da pressão da página fica no rascunho da pressão certa (a do dólar está em `perguntas/dolar-alto.json`). Os degraus presos a um dia, como o fato e a causa imediata, ficam na escada do post. Todo degrau da pergunta-mãe tem um rótulo:

- `consenso`: as fontes de nível 1 a 3 concordam;
- `maioria_com_dissenso`: há uma leitura dominante e leituras minoritárias sérias;
- `em_disputa`: a evidência ainda não decide.

Um degrau com divisão ou raiz traz `leituras`. Cada leitura tem nome pelo mecanismo (nunca pelo partido), o que diz, o que pesa a favor, a melhor objeção com fonte, a resposta a ela, quem defende e um status: `em_pe`, `maioria`, `em_disputa`, `minoria`, `pouco_testada` ou `testada_e_nao_confirmada`. Na página, `maioria` e `em_pe` viram cartões com `titulo` (o nome que a leitora entende) e a objeção à vista; as outras viram uma linha com `resumo` (uma frase), agrupadas pelo status, e os estudos ficam atrás de um toque.

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
- Uma página por pressão: toda pergunta tem uma `pressao` que existe no topo, só uma pergunta publicada por pressão, e toda pergunta publicada tem resposta curta.
- Fatos do dia com escada: até 100 palavras, 3 parágrafos de até 50, título de até 70 caracteres, todo número numa afirmação citada, `termina_em` igual à pressão da pergunta-mãe citada, só o último degrau sem rótulo, e cada degrau ligado a algo que existe em alguma pergunta (publicada ou rascunho).

## Como rodar (no Mac)

A nuvem não abre as fontes (o proxy recusa), então a conferência de verdade e os agentes rodam no Mac, numa cópia separada do repositório para não mexer na rodada diária.

```sh
cd /Users/pedrojahara/Development/Pessoal/vaidarcrise
git fetch origin claude/project-thread-iwulvz
git worktree add ../vaidarcrise-fase0 origin/claude/project-thread-iwulvz
cd ../vaidarcrise-fase0
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt pypdf

.venv/bin/python src/verifica_base.py                    # confere dados, trechos e regras
.venv/bin/python src/pesquisa_base.py teste --aplicar    # teste das moedas com a Ptax (sem IA; só a partir de 7/12/2026)
.venv/bin/python src/pesquisa_base.py trechos --aplicar  # agente acha o trecho; código confere
.venv/bin/python src/verifica_base.py                    # de novo, com os trechos novos
.venv/bin/python src/pesquisa_base.py advogado           # agente tenta derrubar cada leitura
.venv/bin/python src/pesquisa_base.py uso                # consumo somado
```

`pesquisa_base.py` usa `CLAUDE_BIN` (padrão `~/.local/bin/claude`, o do terminal do Mac) e `VDC_PESQUISA_MODELO` (padrão `opus`). Toda chamada fica em `conferencia/uso.jsonl` com tokens, buscas, segundos e o custo que o `claude -p` informa. Com assinatura, esse custo é uma estimativa do que a chamada gastaria na API, útil para comparar perguntas entre si.
