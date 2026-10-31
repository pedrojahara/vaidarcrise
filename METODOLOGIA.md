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

**A ideia.** Risco de recessão tem duas partes: a chance de a economia encolher e o tamanho da queda. As duas aparecem num número só, o **PIB num ano ruim** (no jargão, o cenário ruim, ou quantil 10%): o crescimento nos 12 meses seguintes que tem só 1 chance em 10 de ser pior. Quanto pior esse ano ruim, mais alto o risco. É o método do FMI chamado crescimento em risco (*growth-at-risk*; Adrian, Boyarchenko e Giannone, 2019).

**1. Quatro entradas do Brasil**, cada uma com o que já tinha sido divulgado no dia:

| Entrada | Definição |
| --- | --- |
| Crescimento em 12 meses | IBC-Br dessazonalizado (BCB 24364): média dos 3 últimos meses contra os mesmos 3 meses um ano antes |
| Crescimento médio em 10 anos | Média do crescimento em 12 meses do PIB do IBGE nos 40 últimos trimestres divulgados |
| Selic: variação em 12 meses | Selic meta (BCB 432) de hoje menos a de um ano antes, em pontos |
| Inflação: variação em 12 meses | IPCA em 12 meses (BCB 13522) do último mês menos o de um ano antes, em pontos |

**2. A conta, tirada de 44 países.** Uma regressão de quantil (Koenker e Bassett, 1978) do crescimento do PIB nos 4 trimestres seguintes, no quantil 10%, num painel trimestral de 44 países (OCDE e grandes emergentes, Brasil incluído) com dados da OCDE: 4.669 trimestres, de 1995 a 2025. Com 4 recessões no Brasil desde 2002, uma conta só com o Brasil não teria dados para separar sinal de acaso; o painel tem centenas.

```
ano ruim = −0,71 − 0,20 × média de 10 anos + 0,23 × crescimento em 12 meses
               − 0,15 × variação da Selic − 0,13 × variação da inflação − 1,31
```

- Crescimentos em 100 × log; no site, convertidos para variação %.
- **Juro subindo e inflação acelerando** pioram o ano ruim: costumam vir antes de recessões, em países ricos e emergentes.
- **Crescer forte hoje** melhora o ano seguinte.
- **Crescimento médio alto** piora o ano ruim: vem junto com economias que oscilam mais, como as emergentes.
- **O ajuste de −1,31** vem do teste fora da amostra (abaixo): sem ele, 15% dos resultados ficaram abaixo do ano ruim, e não 10%.

**3. O nível.** O ano ruim de hoje contra o do Brasil em cada mês desde maio de 2004:

| PIB num ano ruim, em 12 meses | Nível |
| --- | --- |
| Entre os 10% piores meses (−3,5% ou pior) | Muito acima |
| Entre os 10% e os 30% piores (até −2,4%) | Acima |
| No meio (de −2,4% a −1,4%) | Normal |
| Entre os 30% e os 10% melhores (até −0,6%) | Abaixo |
| Entre os 10% melhores (melhor que −0,6%) | Muito abaixo |

No mês típico, o ano ruim é de −1,9%. É a linha "Num ano ruim, em tempos normais" do selo.

**4. Confirmação.** O nível só muda quando duas atualizações diárias seguidas dão o mesmo nível novo. Uma atualização refeita no mesmo dia não confirma a si mesma.

**Mais provável.** O selo mostra também a mediana do Focus para o PIB dos próximos 12 meses (a do ano corrente e a do seguinte, ponderadas pelos meses que faltam). É o mercado, não a conta do site: no Brasil desde 2004, o Focus errou menos que a mediana do painel.

**Os sete fatores de Fator por fator.** Ritmo da economia e juro e inflação entram na conta pelas entradas acima; a página Fator por fator mostra quanto cada uma mexe no ano ruim, contra a mediana do Brasil desde 2004. Dívidas das famílias, dólar e juro longo, contas do governo, emprego e economia lá fora ficam fora do nível e aparecem com o dado de hoje contra a faixa normal desde 2002 (metade dos meses dentro dela) e com a tendência.

