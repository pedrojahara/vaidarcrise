# Metodologia

As regras estão em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json). O que foi estimado com os dados (coeficientes, ajuste, cortes dos níveis, faixas normais) está em [`config/calibracao.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/calibracao.json). O painel de países está em [`data/historico/painel_ocde.csv`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/painel_ocde.csv), e o Brasil mês a mês, em [`data/historico/mensal.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/mensal.json). A conta é refeita por [`src/calibra.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/calibra.py). Cada atualização grava o hash dos dois arquivos de regra.

## A pergunta

> O risco de o Brasil entrar em recessão técnica nos próximos 12 meses está acima ou abaixo do normal?

- **Recessão técnica:** dois trimestres seguidos de queda do PIB dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre anterior, com uma casa decimal; 0,0% não é queda).
- **Recaídas:** quedas separadas por um só trimestre sem queda contam como uma recessão só. 2014–16 é um episódio, não três.
- **Próximos 12 meses:** os 4 trimestres a partir do primeiro que o IBGE ainda não divulgou. O IBGE leva cerca de 60 dias para divulgar cada trimestre.
- **Normal:** o Brasil de maio de 2004 até hoje.
- **Recessões na série atual do IBGE:** 2T01–4T01, 1T03–2T03, 4T08–1T09, 2T14–4T16 e 1T20–2T20. Todas caem dentro de recessões datadas pelo [CODACE/FGV IBRE](https://portalibre.fgv.br/codace). 2021 não conta: na série revisada, a queda do 2T21 ficou isolada.

O nome do site fala em crise; a métrica é recessão técnica.

## O nível

Cinco níveis: Muito abaixo, Abaixo, Normal, Acima e Muito acima. O nível sai só de dados.

**A ideia.** Risco de recessão tem duas partes: a chance de a economia encolher e o tamanho da queda. As duas aparecem num número só, o **cenário ruim do PIB**: o crescimento nos 12 meses seguintes que tem só 1 chance em 10 de ser pior. Quanto pior esse cenário, mais alto o risco. É o método do FMI chamado crescimento em risco (*growth-at-risk*; Adrian, Boyarchenko e Giannone, 2019).

**1. Quatro entradas do Brasil**, cada uma com o que já tinha sido divulgado no dia:

| Entrada | Definição |
| --- | --- |
| Crescimento em 12 meses | IBC-Br dessazonalizado (BCB 24364): média dos 3 últimos meses contra os mesmos 3 meses um ano antes |
| Crescimento médio em 10 anos | Média do crescimento em 12 meses do PIB do IBGE nos 40 últimos trimestres divulgados |
| Selic: variação em 12 meses | Selic meta (BCB 432) de hoje menos a de um ano antes, em pontos |
| Inflação: variação em 12 meses | IPCA em 12 meses (BCB 13522) do último mês menos o de um ano antes, em pontos |

**2. A conta, tirada de 44 países.** Uma regressão de quantil (Koenker e Bassett, 1978) do crescimento do PIB nos 4 trimestres seguintes, no quantil 10%, num painel trimestral de 44 países (OCDE e grandes emergentes, Brasil incluído) com dados da OCDE: 4.669 trimestres, de 1995 a 2025. Com 4 recessões no Brasil desde 2002, uma conta só com o Brasil não teria dados para separar sinal de acaso; o painel tem centenas.

```
cenário ruim = −0,71 − 0,20 × média de 10 anos + 0,23 × crescimento em 12 meses
               − 0,15 × variação da Selic − 0,13 × variação da inflação − 1,31
```

- Crescimentos em 100 × log; no site, convertidos para variação %.
- **Juro subindo e inflação acelerando** pioram o cenário ruim: costumam vir antes de recessões, em países ricos e emergentes.
- **Crescer forte hoje** melhora o ano seguinte.
- **Crescimento médio alto** piora o cenário ruim: vem junto com economias que oscilam mais, como as emergentes.
- **O ajuste de −1,31** vem do teste fora da amostra (abaixo): sem ele, 15% dos resultados ficaram abaixo do cenário ruim, e não 10%.

**3. O nível.** O cenário ruim de hoje contra o do Brasil em cada mês desde maio de 2004:

| Cenário ruim do PIB em 12 meses | Nível |
| --- | --- |
| Entre os 10% piores meses (−3,5% ou pior) | Muito acima |
| Entre os 10% e os 30% piores (até −2,4%) | Acima |
| No meio (de −2,4% a −1,4%) | Normal |
| Entre os 30% e os 10% melhores (até −0,6%) | Abaixo |
| Entre os 10% melhores (melhor que −0,6%) | Muito abaixo |

No mês típico, o cenário ruim é de −1,9%. É a linha "o mesmo cenário em tempos normais" do selo.

**4. Confirmação.** O nível só muda quando duas atualizações diárias seguidas dão o mesmo nível novo. Uma atualização refeita no mesmo dia não confirma a si mesma.

**Mais provável.** O selo mostra também a mediana do Focus para o PIB dos próximos 12 meses (a do ano corrente e a do seguinte, ponderadas pelos meses que faltam). É o mercado, não a conta do site: no Brasil desde 2004, o Focus errou menos que a mediana do painel.

**Os sete fatores do Resumo.** Atividade e juro e inflação entram na conta pelas entradas acima; o Resumo mostra quanto cada uma mexe no cenário ruim, contra a mediana do Brasil desde 2004. Crédito, mercado financeiro, contas públicas, emprego e cenário externo ficam fora do nível e aparecem com o dado de hoje contra a faixa normal desde 2002 (metade dos meses dentro dela) e com a tendência.

| Indicador do Resumo | Fator | Definição |
| --- | --- | --- |
| IBC-Br | Atividade | Média dos últimos 3 meses contra a dos 3 anteriores |
| PIB esperado pelo Focus | Atividade | PIB dos próximos 12 meses, como acima |
| Juro real | Juro e inflação | Selic meta descontada da inflação esperada em 12 meses (Focus) |
| Renda comprometida com dívidas | Crédito e famílias | Comprometimento de renda das famílias (BCB 29034) menos a média dos 36 meses anteriores |
| Juro do Tesouro IPCA+ | Mercado financeiro | Taxa do título IPCA+ com vencimento mais perto de 10 anos menos a sua mediana nos 3 anos anteriores |
| Dólar | Mercado financeiro | Variação do dólar PTAX (BCB 1) em 3 meses |
| Dívida pública | Contas públicas | Variação da dívida bruta do governo geral (BCB 13762) em 12 meses, em pontos do PIB |
| Regra de Sahm | Emprego | Média de 3 meses da desocupação da PNAD (BCB 24369) menos o menor valor dessa média nos 12 meses anteriores |
| Preço das commodities | Cenário externo | Variação em 6 meses do índice de commodities do FMI (FRED PALLFNFINDEXM) |

## Por que essas entradas

As entradas foram escolhidas fora da amostra no painel, pelo erro da regressão de quantil (perda *pinball*), com a mesma validação descrita abaixo. Cada candidata foi somada às quatro e ficaria só se o erro de anos não vistos caísse 1% ou mais.

| Candidata | Erro fora da amostra |
| --- | --- |
| Bolsa (retorno real em 12 meses) | 4,6% menor |
| Crédito acima da tendência | 0,7% menor |
| Juro longo subindo | 0,3% menor |
| Dívida pública | igual |
| Câmbio real acima da média de 10 anos | 0,6% maior |
| Desemprego subindo | 0,9% maior |
| Hiato do produto | 2,7% maior |
| Câmbio (alta em 12 meses) | 2,9% maior |
| Curva de juros | 4,8% maior |

- **A bolsa ficou de fora pela coleta, não pelo teste.** A atualização automática ainda não tem uma fonte diária do Ibovespa testada. Entra quando tiver.
- **Nível alto e parado não avisa.** Dívida, juro e inflação altos não somam à conta. O que avisa é o movimento: juro subindo, inflação acelerando.

## O teste fora da amostra

- **No painel:** cada ano, de 2004 a 2026, foi previsto com coeficientes estimados só com os trimestres cujo PIB 4 trimestres à frente já tinha saído no começo daquele ano. São 3.625 trimestres.
- **No Brasil:** o mesmo, mês a mês, de maio de 2004 a hoje, com os atrasos de divulgação de cada série. São 270 meses.

| Medida | Resultado |
| --- | --- |
| Erro da conta contra usar só o crescimento médio do país (painel) | 3% menor |
| Resultados abaixo do cenário ruim, sem ajuste (painel) | 15% |
| Resultados abaixo do cenário ruim, com ajuste (Brasil, 259 meses) | 8% |
| PIB médio nos 12 meses seguintes, meses em Acima ou Muito acima (Brasil) | +0,8% |
| PIB médio nos 12 meses seguintes, demais meses (Brasil) | +2,8% |
| Recessão à frente, meses em Acima ou Muito acima contra os demais (Brasil) | 1,8 vez mais |
| Chance de um mês com recessão à frente ter nível mais alto que um mês sem (Brasil, 220 meses; 0,5 é o acaso) | 0,60 |

O que isso quer dizer, sem enfeite:

- **O ganho é modesto.** A conta separa bem anos de crescimento fraco de anos de crescimento forte, mas não acerta a data em que cada recessão começa: nos 44 países, nesse ponto, não faz melhor que o acaso.
- **Choques de fora não aparecem antes.** Em 2008 e em 2020, o nível estava entre Abaixo e Normal antes da recessão.
- **A recessão de 2014, feita em casa, apareceu, mas cedo.** O nível ficou em Acima de meados de 2011 em diante.
- **Quatro recessões no Brasil é pouco.** Por isso a conta vem do painel; o Brasil só define o que é normal aqui.
- **Os dados são os de hoje.** PIB, IBC-Br e o painel usados no teste são os revisados, não os divulgados na época. O teste respeita os atrasos de divulgação, mas não as revisões.

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

- **Fatos de dados:** saem de código, todo dia, comparando o dado de hoje com a série histórica ("o maior desde…").
- **Fatos de notícia:** no máximo 2 por fator, válidos por 180 dias.
- **O que outros projetam, em igual destaque:** em atividade, juro e mercado, o Focus, calculado por código; nos demais, a projeção pública mais recente de uma instituição (IFI, por exemplo). Quando a projeção aponta para o lado contrário da nossa tendência, aparece como "Discordam".
- **Quem muda o quê:** o modelo de linguagem só propõe. Fato de notícia novo entra sempre. Troca de tendência só entra com dado divulgado ou decisão tomada, noticiados por pelo menos 2 jornais. Nos fatores com Focus, a projeção não aceita troca pelo modelo.
- **Os dois lados:** cada fator mostra o que o melhoraria e o que o pioraria. Os textos descrevem mecanismos e números, não intenções, pessoas ou partidos, e nunca dizem o que um governo deveria fazer.

**O placar.** Cada tendência é registrada e conferida 6 meses depois contra uma medida fixa por fator (atividade: IBC-Br; juro: juro real; crédito: renda comprometida; mercado: taxa do Tesouro IPCA+; contas: dívida bruta; emprego: desemprego; externo: índice de commodities).

- "Estável" acerta se a medida andou menos de um quarto do desvio-padrão das variações de 6 meses desde 2002; "piora" e "melhora", se andou mais que isso para o lado dito.
- Leitura trocada antes do prazo fica registrada como substituída, sem resultado.
- Para comparar: por acaso, desde 2002, "piora" acertaria 41% das vezes, "estável" 21% e "melhora" 39%, na média dos fatores. Em crédito e contas públicas, "piora" acertaria mais da metade das vezes, porque essas séries subiram na maior parte do período.

## O post do dia

Depois da conta, o modelo de linguagem recebe os números prontos e escreve o post: o nível, o cenário ruim do PIB, o que pesa e o que alivia, para que lado as notícias empurram e as próximas datas. Ele não muda o nível, a pressão nem a tendência. Um verificador em código procura moldes de texto automático, afirmações de chance de recessão e explicações de método, e pede uma reescrita no máximo. Se a escrita falhar, sai a atualização sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta em [`runs/`](https://github.com/pedrojahara/vaidarcrise/tree/main/runs). O que foi publicado fica congelado.

## Salvaguardas

- **Dado defasado:** se a página passar de 36 horas sem atualização, ela avisa.
- **Falha de coleta:** vale o último valor de até 10 dias (dado diário), 101 dias (dado mensal) ou 200 dias (PIB trimestral). Se faltar uma entrada da conta mesmo assim, a atualização não sai, e o site avisa que está defasado.
- **Falha do modelo de linguagem:** a atualização sai só com dados e sem pressão de notícias.
- **Texto das notícias:** é tratado como dado, nunca como instrução. Nenhuma notícia muda pesos ou regras.

## O que ainda falta

- Pôr a bolsa na conta, com uma coleta diária do Ibovespa testada.
- Testar o preço das commodities, que o painel de países não tem.
- Refazer o teste com os dados como eram divulgados na época (com revisões).
- Teste de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Conferir o placar contra o Focus, além do dado.

## Onde erramos

Erros são listados aqui com data, o que estava errado e o efeito no nível. Nenhum até agora.

Achou um? [Abra uma issue](https://github.com/pedrojahara/vaidarcrise/issues).

## Fontes

- Adrian, Boyarchenko e Giannone (2019), *Vulnerable growth*, American Economic Review
- FMI (2017), *Financial conditions and growth at risk*, Global Financial Stability Report, outubro, capítulo 3
- Koenker e Bassett (1978), *Regression quantiles*, Econometrica
- [OCDE: PIB trimestral, juros e preços ao consumidor](https://data-explorer.oecd.org/)
- Sahm (2019), *Direct stimulus payments to individuals*, Brookings, sobre a regra de Sahm
- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- [Tesouro Direto: taxas dos títulos](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto)
- [FMI, índice de preços de commodities, via FRED](https://fred.stlouisfed.org/series/PALLFNFINDEXM)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
