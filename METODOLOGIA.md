# Metodologia

A regra da direção está em [`src/direcao.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/direcao.py), com as escolhas fixas em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json) (seção `direcao`) e o que sai dos dados (o vaivém normal de cada medida e o teste desde 2004) em [`config/calibracao.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/calibracao.json) (seção `direcao`). As séries mensais do Brasil ficam em [`data/historico/series.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/series.json). `python src/direcao.py --calibrar AAAA-MM` refaz os cortes e o teste. Cada atualização grava o hash dos dois arquivos de regra.

## A pergunta

> Para que lado anda o risco de recessão no Brasil: as pressões que costumam vir antes de uma recessão estão apertando ou folgando?

- **Recessão técnica:** dois trimestres seguidos de queda do PIB dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre anterior, com uma casa decimal; 0,0% não é queda).
- **Recaídas:** quedas separadas por um só trimestre sem queda contam como uma recessão só. 2014–16 é um episódio, não três.
- **Recessões na série atual do IBGE:** 2T01–4T01, 1T03–2T03, 4T08–1T09, 2T14–4T16 e 1T20–2T20. Todas caem dentro de recessões datadas pelo [CODACE/FGV IBRE](https://portalibre.fgv.br/codace). 2021 não conta: na série revisada, a queda do 2T21 ficou isolada.
- **Direção, não previsão.** O site não diz se vai haver recessão nem quando. Diz se as pressões que costumam vir antes de uma recessão andaram para o lado ruim ou para o lado bom nos últimos 3 meses. A data de uma recessão não se prevê com segurança: nem os economistas profissionais acertam (An, Jalles e Loungani, 2018), e o teste abaixo mostra o mesmo para esta regra.

O nome do site fala em crise; a métrica é recessão técnica.

## A regra da direção

**1. Cinco pressões**, escolhidas pelo que a pesquisa da seção O que causa recessão, abaixo, mostra que vem antes de uma recessão: juro subindo, inflação esperada subindo, dívida das famílias subindo, dólar e juro longo subindo com desconfiança das contas do governo, e as contas do governo piorando.

| Pressão | Medida | Série | Lado ruim | Atraso de divulgação |
| --- | --- | --- | --- | --- |
| Contas do governo | Dívida bruta do governo geral, % do PIB | BCB 13762 (desde dezembro de 2006) | subir | 2 meses |
| Contas do governo, antes de 2007 | Resultado sem juros do setor público em 12 meses, % do PIB | BCB 5793 | gastar mais do que arrecada | 2 meses |
| Dívidas das famílias | Parte da renda das famílias que vai para parcelas e juros, com ajuste sazonal | BCB 29034 | subir | 3 meses |
| Dólar e juro longo | Dólar PTAX, variação % | BCB 1 | subir | 0 |
| Dólar e juro longo | Taxa real do Tesouro IPCA+ com vencimento mais perto de 10 anos | Tesouro Direto | subir | 0 |
| Inflação esperada | Mediana do Focus para o IPCA dos 12 meses seguintes | Focus | subir | 0 |
| Juro | Selic meta | BCB 432 | subir | 0 |

Fora da soma, a página mostra o **ritmo da economia** (IBC-Br dessazonalizado, BCB 24364: média dos 3 últimos meses contra a dos 3 anteriores; atraso de 2 meses) e o **emprego** (desocupação da PNAD, BCB 24369; atraso de 1 mês). Eles descrevem a economia de agora; o emprego é o último a piorar numa recessão.

**2. Cada medida contra 3 meses antes.** A mudança é a diferença em pontos (em % no dólar e na média do IBC-Br) entre o dado de referência e o de 3 meses antes dele.

**3. O vaivém normal de cada medida** é 1,4826 vezes o desvio absoluto mediano das mudanças de 3 meses desde janeiro de 2002, com o atraso de divulgação de cada série. É uma régua robusta: uma crise grande, como 2008 ou 2020, não a alarga. Nas contas do governo, a régua junta as mudanças da dívida (desde 2007) e as do resultado sem juros (antes), e o mesmo corte vale para as duas.

**4. Apertou, igual ou folgou.** A medida apertou se andou para o lado ruim mais que três quartos do vaivém normal (`corte_vaivem` = 0,75); folgou se andou isso para o lado bom; no resto, ficou igual. Os cortes de hoje:

| Medida | Vaivém normal em 3 meses | Corte (0,75 ×) |
| --- | --- | --- |
| Dívida do governo (régua das contas) | 1,26 ponto do PIB | 0,95 ponto |
| Parcelas das famílias | 0,50 ponto da renda | 0,38 ponto |
| Dólar | 6,4% | 4,8% |
| Juro de 10 anos | 0,58 ponto | 0,43 ponto |
| Inflação esperada | 0,42 ponto | 0,32 ponto |
| Selic | 1,11 ponto | 0,83 ponto |
| Ritmo da economia (fora da soma) | 1,19% | 0,89% |
| Emprego (fora da soma) | 0,74 ponto | 0,56 ponto |

Dólar e juro longo contam como uma pressão só: o sinal da soma dos dois lados (se um aperta e o outro folga, fica igual; se um aperta e o outro fica igual, apertou).

**5. A soma decide.** Pressões que apertaram menos as que folgaram: 2 ou mais, **subindo**; −2 ou menos, **caindo**; no meio, **igual**. Pressão sem dado fica fora da soma naquele dia.

**6. Confirmação.** A direção só muda quando o resultado novo se repete no mês seguinte. No mês da primeira vez, a página avisa: "Pelos dados de hoje, a direção seria (...)".

**7. Encolhendo.** Se o IBC-Br (média de 3 meses contra os 3 anteriores) cair mais de 1,5%, o topo diz "A economia está encolhendo", no lugar da direção. A essa altura, a pergunta de para que lado anda o risco já perdeu o sentido.

**Meses passados e mês corrente.** Na linha do tempo e no teste, cada mês usa o dado com o atraso típico de divulgação da série. No mês corrente, entra o último dado que já saiu, comparado com o de 3 meses antes dele: o dólar de ontem, a dívida de dois meses atrás. O Focus mensal vem da série guardada e, nos meses do site, da coleta de cada atualização.

**A folga.** Cada pressão (menos o dólar, cujo valor em reais não se compara entre décadas) e o emprego mostram o nível de hoje contra todos os meses desde o começo da série: a dívida desde 2006, as parcelas desde 2005, o juro de 10 anos desde 2005, a inflação esperada desde 2001, o juro descontado da inflação esperada (Selic e Focus, pela fórmula de Fisher) desde 2002 e o desemprego desde 2012.

| Onde está hoje | Folga |
| --- | --- |
| O pior valor da série | Nenhuma |
| Pior que 90% dos meses ou mais | Quase nenhuma |
| Pior que 70% a 89% dos meses | Pouca |
| No meio | Média |
| Melhor que 70% dos meses ou mais, ou o melhor da série | Muita |

A folga não entra na soma. Nível alto e parado não marca a data de recessão nenhuma (veja a pesquisa de 166 países, abaixo); a folga diz quanto espaço sobra se a pressão continuar apertando. Na inflação esperada, a página diz também se ela está acima do teto da meta (4,5%).

**O que segura.** Três fatos fixos, com fonte, que amortecem um susto sem mudar a direção: a dívida federal em reais (96%, Tesouro, agosto de 2026), as reservas em dólar do Banco Central e a autonomia do Banco Central (Lei Complementar 179, de 2021).

## Por que esta regra

A regra foi escolhida por quatro critérios fixados antes de olhar o resultado por governo:

1. não ficar em subindo quase sempre (vira papel de parede);
2. não mudar toda hora;
3. deixar o PIB dos 12 meses seguintes em ordem: pior depois de subindo, melhor depois de caindo;
4. apontar subindo antes da recessão de 2014, a única feita em casa desde 2004.

Foram umas 25 versões. As mais próximas:

| Versão | Meses em subindo | Mudanças por ano | PIB em 12 meses, depois de subindo e de caindo | Meses em subindo nos 12 antes de 2014 | Outubro de 2026 |
| --- | --- | --- | --- | --- | --- |
| **A escolhida** | 17% | 2,0 | +0,3% e +4,3% | 6 | Subindo |
| Corte de meio vaivém | 22% | 2,4 | +1,1% e +4,2% | 4 | Subindo |
| Corte de um vaivém inteiro | 11% | 1,6 | +0,1% e +3,9% | 0 | Igual |
| Vaivém pelo desvio padrão comum | 11% | 1,5 | −0,7% e +3,4% | 0 | Igual |
| Comparar com 6 meses antes | 19% | 1,4 | +1,1% e +4,5% | 6 | Igual |
| Basta uma pressão para subir | 43% | 2,1 | +0,8% e +3,6% | 11 | Subindo |
| Sem esperar o mês seguinte | 20% | 4,0 | +0,8% e +3,7% | 5 | Subindo |
| Contas com dívida e resultado sem juros juntos | 16% | 1,8 | +0,4% e +4,4% | 6 | Subindo |
| Inflação do mês (IPCA) em vez da esperada | 15% | 1,8 | −0,4% e +3,2% | 3 | Igual |
| Inflação do mês e esperada juntas | 17% | 1,8 | −0,4% e +3,5% | 6 | Subindo |
| Dólar e juro longo só com o dólar | 17% | 1,9 | −0,1% e +4,3% | 2 | Subindo |
| Sete partes, com ritmo e emprego na soma | 10% | 2,2 | −2,1% e +4,1% | 0 | Subindo |

- **Basta uma pressão** vira papel de parede. **Sem esperar o mês seguinte**, a direção muda 4 vezes por ano.
- **Corte de um vaivém inteiro** e **desvio padrão comum** ficam em igual em três de cada quatro meses e não viram nada antes de 2014.
- **Sete partes** parece melhor no PIB seguinte, mas porque o ritmo e o emprego descrevem a recessão que já chegou. Antes de 2014, ficou em igual o ano todo.
- **Comparar com 6 meses antes**, **contas juntas** e **inflação juntas** quase empatam com a escolhida; ficou a mais simples de explicar.
- **Por que a dívida, e não o resultado sem juros, nas contas do governo.** É a dívida que quem empresta ao governo olha, e ela inclui o custo dos juros. Hoje as duas andam em lados opostos: o resultado sem juros melhorou, e a dívida subiu porque os juros pesam mais que essa melhora. A página mostra as duas.

## O teste desde 2004

De janeiro de 2004 a outubro de 2026 (274 meses), com os atrasos de divulgação e a confirmação de um mês:

| Medida | Subindo | Igual | Caindo | Encolhendo |
| --- | --- | --- | --- | --- |
| Parte dos meses | 17% | 63% | 13% | 7% |
| PIB médio nos 12 meses seguintes | +0,3% | +2,1% | +4,3% | — |
| Meses com recessão começando no ano seguinte | 21% | 16% | 3% | — |

| Medida | Resultado |
| --- | --- |
| Mudanças de direção por ano | 2,0 |
| Chance de um mês com recessão à frente ter soma maior que um mês sem (0,5 é cara ou coroa) | 0,55 |
| Meses em subindo nos 12 antes de cada recessão | 2008: 0; 2014: 6; 2020: 0 |
| Parte dos meses em que cada pressão apertou / folgou | contas 31% / 16%; parcelas 32% / 17%; dólar e juro longo 30% / 34%; inflação esperada 18% / 23%; juro 19% / 24% |

O que isso quer dizer, sem enfeite:

- **A regra separa anos fracos de anos fortes, mas não marca a data da recessão.** A soma quase não distingue um mês com recessão à frente de um sem (0,55). Com três recessões desde 2004, nenhuma regra simples passa disso.
- **Choques de fora passam batido no começo.** Em 2008, a regra ficou em igual até dezembro. Em abril de 2020, disse caindo, porque o juro e a inflação esperada caíram rápido; só em maio a prévia do PIB mostrou a queda e o topo passou a dizer "encolhendo".
- **A recessão de 2014, feita em casa, apareceu:** subindo de setembro de 2013 a fevereiro de 2014.
- **Os dados são os revisados de hoje**, e não os que saíram na época. A dívida é a série que menos muda; o PIB e o IBC-Br mudam mais.

**Por governo, só para conferência.** Nenhuma escolha da regra olhou esta tabela. A regra é a mesma para todos.

| Governo | Subindo | Igual | Caindo |
| --- | --- | --- | --- |
| Lula 1 e 2 (2004 a 2010) | 2% | 73% | 19% |
| Dilma (2011 a abril de 2016) | 27% | 55% | 5% |
| Temer (maio de 2016 a 2018) | 9% | 66% | 25% |
| Bolsonaro (2019 a 2022) | 19% | 65% | 4% |
| Lula 3 (2023 a outubro de 2026) | 33% | 52% | 15% |

O resto de cada linha é encolhendo. No governo atual, a mesma regra disse caindo em meados de 2023 e no começo de 2024, e subindo de agosto de 2024 a março de 2025 (com a Selic subindo e o dólar passando de R$ 6) e na maior parte de 2026.

## As notícias

As notícias não mudam a direção. Se cada notícia somasse um pedaço, como os jornais publicam mais notícia ruim que boa, a direção tenderia a ficar sempre em subindo. Elas mostram, na caixa "Para onde as notícias empurram", para que lado cada assunto é empurrado.

**A leitura das manchetes.** As manchetes de oito jornais com linhas editoriais diferentes (Agência Brasil, Folha, Estadão, Valor, InfoMoney, Poder360, Gazeta do Povo e g1) são coletadas de hora em hora. Às 06h30, um modelo de linguagem (Claude, sem ferramentas, com saída em esquema JSON validado por código) lê as do dia anterior e transforma os fatos em eventos: assunto, lado, tamanho (1 a 3) e estágio. Notícia que só repete um dado já medido fica de fora. Os assuntos são sete: Ritmo da economia, Juro e inflação, Dívidas das famílias, Dólar e juro longo, Contas do governo, Emprego e Economia lá fora.

**A pressão do dia, por assunto:**

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
| Seta do assunto | saldo de 1 ou mais (pesa) ou de −1 ou menos (alivia) |
| Seta geral | soma dos assuntos, com corte de 2 |

**Fatos de dados.** Saem de código ([`src/dossie.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/dossie.py)), todo dia, comparando o dado de hoje com a série histórica ("o maior desde…"). O post os recebe como contexto.

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

