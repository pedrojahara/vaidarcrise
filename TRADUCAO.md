# A tabela de tradução

Esta tabela diz como o site traduz um fato econômico para a vida de quem lê: o que muda, para que lado, quanto, quando e para quem. Ela existe porque o site acompanha o risco de recessão e o que ele muda na vida das pessoas (decisão do Pedro em 9/11/2026), e "os importados ficam mais caros" diz a direção sem dizer o tamanho. O jeito de escrever a tradução está no [PERSONA.md](PERSONA.md), em "O que a notícia muda na vida"; aqui ficam as regras de conta e de onde vem cada uma.

## Por que a tabela é fixa

A tradução é escolhida antes do fato e é a mesma para qualquer governo, como a biblioteca de evidência ([EVIDENCIA.md](EVIDENCIA.md)). Escolher a conta depois de saber a notícia abre espaço para escolher a que dá o número mais forte para um lado. Por isso cada tradução tem uma regra escrita aqui, com a fonte e a força, e a conta é feita em código (`traduz`, em `src/conta.py`), com as séries do próprio site. A IA da pesquisa não inventa regra nova: quando falta uma, ela diz isso em "o que falta", e o editor do site decide se a regra entra, com a data da revisão.

## Como a tradução chega ao texto

- **A pesquisa do dia** roda a tradução quando o argumento do texto chega à vida de alguém (`src/conta.py traduz`), com as séries do site ou com o número que a fonte deu (a parcela com o juro novo do banco, a alta do dólar do dia), e cada conta vira uma linha do caderno, com o comando e a saída (`src/fundo.py`). Nos dias passados, a conta só vê o que já se sabia no dia.
- **O texto do dia** usa a tradução só quando o fato muda algo com número e prazo, ou quando a leitora acharia que muda e não muda ([FUNDO.md](FUNDO.md)). A frase sobre a vida não entra em todo texto: o e daí é a conclusão do argumento.
- **A conferência** roda o comando de novo e confere cada número, como em qualquer conta do caderno.

## Regras que valem para toda tradução

- **Cinco partes.** O que muda (o item: a parcela, o preço do mercado, o reajuste), para que lado, quanto, quando e para quem. A tradução que não chega ao tamanho diz por quê.
- **O número vem da conta ou da notícia.** Conta de cabeça não vale. Um número de exemplo (R$ 100 de compras, R$ 1.000 guardados, um financiamento de R$ 300 mil) é dito como exemplo, nunca como a conta da leitora.
- **Sem conselho.** A tradução diz o que muda, nunca o que fazer com o dinheiro.
- **Estimativa é estimativa.** Uma regra com força média ou fraca vai com "cerca de" e com o limite dela, como a biblioteca de evidência pede.
- **Quando não há regra**, o texto diz a direção e quem decide o tamanho, sem número: o preço da gasolina, que a Petrobras decide, e a conta de luz, que a Aneel reajusta.
- **"Nada muda agora" é resposta** quando a conta mostra isso, dita com o porquê e com o que faria mudar.

## As famílias de referência

O texto as chama pela situação, sem nome inventado. No texto do dia entram só as que o fato atinge, cada uma com o número dela, e só quando o argumento chega à vida delas.

| Família | Portas | Traduções |
| --- | --- | --- |
| Quem vive do salário mínimo ou da aposentadoria do INSS | Renda, preços | `traduz minimo`, `traduz precos` |
| Quem tem financiamento e cartão | Crédito, emprego | `traduz parcela`, `traduz credito`, `traduz emprego` |
| Quem tem dinheiro guardado | Dinheiro guardado | `traduz guardado` |

Quando quem sente depende do que a pessoa compra ou do trabalho que faz (um imposto sobre carro, a escala de trabalho), o texto diz para quem vale sem passar pelas famílias.

## As traduções

### Preços: o que custava R$ 100
<!-- traduz precos -->

