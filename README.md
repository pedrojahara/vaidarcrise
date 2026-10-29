# Vai dar crise?

Quantas vezes a chance de o Brasil entrar em recessão técnica (dois trimestres seguidos de queda do PIB) nos próximos 12 meses está acima da de um ano normal, com um post por dia sobre as notícias da véspera. No ar em **[vaidarcrise.com.br](https://vaidarcrise.com.br)**.

A metodologia está em [METODOLOGIA.md](METODOLOGIA.md) e os parâmetros em [config/modelo.json](config/modelo.json). Cada atualização grava um registro imutável em [`runs/`](runs/) com insumos, versão do modelo, hash do prompt e a resposta do modelo de linguagem.

## Como funciona

```
launchd, de hora em hora (minuto 5) → run.sh --coletar
  └─ src/fetch_news.py      RSS de 8 veículos + GDELT     → data/manchetes.json (acervo local, fora do git)

launchd, todo dia às 06h30 → run.sh   (uma publicação por dia; se o Mac dormir, roda ao acordar)
  ├─ src/fetch_data.py      BCB SGS, Focus, IBGE e Tesouro Direto → data/raw/<dia>/indicadores.json
  ├─ src/calendario.py      calendário de divulgações do IBGE + config/datas.json → data/calendario.json
  ├─ src/classify_news.py   claude -p, sem ferramentas, saída em esquema JSON: manchetes do dia anterior → eventos
  ├─ src/model.py           taxa-base + indicadores (com o Tesouro IPCA+) em log-odds, Shapley; pressão das notícias por tema
  ├─ src/escreve_post.py    claude -p escreve o post a partir da conta pronta; src/revisa_texto.py confere o texto
  ├─ src/run.py             grava runs/<id>.json e data/eventos.json
  ├─ src/build_site.py      gera docs/ (HTML estático, og.png, data.json) com editor/*.md
  └─ git push               GitHub Pages publica docs/
```

O LLM classifica manchetes e redige o post. O risco, a pressão por tema, os pesos e o HTML saem de código determinístico.

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

- [`/data.json`](https://vaidarcrise.com.br/data.json): risco de 12 meses em vezes o normal, seta, chance até 2030, decomposição, pressão das notícias e insumos.
- [`/historico.json`](https://vaidarcrise.com.br/historico.json): todas as atualizações publicadas.

Não é recomendação de investimento.