| Indicador de Fator por fator | Fator | Definição |
| --- | --- | --- |
| IBC-Br | Ritmo da economia | Média dos últimos 3 meses contra a dos 3 anteriores |
| PIB esperado pelo Focus | Ritmo da economia | PIB dos próximos 12 meses, como acima |
| Juro real | Juro e inflação | Selic meta descontada da inflação esperada em 12 meses (Focus) |
| Renda comprometida com dívidas | Dívidas das famílias | Comprometimento de renda das famílias (BCB 29034) menos a média dos 36 meses anteriores |
| Juro do Tesouro IPCA+ | Dólar e juro longo | Taxa do título IPCA+ com vencimento mais perto de 10 anos menos a sua mediana nos 3 anos anteriores |
| Dólar | Dólar e juro longo | Variação do dólar PTAX (BCB 1) em 3 meses |
| Dívida pública | Contas do governo | Variação da dívida bruta do governo geral (BCB 13762) em 12 meses, em pontos do PIB |
| Regra de Sahm | Emprego | Média de 3 meses da desocupação da PNAD (BCB 24369) menos o menor valor dessa média nos 12 meses anteriores |
| Preço das commodities | Economia lá fora | Variação em 6 meses do índice de commodities do FMI (FRED PALLFNFINDEXM) |

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

- **A bolsa passou no painel, mas não no Brasil.** Com o retorno real do Ibovespa em 12 meses (B3) como quinta entrada, o erro fora da amostra no Brasil subiu 3,9%. Como a pergunta é sobre o Brasil, ficou de fora.
- **Nível alto e parado não avisa.** Dívida, juro e inflação altos não somam à conta. O que avisa é o movimento: juro subindo, inflação acelerando.

## O teste fora da amostra

- **No painel:** cada ano, de 2004 a 2026, foi previsto com coeficientes estimados só com os trimestres cujo PIB 4 trimestres à frente já tinha saído no começo daquele ano. São 3.625 trimestres.
- **No Brasil:** o mesmo, mês a mês, de maio de 2004 a hoje, com os atrasos de divulgação de cada série. São 270 meses.

| Medida | Resultado |
| --- | --- |
| Erro da conta contra usar só o crescimento médio do país (painel) | 3% menor |
| Erro da conta contra usar só o crescimento médio do país (Brasil, 259 meses) | 20% menor |
| Resultados abaixo do ano ruim, sem ajuste (painel) | 15% |
| Resultados abaixo do ano ruim, com ajuste (Brasil, 259 meses) | 8% |
| PIB médio nos 12 meses seguintes, meses em Acima ou Muito acima (Brasil) | +0,8% |
| PIB médio nos 12 meses seguintes, demais meses (Brasil) | +2,8% |
| Recessão à frente, meses em Acima ou Muito acima contra os demais (Brasil) | 1,8 vez mais |
| Chance de um mês com recessão à frente ter nível mais alto que um mês sem (Brasil, 220 meses; 0,5 é o acaso) | 0,60 |

O que isso quer dizer, sem enfeite:

- **O ganho é modesto.** A conta separa anos de crescimento fraco de anos de crescimento forte, mas não acerta a data em que cada recessão começa: nos 44 países, nesse ponto, não faz melhor que o acaso.
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
- **O que outros projetam, em igual destaque:** em ritmo da economia, juro e inflação e dólar e juro longo, o Focus, calculado por código; nos demais, a projeção pública mais recente de uma instituição (IFI, por exemplo). Quando a projeção aponta para o lado contrário da tendência do site, aparece como "Analistas veem diferente"; para o mesmo lado, "Analistas concordam".
- **Quem muda o quê:** o modelo de linguagem só propõe. Fato de notícia novo entra sempre. Troca de tendência só entra com dado divulgado ou decisão tomada, noticiados por pelo menos 2 jornais. Nos fatores com Focus, a projeção não aceita troca pelo modelo.
- **Os dois lados:** cada fator mostra o que o melhoraria e o que o pioraria. Os textos descrevem mecanismos e números, não intenções, pessoas ou partidos, e nunca dizem o que um governo deveria fazer.

**O placar.** Cada tendência é registrada e conferida 6 meses depois contra uma medida fixa por fator (ritmo da economia: IBC-Br; juro e inflação: juro real; dívidas das famílias: renda comprometida; dólar e juro longo: taxa do Tesouro IPCA+; contas do governo: dívida bruta; emprego: desemprego; economia lá fora: índice de commodities).

- "Estável" acerta se a medida andou menos de um quarto do desvio-padrão das variações de 6 meses desde 2002; "piora" e "melhora", se andou mais que isso para o lado dito.
- Leitura trocada antes do prazo fica registrada como substituída, sem resultado.
- Para comparar: por acaso, desde 2002, "piora" acertaria 41% das vezes, "estável" 21% e "melhora" 39%, na média dos fatores. Em dívidas das famílias e contas do governo, "piora" acertaria mais da metade das vezes, porque essas séries subiram na maior parte do período.

## O que causa recessão

