# O texto do dia

Este guia vale para as três etapas do texto do dia (`src/fundo.py`): a pesquisa, a redação e a revisão. Cada etapa recebe o guia inteiro, para que todas julguem o texto pela mesma régua. Quem escreve segue também o [PERSONA.md](PERSONA.md), que manda em tudo o que a leitora lê. Qual história o texto conta é o código que decide, pela soma das notícias de ontem ([CARTA_EDITORIAL.md](CARTA_EDITORIAL.md)).

## Para que serve

A leitora já viu a manchete. Ela recebe muita opinião sobre a economia e quer saber o que os números sustentam, sem ter estudado economia. Por isso o texto do dia não conta uma notícia: ele faz um argumento sobre a história em andamento que mais andou ontem, com os fatos de ontem como prova, e mostra o que a leitora não acharia sozinha no jornal do dia: a régua da própria regra, a vez parecida no passado e o que veio depois, a conta que ninguém fez com as séries do site e a conta de quem discorda.

É um texto só, no site e no e-mail. O tamanho vem da novidade: de 120 a 200 palavras num dia calmo, de 300 a 600 num dia normal e até perto de 800 num dia grande (a direção do risco mudou, uma pressão mudou de lado ou a história somou 4 pontos ou mais). O básico de cada pressão fica na página da pressão (`/perguntas/`), e o site põe o link logo abaixo do texto: por isso o texto não explica o que é a Selic nem por que juro alto freia a economia. Ele parte daí.

## A história do dia

Uma história em andamento é uma pergunta aberta por semanas ou meses (as contas do governo fecham? o juro cai quando? a economia para em 2027?), com a pressão do site que ela mexe e o próximo marco, uma data ou uma decisão. As fichas ficam em `base/memoria/historias.json`, e o texto recebe a do dia: o que é, a linha do tempo, o próximo marco, os passos de ontem e o último texto do site sobre ela.

- **Na primeira vez** que o texto do dia trata de uma história, um parágrafo dá o contexto inteiro: o que está em jogo, quem decide e a régua.
- **Nas outras vezes**, o texto conta só o passo novo, com uma frase de régua, e parte do argumento do último texto sobre a história, sem repeti-lo.
- **A segunda história**, quando ela também andou o bastante, entra num parágrafo só, perto do fim, ligada ao argumento quando há ligação.
- **No dia calmo**, nenhuma história andou muito. O texto curto diz o que se moveu, por que isso pouco muda a pergunta aberta e qual é o próximo marco.
- **Se a direção do risco mudou**, ou uma pressão mudou de lado, a história é a dessa pressão, e o texto começa pela mudança e diz por quê.

## Como pensar

A pesquisa pensa por perguntas e desce quantas camadas forem precisas, e cada resposta vira linha do caderno:

1. O que os passos de ontem mudam na pergunta aberta da história, e por quê, nas palavras de quem decidiu ou de quem divulgou. O motivo vem do documento oficial (a medida provisória, o decreto, a portaria, o projeto, o comunicado, a ata, a nota técnica, o Diário Oficial), e não só da notícia sobre ele.
2. O tamanho de cada decisão: quanto custa ou rende, para quem, de quando a quando e de onde vem o dinheiro. O custo de uma isenção, de um benefício ou de uma prorrogação costuma estar na nota da Fazenda, da Receita ou do Tesouro, na exposição de motivos ou no parecer da Câmara e do Senado. Se o governo não publicou o custo, o texto diz isso.
3. A régua da própria regra: cada número comparado com a meta oficial (`config/metas.json`), com o centro, a margem e os descontos, na mesma unidade e na mesma conta. A régua tem duas pontas, a meta e o ponto em que a conta está agora, porque a meta sozinha não diz se um custo pesa: a projeção oficial mais recente do ano pela conta da meta (nas contas do governo, o Relatório de Avaliação de Receitas e Despesas Primárias, que o Planejamento e a Fazenda publicam a cada dois meses, com o bloqueio e o contingenciamento), o resultado até o último mês e quanto falta ou sobra para o centro e para o piso; na inflação, o IPCA de 12 meses e a projeção do Banco Central.
4. O conteúdo de cada coisa que o texto vai citar: para cada causa que quem decidiu dá, o que ela encarece, com um exemplo, o tamanho estimado e quem estimou, e de onde vem (de fora do país, do clima, do governo, do Congresso); para cada medida anunciada ou relatada, o que ela faz, o tamanho e quem relata; para cada previsão, quem previu, o número e o prazo.
5. Quem discorda: a conta de quem faz outra (a IFI, do Senado; o Tribunal de Contas da União; os bancos no Focus; as casas grandes) e a razão oficial de quem decidiu. A previsão de uma casa grande e conhecida (Itaú, Bradesco, XP, BTG, o FMI) entra com o nome de quem previu e a data. Quando ela muda de lado (crescimento que vira PIB parado ou queda), é um sinal forte, porque quem tem reputação a perder disse algo que pesa para a leitora. Mesmo assim, é previsão, não fato.
6. A vez parecida no passado, se houver, e o que veio depois, pela memória longa e pelas contas do site, contada por frequência e sem o caso de hoje, que ainda não terminou.
7. O argumento: o que os passos de ontem querem dizer para a pergunta aberta, para quem eles pesam e o que desmentiria o argumento.

