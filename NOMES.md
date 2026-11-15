# Os nomes do site

O mesmo nome em todas as páginas, no post e nas frases geradas por código. Os nomes dos fatores ficam em `config/modelo.json`; os outros, nos templates e em `src/build_site.py`.

| Coisa | Nome no site |
| --- | --- |
| Cabeçalho | Hoje, O que causa recessão e Perguntas, numa linha só no celular; com a lista aberta, "Receba por e-mail" fecha a frase embaixo do nome do site. O que causa recessão é a pergunta principal e tem item próprio. Perguntas é um menu com a página de cada pressão (rótulo com o nome da pressão). Como funciona fica fora do cabeçalho: no topo, ao lado da data da atualização, e no rodapé. O site não liga para o código em nenhuma página |
| Abas, no texto | O que causa recessão, Como funciona |
| O link do fato do dia para o básico | Logo abaixo do texto: "O básico sobre o juro" e a pergunta da página; sem página da pressão, "O básico, na página O que causa recessão" e o título da parte |
| A direção | "O risco de recessão está subindo", "está igual" ou "está caindo"; quando o texto fala dela, com desde quando ("desde junho de 2026"); "A economia está encolhendo" quando a prévia do PIB cai mais de 1,5% em 3 meses. Na placa: Subindo, Igual, Caindo, Encolhendo |
| O crescimento, logo abaixo da placa | Crescimento em 12 meses: três blocos lado a lado, com os três números do mesmo tamanho e, embaixo de cada um, em letra pequena, os 12 meses que ele cobre, saídos dos dados do dia: "set/24–ago/25", "set/25–ago/26" e, no bloco só com contorno, "dez/26–nov/27" e "previsão". Nenhum número maior que os outros (Pedro, 12/11/2026). Embaixo, uma linha de fonte: "Fontes: prévia do PIB e pesquisa com os bancos (Focus), as duas do Banco Central." Nunca Antes, Agora e Previsão sem a data. À direita do título, como o Piorou de cada pressão: Acelerando, Desacelerando ou No mesmo ritmo. O normal desde 2004 e o erro da previsão "dos bancos (Focus)" ficam em Como funciona |
| As cinco pressões | Contas do governo, Dívidas das famílias, Desconfiança de quem investe, Inflação esperada, Juro |
| Os dois números da Desconfiança de quem investe | o dólar e o juro de 10 anos, os dois na linha fechada; na primeira vez, "o juro de 10 anos é o que o governo paga, acima da inflação, para pegar dinheiro emprestado por uns 10 anos". Nunca "juro longo", "juros futuros" ou "prêmio de risco" |
| O botão que abre as pressões no celular | "Por que está subindo? Veja as cinco pressões" (ou caindo, ou igual); quando a economia encolhe, "Como estão as cinco pressões?". Só aparece quando a página tem uma coluna; no computador, a lista fica aberta |
| As linhas que não mudam a placa | Também acompanhamos: Emprego, Renda, Reservas em dólar, Dívida em reais. Aberta, cada uma diz "Esta linha não muda a placa, porque..." |
| A linha da renda | a renda média do trabalho, descontada a inflação (PNAD Contínua, do IBGE), no trimestre que termina no mês |
| As famílias de referência | quem vive do salário mínimo ou da aposentadoria do INSS; quem tem financiamento e cartão; quem tem dinheiro guardado. Pela situação, nunca com nome inventado nem como "classe C" |
| O que cada linha fez | Piorou, Igual, Melhorou, em todas as linhas do topo: as cinco pressões, o emprego, a renda e as reservas. Em tabela que compara dois períodos, Pior, Igual e Melhor. No texto, "a pressão piorou" ou "pioraram as contas do governo". Nunca Apertou e Folgou, nem "apertando ou folgando" |
| Quais pressões mudaram, no texto | Cada uma pelo nome e com o mês da comparação: "Se compararmos com julho, pioraram as contas do governo, as dívidas das famílias, a desconfiança de quem investe e a inflação esperada. O juro ficou igual." O mês é o do meio das comparações (a dívida de setembro contra a de junho, a Selic de novembro contra a de agosto); cada linha do topo diz os meses dela. No topo, o título da lista é "As cinco pressões, comparadas com julho". No meio da frase, o nome vai em minúscula e com artigo, como qualquer palavra. Nunca a contagem ("quatro das cinco pressões"), porque a leitora não sabe de cor quais são as cinco |
| Categorias, rótulos e tabelas do post | Só as duas listas do topo, com os mesmos nomes: as cinco pressões e Também acompanhamos. Tabela que compara dois momentos diz o estado de cada um (Pior, Igual, Melhor), não o verbo no passado (nada de Piorou e Melhorou nela); Também acompanhamos entra no texto quando ajuda. Nunca "No bolso", "Parcelas", "Preços" ou "Mercado" como categoria |
| A medida das Dívidas das famílias | a parte da renda das famílias que vai para parcelas e juros |
| O que abre cada linha | Uma seta para baixo, sem texto, à direita da primeira linha, logo depois da palavra (Piorou, Igual...); aberta, a seta vira para cima. A linha inteira abre com um toque |
| A régua de cada pressão | o vaivém normal de 3 meses (só no topo aberto e em Como funciona) |
| Quanto falta para o pior já visto | Na página, só a frase que compara com o passado, na linha aberta: "A dívida está mais alta que em 96% dos meses desde 2006." No recorde, com sujeito: "A parte da renda que vai para dívidas é a maior desde 2005, quando começa a série." Nunca "Folga: x" na página; as palavras Nenhuma, Quase nenhuma, Pouca, Média e Muita ficam só no `data.json`. Em Como funciona, a seção "Quanto espaço ainda sobra?" |
| Os assuntos das notícias | Ritmo da economia, Juro e inflação, Dívidas das famílias, Desconfiança de quem investe, Contas do governo, Emprego, Economia lá fora |
| A conta dos 44 países (só em Como funciona) | o PIB num ano ruim (1 chance em 10); "num ano ruim, em tempos normais" para a comparação |
| Boletim Focus | os bancos (Focus) |
| Copom | o Banco Central decide o juro (Copom) |
| Diferença entre taxas | pontos, abreviado "pt" em tabela |
| Tipos de post | Retrato do Brasil, Fato do dia, Pergunta da semana (os Resumos da semana e do mês de 1/11 e 8/11/2026 ficam no ar com o nome que tinham) |
| Quem escreve o post | "Escrito pelo Claude com a ajuda do Pedro.", a mesma assinatura em todo post, sem horário e sem contar notícias |
| A lista por e-mail | "Receba o fato do dia por e-mail" na página da lista, que liga para o último fato do dia para a pessoa ver o que vai receber, o botão "Quero receber" e, no fim de todo e-mail, "Sair da lista". A caixa "Receba o fato do dia no seu e-mail" fica no fim do post (na página Hoje, só depois do primeiro) e no fim de O que causa recessão, das páginas do menu Perguntas e de Como funciona, onde ela diz em uma frase o que é o fato do dia; no e-mail, "Recebeu este e-mail de alguém?"; "Receba por e-mail" no fim da frase embaixo do nome do site e "Receber por e-mail" no rodapé, ao lado de "Privacidade". Nada salta na tela. A caixa, o "Recebeu" e os dois links só aparecem quando a lista está aberta |
| O compartilhar | No fim de todo post: o botão "Mandar no WhatsApp", que abre o WhatsApp com o título e o link, e ao lado "Copiar link", que vira "Link copiado" por 3 segundos. Nada no topo, nada preso à tela, nenhuma outra rede e nenhuma etiqueta de rastreio no link |

**Palavras com lado.** Fora do texto: "gastança", "rombo", "herança maldita", "austericídio", "desgoverno", "farra". No lugar, o número e o que ele mede.

**Palavras de alarme.** Fora do texto: "despenca", "explode", "derrete", "colapso", "tombo", "sangria". No lugar, o verbo neutro ("cai", "sobe") e o tamanho da mudança.
