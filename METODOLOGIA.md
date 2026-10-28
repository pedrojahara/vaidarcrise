# Metodologia v1.0

Pré-registrada em 28 de outubro de 2026, antes da primeira nota. Os parâmetros estão em [`config/modelo.json`](https://github.com/pedrojahara/vaidarcrise/blob/main/config/modelo.json), e cada atualização grava o hash desse arquivo. Mudança de regra ou de peso só acontece com nova versão e nota explicando o efeito.

## O que a nota mede

A nota é a probabilidade, de 0 a 100, de esta pergunta ter resposta "sim":

> O PIB do Brasil terá dois trimestres seguidos de queda entre o 3º trimestre de 2026 e o 4º trimestre de 2030?

- **Dado:** PIB trimestral dessazonalizado do IBGE ([tabela 5932](https://sidra.ibge.gov.br/tabela/5932), taxa contra o trimestre imediatamente anterior).
- **Quando se resolve:** na série vigente em março de 2031. O PIB é revisado; em 2021, uma recessão técnica anunciada sumiu na revisão seguinte.
- **Auditoria:** se a datação do CODACE/FGV IBRE divergir da regra técnica, o site publica as duas leituras.

O nome do site fala em crise; a métrica é recessão técnica. "Vai dar crise?" é a pergunta de bar; a resposta é uma probabilidade com regra escrita antes.

**Como ler a nota.** 50 significa cara ou coroa, não "risco médio". A nota 70 quer dizer que, em 100 Brasis com os dados de hoje, 70 entrariam em recessão até o fim de 2030.

## Taxa-base

Antes de olhar qualquer dado ou notícia, a história já diz muito. O CODACE datou 10 recessões desde 1980. Dividindo os inícios de recessão pelos trimestres em expansão:

| Período de referência | Risco por trimestre | Até o 4T30 (17 inícios possíveis) |
| --- | --- | --- |
| 1980–2026 (10 recessões) | 7,5% | 73% |
| 1995–2026, pós-Real (7) | 7,1% | 71% |
| 2004–2026, metas de inflação maduras (3) | 4,0% | 50% |
| 2004–2026 sem a pandemia (2) | 2,7% | 37% |

O site usa **5,5% por trimestre**, a média das classes 1995–2026 e 2004–2026. Excluir a pandemia é tentador e errado: choques externos fazem parte do risco até 2030. Essa é a escolha que mais pesa na nota, e por isso a página inicial mostra a conta com as alternativas.

Um início de recessão no trimestre *t* exige que *t* e *t+1* estejam na janela, então há 17 inícios possíveis (3T26 a 3T30). Com 5,5% por trimestre, a chance só pela história é 1 − 0,945¹⁷ ≈ 62%.

## A conta

O modelo soma três camadas na escala de log-odds (logit), o que torna cada contribuição exata e aditiva.

```
logit(h_t) = logit(h0) + w_t × (I + N)
P(recessão até 4T30) = 1 − Π (1 − h_t)
```

- **h0** é a taxa-base de 5,5% por trimestre.
- **I** é a soma das contribuições dos indicadores.
- **N** é a soma das contribuições das notícias.
- **w_t** é o peso no tempo: 1 nos quatro primeiros trimestres ainda não divulgados, 2/3 no quinto, 1/3 no sexto e zero daí em diante.

Ninguém prevê recessão a quatro anos com dados de hoje: os melhores métodos acertam de 6 a 18 meses. Por isso indicadores e notícias mexem só no risco dos próximos trimestres, e a nota até 2030 se move devagar. A página também mostra a probabilidade dos próximos 4 trimestres, que é onde as notícias aparecem.

**Trimestres divulgados.** Quando o IBGE divulga um trimestre, ele sai da janela (efeito tempo). Se dois trimestres seguidos vierem negativos, a pergunta está resolvida e a nota vai a 100. Se o último trimestre divulgado vier negativo, a chance de o seguinte também cair parte de 50% (parâmetro por julgamento, a calibrar com a série do IBGE) e recebe o mesmo deslocamento de curto prazo.

**Decomposição.** A conversão de log-odds para probabilidade não é linear, então a repartição em pontos usa valores de Shapley exatos: cada fator recebe a sua contribuição média sobre todas as ordens possíveis, e a soma bate exatamente com a variação. Com mais de 12 fatores, as notícias menores são agrupadas em "outras notícias".

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

Um modelo de linguagem (Claude, chamado sem ferramentas e com saída em esquema JSON validado por código) lê as manchetes do dia de oito veículos com linhas editoriais diferentes: Agência Brasil, Folha, Estadão, Valor, InfoMoney, Poder360, Gazeta do Povo e g1. Ele transforma os fatos relevantes em eventos estruturados; a conta é feita por código.

| Regra | Valor |
| --- | --- |
| Efeito por tamanho do fato (1, 2, 3) | 0,04, 0,12 e 0,20 em log-odds |
| Fato que o mercado já esperava | vale metade |
| Fato noticiado por um só veículo | vale metade |
| Teto por evento | 0,2 em log-odds |
| Teto da camada de notícias | 0,6 em log-odds |
| Prazo de validade | o efeito cai em linha reta até zero em 75 dias |
| Notícia que só relata um dado já medido | não conta (evita dupla contagem) |

O LLM extrai e narra; não prevê. Ele não vê os pesos, não escolhe a direção da nota e não edita o site. O texto das notícias é tratado como dado, nunca como instrução, e nenhuma notícia pode alterar pesos ou regras. A linguagem dos eventos descreve políticas e números, não pessoas ou partidos.

Cada atualização guarda o prompt (hash), o modelo usado e a resposta bruta. Respostas antigas nunca são recalculadas: o que foi publicado fica congelado.

## Salvaguardas

- **Disjuntor:** variação de mais de 5 pontos num dia sai com o selo "em revisão".
- **Dado defasado:** se a nota passar de 36 horas sem atualização, a página avisa.
- **Falha do LLM:** a atualização sai só com dados, e os eventos que já valiam continuam decaindo.
- **Os dois lados:** a página mostra os três melhores argumentos por mais crise e por menos crise.
- **Placar:** as previsões de 12 meses ficam registradas e serão pontuadas pelo escore de Brier quando vencerem.

## O que ainda falta (fase 2)

- Backtest de 1996 a 2026 das camadas 1 e 2, com os dados como eram conhecidos na época. O LLM não entra no backtest, porque ele sabe o que aconteceu em 2015 e 2020.
- Teste mensal de troca de nomes: reprocessar uma amostra de notícias trocando os atores e publicar se a classificação mudou.
- Probit em painel com cerca de 20 emergentes para estimar os pesos com mais dados do que as 7 recessões brasileiras desde 1995.
- Calibrar com a série do IBGE a chance de um trimestre negativo ser seguido de outro.

Se o backtest não bater a taxa-base, o site vai dizer isso em público, e a nota passa a ser só taxa-base mais notícias explicadas.

## Onde erramos

Erros são listados aqui com data, o que estava errado e o efeito na nota.

| Data | O que estava errado | Efeito na nota |
| --- | --- | --- |
| 28/10/2026 | A segunda atualização deu a quatro eventos novos os mesmos códigos de eventos antigos, o que embaralhou a explicação da variação. Os eventos foram renumerados e a decomposição refeita no mesmo dia. | Nenhum: a nota (77,9) não mudou, só a repartição dos pontos. | Achou um? [Abra uma issue](https://github.com/pedrojahara/vaidarcrise/issues).

## Fontes

- [Datação dos ciclos econômicos brasileiros, CODACE/FGV IBRE](https://portalibre.fgv.br/codace)
- [Banco Central: séries temporais (SGS)](https://www3.bcb.gov.br/sgspub/) e [Focus](https://www.bcb.gov.br/publicacoes/focus)
- [IBGE: Contas Nacionais Trimestrais](https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9300-contas-nacionais-trimestrais.html)
- An, Jalles e Loungani (2018), *How well do economists forecast recessions?*, FMI
- Chinn e Ferrara (2024), curva de juros em emergentes, NBER w32084
- Tetlock e Gardner (2015), *Superforecasting*, sobre classes de referência