A prévia de link (`docs/causas/og.png`) e as versões dos desenhos para a página saem de [`src/imagens_causas.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/imagens_causas.py), rodado à mão; a atualização diária não os refaz. Os desenhos foram gerados pelo modelo de imagem Gemini, do Google, a partir do roteiro da aba; os originais ficam em `assets/causas/`.

**Números fixos da aba, com data.** Juros nominais do setor público em 12 meses até agosto de 2026: R$ 1,18 trilhão, 8,9% do PIB (Banco Central, estatísticas fiscais, pela imprensa); cerca de R$ 5.500 por brasileiro, com 213 milhões de habitantes. Resultado sem juros no mesmo período: 0,6% do PIB a mais de gasto que de receita (BCB 5793). Sobra sem juros que estabilizaria a dívida bruta: 2,1% do PIB por ano (IFI, Relatório de Acompanhamento Fiscal de agosto de 2026). Dívida federal em reais: 96% (Tesouro, agosto de 2026); não residentes têm cerca de 10% da dívida interna. IPCA de 2021: 10,06%, com gasolina em 47,5% e energia elétrica em 21,2% (IBGE), com o setor público arrecadando 0,7% do PIB a mais do que gastou, sem juros. Desemprego (PNAD): 6,2% em dezembro de 2013, 13,9% em março de 2017, 14,9% em março de 2021 e 7,9% em dezembro de 2022. Índice de commodities do FMI: caiu 49% de junho de 2014 a janeiro de 2016 e subiu 132% de junho de 2020 a junho de 2022. Resultado sem juros do setor público (BCB 5793): sobra de 1,7% do PIB em 2013 e falta de 1,9% em 2015; sobra de 0,7% em 2021 e de 1,3% em 2022. Dívida bruta (BCB 13762): de 51,5% do PIB em 2013 para 69,8% em 2016; de 86,9% em 2020 para 71,7% em 2022. A aba não diz "não houve recessão" em 2021 e 2022: a primeira divulgação do IBGE do terceiro trimestre de 2021 trouxe duas quedas pequenas seguidas (0,4% e 0,1%); diz que a economia cresceu nos dois anos, que é o que o PIB anual mostra. Títulos da dívida federal ligados à Selic: cerca de metade (51% em julho de 2026, Tesouro, pela imprensa). Parte da renda das famílias usada para pagar dívidas, com ajuste sazonal (BCB 29034): 29,0% em agosto de 2026, a maior desde o começo da série, em março de 2005; 22,8% na média de 2014.

**Onde a ligação com as contas do governo é forte e onde é fraca.** Procura acima da capacidade vira preço, e o Banco Central diz que, com a economia no limite, estímulo do governo vira mais inflação que crescimento (ata do Copom de dezembro de 2022). No Brasil, contas piorando vieram antes das altas da Selic (0,72, acima); nos 44 países, não (0,48). Nem toda inflação vem do gasto: 2021 é o contraexemplo. A bola de neve é aritmética (juro acima do crescimento e sem sobra, a dívida sobe); o círculo de volta para o juro, via dólar e inflação esperada, é o de Blanchard (2004), com força que varia com a confiança. Por isso a corrente da aba tem duas partes. A entrada (gasto acima da arrecadação vira preço) leva a condição "com a economia no limite": empréstimo, por si, não gera inflação, e com gente parada o mesmo gasto vira emprego. O círculo (passos 3 a 6) fecha pela desconfiança, não por mais gasto: pegar emprestado para pagar juros põe pouco dinheiro novo na economia, mas a dívida maior encarece o crédito ao governo, sobe o dólar e mantém o juro alto. Hoje os juros (8,9% do PIB) pesam quase 15 vezes mais que o gasto sem juros acima da arrecadação (0,6%), por isso a aba diz que o círculo gira pelos passos 3 a 6. Dívida alta não marcou a data das recessões em 166 países, por isso a aba não fala em espiral nem em prazo.

**Limites.** Um sinal por vez mostra o que vem antes, não o que causa, e dois sinais podem contar a mesma história. Nada disso passou por teste fora da amostra, exceto a quinta entrada da conta dos 44 países. O Brasil teve sete ciclos de alta desde 2002: a margem de erro é grande. No painel, dívida e déficit são anuais e chegam com 1 ano de atraso, o que enfraquece o fiscal ali.

## Os posts

É um post por dia, escrito na mesma atualização das 06h30, e o tipo muda com o dia ([`PERSONA.md`](https://github.com/pedrojahara/vaidarcrise/blob/main/PERSONA.md), "Os tipos de post"):

| Tipo | Quando | O que recebe | Tamanho |
| --- | --- | --- | --- |
| Fato do dia | Segunda a sábado | As notícias da véspera por assunto, os fatos de dados dos assuntos com notícia, as cinco pressões com as frases do topo e, se a direção mudou ou uma pressão mudou de lado, a mudança | Até 100 palavras |
| A semana | Domingo, com atualizações em pelo menos 4 dos 6 dias anteriores | As atualizações de segunda a domingo: a direção em cada dia, as pressões que mudaram de lado, os dados novos, as notícias somadas por assunto (mesma conta da pressão do dia) e as datas da semana seguinte | Até 250 palavras |
| O mês | Primeiro domingo do mês, no lugar da semana, se as atualizações do mês anterior começaram até o dia 8 e cobrem pelo menos 15 dias dele | As atualizações do mês anterior e dos primeiros dias deste, mais duas tabelas feitas por código: cada pressão no começo e no fim do mês, e o bolso (emprego, preços, parcelas e dólar) | Até 300 palavras de texto; com as tabelas, cerca de 450 |
| Retrato do Brasil | Fixo no topo, escrito à mão em `editor/` | Por que o site nasceu e como usar, sem números do dia | Até 800 palavras |

Sem atualizações bastantes, a semana e o mês viram fato do dia. A semana e o mês saem dos registros em `runs/`, nunca dos posts anteriores. Cada post recebe o anterior do mesmo tipo só para não copiar frases dele.

O modelo de linguagem recebe os fatos prontos e só redige. Ele não muda a direção nem a pressão das notícias. Um verificador em código ([`src/revisa_texto.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/revisa_texto.py)) procura moldes de texto automático, jargão, risco de recessão em porcentagem, previsão de recessão e explicações de método. Nos posts, também confere: número ou data que não está nos dados que o modelo recebeu (com a folga do arredondamento), texto acima do tamanho do tipo, fato do dia que repete a direção sem mudança, data futura no fato do dia (as datas ficam na lateral) e frase copiada do post anterior do mesmo tipo. Qualquer problema pede uma reescrita, no máximo uma. Número fora dos dados, risco em porcentagem, previsão de recessão ou mais de uma frase sobre a conta, se sobrarem, barram o texto, e sai a atualização sem texto corrido.