**A regra.** Com a inflação de 12 meses, o que custava R$ 100 um ano antes custa R$ 100 mais a inflação. Pelo IPCA, a inflação oficial, e pelo INPC, que mede a cesta das famílias com renda de 1 a 5 salários mínimos e corrige o mínimo e o INSS. Para os 12 meses seguintes, a mesma conta com a inflação que os bancos esperam (Focus).
**De onde vem.** IBGE (IPCA, série 13522, e INPC, série 188, pelo Banco Central); Banco Central, pesquisa Focus.
**Força.** O passado é medida, não estimativa. O Focus é previsão e erra.
**Prazo e para quem.** Um ano para trás, ou um ano para a frente. Todos; o INPC, para quem vive do mínimo.

### Dólar: quanto da alta chega aos preços
<!-- traduz dolar -->

**A regra.** Pelas contas do Banco Central, cada 10% de alta do dólar sobe o IPCA em cerca de 1 ponto em quatro trimestres (repasse de 0,10). A conta usa a alta dada pela notícia ou a alta dos últimos 12 meses.
**De onde vem.** Banco Central, Relatório de Política Monetária de março de 2026, boxe "Repasse cambial: estimativas por projeções locais" (`a-repasse-bc` em `base/afirmacoes.json`).
**Força.** Média. É a estimativa do próprio Banco Central, uma média de muitos anos; o repasse muda com o momento da economia e com quanto a alta parece durar.
**Prazo e para quem.** Um ano, se a alta não voltar. Todos, mais quem compra importado (eletrônico, remédio, peça) e combustível.

### Crédito: a parcela de um financiamento
<!-- traduz parcela VALOR MESES JURO [JURO ...] -->

**A regra.** A primeira parcela na tabela SAC, a mais usada na casa própria, e a parcela fixa na tabela Price, com o juro ao ano que a notícia ou o Banco Central dá, sem seguro, taxas e TR. Com dois juros, a diferença entre as parcelas. O exemplo padrão é um financiamento de R$ 300 mil em 30 anos (360 meses), dito como exemplo.
**De onde vem.** A conta das tabelas SAC e Price; o juro, da notícia (o banco que mudou a taxa) ou do Banco Central (juro médio do financiamento imobiliário com taxas de mercado, série 20772).
**Força.** A conta é exata para o juro dado; a parcela de verdade tem seguro e taxas.
**Prazo e para quem.** Para quem pede o crédito a partir de agora. Quem já tem financiamento com juro fixo continua com a mesma parcela. O Minha Casa, Minha Vida tem juro fixado pelo conselho do FGTS e não segue o juro de mercado.

### Crédito: o juro de cada tipo de empréstimo
<!-- traduz credito -->

**A regra.** O juro médio ao ano que os bancos cobram das pessoas em cada tipo de crédito (cartão rotativo, cheque especial, crédito pessoal, consignado do INSS, carro, casa própria), um ano antes e agora, e quanto R$ 1.000 devidos por um ano viram com esse juro.
**De onde vem.** Banco Central, juro médio das operações de crédito para pessoas físicas (séries 20740, 22022, 20741, 20742, 20746, 20749 e 20772).
**Força.** Medida, com um a dois meses de atraso.
**Prazo e para quem.** Quem tem ou pede crédito. A Selic não passa inteira nem logo para esses juros, e alguns ficam muito acima dela, como o do cartão rotativo: por isso a tradução usa o juro que os bancos de fato cobram e não supõe quanto da Selic chega a ele.

### Dinheiro guardado: quanto rendem R$ 1.000
<!-- traduz guardado [VALOR] -->

