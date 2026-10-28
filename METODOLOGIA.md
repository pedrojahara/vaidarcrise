# Metodologia v1.2

Pré-registrada em 28 de outubro de 2026, antes da primeira nota, e revisada nas v1.1 e v1.2 (veja [Versões](#versoes)). Os parâmetros estão em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json), e cada atualização grava o hash desse arquivo. Mudança de regra ou de peso só acontece com nova versão e nota explicando o efeito.

## O que a nota mede

A nota é a probabilidade, de 0 a 100, de esta pergunta ter resposta "sim":

> O PIB do Brasil terá dois trimestres seguidos de queda entre o 3º trimestre de 2026 e o 4º trimestre de 2030?

- **Dado:** PIB trimestral dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre imediatamente anterior). Queda é a taxa divulgada, com uma casa decimal, abaixo de zero; 0,0% não conta.
- **Quando se resolve:** na série vigente em março de 2031. O PIB é revisado; em 2021, uma recessão técnica anunciada sumiu na revisão seguinte.
- **Auditoria:** se a datação do CODACE/FGV IBRE divergir da regra técnica, o site publica as duas leituras.

O nome do site fala em crise; a métrica é recessão técnica. "Vai dar crise?" é a pergunta de bar; a resposta é uma probabilidade com regra escrita antes.

**Como ler a nota.** 50 significa cara ou coroa, não "risco médio". A nota 70 quer dizer que, em 100 Brasis com os dados de hoje, 70 entrariam em recessão até o fim de 2030.

**O número do topo.** Desde a v1.2, o topo do site mostra outra leitura da mesma conta: quantas vezes a chance de uma recessão começar nos próximos 12 meses (os quatro trimestres ainda não divulgados) está acima do normal. O normal é essa mesma chance só com a taxa-base, cerca de 20%. Em 28/10/2026 a conta dava 53%, 2,7 vezes o normal. O horizonte de 12 meses é onde dados e notícias pesam inteiros; a nota até 2030 continua sendo a pergunta que o placar vai resolver, e aparece em "Como a conta funciona" com a faixa da taxa-base.

**A seta.** Ao lado do multiplicador, a seta compara com a atualização mais próxima de 30 dias atrás (ou com a primeira, enquanto o site tiver menos de 30 dias). Se o multiplicador subiu mais de 10%, "piorando"; se caiu mais de 10%, "melhorando"; senão, "estável".

## Taxa-base

Antes de olhar qualquer dado ou notícia, a história já diz muito. O CODACE datou 10 recessões desde 1980. Dividindo os inícios de recessão pelos trimestres em expansão, o resultado depende de onde a conta começa:

| Período de referência | Risco por trimestre | Até o 4T30 (17 inícios possíveis) |
| --- | --- | --- |
| 1980–2026 (10 recessões) | 7,5% | 73% |
| 1995–2026, pós-Real (7) | 7,1% | 71% |
| 2T99–2026, metas de inflação e câmbio flutuante (5) | 5,6% | 63% |
| 2004–2026 (3) | 4,0% | 50% |

Escolher uma linha dessa tabela é escolher a nota. Por isso, desde a v1.1, o site não escolhe: a âncora é a **mediana de nove métodos**, e cada um tem uma regra fixa para decidir quanto o passado pesa.

| Método | Risco por trimestre | Até o 4T30 |
| --- | --- | --- |
| Desde 2T99: metas de inflação e câmbio flutuante | 5,62% | 63% |
| Desde 1T00: com a Lei de Responsabilidade Fiscal | 5,81% | 64% |
| 1980 em diante, peso cai à metade a cada 10 anos | 4,89% | 57% |
| 1980 em diante, peso cai à metade a cada 15 anos | 5,68% | 63% |
| 1980 em diante, peso cai à metade a cada 20 anos | 6,12% | 66% |
| Média das janelas iniciadas entre 1T95 e 4T12 | 5,06% | 59% |
| Quebra estrutural em data desconhecida (bayesiano) | 5,28% | 60% |
| Brasil desde 2T99 + 8 emergentes, peso de 10 anos | 4,92% | 58% |
| Brasil desde 2T99 + 8 emergentes, peso de 25 anos | 4,43% | 54% |
| **Mediana, usada pelo site** | **5,3%** | **60%** |

- **Janelas com data justificada:** 2T99 marca o fim do câmbio fixo, o canal das recessões de 1995 e 1998.
- **Peso que decai:** todo trimestre desde 1980 conta, mas o peso cai à metade a cada 10, 15 ou 20 anos. Com meia-vida de 15 anos, o início da recessão de 2014–16 ainda pesa 57% e o do Plano Collor pesa 19%.
- **Média de janelas:** em vez de uma data de início, a média de todas as que começam entre 1995 e 2012.
- **Quebra em data desconhecida:** um modelo bayesiano compara "nada mudou" com "mudou em alguma data entre 1988 e 2022" e pondera as duas hipóteses pelos dados.
- **Brasil e vizinhos:** o risco do Brasil desde 2T99 é puxado para a média de 8 emergentes parecidos (México, Chile, Colômbia, Peru, Argentina, África do Sul, Turquia e Rússia), de 3,4% por trimestre, com peso equivalente a 10 ou 25 anos de dados ([`data/emergentes.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/emergentes.json)).

Os nove métodos vão de 54% a 66%, e a página inicial mostra essa faixa ao lado da nota. Qualquer pessoa refaz a conta com [`src/taxa_base.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/taxa_base.py) e a cronologia em [`data/cronologia.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/cronologia.json).

**O que ficou de fora.**

- **Tirar a pandemia:** daria 2,7% por trimestre desde 2004 (37% até 2030). Choques externos fazem parte do risco até 2030: das cinco recessões desde 1999, duas vieram de choques globais (2008 e 2020).
- **Começar em 2004:** com só três recessões, o intervalo de 90% para o risco vai de 1,4% a 9,4% por trimestre, e a diferença para antes de 2004 não é estatisticamente significativa (p ≈ 0,09).
- **Começar em 1980:** trataria hiperinflação e câmbio fixo como riscos de hoje.

**Conferência com o IBGE.** A pergunta se resolve pela regra técnica do IBGE, mas a taxa-base usa a datação do CODACE. Em 28/10/2026, recontamos a série atual da tabela 5932 (2T96 a 2T26). Todo episódio de dois trimestres seguidos de queda cai dentro de uma recessão do CODACE, e nenhum fica de fora. 2021 não conta: na série revisada, a queda do 2T21 (−0,7%) ficou isolada. Quando quedas separadas por um único trimestre de alta contam como um episódio só (2014–16 teve três), os riscos coincidem com os do CODACE: 5,6% por trimestre desde 2T99 e 4,0% desde 2004. Contar cada recaída como recessão nova daria 7,7% desde 2T99, mas a nota pergunta pela primeira recessão, não pelas recaídas.

Um início de recessão no trimestre *t* exige que *t* e *t+1* estejam na janela, então há 17 inícios possíveis (3T26 a 3T30). Com 5,3% por trimestre, a chance só pela história é 1 − 0,947¹⁷ ≈ 60%.

## A conta

O modelo soma três camadas na escala de log-odds (logit), o que torna cada contribuição exata e aditiva.

```
logit(h_t) = logit(h0) + w_t × (I + N)
P(recessão até 4T30) = 1 − Π (1 − h_t)
```

- **h0** é a taxa-base de 5,3% por trimestre.
- **I** é a soma das contribuições dos indicadores.
- **N** é a soma das contribuições das notícias.
- **w_t** é o peso no tempo: 1 nos quatro primeiros trimestres ainda não divulgados, 2/3 no quinto, 1/3 no sexto e zero daí em diante.

Ninguém prevê recessão a quatro anos com dados de hoje: os melhores métodos acertam de 6 a 18 meses. Por isso indicadores e notícias mexem só no risco dos próximos trimestres, e a nota até 2030 se move devagar.

**De onde vem o multiplicador.** A página "Como a conta funciona" parte do normal de 12 meses e soma o que cada indicador e cada notícia acrescenta, em pontos percentuais, até chegar à chance de hoje. Na v1.1, a página repartia a nota até 2030 em parcelas por horizonte; a v1.2 trocou essa repartição pela de 12 meses, que é o número do topo.

**Trimestres divulgados.** Quando o IBGE divulga um trimestre, ele sai da janela (efeito tempo). Se dois trimestres seguidos vierem negativos, a pergunta está resolvida e a nota vai a 100. Se o último trimestre divulgado vier negativo, a chance de o seguinte também cair parte de 50% (parâmetro por julgamento, a calibrar com a série do IBGE) e recebe o mesmo deslocamento de curto prazo.

**Decomposição.** A conversão de log-odds para probabilidade não é linear, então a repartição em pontos usa valores de Shapley exatos: cada fator recebe a sua contribuição média sobre todas as ordens possíveis, e a soma bate exatamente com o total repartido. Em "De onde vem", os fatores repartem a diferença entre a chance de 12 meses de hoje e o normal; a tabela de indicadores e a lista de notícias mostram esses mesmos pontos. Em "O que mudou" e na conta do dia de cada post, os fatores repartem a variação entre duas atualizações; no post, a variação aparece em vezes o normal, com duas casas. Com mais de 12 fatores, as notícias menores são agrupadas em "outras notícias". Os números exibidos são arredondados de modo que as parcelas somem o total exibido.

## Indicadores

Seis sinais, cada um com valor neutro, inclinação e efeito máximo, publicados antes da primeira nota. Os pesos são de julgamento, com encolhimento de 25% na soma para não contar duas vezes sinais correlacionados (juros, câmbio e dívida andam juntos), e teto de 1,2 em log-odds para a camada inteira.

| Indicador | Definição | Neutro | Efeito por unidade | Faixa do efeito |
| --- | --- | --- | --- | --- |
| Atividade | IBC-Br dessazonalizado, média de 3 meses contra os 3 anteriores (BCB 24364) | +0,5% | −0,40 por p.p. | −0,30 a +0,60 |
| Desemprego | Regra de Sahm adaptada: média de 3 meses da desocupação da PNAD menos o mínimo dessa média nos 12 meses anteriores (BCB 24369) | 0,15 p.p. | +1,20 por p.p. | −0,20 a +0,70 |
| Juro real ex-ante | Selic meta (BCB 432) descontada da inflação esperada para 12 meses (Focus) | 5% | +0,08 por p.p. | −0,20 a +0,40 |
| Dívida das famílias | Comprometimento de renda com dívidas (BCB 29034) menos a média de 36 meses | 0 | +0,10 por p.p. | −0,15 a +0,30 |
| Dívida pública | Variação da dívida bruta do governo geral em 12 meses (BCB 13762) | +1 p.p. do PIB | +0,04 por p.p. | −0,10 a +0,25 |
| Câmbio | Variação do dólar PTAX em 63 dias úteis (BCB 1) | 0% | +0,015 por p.p. | −0,10 a +0,25 |

Ficaram de fora no MVP, por falta de fonte gratuita estável: inclinação da curva de juros (B3), incerteza (FGV IBRE), CDS e indicador antecedente composto. A curva de juros, a mais citada na literatura, quase não tem poder preditivo em emergentes e não foi robusta no Brasil em 2005–2023.

## Notícias

Um modelo de linguagem (Claude, chamado sem ferramentas e com saída em esquema JSON validado por código) lê as manchetes de oito veículos com linhas editoriais diferentes: Agência Brasil, Folha, Estadão, Valor, InfoMoney, Poder360, Gazeta do Povo e g1. Ele transforma os fatos relevantes em eventos estruturados; a conta é feita por código.

**Uma atualização por dia.** As manchetes são coletadas de hora em hora e guardadas na máquina que roda o site. Às 06h30, a atualização lê as manchetes do dia anterior que ainda não foram lidas, calcula a nota e publica um post. Cada manchete é lida uma vez só.

**Estágio.** Cada evento recebe o estágio em que o fato está, e o estágio multiplica o efeito (v1.2):

| Estágio | Peso |
| --- | --- |
| Dado divulgado (estatística oficial, resultado publicado) | 1 |
| Decisão tomada (lei sancionada, decisão do Copom, medida publicada) | 1 |
| Proposta em votação (projeto enviado, votação marcada) | a chance estimada de aprovação, entre 0,2 e 0,8 |
| Anúncio sem ato formal | 0,3 |
| Rumor, bastidor ou plano em estudo | 0,1 |

Na dúvida, o classificador usa o estágio menos avançado. O peso vale para eventos lidos a partir de 29/10/2026; os anteriores mantêm o efeito com que foram publicados.

| Regra | Valor |
| --- | --- |
| Efeito por tamanho do fato (1, 2, 3) | 0,04, 0,12 e 0,20 em log-odds |
| Fato que o mercado já esperava | vale metade |
| Fato noticiado por um só veículo | vale metade |
| Teto por evento | 0,2 em log-odds |
| Teto da camada de notícias | 0,6 em log-odds |
| Prazo de validade | o efeito cai em linha reta até zero em 75 dias |
| Notícia que só relata um dado já medido | não conta (evita dupla contagem) |
| Estágio do fato | multiplica o efeito (tabela acima) |

O LLM extrai e narra; não prevê. Ele não vê os pesos, não escolhe a direção da nota e não edita o site. O texto das notícias é tratado como dado, nunca como instrução, e nenhuma notícia pode alterar pesos ou regras. A linguagem dos eventos descreve políticas e números, não pessoas ou partidos.

**O post do dia.** Depois da conta, o modelo de linguagem recebe os números prontos e escreve o post: o que mudou, quanto cada fato mexeu e o que acompanhar. Ele não muda a nota. Um verificador em código procura moldes de texto automático e pede uma reescrita no máximo; se a escrita falhar, o site publica a conta do dia sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta. Respostas antigas nunca são recalculadas: o que foi publicado fica congelado.

## Salvaguardas

- **Disjuntor:** variação de mais de 5 pontos num dia sai com o selo "em revisão".
- **Dado defasado:** se a nota passar de 36 horas sem atualização, a página avisa.
- **Falha do LLM:** a atualização sai só com dados, e os eventos que já valiam continuam decaindo.
- **Os dois lados:** a página mostra até quatro argumentos por mais crise e por menos crise, tirados das manchetes. Só troca de lista quando a leitura do dia traz pelo menos um argumento de cada lado.
- **Placar:** as previsões de 12 meses ficam registradas e serão pontuadas pelo escore de Brier quando vencerem.

## O que ainda falta (fase 2)

- Backtest de 1996 a 2026 das camadas 1 e 2, com os dados como eram conhecidos na época. O LLM não entra no backtest, porque ele sabe o que aconteceu em 2015 e 2020.
- Teste mensal de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Probit em painel com cerca de 20 emergentes para estimar os pesos com mais dados do que as 7 recessões brasileiras desde 1995.
- Calibrar a chance de um trimestre negativo ser seguido de outro. Na recontagem de 28/10/2026, isso aconteceu em 7 de 16 casos desde 1996 (44%); o parâmetro fica em 50% até o backtest.
- Avaliar um multiplicador limitado para vulnerabilidades domésticas (fiscal, juros, crédito), com base nas causas das recessões passadas. Ele só entra se melhorar o backtest.

Se o backtest não bater a taxa-base, o site vai dizer isso em público, e a nota passa a ser só taxa-base mais notícias explicadas.

## Onde erramos

Erros são listados aqui com data, o que estava errado e o efeito na nota.

| Data | O que estava errado | Efeito na nota |
| --- | --- | --- |
| 28/10/2026 | A segunda atualização deu a quatro eventos novos os mesmos códigos de eventos antigos, o que embaralhou a explicação da variação. Os eventos foram renumerados e a decomposição refeita no mesmo dia. | Nenhum: a nota (77,9) não mudou, só a repartição dos pontos. |

Achou um? [Abra uma issue](https://github.com/pedrojahara/vaidarcrise/issues).

## Versões

Toda mudança de regra ou de peso ganha uma versão nova. Na atualização em que ela entra, o gráfico da variação mostra uma barra "Nova metodologia": a nota anterior refeita com a regra nova. Essa barra não conta para o disjuntor.

| Versão | Decidida em | O que mudou | Efeito na nota |
| --- | --- | --- | --- |
| 1.0 | 28/10/2026 | Primeira versão. Taxa-base de 5,5% por trimestre, a média das janelas 1995–2026 e 2004–2026. | — |
| 1.1 | 28/10/2026 | Taxa-base passa a ser a mediana de nove métodos (5,3%), com a faixa publicada. A página separa a nota por horizonte. | −1,2 ponto com os dados de 28/10 (77,9 → 76,7) |
| 1.2 | 28/10/2026 | Peso por estágio das notícias (dado e decisão 1; em votação, a chance de aprovação; anúncio 0,3; rumor 0,1). Topo passa a mostrar o risco de 12 meses em vezes o normal. Uma atualização por dia, às 06h30, com post. | Nenhum na data da mudança: o peso vale só para notícias lidas a partir de 29/10/2026. |

A v1.0 escolhia duas datas de início por julgamento, e cada data dava uma nota diferente. A v1.1 troca a escolha por uma regra que qualquer pessoa pode refazer.

## Fontes

- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Chinn e Ferrara (2024), curva de juros em emergentes, NBER w32084
- Tetlock e Gardner (2015), *Superforecasting*, sobre classes de referência
- Pesaran e Timmermann (2007), *Selection of estimation window in the presence of breaks*, Journal of Econometrics
- Pesaran, Pettenuzzo e Timmermann (2006), *Forecasting time series subject to multiple structural breaks*, Review of Economic Studies