Cada atualização guarda o prompt (hash), o modelo usado, a resposta bruta e a direção do dia em [`runs/`](https://github.com/pedrojahara/vaidarcrise/tree/main/runs). Depois do lançamento oficial do site, o que foi publicado fica congelado. Antes dele, os textos e os registros antigos acompanham as mudanças do site, com os mesmos números e datas.

## Salvaguardas

- **Números velhos:** se a página passar de 36 horas sem atualização, ela avisa.
- **Falha de coleta:** cada fonte tem até 4 tentativas, e a série do Banco Central que falha tenta de novo no fim. O desemprego tem uma segunda fonte, o próprio IBGE. Se ainda faltar, vale o último valor guardado enquanto ele for o mais novo que a fonte deveria ter: 10 dias para dado diário, 200 para o PIB trimestral e, para dado mensal, até 15 dias depois do mês em que o seguinte deveria sair (pela defasagem de cada série). Exemplo: o desemprego do trimestre até agosto vale até 15 de novembro. O registro da atualização marca o valor reaproveitado. Pressão sem dado fica fora da soma e aparece como "Sem dado".
- **Falha do modelo de linguagem:** a atualização sai só com dados e sem pressão de notícias.
- **Texto das notícias:** é tratado como dado, nunca como instrução. Nenhuma notícia muda regras nem a direção.

## O que ainda falta

- Refazer o teste com os dados como eram divulgados na época (com revisões).
- Testar a direção em outros países com as mesmas cinco pressões, para ver se a ordem do PIB seguinte se repete fora do Brasil.
- Teste de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Pôr o valor das reservas em dólar em "O que segura", com a série do Banco Central.

## Apêndice: o PIB num ano ruim, pela conta de 44 países

A aba Como funciona mostra, no fim, um segundo número que não entra na direção: o **PIB num ano ruim** (no jargão, o cenário ruim, ou quantil 10%), o crescimento nos 12 meses seguintes que tem só 1 chance em 10 de ser pior. É o método do FMI chamado crescimento em risco (*growth-at-risk*; Adrian, Boyarchenko e Giannone, 2019). A conta fica em [`src/model.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/model.py) e [`src/calibra.py`](https://github.com/pedrojahara/vaidarcrise/blob/main/src/calibra.py); o painel, em [`data/historico/painel_ocde.csv`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/painel_ocde.csv); o Brasil mês a mês, em [`data/historico/mensal.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/data/historico/mensal.json).

**Quatro entradas do Brasil**, cada uma com o que já tinha sido divulgado no dia:

| Entrada | Definição |
| --- | --- |
| Crescimento em 12 meses | IBC-Br dessazonalizado (BCB 24364): média dos 3 últimos meses contra os mesmos 3 meses um ano antes |
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
| Juro longo subindo | 0,3% menor |
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
- Rousseeuw e Croux (1993), *Alternatives to the median absolute deviation*, Journal of the American Statistical Association, sobre a régua robusta do vaivém
- Tesouro Nacional, Relatório Mensal da Dívida Pública Federal (agosto de 2026), para a parte da dívida federal em reais
- [Lei Complementar 179, de 2021](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp179.htm), autonomia do Banco Central
- [FMI, World Economic Outlook](https://www.imf.org/en/Publications/WEO), dívida bruta do governo da Argentina em 2001 e do Japão, citadas em Como funciona
- Mian, Sufi e Verner (2017), *Household debt and business cycles worldwide*, Quarterly Journal of Economics
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Blanchard (2004), *Fiscal dominance and inflation targeting: lessons from Brazil*, NBER Working Paper 10389
- Jordà, Schularick e Taylor (2013), *When credit bites back*, Journal of Money, Credit and Banking
- Romer e Romer (2018), *Why some times are different: macroeconomic policy and the aftermath of financial crises*, Economica
- Müller, Xu, Lehbib e Chen (2025), *The Global Macro Database*, NBER Working Paper 33714
