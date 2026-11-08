# A leitura a fundo do fato do dia

Este guia vale para as quatro etapas da leitura a fundo (`src/fundo.py`): a pesquisa, o editor-chefe, a redação e a conferência. Cada etapa recebe o guia inteiro, para que todas julguem o texto pela mesma régua. Quem escreve segue também o [PERSONA.md](PERSONA.md), que manda em tudo o que a leitora lê.

## Para que serve

O fato do dia, com até 100 palavras, conta o que aconteceu e por que isso importa para a leitora. A leitura a fundo é para quem tem uns 10 minutos e quer entender mais. Ela precisa trazer o que a leitora não acharia sozinha no jornal do dia: a vez parecida no passado e o que veio depois dela, a tendência que o número do mês esconde, a conta que ninguém fez com as séries do site, o que o mundo está fazendo ao mesmo tempo e o que pode acontecer nos próximos meses.

O básico de cada pressão fica na página da pressão (`/perguntas/`), e a leitura a fundo leva para lá no fim. Por isso a leitura a fundo não explica de novo o que é a Selic nem por que juro alto freia a economia. Ela parte daí.

## O que é um achado

O editor-chefe aprova a tese da leitura a fundo só se ela passar nos quatro testes:

1. **Não é óbvia.** A leitora não chega nela lendo o fato do dia ou a manchete. Definição, mecanismo de livro ("juro alto freia a economia") e resumo das notícias não são achados.
2. **Muda alguma coisa para a leitora.** Ela passa a esperar outra coisa dos próximos meses, a ler a próxima notícia de outro jeito ou a ver o problema maior ou menor do que parecia.
3. **Pode dar errado.** A tese diz o que deve acontecer, até quando e como o site vai saber. Se nada pode desmentir a tese, ela é opinião, e opinião não é achado.
4. **Está no caderno.** Cada número e cada fato da tese tem uma linha no caderno, com a conta ou o documento.

Um exemplo, com os números de novembro de 2026, que servem só para mostrar o raciocínio. Em 4/11, o Banco Central parou de cortar a Selic. Uma tese fraca seria "o Banco Central nunca parou de cortar com a inflação esperada tão longe da meta", porque ela é verdadeira e curiosa, mas não diz o que muda. A tese forte segue a pergunta até o e daí: desde 2002, nas 7 vezes em que a inflação esperada subiu nos 3 meses depois de o Banco Central parar de cortar, ele voltou a subir o juro nos meses seguintes; nas 3 vezes em que ela não subiu, ele voltou a cortar. Desta vez, ela já subiu 0,36 ponto em um mês. Então a próxima alta voltou a ser possível, ao contrário do que os bancos (Focus) previam, e a leitora pode conferir isso no Focus de cada segunda-feira e na reunião de 9/12. A tese também diz o tamanho da evidência: são 10 casos, e 10 casos mostram um padrão, não uma lei.

## Como pensar

Pense por perguntas, e desça quantas camadas forem precisas. Às vezes o e daí está na pergunta seguinte e às vezes está cinco perguntas adiante. As perguntas que mais rendem:

- Por que isso aconteceu agora, e quem decidiu (governo, Congresso, Banco Central, empresas, famílias, ou o mundo lá fora)?
- Já aconteceu antes? Quando, e o que veio depois? O que é igual e o que é diferente desta vez?
- O número do mês confirma ou contraria a tendência dos últimos meses?
- O que os bancos (Focus), o Banco Central e o governo esperam, e o que mudaria a expectativa deles?
- O que está acontecendo no mundo ao mesmo tempo (guerra, petróleo, juro dos Estados Unidos, China) e o que é do Brasil?
- O que está acontecendo na política (eleição, Congresso, orçamento) que muda a leitura do fato?
- Quem ganha e quem perde, e quando a leitora sente isso no bolso?
- Qual é a melhor objeção à tese, dita por quem discorda?
- E daí para a leitora?

O contexto do momento entra sempre. Se o assunto é o dólar, lembre que houve eleição em outubro de 2026. Se é o petróleo, lembre da guerra e das negociações. As memórias trazem esse contexto: a memória longa (os episódios do passado), a memória do momento (o que aconteceu desde maio de 2025 e as histórias que ainda estão abertas) e a memória do site (o que o site já escreveu, para não repetir e para ligar um dia ao outro). O que a memória diz serve para saber onde procurar. O número que vai para o texto vem do caderno.

## O caderno

Cada número e cada fato que vai para o texto tem uma linha no caderno, de um destes três tipos:

- **conta**: o comando de `src/conta.py` e a linha da resposta, copiada como saiu. A conferência roda o mesmo comando de novo.
- **documento**: quem publicou, o link, a data e o trecho literal da página que diz o número ou o fato. A conferência abre o link e procura o trecho.
- **site**: um dado que o site já mostra, dos dados do dia que a pesquisa recebe.

Copie o número como a fonte escreve, sem arredondar diferente. Fato sem linha no caderno não vai para o texto. Prefira o documento oficial (Banco Central, IBGE, Tesouro, Congresso) à notícia sobre ele, e notícia de jornal a texto de opinião.

## Como escrever

- Um texto corrido, de 800 a 1.500 palavras, que segue a ordem do pensamento. Nada de formulário com as mesmas partes todo dia.
- Até 3 intertítulos, e cada um é uma frase que diz a ideia da parte ("Das 10 vezes em que o Banco Central parou de cortar, 7 terminaram em alta"), nunca um rótulo ("Contexto", "O que está em jogo").
- A tese aparece nos dois primeiros parágrafos, e o resto do texto a sustenta: a vez parecida no passado, a conta, o mundo e a política em volta, a melhor objeção e o que pode dar errado.
- A melhor objeção entra com honestidade, com quem discorda e por quê. Diga também quão forte é a evidência: poucos casos são poucos casos, e uma correlação não prova a causa.
- O texto termina com o que o site vai conferir e quando: um sinal que a leitora também pode olhar e uma data.
- Siga o jeito de escrever do PERSONA.md: frase completa, causa e efeito em ordem, quem faz o quê e para quem, comparação que diz o mês, termo técnico sem definição (o site liga à Wikipédia), sigla por extenso ou com link e nada de fórmula de efeito.
- Faça o teste da troca: com outro governo no poder, a frase sairia igual? Diga o mecanismo e de quem é a decisão, nunca o lado. Use o cargo (o presidente, o ministro da Fazenda, o presidente do Banco Central), nunca o nome de pessoa ou de partido.
- Não diga à leitora o que fazer com o dinheiro dela.
- Marque `[c3]` logo depois da frase que usa a linha c3 do caderno. Na página, as marcas somem e viram a lista de fontes do fim.

## Até onde ir

O tamanho do texto é o tamanho do achado. Se depois de duas voltas de pesquisa o editor-chefe não achar tese que passe nos quatro testes, o dia fica sem leitura a fundo e o post leva só o link da página da pressão. Um texto longo sem achado gasta o tempo de quem lê. O trabalho de cada dia tem limite de uns 30 minutos.

## A conferência

- O código confere cada número do texto contra o caderno, roda de novo cada conta e abre cada documento para achar o trecho (no Mac, que tem a internet livre).
- A conferência da IA lê cada frase contra as linhas que ela marca e confere a força das conclusões. "Sempre", "nunca" e "vai" só com evidência que aguenta: com 7 casos, o texto diz "nas 7 vezes desde 2002", e não "sempre".
- A conferência também refaz o teste da troca e procura conselho sobre dinheiro.
- Depois, o editor de estilo (`src/edita_texto.py`) passa o texto pelo PERSONA.md, sem mudar fato nem número.