**A regra.** Numa aplicação que rende o mesmo que a Selic, R$ 1.000 rendem a Selic do mês, antes do imposto de renda; descontada a inflação que os bancos esperam (Focus), sobra o juro acima da inflação. Na poupança, pela Lei 12.703, de 2012, com a Selic acima de 8,5% o rendimento é de 0,5% ao mês mais a TR, sem imposto; com a Selic em 8,5% ou menos, 70% da Selic mais a TR.
**De onde vem.** Banco Central (Selic, série 432; TR, série 7811); Focus; a lei da poupança.
**Força.** A conta é exata para a Selic do dia; o rendimento acima da inflação depende da inflação que vier.
**Prazo e para quem.** Um ano. Quem tem dinheiro guardado; o juro alto que encarece a parcela de quem pega empréstimo aumenta o rendimento de quem guarda.

### Renda: o salário mínimo e o INSS
<!-- traduz minimo -->

**A regra.** O mínimo é reajustado todo janeiro pelo INPC dos 12 meses até novembro mais o crescimento do PIB de dois anos antes, com ganho acima da inflação de até 2,5%. Os benefícios do INSS acima do mínimo são corrigidos só pelo INPC do ano anterior. Até janeiro, o mínimo perde para os preços o INPC acumulado desde o último reajuste.
**De onde vem.** Lei 14.663, de 2023 (`a-lei-salario-minimo` em `base/afirmacoes.json`), e Lei 15.077, de 2024, que limitou o ganho a 2,5% ao ano (EVIDENCIA.md, "Preço administrado e regulação"); salário mínimo (série 1619) e INPC (série 188), pelo Banco Central.
**Força.** Regra de lei: o reajuste só muda se o Congresso mudar a lei. O ganho acima da inflação depende do PIB, e a conta mostra os dois extremos.
**Prazo e para quem.** Janeiro. Quem vive do mínimo ou de benefício ligado a ele, e quem recebe aposentadoria do INSS.

### Renda: o que o trabalho paga
<!-- traduz renda -->

**A regra.** A renda média do trabalho, descontada a inflação, no trimestre que termina no mês, contra o mesmo trimestre um ano antes.
**De onde vem.** IBGE, PNAD Contínua, tabela 6390 (rendimento médio real habitual de todos os trabalhos).
**Força.** Medida. É uma média: quando quem ganha menos perde o emprego, ela pode subir mesmo com a vida piorando, como em 2020.
**Prazo e para quem.** O que já aconteceu. Quem trabalha.

### Emprego: quantas pessoas cabem em um ponto
<!-- traduz emprego -->

**A regra.** O desemprego de agora, quantas pessoas são 1 ponto de desemprego (1% da força de trabalho) e quanto o desemprego subiu nas recessões desde 2012, quando a série começa.
**De onde vem.** IBGE, PNAD Contínua, pelo Banco Central (desemprego, série 24369; força de trabalho, série 24378); as recessões, do PIB do IBGE.
**Força.** Medida. O passado mostra o tamanho do que já aconteceu, e não o que vai acontecer.
**Prazo e para quem.** O desemprego costuma subir depois que a recessão começa e cair devagar depois que ela acaba. Quem trabalha, e mais quem tem emprego sem carteira.

### Imposto e benefício: quanto é por pessoa
<!-- calc -->

**A regra.** O valor que a notícia dá (o imposto novo, o benefício, o corte), dividido pelo número de pessoas a quem ele vale, quando a fonte dá esse número, com `calc`. Um valor do governo inteiro ganha escala por brasileiro só com a população de uma fonte do caderno.
**De onde vem.** A notícia e o documento oficial (a lei, o projeto, a exposição de motivos).
**Força.** A da fonte. Proposta ainda não é regra, e o texto diz o estágio.
**Prazo e para quem.** Quando a regra começa a valer, e para quem ela vale.

### Sem número: combustível e conta de luz

**A regra.** O preço da gasolina e do diesel nas refinarias é decidido pela Petrobras, e o da bomba depende também do imposto e do posto; o reajuste da conta de luz é da Aneel. O texto diz a direção e quem decide o tamanho, sem conta, até que a decisão saia com o número.
