# Metodologia

A regra da direção está em [`src/direcao.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/direcao.py), com as escolhas fixas em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json) (seção `direcao`) e o que sai dos dados (o vaivém normal de cada medida e o resultado desde 2004) em [`config/calibracao.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/calibracao.json) (seção `direcao`). As séries mensais do Brasil ficam em [`data/historico/series.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/series.json). `python src/direcao.py --calibrar AAAA-MM` refaz os cortes e o teste. O crescimento em 12 meses que fica logo abaixo da placa sai de [`src/ritmo.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/ritmo.py), e `python src/ritmo.py --calibrar` refaz a faixa normal dele e o erro do Focus (seção `ritmo` de `config/calibracao.json`). Cada atualização grava o hash dos dois arquivos de regra.

## A pergunta

> Para que lado anda o risco de recessão no Brasil: as pressões que costumam vir antes de uma recessão estão piorando ou melhorando?

- **Recessão técnica:** dois trimestres seguidos de queda do PIB dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre anterior, com uma casa decimal; 0,0% não é queda).
- **Recaídas:** quedas separadas por um só trimestre sem queda contam como uma recessão só. 2014–16 é um episódio, não três.
- **Recessões na série atual do IBGE:** 2T01–4T01, 1T03–2T03, 4T08–1T09, 2T14–4T16 e 1T20–2T20. Todas caem dentro de recessões datadas pelo [CODACE/FGV IBRE](https://portalibre.fgv.br/codace). 2021 não conta: na série revisada, a queda do 2T21 ficou isolada.
- **Direção, não previsão.** O site não diz se vai haver recessão nem quando. Diz se as pressões que costumam vir antes de uma recessão andaram para o lado ruim ou para o lado bom nos últimos 3 meses. A data de uma recessão não se prevê com segurança: nem os economistas profissionais acertam (An, Jalles e Loungani, 2018), e a conta do passado, abaixo, mostra o mesmo para esta regra.

O nome do site fala em crise; a métrica é recessão técnica.

## A regra da direção

**1. Cinco pressões**, escolhidas pelo que a pesquisa da seção O que causa recessão, abaixo, mostra que vem antes de uma recessão: juro subindo, inflação esperada subindo, dívida das famílias subindo, desconfiança de quem investe (dólar e juro de 10 anos subindo, muitas vezes por medo das contas do governo), e as contas do governo piorando.

| Pressão | Medida | Série | Lado ruim | Atraso de divulgação |
| --- | --- | --- | --- | --- |
| Contas do governo | Dívida bruta do governo geral, % do PIB | BCB 13762 (desde dezembro de 2006) | subir | 2 meses |
| Contas do governo, antes de 2007 | Resultado sem juros do setor público em 12 meses, % do PIB | BCB 5793 | gastar mais do que arrecada | 2 meses |
| Dívidas das famílias | Parte da renda das famílias que vai para parcelas e juros, com ajuste sazonal | BCB 29034 | subir | 3 meses |
| Desconfiança de quem investe | Dólar PTAX, variação % | BCB 1 | subir | 0 |
| Desconfiança de quem investe | Juro de 10 anos: taxa real do Tesouro IPCA+ com vencimento mais perto de 10 anos, comparada sempre no mesmo título | Tesouro Direto | subir | 0 |
| Inflação esperada | Mediana do Focus para o IPCA dos 12 meses seguintes | Focus | subir | 0 |
| Juro | Selic meta | BCB 432 | subir | 0 |

Fora da soma, a conta acompanha o **ritmo da economia** (IBC-Br dessazonalizado, BCB 24364: média dos 3 últimos meses contra a dos 3 anteriores; atraso de 2 meses). Ele só decide o "encolhendo" (passo 7) e não é linha da página. Abaixo das cinco pressões, em **Também acompanhamos**, a página mostra quatro linhas que não mudam a placa:

| Linha | Medida | Série | Lado ruim | Atraso de divulgação |
| --- | --- | --- | --- | --- |
| Emprego | Desocupação da PNAD | BCB 24369 | subir | 1 mês |
| Renda | Rendimento médio real habitual de todos os trabalhos (PNAD Contínua, trimestre móvel, em reais do último trimestre); variação % em 3 meses. O IBGE refaz a série inteira com os preços de cada trimestre novo, e por isso a coleta do dia busca a série inteira, desde março de 2012 | IBGE, tabela 6390, variável 5933 | cair | 1 mês |
| Reservas em dólar | Reservas internacionais do Banco Central, conceito liquidez, fim do mês, em US$ milhões; variação % em 3 meses | BCB 3546 | cair | 1 mês |
| Dívida em reais | Parte da dívida pública federal em reais | Tesouro, Relatório Mensal da Dívida, posta à mão em `config/modelo.json` (`direcao.divida_reais`) | cair; a linha ainda não diz o que a parte fez em 3 meses | posta à mão quando sai o relatório do mês |

O emprego é o último a piorar numa recessão, porque as empresas primeiro vendem menos e só depois demitem. A renda média cai junto com o emprego ou depois dele, e pode até subir no começo de uma recessão, quando quem ganha menos perde o trabalho primeiro (de fevereiro a julho de 2020, ela foi de R$ 3.378 para R$ 3.595, em reais de setembro de 2026). As reservas e a dívida em reais amortecem um susto do dólar, mas não avisam que uma recessão vem. Por isso nenhuma das quatro entra na soma.

**2. Cada medida contra 3 meses antes.** A mudança é a diferença em pontos (em % no dólar e na média do IBC-Br) entre o dado de referência e o de 3 meses antes dele.

**3. A escala de cada medida** é 1,4826 vezes o desvio absoluto mediano das mudanças de 3 meses desde janeiro de 2002, com o atraso de divulgação de cada série (em `config/calibracao.json`, `direcao.cortes`). É uma régua robusta: uma crise grande, como 2008 ou 2020, não a alarga. Nas contas do governo, a escala junta as mudanças da dívida (desde 2007) e as do resultado sem juros (antes), e o mesmo corte vale para as duas.

**4. Piorou, igual ou melhorou.** O corte é três quartos da escala (`corte_vaivem` = 0,75); é o que a página chama de vaivém normal de 3 meses. A medida piorou se andou para o lado ruim mais que o corte; melhorou se andou isso para o lado bom; no resto, ficou igual. A página diz "passou raspando" quando a mudança fica abaixo de 1,25 vez o corte. Os cortes de hoje:

| Medida | Escala em 3 meses | Corte, o vaivém normal da página (0,75 × escala) |
| --- | --- | --- |
| Dívida do governo (régua das contas) | 1,26 ponto do PIB | 0,95 ponto |
| Dívidas das famílias (parte da renda que vai para parcelas e juros) | 0,50 ponto da renda | 0,38 ponto |
| Dólar | 6,4% | 4,8% |
| Juro de 10 anos | 0,55 ponto | 0,41 ponto |
| Inflação esperada | 0,42 ponto | 0,32 ponto |
| Selic | 1,11 ponto | 0,83 ponto |
| Ritmo da economia (só para o "encolhendo"; não é linha da página) | 1,19% | 0,89% |
| Emprego (Também acompanhamos) | 0,74 ponto | 0,56 ponto |
| Reservas em dólar (Também acompanhamos) | tirada na hora das variações de 3 meses desde 2002 | 0,75 × essa escala; o valor aparece depois da primeira coleta do Mac |
| Renda (Também acompanhamos) | tirada na hora das variações de 3 meses desde 2012 | 0,75 × essa escala (0,89% em novembro de 2026) |

As reservas ainda não têm corte em `config/calibracao.json`. Enquanto não têm, o corte sai na hora, com a mesma conta, das variações de 3 meses que a coleta do dia traz desde janeiro de 2002 (`src/fetch_data.py` busca essa série inteira); com menos de 36 variações, a linha fica sem lado. Só a atualização do Mac coleta a série, e a página esconde a linha enquanto ela não tem dado. Depois que `src/historico.py` guardar a série, `python src/direcao.py --calibrar` grava o corte das reservas junto com os outros.

O dólar e o juro de 10 anos contam como uma pressão só, a Desconfiança de quem investe: o sinal da soma dos dois lados (se um piora e o outro melhora, fica igual; se um piora e o outro fica igual, piorou).

**Três dias úteis seguidos no dólar e no juro de 10 anos.** Os dois saem todo dia. A mudança de cada dia continua sendo o fechamento contra o fim do mês de 3 meses antes, mas cada um só troca de lado (piorou, igual, melhorou) quando o lado novo se mantém por 3 dias úteis seguidos (`persiste_dias` em `config/modelo.json`). Com o fechamento de um dia só, a Desconfiança de quem investe trocava de lado umas 22 vezes por ano desde 2006 (44 de novembro de 2025 a outubro de 2026), e metade das trocas se desfazia em até 7 dias; com os 3 dias, são umas 11 por ano, e 18% se desfazem em até 7 dias. Na linha do tempo e na conta do passado, cada mês usa o lado que vale no último dia útil dele, com a mesma persistência, calculada dia a dia desde 2002 (dólar) e 2005 (juro de 10 anos). Quando o número do dia já está do outro lado do vaivém e a linha ainda espera os 3 dias, a linha aberta diz isso.

**O juro de 10 anos sempre no mesmo título.** O título do Tesouro IPCA+ que vence mais perto de 10 anos muda de tempos em tempos: em 31/12/2009 (do que vence em 2015 para o de 2024), em 2/1/2020 (do de 2024 para o de 2035), em 10/2/2020 (do de 2035 para o de 2026, que aparece nas taxas do Tesouro Direto a partir desse dia) e em 30/12/2020 (do de 2026 de volta para o de 2035). Cada título paga uma taxa diferente, e a série pula no dia da troca sem que o mercado tenha mexido: −0,41, +0,99, −0,66 e +1,02 ponto, quando o corte é de 0,41. Por isso a mudança de 3 meses compara sempre o título de agora: a taxa dele no dia contra a taxa do mesmo título no fim do mês de 3 meses antes. A taxa de cada título no fim de cada mês, desde julho de 2005, está em `data/historico/titulos_ipca.json` (`python src/historico.py --titulos`, com o arquivo de preços e taxas do Tesouro Transparente) e, nos meses recentes, no `fim_de_mes` da coleta do dia. Quando o título de agora ainda não existia naquele fim de mês (de fevereiro a abril de 2020, com o título de 2026), desconta-se o pulo do dia de cada troca. A comparação no mesmo título muda 4 dos 274 meses do teste: janeiro a março de 2021 deixam de ser subindo, porque eram subindo por causa do pulo de 30/12/2020, e junho de 2021 passa a subindo. A folga (abaixo) compara o nível do juro de 10 anos de hoje com o de todos os meses desde 2005, e esse nível é o do título de cada época, que de 2010 a 2019 foi o de 2024, cada vez mais perto de vencer.

**5. A soma decide.** Pressões que pioraram menos as que melhoraram: 2 ou mais, **subindo**; −2 ou menos, **caindo**; no meio, **igual**. Pressão sem dado fica fora da soma naquele dia.

**6. Confirmação.** A direção só muda quando o resultado novo se repete no mês seguinte. No mês da primeira vez, a página avisa: "Pelos dados de hoje, a direção seria (...)".

**7. Encolhendo.** Se o IBC-Br (média de 3 meses contra os 3 anteriores) cair mais de 1,5%, o topo diz "A economia está encolhendo", no lugar da direção. A essa altura, a pergunta de para que lado anda o risco já perdeu o sentido.

**Meses passados e mês corrente.** Na linha do tempo e na conta do passado, cada mês usa o dado com o atraso típico de divulgação da série. No mês corrente, entra o último dado que já saiu, comparado com o de 3 meses antes dele: o dólar de ontem (com os 3 dias de persistência acima), a dívida de dois meses atrás. O Focus mensal vem da série guardada e, nos meses do site, da coleta de cada atualização.

**Quanto espaço ainda sobra (a `folga` do `data.json`).** Cada pressão (menos o dólar, cujo valor em reais não se compara entre décadas) e o emprego comparam o nível de hoje com todos os meses desde o começo da série: a dívida desde 2006, as dívidas das famílias desde 2005, o juro de 10 anos desde 2005, a inflação esperada desde 2001, o juro descontado da inflação esperada (Selic e Focus, pela fórmula de Fisher) desde 2002 e o desemprego desde 2012. As reservas em dólar também ficam sem folga, porque o valor em dólares de hoje não se compara com o de 2002.

| Onde está hoje | Palavra da folga (só no `data.json`) |
| --- | --- |
| O pior valor da série | Nenhuma |
| Pior que 90% dos meses ou mais | Quase nenhuma |
| Pior que 70% a 89% dos meses | Pouca |
| No meio | Média |
| Melhor que 70% dos meses ou mais, ou o melhor da série | Muita |

A palavra fica só no `data.json`; a página não a mostra, nem na linha fechada nem na aberta. Aberta, a linha diz só a frase da comparação, com os mesmos cortes: "A dívida está mais alta que em 96% dos meses desde 2006." No pior ou no melhor valor da série, a frase leva o sujeito da medida: "A parte da renda que vai para dívidas é a maior desde 2005, quando começa a série." Em Como funciona, a seção que explica a conta se chama "Quanto espaço ainda sobra?" (âncora `t-folga`).

A folga não entra na soma. Nível alto e parado não marca a data de recessão nenhuma (veja a pesquisa de 166 países, abaixo); a folga diz quanto espaço sobra se a pressão continuar piorando. Na inflação esperada, a página diz também se ela está acima do teto da meta (4,5%).

### O topo da página

Abaixo da placa vêm, nesta ordem, o crescimento em 12 meses, as cinco pressões e Também acompanhamos. Cada linha diz o que a medida fez em 3 meses (Piorou, Igual ou Melhorou, nas pressões, no emprego, na renda e nas reservas; a dívida em reais ainda não tem palavra) e, aberta, o vaivém normal e a frase da folga; nas linhas de Também acompanhamos, também por que ela importa (`direcao.por_que_importa` em `config/modelo.json`).

**Crescimento em 12 meses.** É o bloco logo abaixo da placa. O título tem à direita a palavra do bloco, no mesmo lugar e no mesmo estilo do Piorou de cada pressão. Os três números ficam lado a lado, do mesmo tamanho, cada um num bloco com os 12 meses que ele cobre embaixo, com o mês de início e o de fim abreviados ("set/25–ago/26"); a previsão fica num bloco só com contorno, e o bloco fecha com uma linha de fonte: a prévia do PIB e o Focus, os dois do Banco Central. A faixa normal e o erro do Focus continuam calculados (seção `ritmo` de `config/calibracao.json`) e ficam explicados em Como funciona. Os três números e os períodos saem de [`src/ritmo.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/ritmo.py):

| Linha | Conta | Hoje |
| --- | --- | --- |
| Os 12 meses até o último dado | IBC-Br dessazonalizado (BCB 24364): soma dos 12 meses até o último dado contra a soma dos 12 meses anteriores | 1,4%, de setembro de 2025 a agosto de 2026 |
| Um ano antes | A mesma conta, 12 meses antes | 3,5%, de setembro de 2024 a agosto de 2025 |
| Previsão | Mediana do Focus para o PIB do ano corrente e do seguinte, com peso pelos meses que faltam: ((12 − m) × ano corrente + m × ano seguinte) / 12, com m o mês do Focus (`indicadores.focus_pib`). Os pesos são os dos 12 meses do mês seguinte ao do Focus até o mesmo mês do ano seguinte, e é esse o período que a linha mostra (`ritmo.janela_previsao`) | 1,2%, de dezembro de 2026 a novembro de 2027 (Focus de 6/11/2026) |

- **A palavra do bloco** (Acelerando, Desacelerando ou No mesmo ritmo, à direita do título) compara agora e antes, os dois com uma casa, como a página mostra. Diferença de até 0,1 ponto é "no mesmo ritmo"; acima disso, "acelerando" ou "desacelerando". A palavra descreve e não é sinal: o crescimento do Brasil varia muito de um ano para o outro, e a direção não usa esta conta.
- **O normal** são os percentis 25 e 75 do crescimento em 12 meses desde 2004, hoje de 0,8% a 3,9% ao ano (`config/calibracao.json`, `ritmo.faixa`). Não aparece no bloco; Como funciona o explica.
- **A previsão só aparece na tela.** O PIB esperado pelo Focus não entra em conta nenhuma do site: nem na direção, nem no "encolhendo", nem na palavra do bloco. Como funciona diz quanto os bancos erram; o bloco, não. O erro médio absoluto da previsão de 12 meses do Focus contra o PIB que o IBGE divulgou depois, com a mesma ponderação dos anos (o PIB anual é a média do ano contra a do ano anterior), foi de 1,46 ponto em 252 meses, de janeiro de 2004 a dezembro de 2024. Só em 40% desses meses o erro ficou dentro de 1 ponto.
- **Quando a economia está encolhendo** (passo 7), o bloco ganha uma linha com a queda da prévia do PIB nos 3 últimos meses contra os 3 anteriores, que é a conta que decide o "encolhendo".

**Também acompanhamos.** Abaixo das cinco pressões, no mesmo desenho, ficam as quatro linhas da tabela do passo 1 que não mudam a placa. Aberta, cada uma diz numa frase por que não muda (`direcao.nao_muda_a_placa` em `config/modelo.json`). O emprego, a renda e as reservas em dólar dizem Piorou, Igual ou Melhorou, como as pressões, pela mesma regra de corte (passo 4); a renda piora quando cai. O emprego e a renda têm folga, contra todos os meses desde 2012. A dívida em reais mostra a parte da dívida pública federal em reais (96%, Tesouro, agosto de 2026), posta à mão todo mês, e ainda não diz o que ela fez em 3 meses.

## Por que esta regra

A regra foi escolhida por quatro critérios fixados antes de olhar o resultado por governo:

1. não ficar em subindo quase sempre (vira papel de parede);
2. não mudar toda hora;
3. deixar o PIB dos 12 meses seguintes em ordem: pior depois de subindo, melhor depois de caindo;
4. apontar subindo antes da recessão de 2014, a única feita em casa desde 2004.

**Por que a dívida, e não o resultado sem juros, nas contas do governo.** É a dívida que quem empresta ao governo olha, e ela inclui o custo dos juros. Hoje as duas andam em lados opostos: o resultado sem juros melhorou, e a dívida subiu porque os juros pesam mais que essa melhora. A página mostra as duas.

## Como a regra se saiu desde 2004

De janeiro de 2004 a outubro de 2026 (274 meses), com os atrasos de divulgação e a confirmação de um mês:

| Medida | Subindo | Igual | Caindo | Encolhendo |
| --- | --- | --- | --- | --- |
| Parte dos meses | 17% | 63% | 13% | 7% |
| PIB médio nos 12 meses seguintes | +0,4% | +2,1% | +4,3% | — |
| Meses com recessão começando no ano seguinte | 21% | 16% | 3% | — |

| Medida | Resultado |
| --- | --- |
| Mudanças de direção por ano | 1,9 |
| Chance de um mês com recessão à frente ter soma maior que um mês sem (0,5 é cara ou coroa) | 0,53 |
| Meses em subindo nos 12 antes de cada recessão | 2008: 0; 2014: 6; 2020: 0 |
| Parte dos meses em que cada pressão piorou / melhorou | contas 31% / 16%; dívidas das famílias 32% / 17%; desconfiança de quem investe 32% / 32%; inflação esperada 19% / 24%; juro 19% / 24% |

O que isso quer dizer, sem enfeite:

- **A regra separa anos fracos de anos fortes, mas não marca a data da recessão.** A soma quase não distingue um mês com recessão à frente de um sem (0,53). Com três recessões desde 2004, nenhuma regra simples passa disso.
- **Choques de fora passam batido no começo.** Em 2008, a regra ficou em igual até dezembro. Em abril de 2020, disse caindo, porque o juro e a inflação esperada caíram rápido; só em maio a prévia do PIB mostrou a queda e o topo passou a dizer "encolhendo".
- **A recessão de 2014, feita em casa, apareceu:** subindo de setembro de 2013 a fevereiro de 2014.
- **Os dados são os revisados de hoje**, e não os que saíram na época. A dívida é a série que menos muda; o PIB e o IBC-Br mudam mais.

**Por governo, só para conferência.** Nenhuma escolha da regra olhou esta tabela. A regra é a mesma para todos.

| Governo | Subindo | Igual | Caindo |
| --- | --- | --- | --- |
| Lula 1 e 2 (2004 a 2010) | 2% | 74% | 18% |
| Dilma (2011 a abril de 2016) | 27% | 55% | 5% |
| Temer (maio de 2016 a 2018) | 9% | 66% | 25% |
| Bolsonaro (2019 a 2022) | 21% | 62% | 4% |
| Lula 3 (2023 a outubro de 2026) | 33% | 52% | 15% |

O resto de cada linha é encolhendo. No governo atual, a mesma regra disse caindo em meados de 2023 e no começo de 2024, e subindo de agosto de 2024 a março de 2025 (com a Selic subindo e o dólar passando de R$ 6) e na maior parte de 2026.

## O que causa recessão

A aba [O que causa recessão](https://vaidarcrise.com.br/causas/) explica o caminho mais comum até a recessão para quem não é economista: por que os preços sobem, o juro alto como freio, a bola de neve das famílias endividadas, os casos de 2013 a 2016 e de 2021 e 2022, a bola de neve da dívida do governo e, no fim, um mapa que junta as partes. Ela não mostra dados do dia; os números com data ficam listados abaixo. Segue a seção "Como explicar um mecanismo" do [PERSONA.md](https://github.com/pedrojahara/vaidarcrise/blob/main/PERSONA.md). Nada dela entra na direção. As duas pesquisas abaixo sustentam o que a aba diz; os números delas ficam aqui, não na aba.

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
- O caminho é a dominância fiscal de Blanchard (2004), escrita sobre o Brasil: déficit subindo eleva a inflação esperada, e o Banco Central sobe o juro. O déficit subindo não avisa a recessão direto (0,48): age pela inflação esperada e pelo juro, que são duas das cinco pressões da direção.
- Juro americano e commodities, testados como quinta entrada da conta dos 44 países (apêndice), pioraram o erro fora da amostra em 12 meses: 5,1% e 5,8% no painel; 15,1% e 23,5% no Brasil.

**Números fixos da aba, com data.** Juros nominais do setor público em 12 meses até agosto de 2026: R$ 1,18 trilhão, 8,9% do PIB (Banco Central, estatísticas fiscais, pela imprensa); cerca de R$ 5.500 por brasileiro, com 213 milhões de habitantes. Resultado sem juros no mesmo período: 0,6% do PIB a mais de gasto que de receita (BCB 5793). Sobra sem juros que estabilizaria a dívida bruta: 2,1% do PIB por ano (IFI, Relatório de Acompanhamento Fiscal de agosto de 2026). Dívida federal em reais: 96% (Tesouro, agosto de 2026); não residentes têm cerca de 10% da dívida interna. IPCA de 2021: 10,06%, com gasolina em 47,5% e energia elétrica em 21,2% (IBGE), com o setor público arrecadando 0,7% do PIB a mais do que gastou, sem juros. Desemprego (PNAD): 6,2% em dezembro de 2013, 13,9% em março de 2017, 14,9% em março de 2021 e 7,9% em dezembro de 2022. Índice de commodities do FMI: caiu 49% de junho de 2014 a janeiro de 2016 e subiu 132% de junho de 2020 a junho de 2022. Resultado sem juros do setor público (BCB 5793): sobra de 1,7% do PIB em 2013 e falta de 1,9% em 2015; sobra de 0,7% em 2021 e de 1,3% em 2022. Dívida bruta (BCB 13762): de 51,5% do PIB em 2013 para 69,8% em 2016; de 86,9% em 2020 para 71,7% em 2022. A aba não diz "não houve recessão" em 2021 e 2022: a primeira divulgação do IBGE do terceiro trimestre de 2021 trouxe duas quedas pequenas seguidas (0,4% e 0,1%); diz que a economia cresceu nos dois anos, que é o que o PIB anual mostra. Títulos da dívida federal ligados à Selic: cerca de metade (51% em julho de 2026, Tesouro, pela imprensa). Parte da renda das famílias usada para pagar dívidas, com ajuste sazonal (BCB 29034): 29,0% em agosto de 2026, a maior desde o começo da série, em março de 2005; 22,8% na média de 2014.

**Onde a ligação com as contas do governo é forte e onde é fraca.** Procura acima da capacidade vira preço, e o Banco Central diz que, com a economia no limite, estímulo do governo vira mais inflação que crescimento (ata do Copom de dezembro de 2022). No Brasil, contas piorando vieram antes das altas da Selic (0,72, acima); nos 44 países, não (0,48). Nem toda inflação vem do gasto: 2021 é o contraexemplo. A bola de neve é aritmética (juro acima do crescimento e sem sobra, a dívida sobe); o círculo de volta para o juro, via dólar e inflação esperada, é o de Blanchard (2004), com força que varia com a confiança. Por isso a corrente da aba tem duas partes. A entrada (gasto acima da arrecadação vira preço) leva a condição "com a economia no limite": empréstimo, por si, não gera inflação, e com gente parada o mesmo gasto vira emprego. O círculo (passos 3 a 6) fecha pela desconfiança, não por mais gasto: pegar emprestado para pagar juros põe pouco dinheiro novo na economia, mas a dívida maior encarece o crédito ao governo, sobe o dólar e mantém o juro alto. Hoje os juros (8,9% do PIB) pesam quase 15 vezes mais que o gasto sem juros acima da arrecadação (0,6%), por isso a aba diz que o círculo gira pelos passos 3 a 6. Dívida alta não marcou a data das recessões em 166 países, por isso a aba não fala em espiral nem em prazo.

**Limites.** Um sinal por vez mostra o que vem antes, não o que causa, e dois sinais podem contar a mesma história. Nada disso passou por teste fora da amostra, exceto a quinta entrada da conta dos 44 países. O Brasil teve sete ciclos de alta desde 2002: a margem de erro é grande. No painel, dívida e déficit são anuais e chegam com 1 ano de atraso, o que enfraquece o fiscal ali.

## Apêndice: o PIB num ano ruim, pela conta de 44 países

A aba Como funciona mostra, no fim, um segundo número que não entra na direção: o **PIB num ano ruim** (no jargão, o cenário ruim, ou quantil 10%), o crescimento nos 12 meses seguintes que tem só 1 chance em 10 de ser pior. É o método do FMI chamado crescimento em risco (*growth-at-risk*; Adrian, Boyarchenko e Giannone, 2019). A conta fica em [`src/model.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/model.py) e [`src/calibra.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/calibra.py); o painel, em [`data/historico/painel_ocde.csv`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/painel_ocde.csv); o Brasil mês a mês, em [`data/historico/mensal.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/mensal.json).

**Quatro entradas do Brasil**, cada uma com o que já tinha sido divulgado no dia:

| Entrada | Definição |
| --- | --- |
| Crescimento contra um ano antes (3 meses) | IBC-Br dessazonalizado (BCB 24364): média dos 3 últimos meses contra os mesmos 3 meses um ano antes |
| Crescimento médio em 10 anos | Média do crescimento em 12 meses do PIB do IBGE nos 40 últimos trimestres divulgados |
| Selic: variação em 12 meses | Selic meta (BCB 432) de hoje menos a de um ano antes, em pontos |
| Inflação: variação em 12 meses | IPCA em 12 meses (BCB 13522) do último mês menos o de um ano antes, em pontos |

**A conta, tirada de 44 países.** Uma regressão de quantil (Koenker e Bassett, 1978) do crescimento do PIB nos 4 trimestres seguintes, no quantil 10%, num painel trimestral de 44 países (OCDE e grandes emergentes, Brasil incluído) com dados da OCDE: 4.669 trimestres, de 1995 a 2025. Com 4 recessões no Brasil desde 2002, uma conta só com o Brasil não teria dados para separar sinal de acaso.

```
ano ruim = −0,71 − 0,20 × média de 10 anos + 0,23 × crescimento em 12 meses
               − 0,15 × variação da Selic − 0,13 × variação da inflação − 1,31
```

- Crescimentos em 100 × log; no site, convertidos para variação %.
- **Juro subindo e inflação acelerando** pioram o ano ruim; **crescer forte hoje** melhora o ano seguinte; **crescimento médio alto** piora o ano ruim, porque vem junto com economias que oscilam mais.
- **O ajuste de −1,31** vem do teste fora da amostra: sem ele, 15% dos resultados ficaram abaixo do ano ruim, e não 10%.
- **Em tempos normais**, o mês típico do Brasil desde maio de 2004, o ano ruim é de −1,9%. A aba mostra os dois números lado a lado.

**Por que essas entradas.** Escolhidas fora da amostra no painel, pelo erro da regressão de quantil (perda *pinball*). Cada candidata foi somada às quatro e ficaria só se o erro de anos não vistos caísse 1% ou mais.

| Candidata | Erro fora da amostra |
| --- | --- |
| Bolsa (retorno real em 12 meses) | 4,6% menor |
| Crédito acima da tendência | 0,7% menor |
| Juro de 10 anos subindo | 0,3% menor |
| Dívida pública | igual |
| Câmbio real acima da média de 10 anos | 0,6% maior |
| Desemprego subindo | 0,9% maior |
| Hiato do produto | 2,7% maior |
| Câmbio (alta em 12 meses) | 2,9% maior |
| Curva de juros | 4,8% maior |

A bolsa passou no painel, mas não no Brasil: com o retorno real do Ibovespa em 12 meses (B3) como quinta entrada, o erro fora da amostra no Brasil subiu 3,9%.

**O teste fora da amostra.** No painel, cada ano de 2004 a 2026 foi previsto com coeficientes estimados só com os trimestres cujo PIB 4 trimestres à frente já tinha saído no começo daquele ano (3.625 trimestres). No Brasil, o mesmo, mês a mês, de maio de 2004 a hoje, com os atrasos de divulgação.

| Medida | Resultado |
| --- | --- |
| Erro da conta contra usar só o crescimento médio do país (painel) | 3% menor |
| Erro da conta contra usar só o crescimento médio do país (Brasil, 259 meses) | 20% menor |
| Resultados abaixo do ano ruim, sem ajuste (painel) | 15% |
| Resultados abaixo do ano ruim, com ajuste (Brasil, 259 meses) | 8% |
| Chance de um mês com recessão à frente ter ano ruim pior que um mês sem (Brasil, 220 meses; 0,5 é o acaso) | 0,60 |

O ganho é modesto e, como a direção, a conta não acerta a data em que cada recessão começa. Em 2008 e em 2020 ela não viu a recessão antes; a de 2014 apareceu cedo, desde meados de 2011. Por isso o número fica no fim de Como funciona, como segunda opinião, e não no topo.

## Fontes

- Adrian, Boyarchenko e Giannone (2019), *Vulnerable growth*, American Economic Review
- FMI (2017), *Financial conditions and growth at risk*, Global Financial Stability Report, outubro, capítulo 3
- Koenker e Bassett (1978), *Regression quantiles*, Econometrica
- [OCDE: PIB trimestral, juros e preços ao consumidor](https://data-explorer.oecd.org/)
- [B3: estatísticas do Ibovespa](https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm), para o teste da bolsa
- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- [Tesouro Direto: taxas dos títulos](https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto)
- [FMI, índice de preços de commodities, via FRED](https://fred.stlouisfed.org/series/PALLFNFINDEXM)
- Rousseeuw e Croux (1993), *Alternatives to the median absolute deviation*, Journal of the American Statistical Association, sobre a escala robusta
- Tesouro Nacional, Relatório Mensal da Dívida Pública Federal (agosto de 2026), para a parte da dívida federal em reais
- [Lei Complementar 179, de 2021](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp179.htm), autonomia do Banco Central, citada na linha do Juro
- [FMI, World Economic Outlook](https://www.imf.org/en/Publications/WEO), dívida bruta do governo da Argentina em 2001 e do Japão, citadas em Como funciona
- Mian, Sufi e Verner (2017), *Household debt and business cycles worldwide*, Quarterly Journal of Economics
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Blanchard (2004), *Fiscal dominance and inflation targeting: lessons from Brazil*, NBER Working Paper 10389
- Jordà, Schularick e Taylor (2013), *When credit bites back*, Journal of Money, Credit and Banking
- Romer e Romer (2018), *Why some times are different: macroeconomic policy and the aftermath of financial crises*, Economica
- Müller, Xu, Lehbib e Chen (2025), *The Global Macro Database*, NBER Working Paper 33714
