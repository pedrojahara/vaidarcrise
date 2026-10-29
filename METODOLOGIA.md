# Metodologia

Os parâmetros estão em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json). Cada atualização grava a versão da regra e o hash desse arquivo, e o histórico dele fica no GitHub.

## O que o site mede

**O número do topo.** Quantas vezes a chance de uma recessão começar nos próximos 12 meses (os quatro trimestres ainda não divulgados) está acima do normal. O normal é essa mesma chance só com a história das recessões brasileiras (a [taxa-base](#taxa-base)): cerca de 20%. Com 2×, a chance é o dobro da de um ano comum. Doze meses é o horizonte em que os indicadores pesam inteiros.

**A seta.** Ao lado do número, a seta compara com a atualização mais próxima de 30 dias atrás (ou com a primeira, enquanto o site tiver menos de 30 dias; na primeira atualização, não há seta). Se o multiplicador subiu mais de 10%, "piorando"; se caiu mais de 10%, "melhorando"; senão, "estável".

**Recessão técnica.** Dois trimestres seguidos de queda do PIB:

- **Dado:** PIB trimestral dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre imediatamente anterior). Queda é a taxa divulgada, com uma casa decimal, abaixo de zero; 0,0% não conta.
- **Revisões:** o PIB é revisado; em 2021, uma recessão técnica anunciada sumiu na revisão seguinte.
- **Auditoria:** se a datação do CODACE/FGV IBRE divergir da regra técnica, o site publica as duas leituras.

O nome do site fala em crise; a métrica é recessão técnica. "Vai dar crise?" é a pergunta de bar; a resposta é uma conta com regra escrita.

**E até 2030.** A mesma conta, estendida, dá a chance de pelo menos uma recessão técnica até o fim de 2030:

> O PIB do Brasil terá dois trimestres seguidos de queda entre o 3º trimestre de 2026 e o 4º trimestre de 2030?

A resposta sai na série vigente em março de 2031. Essa chance aparece no fim de "Como a conta funciona", com a faixa dos nove métodos da taxa-base. Ela se move devagar, porque os indicadores só pesam nos próximos trimestres.

## Taxa-base

Antes de olhar qualquer dado ou notícia, a história já diz muito. O CODACE datou 10 recessões desde 1980. Dividindo os inícios de recessão pelos trimestres em expansão, o resultado depende de onde a conta começa:

| Período de referência | Risco por trimestre | Até o 4T30 (17 inícios possíveis) |
| --- | --- | --- |
| 1980–2026 (10 recessões) | 7,5% | 73% |
| 1995–2026, pós-Real (7) | 7,1% | 71% |
| 2T99–2026, metas de inflação e câmbio flutuante (5) | 5,6% | 63% |
| 2004–2026 (3) | 4,0% | 50% |

Escolher uma linha dessa tabela é escolher o resultado. Por isso o site não escolhe: a âncora é a **mediana de nove métodos**, e cada um tem uma regra fixa para decidir quanto o passado pesa.

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

Só com a história, os nove métodos vão de 54% a 66% até 2030. Qualquer pessoa refaz a conta com [`src/taxa_base.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/taxa_base.py) e a cronologia em [`data/cronologia.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/cronologia.json).

**O que ficou de fora.**

- **Tirar a pandemia:** daria 2,7% por trimestre desde 2004 (37% até 2030). Choques externos fazem parte do risco até 2030: das cinco recessões desde 1999, duas vieram de choques globais (2008 e 2020).
- **Começar em 2004:** com só três recessões, o intervalo de 90% para o risco vai de 1,4% a 9,4% por trimestre, e a diferença para antes de 2004 não é estatisticamente significativa (p ≈ 0,09).
- **Começar em 1980:** trataria hiperinflação e câmbio fixo como riscos de hoje.

**Conferência com o IBGE.** A pergunta se resolve pela regra técnica do IBGE, mas a taxa-base usa a datação do CODACE. Na série atual da tabela 5932 (2T96 a 2T26), todo episódio de dois trimestres seguidos de queda cai dentro de uma recessão do CODACE, e nenhum fica de fora. 2021 não conta: na série revisada, a queda do 2T21 (−0,7%) ficou isolada. Quando quedas separadas por um único trimestre de alta contam como um episódio só (2014–16 teve três), os riscos coincidem com os do CODACE: 5,6% por trimestre desde 2T99 e 4,0% desde 2004. Contar cada recaída como recessão nova daria 7,7% desde 2T99, mas a pergunta é pela primeira recessão, não pelas recaídas.

Um início de recessão no trimestre *t* exige que *t* e *t+1* estejam na janela, então há 17 inícios possíveis (3T26 a 3T30). Com 5,3% por trimestre, a chance só pela história é 1 − 0,947¹⁷ ≈ 60%.

## A conta

O modelo soma duas camadas na escala de log-odds (logit), o que torna cada contribuição exata e aditiva. As notícias não entram na conta: elas aparecem à parte, como pressão por tema (veja [Notícias](#noticias)).

```
logit(h_t) = logit(h0) + w_t × I
chance de 12 meses = 1 − Π (1 − h_t), nos quatro primeiros trimestres
multiplicador = chance de 12 meses ÷ normal
P(recessão até 4T30) = 1 − Π (1 − h_t), em todos os trimestres até o 3T30
```

- **h0** é a taxa-base de 5,3% por trimestre. O normal é a chance de 12 meses com I = 0: 1 − 0,947⁴ ≈ 19,6%.
- **I** é a soma das contribuições dos indicadores, inclusive o de mercado.
- **w_t** é o peso no tempo: 1 nos quatro primeiros trimestres ainda não divulgados, 2/3 no quinto, 1/3 no sexto e zero daí em diante.

Ninguém prevê recessão a quatro anos com dados de hoje: os melhores métodos acertam de 6 a 18 meses. Por isso os indicadores mexem só no risco dos próximos trimestres, e a chance até 2030 se move devagar.

**De onde vem o multiplicador.** A página "Como a conta funciona" parte do normal de 12 meses e soma o que cada indicador acrescenta, em pontos percentuais, até chegar à chance de hoje.

**Trimestres divulgados.** Quando o IBGE divulga um trimestre, ele sai da janela (efeito tempo). Se dois trimestres seguidos vierem negativos, a pergunta está resolvida e a chance vai a 100%. Se o último trimestre divulgado vier negativo, a chance de o seguinte também cair parte de 50% (parâmetro por julgamento, a calibrar com a série do IBGE) e recebe o mesmo deslocamento de curto prazo.

**Decomposição.** A conversão de log-odds para probabilidade não é linear, então a repartição em pontos usa valores de Shapley exatos: cada fator recebe a sua contribuição média sobre todas as ordens possíveis, e a soma bate exatamente com o total repartido. Em "De onde vem", os fatores repartem a diferença entre a chance de 12 meses de hoje e o normal; a tabela de indicadores mostra esses mesmos pontos. Em "O que mudou" e na conta do dia de cada post, os fatores repartem a variação entre duas atualizações; no post, a variação aparece em vezes o normal, com duas casas. Os números exibidos são arredondados de modo que as parcelas somem o total exibido.

## Indicadores

Sete sinais, cada um com valor neutro, inclinação e efeito máximo, publicados antes de entrarem na conta. Os pesos são de julgamento, com encolhimento de 25% na soma para não contar duas vezes sinais correlacionados (juros, câmbio e dívida andam juntos), e teto de 1,2 em log-odds para a camada inteira.

| Indicador | Definição | Neutro | Efeito por unidade | Faixa do efeito |
| --- | --- | --- | --- | --- |
| Atividade | IBC-Br dessazonalizado, média de 3 meses contra os 3 anteriores (BCB 24364) | +0,5% | −0,40 por p.p. | −0,30 a +0,60 |
| Desemprego | Regra de Sahm adaptada: média de 3 meses da desocupação da PNAD menos o mínimo dessa média nos 12 meses anteriores (BCB 24369) | 0,15 p.p. | +1,20 por p.p. | −0,20 a +0,70 |
| Juro real ex-ante | Selic meta (BCB 432) descontada da inflação esperada para 12 meses (Focus) | 5% | +0,08 por p.p. | −0,20 a +0,40 |
| Dívida das famílias | Comprometimento de renda com dívidas (BCB 29034) menos a média de 36 meses | 0 | +0,10 por p.p. | −0,15 a +0,30 |
| Dívida pública | Variação da dívida bruta do governo geral em 12 meses (BCB 13762) | +1 p.p. do PIB | +0,04 por p.p. | −0,10 a +0,25 |
| Câmbio | Variação do dólar PTAX em 63 dias úteis (BCB 1) | 0% | +0,015 por p.p. | −0,10 a +0,25 |
| Juro real longo (mercado) | Taxa do Tesouro IPCA+ com vencimento mais perto de 10 anos ([Tesouro Direto](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto), venda pela manhã) menos a sua mediana nos 3 anos anteriores | 0 p.p. | +0,25 por p.p. | −0,15 a +0,40 |

**Por que um indicador de mercado.** Como as notícias ficam fora da conta, o número precisa de algo que reaja no mesmo dia a um choque de confiança, como o do dia seguinte à eleição de 2026 (a taxa de 10 anos foi de 6,9% para 8,1%). O juro real longo resume, em preço, o prêmio que o mercado cobra pelo risco fiscal e pela incerteza, e não depende de quem escreve as manchetes. A série sai com um dia de atraso; se o arquivo do Tesouro não puder ser baixado e a cópia local tiver mais de 5 dias, o indicador sai da conta naquele dia. O peso é de julgamento: num teste com dados de 1999 a 2025, nenhum modelo de pilares estimado, nem um com o prêmio de risco (EMBI+), bateu a taxa-base fora da amostra. Ele sobrepõe em parte o juro real ex-ante, e o encolhimento de 25% e o teto da camada valem para os sete juntos.

Ficaram de fora, por falta de fonte gratuita estável: inclinação da curva de juros (B3), incerteza (FGV IBRE), CDS e indicador antecedente composto. A curva de juros, a mais citada na literatura, quase não tem poder preditivo em emergentes e não foi robusta no Brasil em 2005–2023.

## Notícias

Um modelo de linguagem (Claude, chamado sem ferramentas e com saída em esquema JSON validado por código) lê as manchetes de oito veículos com linhas editoriais diferentes: Agência Brasil, Folha, Estadão, Valor, InfoMoney, Poder360, Gazeta do Povo e g1. Ele transforma os fatos relevantes em eventos estruturados: tema, direção, tamanho e estágio.

**As notícias não mexem no número.** Se cada notícia somasse um pedaço até um teto, uma ou duas notícias ruins por dia encheriam o teto em poucos dias e o número travaria; e, como os jornais publicam mais notícia ruim que boa, a camada tenderia a ficar sempre no limite de cima. Por isso o número só se mexe com dados e mercado, e as notícias mostram, à parte, para que lado o risco está sendo empurrado antes de os dados confirmarem.

**Uma atualização por dia.** As manchetes são coletadas de hora em hora e guardadas na máquina que roda o site. Às 06h30, a atualização lê as manchetes do dia anterior que ainda não foram lidas, calcula o número e publica um post. Cada manchete é lida uma vez só.

**A pressão por tema.** Cada evento entra num de oito temas: contas públicas, juros e inflação, crédito, atividade e emprego, mundo, mercado financeiro, instituições, e energia, safra e preços. Em cada tema:

1. Cada evento tem um efeito, em log-odds, conforme o tamanho e o estágio do fato (tabelas abaixo). O efeito cai em linha reta até zero em 75 dias.
2. De cada lado (o que pesa e o que alivia), conta inteiro o evento mais forte, metade do segundo, um quarto do terceiro, e assim por diante. Dez manchetes sobre o mesmo aperto não valem dez vezes uma.
3. O saldo do tema é o que pesa menos o que alivia. A seta do tema sobe com saldo de 0,05 ou mais, desce com −0,05 ou menos e fica em "sem pressão clara" no meio. A seta geral soma os saldos dos temas, com corte de 0,10.

A pressão não tem número na página: só a seta de cada tema e as notícias que mais pesam nela. O cálculo é feito por código, a partir dos eventos já classificados; o modelo de linguagem não decide a seta.

**Estágio.** Cada evento recebe o estágio em que o fato está, e o estágio multiplica o efeito:

| Estágio | Peso |
| --- | --- |
| Dado divulgado (estatística oficial, resultado publicado) | 1 |
| Decisão tomada (lei sancionada, decisão do Copom, medida publicada) | 1 |
| Proposta em votação (projeto enviado, votação marcada) | a chance estimada de aprovação, entre 0,2 e 0,8 |
| Anúncio sem ato formal | 0,3 |
| Rumor, bastidor ou plano em estudo | 0,1 |

Na dúvida, o classificador usa o estágio menos avançado. Evento sem estágio marcado vale inteiro.

| Regra | Valor |
| --- | --- |
| Efeito por tamanho do fato (1, 2, 3) | 0,04, 0,12 e 0,20 em log-odds |
| Fato que o mercado já esperava | vale metade |
| Fato noticiado por um só veículo | vale metade |
| Teto por evento | 0,2 em log-odds |
| Prazo de validade | o efeito cai em linha reta até zero em 75 dias |
| Notícia que só relata um dado já medido | fica de fora (evita dupla contagem) |
| Estágio do fato | multiplica o efeito (tabela acima) |

O LLM extrai e narra; não prevê. Ele não vê os pesos, não escolhe a direção do número nem da pressão e não edita o site. O texto das notícias é tratado como dado, nunca como instrução, e nenhuma notícia pode alterar pesos ou regras. A linguagem dos eventos descreve políticas e números, não pessoas ou partidos.

**O post do dia.** Depois da conta, o modelo de linguagem recebe os números prontos e escreve o post: o que moveu o número, para que lado as notícias empurram, tema a tema, e o que acompanhar. Ele não muda o número nem a pressão. Um verificador em código procura moldes de texto automático e pede uma reescrita no máximo; se a escrita falhar, o site publica a conta do dia sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta. Respostas antigas nunca são recalculadas: o que foi publicado fica congelado.

## Salvaguardas

- **Disjuntor:** se a chance até 2030 andar mais de 5 pontos de uma atualização para a outra, a conta sai com o selo "em revisão".
- **Dado defasado:** se a conta passar de 36 horas sem atualização, a página avisa.
- **Falha do LLM:** a atualização sai só com dados, e a pressão mostra só os eventos que já valiam, perdendo força.
- **Falha do Tesouro Direto:** vale a cópia local de até 5 dias; mais velha, o indicador de mercado sai da conta naquele dia.
- **Os dois lados:** a página mostra até quatro argumentos por mais crise e por menos crise, tirados das manchetes. Só troca de lista quando a leitura do dia traz pelo menos um argumento de cada lado.
- **Placar:** as previsões de 12 meses ficam registradas e serão pontuadas pelo escore de Brier quando vencerem.

## O que ainda falta

- Backtest de 1996 a 2026 das camadas 1 e 2, com os dados como eram conhecidos na época. O LLM não entra no backtest, porque ele sabe o que aconteceu em 2015 e 2020.
- Teste mensal de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Probit em painel com cerca de 20 emergentes para estimar os pesos com mais dados do que as 7 recessões brasileiras desde 1995.
- Calibrar a chance de um trimestre negativo ser seguido de outro. Na série atual do IBGE, isso aconteceu em 7 de 16 casos desde 1996 (44%); o parâmetro fica em 50% até o backtest.
- Avaliar um ajuste limitado para vulnerabilidades domésticas (fiscal, juros, crédito), com base nas causas das recessões passadas. Ele só entra se melhorar o backtest.

Se o backtest não bater a taxa-base, o site vai dizer isso em público. Um teste com seis séries do Banco Central e o EMBI+ (1999–2025) não bateu: os pesos estimados mudavam de sinal conforme a versão, e o erro fora da amostra ficou de 8% a 58% maior que o da taxa-base. Por isso os pesos continuam de julgamento.

## Onde erramos

Erros são listados aqui com data, o que estava errado e o efeito no número. Nenhum até agora.

Achou um? [Abra uma issue](https://github.com/pedrojahara/vaidarcrise/issues).

## Fontes

- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Chinn e Ferrara (2024), curva de juros em emergentes, NBER w32084
- Tetlock e Gardner (2015), *Superforecasting*, sobre classes de referência
- Pesaran e Timmermann (2007), *Selection of estimation window in the presence of breaks*, Journal of Econometrics
- Pesaran, Pettenuzzo e Timmermann (2006), *Forecasting time series subject to multiple structural breaks*, Review of Economic Studies