A aba [O que causa recessão](https://vaidarcrise.com.br/causas/) explica o caminho mais comum até a recessão para quem não é economista: por que os preços sobem, o juro alto como freio, a bola de neve das famílias endividadas, os casos de 2013 a 2016 e de 2021 e 2022, a bola de neve da dívida do governo e, no fim, um mapa que junta as partes. Ela não mostra dados do dia; os números com data ficam listados abaixo. Segue a seção "Como explicar um mecanismo" do [PERSONA.md](https://github.com/pedrojahara/vaidarcrise/blob/main/PERSONA.md). Nada dela entra no nível. As duas pesquisas abaixo sustentam o que a aba diz; os números delas ficam aqui, não na aba.

**Gatilhos e fragilidades.** Recessões de 166 países, com dados anuais (Global Macro Database, FMI, Banco Mundial e Jordà, Schularick e Taylor). AUC: 0,5 é cara ou coroa; 1 acerta sempre.

- Dívida, déficit, juro real e inflação altos, em nível ou parados por anos, não preveem a data da recessão em 1, 2 a 3 ou 5 anos (AUC de 0,43 a 0,53).
- O que avisa é o movimento: juro subindo (0,56 a 0,65, em ricos e emergentes) e inflação acelerando (cerca de 0,60 em 1 ano).
- Crédito alto aprofunda a queda: depois de um boom de crédito, a perda de PIB chega ao dobro (Jordà, Schularick e Taylor, 2013). Em 30 países, de 1960 a 2012, dívida das famílias subindo em relação ao PIB antecede crescimento menor e desemprego maior (Mian, Sufi e Verner, 2017). A corrente das famílias na aba junta os dois canais: quem perde o emprego atrasa e o banco empresta menos; quem tem emprego e deve muito corta gasto mesmo pagando em dia.
- Tamanho da queda em 196 recessões do painel de 44 países (abaixo), desde 1996: crédito subindo, crédito acima da tendência e déficit externo vieram com quedas mais fundas; dívida e déficit públicos, não. Juro real acima do crescimento veio com quedas menores: o Banco Central tinha espaço para cortar. Romer e Romer (2018) acham o mesmo para espaço fiscal e monetário.

**O que faz o juro subir.** AUC de cada sinal para "juro 1 ponto ou mais acima nos 12 meses seguintes", um sinal por vez.

- 44 países: painel trimestral da OCDE e grandes emergentes, de 1991 a 2026; juro de curto prazo da OCDE, commodities do FMI, dívida e déficit anuais da Global Macro Database.
- Brasil: Selic meta, mês a mês, de 2002 a 2026; 117 de 286 meses tiveram alta. Cada sinal com o que já tinha saído no mês (IBC-Br, primário e dívida com 2 meses de atraso; commodities com 1). Refeito por [`src/causas.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/causas.py) a partir de `data/historico/series.json`; os números dos 44 países ficam em [`config/causas.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/causas.json).

| Sinal | Definição no Brasil | 44 países | Brasil |
| --- | --- | --- | --- |
| Contas do governo piorando | Déficit primário em 12 meses (BCB 5793) contra um ano antes | 0,48 | 0,72 |
| Inflação esperada subindo | Focus, IPCA esperado para 12 meses, contra 6 meses antes | — | 0,72 |
| Juro perto da inflação | Focus menos Selic (juro real baixo) | 0,59 | 0,68 |
| Economia aquecida | IBC-Br em 12 meses | 0,69 | 0,55 |
| Soja, minério e petróleo subindo | Índice de commodities do FMI em 12 meses | 0,68 | 0,48 |
| Dívida pública alta | Dívida bruta do governo geral (BCB 13762) | 0,46 | 0,50 |

- No começo de cada ciclo de alta da Selic, o déficit primário em 12 meses tinha mudado: 2004, −0,2 ponto do PIB; 2008, +0,1; 2010, +0,6; 2013, +1,1; 2021, +8,4 (pandemia); 2024, +1,5. A alta de 2002 começa antes da série.
- O caminho é a dominância fiscal de Blanchard (2004), escrita sobre o Brasil: déficit subindo eleva a inflação esperada, e o Banco Central sobe o juro. O déficit subindo não avisa a recessão direto (0,48): age pelo juro, que já está na conta.
- Juro americano e commodities, testados como quinta entrada da conta, pioraram o erro fora da amostra em 12 meses: 5,1% e 5,8% no painel; 15,1% e 23,5% no Brasil.

A prévia de link (`docs/causas/og.png`) e as versões dos desenhos para a página saem de [`src/imagens_causas.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/imagens_causas.py), rodado à mão; a atualização diária não os refaz. Os desenhos foram gerados pelo modelo de imagem Gemini, do Google, a partir do roteiro da aba; os originais ficam em `assets/causas/`.

**Números fixos da aba, com data.** Juros nominais do setor público em 12 meses até agosto de 2026: R$ 1,18 trilhão, 8,9% do PIB (Banco Central, estatísticas fiscais, pela imprensa); cerca de R$ 5.500 por brasileiro, com 213 milhões de habitantes. Resultado sem juros no mesmo período: 0,6% do PIB a mais de gasto que de receita (BCB 5793). Sobra sem juros que estabilizaria a dívida bruta: 2,1% do PIB por ano (IFI, Relatório de Acompanhamento Fiscal de agosto de 2026). Dívida federal em reais: 96% (Tesouro, agosto de 2026); não residentes têm cerca de 10% da dívida interna. IPCA de 2021: 10,06%, com gasolina em 47,5% e energia elétrica em 21,2% (IBGE), com o setor público arrecadando 0,7% do PIB a mais do que gastou, sem juros. Desemprego (PNAD): 6,2% em dezembro de 2013, 13,9% em março de 2017, 14,9% em março de 2021 e 7,9% em dezembro de 2022. Índice de commodities do FMI: caiu 49% de junho de 2014 a janeiro de 2016 e subiu 132% de junho de 2020 a junho de 2022. Resultado sem juros do setor público (BCB 5793): sobra de 1,7% do PIB em 2013 e falta de 1,9% em 2015; sobra de 0,7% em 2021 e de 1,3% em 2022. Dívida bruta (BCB 13762): de 51,5% do PIB em 2013 para 69,8% em 2016; de 86,9% em 2020 para 71,7% em 2022. A aba não diz "não houve recessão" em 2021 e 2022: a primeira divulgação do IBGE do terceiro trimestre de 2021 trouxe duas quedas pequenas seguidas (0,4% e 0,1%); diz que a economia cresceu nos dois anos, que é o que o PIB anual mostra. Títulos da dívida federal ligados à Selic: cerca de metade (51% em julho de 2026, Tesouro, pela imprensa). Parte da renda das famílias usada para pagar dívidas, com ajuste sazonal (BCB 29034): 29,0% em agosto de 2026, a maior desde o começo da série, em março de 2005; 22,8% na média de 2014.

**Onde a ligação com as contas do governo é forte e onde é fraca.** Procura acima da capacidade vira preço, e o Banco Central diz que, com a economia no limite, estímulo do governo vira mais inflação que crescimento (ata do Copom de dezembro de 2022). No Brasil, contas piorando vieram antes das altas da Selic (0,72, acima); nos 44 países, não (0,48). Nem toda inflação vem do gasto: 2021 é o contraexemplo. A bola de neve é aritmética (juro acima do crescimento e sem sobra, a dívida sobe); o círculo de volta para o juro, via dólar e inflação esperada, é o de Blanchard (2004), com força que varia com a confiança. Por isso a corrente da aba tem duas partes. A entrada (gasto acima da arrecadação vira preço) leva a condição "com a economia no limite": empréstimo, por si, não gera inflação, e com gente parada o mesmo gasto vira emprego. O círculo (passos 3 a 6) fecha pela desconfiança, não por mais gasto: pegar emprestado para pagar juros põe pouco dinheiro novo na economia, mas a dívida maior encarece o crédito ao governo, sobe o dólar e mantém o juro alto. Hoje os juros (8,9% do PIB) pesam quase 15 vezes mais que o gasto sem juros acima da arrecadação (0,6%), por isso a aba diz que o círculo gira pelos passos 3 a 6. Dívida alta não marcou a data das recessões em 166 países, por isso a aba não fala em espiral nem em prazo.

**Limites.** Um sinal por vez mostra o que vem antes, não o que causa, e dois sinais podem contar a mesma história. Nada disso passou por teste fora da amostra, exceto a quinta entrada. O Brasil teve sete ciclos de alta desde 2002: a margem de erro é grande. No painel, dívida e déficit são anuais e chegam com 1 ano de atraso, o que enfraquece o fiscal ali.

## Os posts

É um post por dia, escrito na mesma atualização das 06h30, e o tipo muda com o dia ([`PERSONA.md`](https://github.com/pedrojahara/vaidarcrise/blob/main/PERSONA.md), "Os tipos de post"):

| Tipo | Quando | O que recebe | Tamanho |
| --- | --- | --- | --- |
| Fato do dia | Segunda a sábado | As notícias da véspera por fator, os fatos de dados dos fatores com notícia e, só se o nível mudou, o PIB num ano ruim e as entradas da conta | Até 100 palavras |
| A semana | Domingo, com atualizações em pelo menos 4 dos 6 dias anteriores | As atualizações de segunda a domingo: nível, entradas e fatores que mudaram, dados novos, notícias somadas por fator (mesma conta da pressão do dia) e as datas da semana seguinte | Até 250 palavras |
| O mês | Primeiro domingo do mês, no lugar da semana, se as atualizações do mês anterior começaram até o dia 8 e cobrem pelo menos 15 dias dele | As atualizações do mês anterior e dos primeiros dias deste, mais quatro partes feitas por código: o que mudou em cada fator, o bolso (emprego, preços, parcelas e dólar), o que faria o risco mudar e o placar | Até 300 palavras de texto; com as tabelas, cerca de 450 |
| Retrato do Brasil | Fixo no topo, escrito à mão em `editor/` | Os números do dia em que foi escrito, com a data | 500 a 600 palavras |

Sem atualizações bastantes, a semana e o mês viram fato do dia. A semana e o mês saem dos registros em `runs/`, nunca dos posts anteriores. Cada post recebe o anterior do mesmo tipo só para não copiar frases dele.

O modelo de linguagem recebe os fatos prontos e só redige. Ele não muda o nível, a pressão nem a tendência. Um verificador em código ([`src/revisa_texto.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/revisa_texto.py)) procura moldes de texto automático, jargão, afirmações de chance de recessão e explicações de método. Nos posts, também confere: número ou data que não está nos dados que o modelo recebeu (com a folga do arredondamento), texto acima do tamanho do tipo, fato do dia que repete o nível sem mudança, data futura no fato do dia (as datas ficam na lateral) e frase copiada do post anterior do mesmo tipo. Qualquer problema pede uma reescrita, no máximo uma. Número fora dos dados, chance de recessão ou mais de uma frase sobre a conta, se sobrarem, barram o texto, e sai a atualização sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta em [`runs/`](https://github.com/pedrojahara/vaidarcrise/tree/main/runs). Depois do lançamento oficial do site, o que foi publicado fica congelado. Antes dele, os textos antigos acompanham as mudanças do site, com os mesmos números e datas.

## Salvaguardas

- **Números velhos:** se a página passar de 36 horas sem atualização, ela avisa.
- **Falha de coleta:** cada fonte tem até 4 tentativas, e a série do Banco Central que falha tenta de novo no fim. O desemprego tem uma segunda fonte, o próprio IBGE. Se ainda faltar, vale o último valor guardado enquanto ele for o mais novo que a fonte deveria ter: 10 dias para dado diário, 200 para o PIB trimestral e, para dado mensal, até 15 dias depois do mês em que o seguinte deveria sair (pela defasagem de cada série). Exemplo: o desemprego do trimestre até agosto vale até 15 de novembro. O cartão do fator avisa quando o dado é de uma atualização anterior. Se faltar uma entrada da conta mesmo assim, a atualização não sai, e o site avisa que está defasado.
- **Falha do modelo de linguagem:** a atualização sai só com dados e sem pressão de notícias.
- **Texto das notícias:** é tratado como dado, nunca como instrução. Nenhuma notícia muda pesos ou regras.

## O que ainda falta

- Testar o preço das commodities, que o painel de países não tem.
- Refazer o teste com os dados como eram divulgados na época (com revisões).
- Teste de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Conferir o placar contra o Focus, além do dado.

## Fontes

- Adrian, Boyarchenko e Giannone (2019), *Vulnerable growth*, American Economic Review
- FMI (2017), *Financial conditions and growth at risk*, Global Financial Stability Report, outubro, capítulo 3
- Koenker e Bassett (1978), *Regression quantiles*, Econometrica
- [OCDE: PIB trimestral, juros e preços ao consumidor](https://data-explorer.oecd.org/)
- [B3: estatísticas do Ibovespa](https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm), para o teste da bolsa
- Sahm (2019), *Direct stimulus payments to individuals*, Brookings, sobre a regra de Sahm
- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- [Tesouro Direto: taxas dos títulos](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto)
- [FMI, índice de preços de commodities, via FRED](https://fred.stlouisfed.org/series/PALLFNFINDEXM)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Blanchard (2004), *Fiscal dominance and inflation targeting: lessons from Brazil*, NBER Working Paper 10389
- Jordà, Schularick e Taylor (2013), *When credit bites back*, Journal of Money, Credit and Banking
- Romer e Romer (2018), *Why some times are different: macroeconomic policy and the aftermath of financial crises*, Economica
- Müller, Xu, Lehbib e Chen (2025), *The Global Macro Database*, NBER Working Paper 33714
