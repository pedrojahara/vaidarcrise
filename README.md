# Vai dar crise?

Para que lado anda o risco de o Brasil entrar em recessão técnica (dois trimestres seguidos de queda do PIB): subindo, igual ou caindo, conforme cinco pressões que costumam vir antes de uma recessão (contas do governo, dívidas das famílias, dólar e juro longo, inflação esperada e juro) apertam ou folgam contra 3 meses antes. Com um post por dia: o fato do dia de segunda a sábado, a semana aos domingos e o mês no primeiro domingo do mês, com o Retrato do Brasil fixo no topo. No ar em **[vaidarcrise.com.br](https://vaidarcrise.com.br)**.

A metodologia está em [METODOLOGIA.md](METODOLOGIA.md), a regra da direção em [src/direcao.py](src/direcao.py), as escolhas fixas em [config/modelo.json](config/modelo.json) e o que sai dos dados (o vaivém normal de cada pressão e o teste desde 2004) em [config/calibracao.json](config/calibracao.json). Cada atualização grava um registro em [`runs/`](runs/), imutável depois do lançamento oficial, com insumos, hash das regras e do prompt e a resposta do modelo de linguagem. Para quem os textos são escritos (leitor, tom, palavras, números e a lista que todo texto passa) está em [PERSONA.md](PERSONA.md); [CLAUDE.md](CLAUDE.md) manda todo texto novo passar por ele.

## Como funciona

```
launchd, de hora em hora (minuto 5) → run.sh --coletar
  └─ src/fetch_news.py      RSS de 8 veículos + GDELT     → data/manchetes.json (acervo local, fora do git)

launchd, todo dia às 06h30 → run.sh   (uma publicação por dia; se o Mac dormir, roda ao acordar)
  ├─ src/fetch_data.py      BCB SGS, Focus, IBGE, Tesouro Direto e FMI (FRED) → data/raw/<dia>/indicadores.json
  ├─ src/calendario.py      calendário de divulgações do IBGE + config/datas.json → data/calendario.json
  ├─ src/direcao.py         a direção do risco: as cinco pressões contra 3 meses antes, com os cortes de
  │                         config/calibracao.json, a folga de cada uma e a linha do tempo desde 2004
  ├─ src/model.py           indicadores do dia (src/indicadores.py) e o PIB num ano ruim (src/gar.py), que fica
  │                         só no fim de Como funciona
  ├─ src/classify_news.py   claude -p, sem ferramentas, saída em esquema JSON: manchetes do dia anterior → eventos
  ├─ src/dossie.py          fatos de dados de cada assunto, contexto para o post
  ├─ src/escreve_post.py    claude -p escreve o post do tipo do dia (fato do dia, semana ou mês) a partir da conta pronta
  │                         e dos registros em runs/; src/revisa_texto.py confere o texto e os números
  ├─ src/run.py             grava runs/<id>.json e data/eventos.json
  ├─ src/build_site.py      gera docs/ (HTML estático, og.png, data.json) com editor/*.md;
  │                         a aba O que causa recessão é texto fixo em templates/causas.html
  │                         (a pesquisa por trás dela, na metodologia: src/causas.py e config/causas.json)
  │                         (desenhos e prévia da aba: src/imagens_causas.py, rodado à mão)
  └─ git push               GitHub Pages publica docs/
```

O LLM classifica manchetes e redige o post. A direção, a pressão das notícias por assunto e o HTML saem de código determinístico.

Calibração (rodar só quando mudar uma regra ou o IBGE confirmar uma recessão nova):

```
src/historico.py   baixa as séries do Brasil desde 2002 → data/historico/series.json (o PIB fica em data/historico/pib.json)
src/calibra.py     regressão de quantil no painel de 44 países (data/historico/painel_ocde.csv), teste fora da amostra
                   e, no fim, os cortes e o teste da direção → config/calibracao.json, data/historico/mensal.json
                   (precisa de pandas e statsmodels)
src/direcao.py --calibrar AAAA-MM   só os cortes e o teste da direção, sem refazer a conta dos 44 países
```

## Rodar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh            # atualização do dia e publicação (pula se já houver uma hoje)
./run.sh --forcar   # publica de novo hoje
./run.sh --sem-llm  # só dados
./run.sh --coletar  # só junta manchetes ao acervo
.venv/bin/python src/build_site.py              # só regerar o site
.venv/bin/python src/escreve_post.py                      # escreve o post da última atualização e imprime, sem gravar
.venv/bin/python src/escreve_post.py --so-dados            # só os dados que o post recebe, sem chamar o LLM
.venv/bin/python src/escreve_post.py --tipo semana --so-dados  # força o tipo (dia, semana ou mes)
```

Agendamento: copie `launchd/com.pedrojahara.vaidarcrise.plist` (06h30) e `launchd/com.pedrojahara.vaidarcrise.coleta.plist` (de hora em hora) para `~/Library/LaunchAgents` e carregue com `launchctl bootstrap gui/$(id -u) <arquivo>`. Logs em `logs/`.

Textos escritos à mão ficam em `editor/AAAA-MM-DD-slug.md` (cabeçalho, `---`, Markdown) e entram no blog na próxima geração do site. Com `tipo: retrato` no cabeçalho, o texto vira o Retrato do Brasil, fixo no topo da página principal (vale o mais novo).

## Dados públicos

- [`/data.json`](https://vaidarcrise.com.br/data.json): a direção, desde quando, cada pressão com o dado de agora, o de 3 meses antes, o corte e a folga, o PIB num ano ruim e a pressão das notícias por assunto.
- [`/historico.json`](https://vaidarcrise.com.br/historico.json): a direção de todas as atualizações publicadas.

Não é recomendação de investimento.
