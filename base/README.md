# Base de conhecimento

Esta pasta guarda o que dura mais que um dia: as páginas das Grandes perguntas (`/perguntas/<id>/`, uma por pressão do topo), as frases que sustentam essas páginas e as memórias que o texto do dia usa. `src/base_site.py` monta as páginas; `src/memoria.py` cuida das memórias.

## Arquivos

| Arquivo | O que guarda |
|---|---|
| `perguntas/<id>.json` | Uma página: `pressao` (uma chave de `direcao.nomes` em `config/modelo.json`), `publicada`, a resposta curta, `medida` (como o topo mede a pressão), `governo` (se a causa é de um governo só, com os episódios), `agora` (o que está em jogo) e a `escada`, com a `raiz` (as explicações) e `o_que_vem_depois` ("O que isso muda para você?"). |
| `afirmacoes.json` | Cada frase que a base pode dizer, com a prova. Quatro tipos: `dado` (número de uma série do site, com data e tolerância), `documento` (fonte com nível, endereço e trecho literal), `site` (trecho de uma página do site) e `conta` (a tradução de `TRADUCAO.md`, com o comando de `src/conta.py`). |
| `episodios.json` | Episódios de 2002 a 2026, com números das séries do site e de onde veio a causa (`daqui`, `de fora`, `as duas`). |
| `memoria/` | As memórias do texto do dia: `longa.json` (episódios do passado), `momento/AAAA-MM.json` (o que aconteceu mês a mês, com fonte) e `historias.json` (as histórias em andamento, que a pauta soma). |
| `cache/` | Cópia das páginas que o verificador abriu. Fora do git. |

## Regras das páginas

- **Uma página por pressão**, e nenhuma página nova sai sozinha. Quando a rodada sente falta de uma, ela avisa o Pedro, que decide.
- **Um fato do dia liga a uma página só**, na linha "O básico sobre…" logo abaixo do texto (`ponte()` em `src/base_site.py`).
- **Rascunho** (`publicada: false`) não vira página.
- **Sem bastidor.** A página mostra a análise e para aí: cada trecho tem a linha de fontes, com o nome e o link, e nada mais. Não há selo de conferência, histórico de mudanças, data de atualização, teste guardado nem promessa de voltar ao assunto.
- **"O que está em jogo agora"** só aparece quando um fato ligado saiu nos últimos 30 dias, e o texto dele diz o mês de cada número.
- **O texto segue o PERSONA.md**, como qualquer texto do site, e fala com quem é gestor ou tem o próprio negócio: o que a pressão muda em casa e no trabalho.

## A escada

A `raiz` traz as explicações (`leituras`), e cada leitura tem nome pelo mecanismo (nunca pelo partido), o que diz, o que pesa a favor, a melhor objeção com fonte, a resposta a ela, quem defende e um status: `em_pe`, `maioria`, `em_disputa`, `minoria`, `pouco_testada` ou `testada_e_nao_confirmada`. O `peso_da_evidencia` diz, numa frase, quanto os estudos concordam. O rótulo do degrau é `consenso`, `maioria_com_dissenso` ou `em_disputa`.

Níveis de fonte: 1 metanálise; 2 artigo revisado por pares ou capítulo de livro acadêmico; 3 Banco Central, FMI, Tesouro, IBGE, IFI, Ipea ou lei; 4 tese ou dissertação; 5 banco ou consultoria; 6 notícia; 7 comentarista. Comentarista pode aparecer em `quem_defende`, nunca como prova.

## O verificador

`.venv/bin/python src/verifica_base.py` confere, sem IA, as ligações (toda afirmação e episódio citado existe), os dados e as contas contra as séries do site, os números de cada texto, as regras de leitura (melhor objeção, nenhum nome de partido, nenhum teste nem promessa de conferir depois) e a escrita (frase de até 30 palavras, sigla com link). O trecho literal de cada documento só é procurado com rede, no Mac; na nuvem, use `--offline`. O resultado aparece na tela e não fica guardado.
