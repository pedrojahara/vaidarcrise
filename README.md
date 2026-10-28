# Vai dar crise?

Probabilidade de recessão técnica no Brasil (dois trimestres seguidos de queda do PIB) entre o 3º trimestre de 2026 e o 4º trimestre de 2030. No ar em **[vaidarcrise.com.br](https://vaidarcrise.com.br)**.

A metodologia está em [METODOLOGIA.md](METODOLOGIA.md) e os parâmetros em [config/modelo.json](config/modelo.json). Cada atualização grava um registro imutável em [`runs/`](runs/) com insumos, versão do modelo, hash do prompt e a resposta do modelo de linguagem.

## Como funciona

```
launchd (07h30 e 18h30) → run.sh
  ├─ src/fetch_data.py      BCB SGS, Focus e IBGE        → data/raw/<dia>/indicadores.json
  ├─ src/fetch_news.py      RSS de 8 veículos + GDELT     → data/raw/<dia>/noticias.json (fica fora do git)
  ├─ src/classify_news.py   claude -p, sem ferramentas, saída em esquema JSON → eventos
  ├─ src/model.py           taxa-base + indicadores + notícias em log-odds, Shapley
  ├─ src/run.py             grava runs/<id>.json e data/eventos.json
  ├─ src/build_site.py      gera docs/ (HTML estático, og.png, data.json)
  └─ git push               GitHub Pages publica docs/
```

O LLM só classifica manchetes. A nota, os pesos e o HTML saem de código determinístico.

## Rodar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh            # rodada completa e publicação
./run.sh --sem-llm  # só dados
.venv/bin/python src/build_site.py   # só regerar o site
```

Agendamento: `launchd/com.pedrojahara.vaidarcrise.plist` (copiado para `~/Library/LaunchAgents`). Logs em `logs/`.

## Dados públicos

- [`/data.json`](https://vaidarcrise.com.br/data.json): nota atual, decomposição e insumos.
- [`/historico.json`](https://vaidarcrise.com.br/historico.json): todas as notas publicadas.

Não é recomendação de investimento.
