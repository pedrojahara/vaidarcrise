# Vai dar crise?

## Todo texto passa pelo leitor

O site escreve para o brasileiro médio que gosta de política, não estudou economia e lê pelo celular. Antes de escrever ou mudar qualquer texto que alguém vai ler, leia [PERSONA.md](PERSONA.md) e passe o texto pela lista "O que todo texto passa antes de sair". Use os nomes da tabela "Os nomes do site". Escreva no padrão de "O jeito de escrever do site": frase completa, causa e efeito em ordem com exemplo, nada de fórmula de efeito (rótulo seguido de explicação, "X, sim.", "isto, não aquilo"). Para explicar como algo funciona (abas, desenhos, vídeos, o porquê de um fato no post), siga também "Como explicar um mecanismo": pergunta da leitora primeiro, uma imagem do dia a dia por ideia, a crença errada corrigida de frente e nada do bastidor da pesquisa na página.

Vale para tudo o que chega ao leitor:

- páginas: `templates/`, rótulos e legendas em `src/build_site.py`, `src/causas.py`, `config/causas.json`, `src/calendario.py`, `src/og_image.py`;
- frases geradas por código: o topo da página em `src/build_site.py` (cada pressão, o vaivém normal e a folga), os textos da seção `direcao` de `config/modelo.json` (quem mexe, o que segura) e `src/dossie.py` (fatos de dados que o post recebe);
- prompts da IA: `src/escreve_post.py` (post) e `src/classify_news.py` (títulos de notícia e leituras). Mudou o guia, mude as regras dos prompts e os moldes de `src/revisa_texto.py`;
- textos à mão em `editor/`.

`METODOLOGIA.md` é a exceção: fica técnica de propósito, para quem quer conferir ou refazer a conta, mas usa os mesmos nomes do site. Os nomes das pressões e dos assuntos das notícias ficam em `config/modelo.json`.

## Antes de entregar

- Gere o site com `.venv/bin/python src/build_site.py` e confira as páginas mudadas a 390 px de largura.
- Os posts (fato do dia, semana e mês) passam por `src/revisa_texto.py`; texto à mão, como o Retrato do Brasil em `editor/`, leia em voz alta.
- Até o lançamento oficial (Pedro avisa quando), toda mudança importante vale para o site inteiro, inclusive o passado: reescreva posts antigos, títulos de notícia e leituras em `runs/` e `data/`, com os mesmos números e datas. Depois do lançamento, `runs/` passa a ser registro imutável.
