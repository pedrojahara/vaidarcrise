# Vai dar crise?

## Todo texto passa pelo leitor

O site escreve para o brasileiro médio que gosta de política, não estudou economia e lê pelo celular. Antes de escrever ou mudar qualquer texto que alguém vai ler, leia [PERSONA.md](PERSONA.md) e passe o texto pela lista "O que todo texto passa antes de sair". Use os nomes da tabela "Os nomes do site". Escreva no padrão de "O jeito de escrever do site": frase completa, causa e efeito em ordem com exemplo, nada de fórmula de efeito (rótulo seguido de explicação, "X, sim.", "isto, não aquilo"), texto que se explica sozinho, frases ligadas em vez de empilhadas, termo técnico sem definição (o site liga à Wikipédia), em todo fato o "e daí" sem lado, comparação que diz o mês ("se compararmos com julho", nunca "contra 3 meses antes"), importados no lugar de "o que vem de fora", sigla que a leitora não conhece por extenso ou com link, e cada frase dizendo quem faz o quê e para quem, exata no que importa e natural no resto. Para explicar como algo funciona (abas, desenhos, vídeos, o porquê de um fato no post), siga também "Como explicar um mecanismo": pergunta da leitora primeiro, uma imagem do dia a dia por ideia, a crença errada corrigida de frente e nada do bastidor da pesquisa na página.

Vale para tudo o que chega ao leitor:

- páginas: `templates/`, rótulos e legendas em `src/build_site.py`, `src/causas.py`, `config/causas.json`, `src/calendario.py`, `src/og_image.py`;
- frases geradas por código: o topo da página em `src/build_site.py` (o crescimento em 12 meses, cada pressão, o vaivém normal e a folga), os textos da seção `direcao` de `config/modelo.json` (por que cada linha de Também acompanhamos importa e não muda a placa, a dívida em reais) e `src/dossie.py` (fatos de dados que o post recebe);
- prompts da IA: `src/escreve_post.py` (post), `src/classify_news.py` (títulos de notícia e leituras) e `src/fundo.py` (a leitura a fundo do fato do dia, com o guia [FUNDO.md](FUNDO.md); a pesquisa lê as memórias de `src/memoria.py`). Mudou o guia, mude as regras dos prompts e os moldes de `src/revisa_texto.py` (o editor, `src/edita_texto.py`, lê o PERSONA.md inteiro a cada post e segue o guia novo sozinho);
- textos à mão em `editor/`.

`METODOLOGIA.md` é a exceção: fica técnica de propósito, para quem quer conferir ou refazer a conta, mas usa os mesmos nomes do site. Os nomes das pressões e dos assuntos das notícias ficam em `config/modelo.json`.

## Antes de entregar

- Gere o site com `.venv/bin/python src/build_site.py` e confira as páginas mudadas a 390 px de largura.
- A leitura a fundo passa sozinha pelo editor-chefe, pela conferência e pelo editor de estilo (`src/fundo.py`); para refazer uma, `.venv/bin/python src/fundo.py runs/<id>.json --grava`, no Mac (que abre as fontes).
- Os posts (fato do dia, semana e mês) passam pelo editor (`src/edita_texto.py`, que revisa o rascunho com o PERSONA.md, sugere e edita) e por `src/revisa_texto.py`; texto à mão, como o Retrato do Brasil em `editor/`, passe pelo editor (`python src/edita_texto.py editor/<texto>.md`) e leia em voz alta.
- Até o lançamento oficial (Pedro avisa quando), toda mudança importante vale para o site inteiro, inclusive o passado: reescreva posts antigos, títulos de notícia e leituras em `runs/` e `data/`, com os mesmos números e datas. Depois do lançamento, `runs/` passa a ser registro imutável.
