# Vai dar crise?

Se o risco de o Brasil entrar em recessão técnica (dois trimestres seguidos de queda do PIB) nos próximos 12 meses está acima ou abaixo do normal, em cinco níveis, com um resumo por fator e um post por dia sobre as notícias da véspera. No ar em **[vaidarcrise.com.br](https://vaidarcrise.com.br)**.

A metodologia está em [METODOLOGIA.md](METODOLOGIA.md), as regras em [config/modelo.json](config/modelo.json) e o que foi estimado com os dados em [config/calibracao.json](config/calibracao.json). Cada atualização grava um registro imutável em [`runs/`](runs/) com insumos, hash das regras e do prompt e a resposta do modelo de linguagem.

## Como funciona

```
launchd, de hora em hora (minuto 5) → run.sh --coletar
  └─ src/fetch_news.py      RSS de 8 veículos + GDELT     → data/manchetes.json (acervo local, fora do git)

launchd, todo dia às 06h30 → run.sh   (uma publicação por dia; se o Mac dormir, roda ao acordar)
  ├─ src/fetch_data.py      BCB SGS, Focus, IBGE, Tesouro Direto e FMI (FRED) → data/raw/<dia>/indicadores.json
  ├─ src/calendario.py      calendário de divulgações do IBGE + config/datas.json → data/calendario.json
  ├─ src/model.py           nível: cenário ruim do PIB (src/gar.py) contra os cortes de config/calibracao.json;
  │                         os nove indicadores do Resumo (src/indicadores.py) contra a faixa normal
  ├─ src/classify_news.py   claude -p, sem ferramentas, saída em esquema JSON: manchetes do dia anterior → eventos e revisões
  ├─ src/dossie.py          tendência de cada fator, fatos de dados, Focus e placar → data/dossie.json, data/placar.json
  ├─ src/escreve_post.py    claude -p escreve o post a partir da conta pronta; src/revisa_texto.py confere o texto
  ├─ src/run.py             grava runs/<id>.json e data/eventos.json
  ├─ src/build_site.py      gera docs/ (HTML estático, og.png, data.json) com editor/*.md
  └─ git push               GitHub Pages publica docs/
```

O LLM classifica manchetes, propõe revisões das tendências e redige o post. O nível, a pressão por fator, o que entra nas tendências e o HTML saem de código determinístico.

Calibração (rodar só quando mudar uma regra ou o IBGE confirmar uma recessão nova):

```
src/historico.py   baixa as séries do Brasil desde 2002 → data/historico/series.json (o PIB fica em data/historico/pib.json)
src/calibra.py     regressão de quantil no painel de 44 países (data/historico/painel_ocde.csv), cortes dos níveis e
                   teste fora da amostra → config/calibracao.json, data/historico/mensal.json (precisa de pandas e statsmodels)
```

## Rodar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh            # atualização do dia e publicação (pula se já houver uma hoje)
./run.sh --forcar   # publica de novo hoje
./run.sh --sem-llm  # só dados
./run.sh --coletar  # só junta manchetes ao acervo
.venv/bin/python src/build_site.py              # só regerar o site
.venv/bin/python src/escreve_post.py            # escreve o post da última atualização e imprime, sem gravar
.venv/bin/python src/escreve_post.py --so-dados # só os dados que o post recebe, sem chamar o LLM
```

Agendamento: copie `launchd/com.pedrojahara.vaidarcrise.plist` (06h30) e `launchd/com.pedrojahara.vaidarcrise.coleta.plist` (de hora em hora) para `~/Library/LaunchAgents` e carregue com `launchctl bootstrap gui/$(id -u) <arquivo>`. Logs em `logs/`.

Textos escritos à mão ficam em `editor/AAAA-MM-DD-slug.md` (cabeçalho, `---`, Markdown) e entram no blog na próxima geração do site.

## Dados públicos

- [`/data.json`](https://vaidarcrise.com.br/data.json): nível, cenário ruim do PIB, entradas da conta, fatores, indicadores com faixa normal, pressão das notícias.
- [`/historico.json`](https://vaidarcrise.com.br/historico.json): o nível de todas as atualizações publicadas.

Não é recomendação de investimento.