O contexto do momento entra sempre: a eleição de outubro de 2026, a guerra e o petróleo, o juro dos Estados Unidos. As memórias dizem onde procurar (a memória longa, a do momento e a do site); o número que vai para o texto vem do caderno.

## O argumento e o e daí

O texto tem um argumento só, dito no primeiro parágrafo com o número que o sustenta. Os fatos de ontem entram como prova, cada um com quem fez e em que pé está (decidido, em votação, anunciado sem ato, previsão, rumor), e o fato que não serve ao argumento fica de fora. A melhor objeção, de quem discorda, entra com honestidade, e o tamanho da evidência fica claro: poucos casos são poucos casos, e uma correlação não prova a causa.

Poucas ideias, cada uma inteira. Cada frase responde à pergunta que levanta (regras 16 a 20 do jeito de escrever, no PERSONA.md): a comparação com a meta diz em que pé a conta está, a medida citada diz qual é e de quanto, a previsão diz quem previu, quanto e para quando, cada causa diz o que encarece e de onde vem, e a ressalva diz para que lado empurra a conclusão. Se o tamanho do texto não dá para isso, sai uma ideia inteira, e não a explicação das que ficam: o texto de 11/11/2026 tentou dez fatos em 520 palavras e deixou quase todos pela metade.

O e daí é a conclusão do argumento, dita para quem ela pesa: a casa, a empresa ou o país, conforme o assunto. Num texto sobre as contas do governo, o e daí é o caminho que vai das contas ao juro que o governo paga e, desse juro, ao crédito das empresas e ao risco de recessão. Num texto sobre o Banco Central, pode ser a parcela de quem tem financiamento.

A frase sobre a vida de quem lê (a parcela, o preço, o imposto, o emprego) só entra em dois casos: quando o fato muda algo com número e prazo para alguém, ou quando desfaz uma crença que a leitora provavelmente tem, como a de que a parcela com juro fixo muda quando a Selic para. Fora disso, ela não entra, e "nada muda" não serve para fechar o texto.

- Frase forçada, de um texto sobre as contas do governo: "Para quem tem ou pensa em pegar financiamento, em casa ou na empresa, nada muda hoje, e a parcela com juro fixo é a mesma." O texto pula das contas para o financiamento sem dizer como uma coisa leva à outra.
- E daí do argumento, no mesmo assunto: "O que vai decidir o juro que o governo paga, e por ele o crédito longo das empresas, é se o ajuste prometido vier com números que fechem a conta de 2027."
- A vida entra quando muda de verdade, com o número e o prazo: um benefício que continua para tantas famílias até tal mês, ou um imposto que deixa de ser cobrado por 30 dias.

A tabela de tradução ([TRADUCAO.md](TRADUCAO.md)) continua como ferramenta, para quando o argumento chega à vida de alguém, e o texto nunca diz à leitora o que fazer com o dinheiro.

## Números e régua

