# Carta editorial: como o site escolhe a história do dia

O fato do dia não conta uma notícia: ele faz um argumento sobre a história em andamento que mais andou ontem ([FUNDO.md](FUNDO.md)). Esta carta diz como o código escolhe essa história, sem IA, para quem quiser conferir. A conta está em [`src/pauta.py`](src/pauta.py): mude os dois juntos. Os casos julgados, no fim, crescem com cada dia que o Pedro julgar.

## O que é uma história

Uma história em andamento é uma pergunta aberta por semanas ou meses (as contas do governo fecham? o juro cai quando? a economia para em 2027?), com a pressão do site que ela mexe e o próximo marco, uma data ou uma decisão. Ela fecha quando a pergunta é respondida. As fichas ficam em `base/memoria/historias.json`: uma IA as revê no domingo, junta as que respondem à mesma pergunta e completa a ficha das que o texto do dia abriu na semana.

Toda manhã, o classificador de notícias ([`src/classify_news.py`](src/classify_news.py)) lê as manchetes de ontem (até 240) e devolve até 15 notícias, dizendo de qual história cada uma é um passo, o estágio e o tamanho dela, se é o marco que a história esperava, se é uma previsão de casa grande que mudou de lado e se é uma fala sem medida.

## A soma

Cada notícia vale o tamanho dela (de 1 a 3) vezes o peso do estágio, e a história soma as notícias dela:

| Notícia | Peso |
| --- | --- |
| Decisão tomada ou dado divulgado | 1 |
| O marco que a história esperava, mesmo se chegar vazio (a data do PIB, do Copom, do desemprego, da inflação, ou o anúncio prometido) | 1 |
| Previsão de PIB ou de recessão de banco ou consultoria grande que mudou de direção | 1 |
| Proposta em votação | 0,7 |
| Anúncio com medida, ou previsão comum | 0,5 |
| Fala sem medida, ou rumor | 0,25 |

A notícia que é o mesmo fato de outra já contada, ou um dado que os indicadores do site já medem, fica fora da soma.

## As regras

1. Quando a direção do risco muda, ou uma das cinco pressões muda de lado, ganha a história daquela pressão, mesmo com poucos pontos.
2. A mesma história ganha no máximo dois dias seguidos, a não ser que traga uma decisão ou um dado de tamanho 2 ou mais. No terceiro dia, ganha a seguinte, se ela também passar de 1,5 ponto.
3. Quando nenhuma história passa de 1,5 ponto, o dia é calmo e o texto é curto, de 120 a 200 palavras.
4. Um tema novo, que não é passo de nenhuma história, abre uma história no mesmo dia se for grande (tamanho 2 ou mais) e já decidido ou divulgado. Um tema menor espera e abre a história se voltar em 3 dos últimos 7 dias. Nos dois casos, o Pedro recebe um aviso.
5. No empate, ganha a história que saiu em mais jornais.

Uma segunda história entra no texto, num parágrafo, se ela também passou de 1,5 ponto. O dia é grande, e o texto chega a perto de 800 palavras, quando a direção mudou, quando uma pressão mudou de lado ou quando a história somou 4 pontos ou mais.

## O que não se faz

- Escolher pelo tom ou pelo drama.
- Escolher porque um lado político vai gostar ou não gostar.
- Dar peso de fato a bastidor político (quem será ministro, quem apoia quem) enquanto não houver ato.
- Seguir o volume da imprensa sozinho: a cesta pende para os jornais de mercado, que publicam mais manchetes por dia. Por isso o número de jornais só desempata.

## Os casos julgados

Cada caso traz o dia, o que o site publicou, o que o Pedro decidiu e a regra que fica.

### 5/11/2026: a decisão do Copom e as vagas com carteira

O site publicou "Brasil abre 121,3 mil vagas com carteira, o pior setembro já visto", e a decisão do Banco Central de 4/11, que manteve a Selic em 13,75% e parou uma sequência de cinco cortes, entrou só no terceiro parágrafo. O Pedro, em 7/11/2026, julgou que no dia seguinte à decisão dos juros o fato do dia tem de ser a decisão. Fica a regra: a data marcada é o marco da história e vale peso 1 mesmo quando o mercado esperava a decisão, e o dado do mesmo dia entra como passo da história dele.

### 7/11/2026: as previsões de PIB para 2027

O site escreveu sobre as contas do governo, e Bradesco, XP e Genoa tinham passado a ver o PIB parado ou em queda em 2027. O Pedro, em 10/11/2026, julgou que a previsão de um banco respeitado sobre o que importa à leitora é um sinal forte, mesmo sem ser dado. Fica a regra: a previsão de PIB ou de recessão de uma casa grande que muda de direção vale peso 1, como um dado.

### 9/11/2026: o pronunciamento sem medida

O pronunciamento esperado sobre as contas veio sem medidas. Fica a regra: a fala sem medida vale 0,25, e o marco que chega vazio vale 1 como passo da história, sem fazer o dia parecer grande.
