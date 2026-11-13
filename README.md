# Vai dar crise?

Para que lado anda o risco de o Brasil entrar em recessão técnica (dois trimestres seguidos de queda do PIB): subindo, igual ou caindo, conforme cinco pressões que costumam vir antes de uma recessão (contas do governo, dívidas das famílias, desconfiança de quem investe, inflação esperada e juro) pioram ou melhoram contra 3 meses antes. Com um post por dia: o fato do dia de segunda a sábado e a pergunta da semana aos domingos, num blog de rolagem só, do post mais novo ao mais antigo, com o Retrato do Brasil também no topo. No ar em **[vaidarcrise.com.br](https://vaidarcrise.com.br)**.

A metodologia está em [METODOLOGIA.md](METODOLOGIA.md), a regra da direção em [src/direcao.py](src/direcao.py), as escolhas fixas em [config/modelo.json](config/modelo.json) e o que sai dos dados (o vaivém normal de cada pressão e o teste desde 2004) em [config/calibracao.json](config/calibracao.json). Cada atualização grava um registro em [`runs/`](runs/), imutável depois do lançamento oficial, com insumos, hash das regras e do prompt e a resposta do modelo de linguagem. Para quem os textos são escritos (leitor, tom, palavras, números e a lista que todo texto passa) está em [PERSONA.md](PERSONA.md); [CLAUDE.md](CLAUDE.md) manda todo texto novo passar por ele.

## Como funciona

```
launchd, de hora em hora (minuto 5) → run.sh --coletar
  └─ src/fetch_news.py      RSS de 8 veículos + GDELT     → data/manchetes.json (acervo local, fora do git)

launchd, todo dia às 04h00 → run.sh   (uma publicação por dia; se o Mac dormir, roda ao acordar)
  ├─ src/fetch_data.py      BCB SGS, Focus, IBGE, Tesouro Direto e FMI (FRED) → data/raw/<dia>/indicadores.json
  ├─ src/calendario.py      calendário de divulgações do IBGE + config/datas.json → data/calendario.json
  ├─ src/direcao.py         a direção do risco: as cinco pressões contra 3 meses antes, com os cortes de
  │                         config/calibracao.json, a folga de cada uma e a linha do tempo desde 2004
  ├─ src/model.py           indicadores do dia (src/indicadores.py) e o PIB num ano ruim (src/gar.py), que fica
  │                         só no fim de Como funciona
  ├─ src/classify_news.py   claude -p, sem ferramentas, saída em esquema JSON: manchetes do dia anterior → eventos,
  │                         cada um como passo de uma história em andamento (base/memoria/historias.json)
  ├─ src/dossie.py          fatos de dados de cada assunto, contexto para o texto
  ├─ src/pauta.py           a história do dia, sem IA: a soma das notícias por história, tamanho x estágio
  │                         (CARTA_EDITORIAL.md)
  ├─ src/fundo.py fazer     no fato do dia e na pergunta da semana (domingo), a pesquisa da história (claude -p com
  │                         busca na internet, src/conta.py e as metas de config/metas.json), a segunda busca só do
  │                         que a pesquisa não achou, a
  │                         investigação (src/investiga.py: perguntas da leitora, explicações rivais, testes cegos
  │                         contra o dado, cético e juiz), o esqueleto do argumento, um texto só, o leitor que só
  │                         recebe o texto e o revisor de três leitores e um editor, que devolvem objeções em até
  │                         duas voltas, e uma conferência final só de erros; o código confere cada número (guia
  │                         em FUNDO.md, até 65 min; no domingo, até 85, sobre a história que mais andou na semana)
  ├─ src/escreve_post.py    os dados do site que o texto recebe e o tipo do post de cada dia, sem IA
  ├─ src/run.py             grava runs/<id>.json e data/eventos.json
  ├─ src/build_site.py      gera docs/ (HTML estático, og.png, data.json) com editor/*.md;
  │                         a aba O que causa recessão é texto fixo em templates/causas.html
  │                         (a pesquisa por trás dela, na metodologia: src/causas.py e config/causas.json)
  │                         (desenhos e prévia da aba: src/imagens_causas.py, rodado à mão)
  ├─ git push               GitHub Pages publica docs/
  └─ src/fundo.py --hoje    se o texto do dia não saiu na rodada, outra tentativa, num segundo push; se ainda faltar,
                            aviso ao Pedro no Mac (o guarda, garantir()). Antes, --reconfere abre as fontes dos textos
                            feitos na nuvem e tira a frase que não confere
```

O LLM classifica manchetes, pesquisa, escreve e revisa o texto. A escolha da história, a direção, a pressão das notícias por assunto e o HTML saem de código determinístico. 

Calibração (rodar só quando mudar uma regra ou o IBGE confirmar uma recessão nova):

```
src/historico.py   baixa as séries do Brasil desde 2002 → data/historico/series.json (o PIB fica em data/historico/pib.json)
src/calibra.py     regressão de quantil no painel de 44 países (data/historico/painel_ocde.csv), teste fora da amostra
                   e, no fim, os cortes e o teste da direção → config/calibracao.json, data/historico/mensal.json
                   (precisa de pandas e statsmodels)
src/direcao.py --calibrar AAAA-MM   só os cortes e o teste da direção, sem refazer a conta dos 44 países
src/ritmo.py --calibrar             a faixa normal do crescimento em 12 meses e o erro do Focus (bloco abaixo da placa)
```

## Rodar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh            # atualização do dia e publicação (pula se já houver uma hoje)
./run.sh --forcar   # publica de novo hoje
./run.sh --sem-llm  # só dados
./run.sh --coletar  # só junta manchetes ao acervo
.venv/bin/python src/build_site.py              # só regerar o site
.venv/bin/python src/escreve_post.py                       # os dados do site que o texto do dia recebe, sem chamar o LLM
.venv/bin/python src/fundo.py runs/<id>.json --grava         # refaz o texto do dia: pesquisa, segunda busca, esqueleto, texto e revisão (--offline na nuvem;
                                                              # --sem-esqueleto roda sem o esqueleto e sem o leitor frio;
                                                              # --semana faz a pergunta da semana numa rodada que não é de domingo)
.venv/bin/python src/investiga.py runs/<id>.json [--semana]   # só a investigação de uma rodada, sem texto e sem gravar
.venv/bin/python src/fundo.py --confere                       # lista os fatos do dia sem texto
.venv/bin/python src/edita_texto.py editor/<texto>.md       # o editor num texto à mão
```

Agendamento: copie `launchd/com.pedrojahara.vaidarcrise.plist` (04h00) e `launchd/com.pedrojahara.vaidarcrise.coleta.plist` (de hora em hora) para `~/Library/LaunchAgents` e carregue com `launchctl bootstrap gui/$(id -u) <arquivo>`. Logs em `logs/`.

Textos escritos à mão ficam em `editor/AAAA-MM-DD-slug.md` (cabeçalho, `---`, Markdown) e entram no blog na próxima geração do site. Todo post, do dia ou escrito à mão, entra na rolagem da página principal na data do cabeçalho, do mais novo ao mais antigo: a página traz os 5 primeiros, e o resto vem de `docs/posts/` (um pedaço de HTML por post e `indice.json`) quando a leitora chega ao fim. Com `tipo: retrato` no cabeçalho, o texto vira o Retrato do Brasil e também fica no cartão "Comece por aqui", no topo da página principal (vale o mais novo).

## Dados públicos

- [`/data.json`](https://vaidarcrise.com.br/data.json): a direção, desde quando, cada pressão com o dado de agora, o de 3 meses antes, o corte e a folga, o PIB num ano ruim e a pressão das notícias por assunto.
- [`/historico.json`](https://vaidarcrise.com.br/historico.json): a direção de todas as atualizações publicadas.

Não é recomendação de investimento.