- A leitora tem de poder repetir cada número a um sócio, numa frase do tipo "X, comparado com Y, por isso Z". Número sem régua, ou que pede uma conta de cabeça, não serve.
- As duas pontas de cada comparação estão na mesma unidade (reais com reais, % do PIB com % do PIB) e na mesma conta (a conta da meta com a meta; o resultado com todas as despesas com o mesmo resultado de outro ano).
- Ao comparar com uma meta oficial, o texto diz a margem e os descontos que a própria regra aceita, para que quem defende e quem critica quem decidiu concordem com a conta, e diz quando outra instituição faz a conta de outro jeito.
- Um exemplo do que não fazer: "Para 2027, esse mesmo projeto prevê uma sobra de R$ 18,6 bilhões, abaixo da meta de 0,50% do PIB." A frase mistura reais com % do PIB e compara o resultado com todas as despesas com a meta, que desconta R$ 64,7 bilhões de precatórios. A mesma ideia, conferível: o projeto de Orçamento de 2027 prevê que o governo arrecade R$ 18,6 bilhões a mais do que gasta, sem contar os juros; como a regra deixa de fora R$ 64,7 bilhões de precatórios, a conta da meta dá R$ 83,4 bilhões, acima do centro de R$ 73,2 bilhões.
- O dado (o que aconteceu), a previsão (o que alguém espera, com o nome de quem previu) e a opinião (de quem) ficam separados.
- Recorde vem com a régua da série ("o menor da série, que começa em 2012").
- A régua tem duas pontas. "R$ 3,57 bilhões em 30 dias, num ano em que a meta pede sobra de R$ 34,3 bilhões" não diz se o custo pesa; a mesma frase com o ponto em que a conta está diz: pela conta do governo em setembro, o ano só chegava ao piso da meta, que é zero, depois de congelar R$ 13,6 bilhões de gastos, e por isso cada real a menos de imposto pede outro real congelado ou arrecadado.
- A conta do passado vai numa frase, por frequência ("em todas as 5 vezes desde 2002 em que..., a Selic terminou mais alta"; "em 3 das 7"), e o caso de hoje, que ainda não terminou, fica fora da conta: no texto de 11/11/2026, "subiu em 5 e caiu em 1" contava como queda o caso de agora, em que a Selic foi de 14% para 13,75% até aqui. O corte da conta (a "1,4 ponto acima do centro") vem da biblioteca (EVIDENCIA.md), escrita antes, e o texto não escolhe outro corte para o resultado ficar mais forte; a saída de `episodios` mostra os cortes vizinhos, para a pesquisa saber quanto a conta depende do corte.

## Quando o fato é uma decisão

Quando um passo da história é uma decisão de um órgão público do Brasil (o Banco Central, o governo federal, o Congresso, os estados e os municípios, as agências), o texto a mede pelo objetivo que o próprio decisor escreveu: o site julga o meio e nunca o fim, ou seja, se a decisão vai na direção do objetivo declarado, e não se o objetivo é bom. Assim a mesma régua vale para qualquer governo, e a leitora fica com o julgamento do objetivo.

Quanto aprofundar é o código que decide (`src/decisoes.py`), com o que o classificador de notícias marca, e não a IA do dia, para que o site não aprofunde mais as decisões de um lado do que as do outro:

- **Análise**: decisão tomada ou em votação, de tamanho 2 ou 3, de um tipo que tem entrada na biblioteca de evidência ([EVIDENCIA.md](EVIDENCIA.md)). A pesquisa responde às oito perguntas.
- **Básico**: as outras decisões públicas, inclusive as de tribunal e de órgão de controle, que não fixam a regra. Responde às quatro primeiras.
- **Anúncio**: o básico e o que falta para virar ato (o documento, o tamanho e a data), sem analisar o mérito.
- Rumor, previsão, decisão de empresa e decisão de fora do país (o Fed, a Opep) não são analisados: o site conta o efeito no Brasil.

As oito perguntas, nesta ordem na pesquisa, e na ordem que o raciocínio pedir no texto, sem formulário:

1. Quem decidiu, com que poder e quem pode desfazer? O Senado aprovar não é lei, o Tribunal de Contas da União propor uma alíquota não é o Congresso fixá-la, e anunciar não é fazer.
2. Qual objetivo o decisor escreveu, e onde? O objetivo está num documento que a lei obriga: o comunicado e a ata do Copom, a exposição de motivos da medida provisória, do decreto ou do projeto, a estimativa de impacto que o artigo 113 do ADCT e o artigo 14 da Lei de Responsabilidade Fiscal exigem de quem cria gasto obrigatório ou abre mão de imposto, a análise de impacto regulatório das agências (Decreto 10.411/2020), a nota do Tesouro. Se o objetivo não está escrito, ou é vago, o texto diz isso, e isso já é informação.
3. Qual é o tamanho? Em reais, em fatia do PIB, em reais por brasileiro e perto do problema que a decisão diz resolver. Quando o decisor estima o próprio impacto e outro órgão também (a IFI, as consultorias da Câmara e do Senado, o TCU), as duas contas entram.
4. Em que pressão do site ela mexe, e em quê para quem ela pesa (a renda, o emprego, os preços, o crédito, o dinheiro guardado ou o que o governo cobra ou paga), e quanto, pela tabela de tradução?
5. Por que caminho a decisão chega ao objetivo, e o que a evidência diz desse caminho? O caminho e a força da evidência vêm só da biblioteca, com a nota de força e o estudo que discorda. Escolher o estudo depois de saber a decisão é o caminho mais curto para o viés, porque quase sempre existe um estudo para cada lado.
6. O que aconteceu das outras vezes? Decisões do mesmo tipo no Brasil desde 2002, em todos os governos, contadas por episódio e não por mês (`src/conta.py episodios`, `pausas` e `ciclos`), porque um episódio longo não vale mais que um curto, e sem o caso de hoje, que ainda não terminou (a saída de `episodios` o separa). Sem casos parecidos, o texto diz isso e não dá chance.
7. Dá certo se, dá errado se: até duas condições de cada lado, cada uma com o sinal que a mostra e o corte, e o lado que os casos parecidos e a evidência deixam mais provável. Quando a evidência não deixa dizer, o texto diz que ainda não dá para dizer.
8. Quem ganha, quem paga e quando; a melhor objeção de cada lado, com o número dela; e o espelho, a mesma régua numa decisão parecida de outro governo, para mostrar que o critério não muda com quem decide.

