# Metodologia

As regras estão em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json). O que foi estimado com os dados (limites, pesos, regressão) está em [`config/calibracao.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/calibracao.json), e os indicadores mês a mês, em [`data/historico/mensal.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/mensal.json). Cada atualização grava o hash dos dois arquivos de regra.

## A pergunta

> O risco de o Brasil entrar em recessão técnica nos próximos 12 meses está acima ou abaixo do normal?

- **Recessão técnica:** dois trimestres seguidos de queda do PIB dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre anterior, com uma casa decimal; 0,0% não é queda).
- **Recaídas:** quedas separadas por um só trimestre sem queda contam como uma recessão só. 2014–16 é um episódio, não três.
- **Próximos 12 meses:** os 4 trimestres a partir do primeiro que o IBGE ainda não divulgou. O IBGE leva cerca de 60 dias para divulgar cada trimestre.
- **Normal:** a média dos meses desde 2002.
- **Recessões na série atual do IBGE:** 2T01–4T01, 1T03–2T03, 4T08–1T09, 2T14–4T16 e 1T20–2T20. Todas caem dentro de recessões datadas pelo [CODACE/FGV IBRE](https://portalibre.fgv.br/codace). 2021 não conta: na série revisada, a queda do 2T21 ficou isolada.

O nome do site fala em crise; a métrica é recessão técnica.

## O nível

Cinco níveis: Muito abaixo, Abaixo, Normal, Acima e Muito acima. O nível sai só de dados, em cinco passos.

**1. Nove indicadores**, cada um calculado só com o que já tinha sido divulgado no dia:

| Indicador | Fator | Definição | Alerta quando |
| --- | --- | --- | --- |
| IBC-Br | Atividade | IBC-Br dessazonalizado (BCB 24364): média dos últimos 3 meses contra a dos 3 anteriores | cai |
| PIB esperado pelo Focus | Atividade | Mediana do Focus para o PIB do ano e do seguinte, ponderada pelos meses que faltam em cada um (próximos 12 meses) | cai |
| Juro real | Juro real e inflação | Selic meta (BCB 432) descontada da inflação esperada em 12 meses (Focus) | sobe |
| Renda comprometida com dívidas | Crédito e famílias | Comprometimento de renda das famílias (BCB 29034) menos a média dos 36 meses anteriores | sobe |
| Juro do Tesouro IPCA+ | Mercado financeiro | Taxa do título IPCA+ com vencimento mais perto de 10 anos menos a sua mediana nos 3 anos anteriores | sobe |
| Dólar | Mercado financeiro | Variação do dólar PTAX (BCB 1) em 3 meses | sobe |
| Dívida pública | Contas públicas | Variação da dívida bruta do governo geral (BCB 13762) em 12 meses, em pontos do PIB | sobe |
| Regra de Sahm | Emprego | Média de 3 meses da desocupação da PNAD (BCB 24369) menos o menor valor dessa média nos 12 meses anteriores | sobe |
| Preço das commodities | Cenário externo | Variação em 6 meses do índice de commodities do FMI (FRED PALLFNFINDEXM) | cai |

**2. Um limite de alerta para cada indicador**, pelo método de sinais de Kaminsky, Lizondo e Reinhart (1998):

- Candidatos: os percentis 70, 75, 80, 85, 90 e 95 da história do próprio indicador, do lado ruim.
- Fica o candidato com a menor razão ruído/sinal: a fração de alarmes falsos nos meses sem recessão à frente, dividida pela fração de alertas certos nos meses com recessão à frente.
- O indicador precisa ter alertado antes de pelo menos 2 recessões. Um indicador sem nenhum alarme falso é tratado como se tivesse dado um, para o peso não ficar infinito.

**3. Pesos pelo histórico.** Peso = 1 ÷ razão ruído/sinal. Razão de 1 ou mais (mais alarme falso que alerta certo) dá peso zero, e o indicador aparece como "não antecipou recessões". O composto do mês é a soma dos pesos dos indicadores em alerta, dividida pela soma dos pesos dos indicadores com dado. São precisos pelo menos 3 indicadores com dado.

**4. Do composto ao nível.**

```
logit(p) = logit(p̄) + k × (a + b × composto − logit(p̄))
razão = p ÷ p̄
```

- **a** e **b** saem de uma regressão logística dos meses com recessão à frente contra o composto, com uma penalidade mínima (0,01 × b²) só para a conta ter solução quando o composto separa os meses sem erro.
- **p̄** é a média da amostra. **k** puxa a estimativa para a média; ele é escolhido no teste fora da amostra (abaixo).
- Cortes da razão: abaixo de 0,5, Muito abaixo; de 0,5 a 0,8, Abaixo; de 0,8 a 1,25, Normal; de 1,25 a 2, Acima; 2 ou mais, Muito acima.

**5. Confirmação.** O nível só muda quando duas atualizações diárias seguidas dão o mesmo nível novo. Uma atualização refeita no mesmo dia não confirma a si mesma.

**O resultado com os dados de 2002 a agosto de 2025** (243 meses, 48 com recessão à frente):

| Indicador | Limite de alerta | Alertou antes de | Parte do peso |
| --- | --- | --- | --- |
| Dólar | alta de 18,8% em 3 meses | 3 de 4 recessões | 82% |
| IBC-Br | queda de 1,0% no trimestre | 3 de 3 | 6% |
| Preço das commodities | queda de 16% em 6 meses | 2 de 4 | 6% |
| PIB esperado pelo Focus | abaixo de 1,9% em 12 meses | 4 de 4 | 3% |
| Juro do Tesouro IPCA+ | 0,47 ponto acima da mediana de 3 anos | 2 de 3 | 2% |
| Juro real, regra de Sahm | mais alarme falso que alerta certo | – | 0 |
| Renda comprometida, dívida pública | alertaram antes de menos de 2 recessões | – | 0 |

"Recessões" aqui são as que cada série alcança: a de 2001 começou antes da amostra, e várias séries começam depois de 2002.

## O teste fora da amostra

- A amostra foi cortada em blocos de 3 anos. Um corte que cairia dentro do período de aviso de uma recessão foi empurrado para o fim dele.
- Cada bloco foi previsto por uma conta que não o viu: limites, pesos e regressão reestimados só com os outros blocos.
- Medida de erro: escore de Brier (o quadrado da diferença entre a chance prevista e o que aconteceu).

| Conta | Erro fora da amostra |
| --- | --- |
| Repetir sempre a média | 0,171 |
| A conta do site (k = 0,8) | 0,159, ou 7% menor |
| A conta do site sem o dólar | não ganha da média (k = 0) |
| Todos os pesos iguais | não ganha da média (k = 0) |

O que isso quer dizer, sem enfeite:

- **O ganho é pequeno e depende do dólar.** Os outros indicadores, somados por esse método, não acrescentam acerto fora da amostra.
- **Por isso o nível fica no normal na maior parte do tempo.** Sem o dólar em alerta, a conta vai de Abaixo a Acima; com ele, vai a Muito acima.
- **Parte do acerto é de diagnóstico, não de previsão.** Em 2008 e 2020, o dólar disparou junto com o começo da recessão, meses antes de o IBGE confirmá-la. Em 2002, o alerta veio meses antes da recessão de 2003.
- **Muito abaixo não aparece.** Os indicadores medem perigo, não calmaria. Sem nenhum alerta, a razão fica em cerca de 0,77, que é Abaixo.
- **Quatro recessões é pouco.** Um limite ou um peso pode mudar bastante com a próxima recessão. A calibração é refeita quando o IBGE confirmar um novo episódio.
- **Os dados são os de hoje.** A série do PIB e a do IBC-Br usadas no teste são as revisadas, não as divulgadas na época. O teste respeita os atrasos de divulgação, mas não as revisões.

O resultado não cria valor do zero: ele diz que, desde 2002, só choques grandes de câmbio separaram com clareza os meses antes de recessões. O resto dos fatores aparece no Resumo com o seu peso de hoje, quase sempre pequeno, e com a sua tendência.

## Tendência e notícias

As notícias não mexem no nível. Se cada notícia somasse um pedaço, como os jornais publicam mais notícia ruim que boa, o nível tenderia a ficar sempre em cima. As notícias servem para a tendência de cada fator nos próximos 6 meses.

**A leitura das manchetes.** As manchetes de oito jornais com linhas editoriais diferentes (Agência Brasil, Folha, Estadão, Valor, InfoMoney, Poder360, Gazeta do Povo e g1) são coletadas de hora em hora. Às 06h30, um modelo de linguagem (Claude, sem ferramentas, com saída em esquema JSON validado por código) lê as do dia anterior e transforma os fatos em eventos: fator, lado, tamanho (1 a 3) e estágio. Notícia que só repete um dado já medido pelos indicadores fica de fora.

**A pressão do dia, por fator:**

| Regra | Valor |
| --- | --- |
| Pontos por tamanho do fato | 1, 2 ou 3 |
| Dado divulgado, decisão tomada | vale inteiro |
| Proposta em votação | a chance estimada de aprovação, entre 0,2 e 0,8 |
| Anúncio sem ato formal | 0,3 |
| Rumor, bastidor ou plano em estudo | 0,1 |
| Fato de um só jornal | vale metade |
| Fato que o mercado já esperava | vale metade |
| Vários fatos do mesmo lado | o mais forte conta inteiro, o segundo metade, o terceiro um quarto |
| Seta do fator | saldo de 1 ou mais (pesa) ou de −1 ou menos (alivia) |
| Seta geral | soma dos fatores, com corte de 2 |

**A tendência de cada fator.** Fica em [`data/dossie.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/dossie.json): piora, estável, melhora ou sem direção clara.

- **Fatos de dados:** saem de código, todo dia, comparando o dado de hoje com a série desde 2002 ("o maior desde…").
- **Fatos de notícia:** no máximo 2 por fator, válidos por 180 dias.
- **O que outros projetam, em igual destaque:** em atividade, juro e mercado, o Focus, calculado por código; nos demais, a projeção pública mais recente de uma instituição (IFI, por exemplo). Quando a projeção aponta para o lado contrário da nossa tendência, aparece como "Discordam".
- **Quem muda o quê:** o modelo de linguagem só propõe. Fato de notícia novo entra sempre. Troca de tendência só entra com dado divulgado ou decisão tomada, noticiados por pelo menos 2 jornais. Nos fatores com Focus, a projeção não aceita troca pelo modelo.
- **Os dois lados:** cada fator mostra o que o melhoraria e o que o pioraria. Os textos descrevem mecanismos e números, não intenções, pessoas ou partidos, e nunca dizem o que um governo deveria fazer.

**O placar.** Cada tendência é registrada e conferida 6 meses depois contra uma medida fixa por fator (atividade: IBC-Br; juro: juro real; crédito: renda comprometida; mercado: taxa do Tesouro IPCA+; contas: dívida bruta; emprego: desemprego; externo: índice de commodities).

- "Estável" acerta se a medida andou menos de um quarto do desvio-padrão das variações de 6 meses desde 2002; "piora" e "melhora", se andou mais que isso para o lado dito.
- Leitura trocada antes do prazo fica registrada como substituída, sem resultado.
- Para comparar: por acaso, desde 2002, "piora" acertaria 41% das vezes, "estável" 21% e "melhora" 39%, na média dos fatores. Em crédito e contas públicas, "piora" acertaria mais da metade das vezes, porque essas séries subiram na maior parte do período.

## O post do dia

Depois da conta, o modelo de linguagem recebe os números prontos e escreve o post: o nível, os fatores que pesam, para que lado as notícias empurram e as próximas datas. Ele não muda o nível, a pressão nem a tendência. Um verificador em código procura moldes de texto automático, afirmações de chance de recessão e explicações de método, e pede uma reescrita no máximo. Se a escrita falhar, sai a atualização sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta em [`runs/`](https://github.com/pedrojahara/vaidarcrise/tree/main/runs). O que foi publicado fica congelado.

## Salvaguardas

- **Dado defasado:** se a página passar de 36 horas sem atualização, ela avisa.
- **Falha de coleta:** vale o último valor de até 10 dias (dado diário) ou 70 dias (dado mensal). Mais velho, o indicador sai da conta do dia, e o composto usa só os que têm dado.
- **Falha do modelo de linguagem:** a atualização sai só com dados e sem pressão de notícias.
- **Texto das notícias:** é tratado como dado, nunca como instrução. Nenhuma notícia muda pesos ou regras.

## O que ainda falta

- Refazer o teste com os dados como eram divulgados na época (com revisões), quando houver séries de vintage para todos os indicadores.
- Estimar os limites com um painel de emergentes, para ter mais que quatro recessões.
- Teste de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Conferir o placar contra o Focus, além do dado.

## Onde erramos

Erros são listados aqui com data, o que estava errado e o efeito no nível. Nenhum até agora.

Achou um? [Abra uma issue](https://github.com/pedrojahara/vaidarcrise/issues).

## Fontes

- Kaminsky, Lizondo e Reinhart (1998), *Leading indicators of currency crises*, IMF Staff Papers
- Sahm (2019), *Direct stimulus payments to individuals*, Brookings, sobre a regra de Sahm
- Brier (1950), *Verification of forecasts expressed in terms of probability*, Monthly Weather Review
- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- [Tesouro Direto: taxas dos títulos](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto)
- [FMI, índice de preços de commodities, via FRED](https://fred.stlouisfed.org/series/PALLFNFINDEXM)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