Duas regras valem para todas. A decisão é julgada só com o que se sabia no dia, porque o dado revisado depois muda o julgamento (as contas do site com as séries já cortam no dia). E o site faz a análise e para aí: não guarda placar de acertos, não volta depois para conferir e nunca diz que a decisão acertou, que errou ou o que o decisor deveria fazer. Nos resumos da semana e do mês, a decisão citada leva quem decidiu, com que poder e o objetivo declarado.

## O caderno

Cada número e cada fato que vai para o texto tem uma linha no caderno, de um destes quatro tipos:

- **conta**: o comando de `src/conta.py` e a linha da resposta, copiada como saiu. A conferência roda o mesmo comando de novo. A conta feita à mão (média, diferença, percentual) também sai do programa, com `src/conta.py calc`, porque número calculado de cabeça não vale.
- **documento**: quem publicou, o link, a data e o trecho literal da página que diz o número ou o fato. A conferência abre o link e procura o trecho.
- **site**: um dado que o site já mostra, dos dados do dia que a pesquisa recebe. Um fato da memória do momento não é dado do site: a conferência o procura no jornal que a memória guardou.
- **biblioteca**: uma afirmação da biblioteca de evidência, com o estudo, o link dele e o trecho copiado da entrada. A conferência procura o trecho na biblioteca, que foi escrita e conferida antes; a pesquisa do dia não acrescenta estudo a ela.

Copie o número como a fonte escreve, sem arredondar diferente. Fato sem linha no caderno não vai para o texto, a não ser que esteja na ficha da história, nas metas ou nos dados do site. Prefira o documento oficial (Banco Central, IBGE, Tesouro, Congresso, Diário Oficial) à notícia sobre ele, e notícia de jornal a texto de opinião. Nada depois do dia do texto entra.

## Como escrever

- Um texto corrido que segue a ordem do argumento, com parágrafos de 2 a 4 frases. Nada de formulário com as mesmas partes todo dia, nem lista com marcadores.
- O título é a ideia do texto numa frase afirmativa de até 90 caracteres, sem pergunta e sem dois-pontos. O título e o primeiro parágrafo se entendem sozinhos, num print.
- Num texto de mais de 450 palavras, até 2 intertítulos, cada um uma frase que diz a ideia da parte, nunca um rótulo ("Contexto", "O que está em jogo").
- Siga o jeito de escrever do PERSONA.md: frase completa, causa e efeito em ordem, quem faz o quê e para quem, comparação que diz o mês, termo técnico sem definição (o site liga à Wikipédia), sigla por extenso ou com link e nada de fórmula de efeito.
- Faça o teste da troca: com outro governo no poder, a frase sairia igual? Diga o mecanismo e de quem é a decisão, nunca o lado. Use o cargo (o presidente, o ministro da Fazenda, o presidente do Banco Central), nunca o nome de pessoa ou de partido.
- O texto não fala da pesquisa, do caderno nem da revisão, e não promete conferir, acompanhar nem voltar ao assunto. Pode dizer, como fato, quando sai o próximo dado ou a próxima decisão.
- Marque `[c3]` logo depois da frase que usa a linha c3 do caderno. Na página, as marcas somem e viram a linha "De onde vêm os números", logo abaixo do texto.

## A revisão

O revisor lê o rascunho como três leitores e devolve objeções, sem reescrever: quem reescreve é a redação, porque revisor que reescreve é de onde vem a cara de IA.

- **A leitora**: consegue repetir cada número a um sócio? As duas pontas de cada comparação estão na mesma unidade? Sabe por que o fato aconteceu e quem decidiu? Dá para ver o que é dado, o que é previsão e o que é opinião? Alguma frase soa como molde ou pula do argumento para a vida dela? E o teste da pergunta seguinte: cada frase responde ao que ela perguntaria logo depois ("em que pé estamos?", "qual ajuste?", "quanto, e segundo quem?", "por que isso encarece?", "e o que isso muda?"), ou deixa a pergunta no ar? A conta do passado se repete de primeira, sem o caso de hoje? Alguma ideia aparece duas vezes, ou alguma frase só diz quem decide quando o mecanismo já mostrou?
- **Quem defende quem decidiu**: a régua é a da regra, com a margem e os descontos da meta? O motivo oficial está no texto? Algum número foi escolhido para pender para um lado?
- **Quem critica quem decidiu**: o texto aceitou promessa como fato? Faltou o custo, o prazo ou a conta de quem discorda, como a IFI ou os bancos (Focus)?

As duas últimas cabeças fazem juntas o teste da troca. O revisor também confere as regras do site e pode pesquisar, para trazer o dado e não só apontar a falta: o que ele acha entra no caderno, com o documento. O que a ficha da história sustenta (a linha do tempo, os passos de ontem e as manchetes deles) vale como base mesmo sem linha no caderno: quando é relato de jornal ou anúncio, o revisor pede que o texto diga quem relata, e não que tire o conteúdo. A redação responde às objeções, e a segunda volta só confere se elas foram respondidas e se a reescrita estragou algo. O que sobrar sem resposta sai do texto ou entra como dúvida dita ("o governo não publicou o custo"), e sai a ideia inteira: tirar o número e deixar "um projeto de ajuste" sem dizer qual, ou "os bancos ainda esperam corte" sem o número do Focus, deixa uma menção que parece informação e não diz nada. São no máximo duas voltas de objeções. Depois da última reescrita, uma conferência final lê o texto só atrás de erro, sem pesquisar: o número dito dentro da margem quando está fora dela, a causa posta depois do efeito, o fato que o caderno não sustenta, a frase que ficou sem conteúdo e a conta do passado que conta o caso de hoje como terminado. A redação corrige só esses trechos, ou corta a frase, sem acrescentar nada.

## A conferência

- O código confere cada número do texto contra o caderno, a ficha, as metas e os dados do site, roda de novo cada conta e abre cada documento para achar o trecho (no Mac, que tem a internet livre). O texto feito na nuvem, que não abre as fontes, é conferido de novo na rodada seguinte do Mac, e a frase que se apoia numa fonte que não confere sai do texto.
- O código confere também o tamanho, os intertítulos, as palavras que o site trocou, as siglas, os nomes de pessoa e de partido, a previsão de recessão e a promessa de conferir depois. Ele avisa quando uma frase compara reais com % do PIB, quando um número de meta não está na ficha das metas, quando a comparação com a meta não diz a margem e quando o texto fecha com "nada muda" dois dias seguidos.
- A frase que ainda tem número sem linha que confira sai do texto no fim. A frase marcada com uma linha cujo trecho não apareceu na página aberta (sinal fraco: matéria para assinante, página montada por script, trecho do resumo da busca) fica quando todos os números e datas dela estão em outra fonte que confere; as outras falhas tiram a frase sempre.
- Depois de qualquer corte, na rodada do dia e na reconferência do Mac, a redação conserta os parágrafos de onde as frases saíram, sem trazer de volta o que saiu nem acrescentar fato, e o corte roda de novo no texto consertado. Sem o conserto, o parágrafo que ficou com uma frase só, curta, sai junto. A reconferência de 11/11/2026 cortou a frase do fato que abria o texto de 10/11, que passou a começar por "Segundo a Consultoria de Orçamento da Câmara, são R$ 7,6 bilhões em 2027", e o corte da rodada de 11/11 deixou "Os bancos ainda esperam corte." sozinha. O texto de antes dos cortes fica no registro, em `texto_antes_dos_cortes`.

## Até onde ir

A rodada das 5h tem uns 35 minutos para a pesquisa, o texto, as duas voltas de revisão e a conferência final, para o texto sair no site e no e-mail por volta das 6h. Sem tempo para a pesquisa, o texto sai da ficha da história e dos dados do site. Se o texto falhar, o `src/fundo.py --hoje` tenta de novo no mesmo `run.sh`, e se o dia ainda ficar sem texto, o editor do site recebe um aviso. A pesquisa também diz se a leitora precisaria de uma página do básico que o site ainda não tem; a rodada só avisa o editor do site, que decide se a página sai.
