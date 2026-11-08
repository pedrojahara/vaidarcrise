#!/bin/zsh
# Atualização agendada: lê as manchetes do dia anterior, calcula, escreve o post, gera o site
# e publica (git push -> GitHub Pages). Só publica uma vez por dia.
# Uso manual: ./run.sh            (atualização do dia; se já houver uma hoje, só coleta)
#             ./run.sh --forcar   (publica de novo hoje)
#             ./run.sh --sem-llm  (só dados, sem ler notícias)
#             ./run.sh --coletar  (só junta manchetes ao acervo local; sem git e sem publicar)
set -u
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export LANG=pt_BR.UTF-8
mkdir -p logs

if [[ "${1:-}" == "--coletar" ]]; then
  exec >> "logs/coleta-$(date +%Y-%m).log" 2>&1
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $(.venv/bin/python src/run.py --coletar | tail -1)"
  exit 0
fi

exec >> "logs/run-$(date +%Y-%m).log" 2>&1
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') início"

git pull --rebase --quiet origin main || echo "aviso: git pull falhou; seguindo com a cópia local"

if ! /usr/bin/caffeinate -i .venv/bin/python src/run.py "$@"; then
  echo "ERRO: a rodada falhou; nada foi publicado"
  exit 1
fi

direcao=$(jq -r '.direcao' docs/data.json)
git add -A runs data docs
if git diff --cached --quiet; then
  echo "nada mudou"
else
  git commit -q -m "Post de $(date '+%d/%m/%Y'): risco ${direcao}"
  for i in 1 2 3 4; do
    git push -q origin main && break
    echo "push falhou (tentativa $i)"; sleep $((2 ** i))
  done
fi
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') post publicado (direção ${direcao})"

# O site não cria página de pergunta sozinho: quando a rodada sente falta de uma (src/base_site.py, falta_pagina()),
# o aviso fica no registro do dia e aparece como notificação no Mac, para o Pedro decidir.
ultimo=$(ls runs/*.json 2>/dev/null | tail -1)
if [[ -n "$ultimo" ]]; then
  jq -r '.avisos_ao_pedro[]?' "$ultimo" | while IFS= read -r aviso; do
    echo "aviso ao Pedro: $aviso"
    /usr/bin/osascript -e "display notification \"${aviso//\"/}\" with title \"Vai dar crise?\" subtitle \"Falta uma página?\"" || true
  done
fi

# A leitura a fundo do fato do dia (src/fundo.py, guia em FUNDO.md) sai depois do post, num segundo push: a pesquisa
# rodou antes do post (src/run.py), e aqui fica a redação, da mesma pesquisa (se a pesquisa falhou, faz tudo de novo).
# Antes, a memória do momento junta os fatos do dia; no domingo, revê as histórias.
if [[ "${1:-}" != "--sem-llm" ]]; then
  .venv/bin/python src/memoria.py dia || echo "aviso: a memória do dia falhou"
  if [[ "$(date +%u)" == "7" ]]; then
    .venv/bin/python src/memoria.py historias --semana || echo "aviso: a revisão das histórias falhou"
  fi
  # Leitura a fundo feita na nuvem (que não abre as fontes): o Mac abre as fontes e tira a frase que não confere.
  .venv/bin/python src/fundo.py --reconfere --grava || echo "aviso: a reconferência das fontes falhou"
  /usr/bin/caffeinate -i .venv/bin/python src/fundo.py --hoje --grava --limite-min 35 || echo "aviso: a leitura a fundo falhou"
  .venv/bin/python src/build_site.py > /dev/null || echo "aviso: o site não foi gerado de novo"
  git add -A runs base/memoria docs
  if ! git diff --cached --quiet; then
    git commit -q -m "Leitura a fundo de $(date '+%d/%m/%Y')"
    for i in 1 2 3 4; do
      git push -q origin main && break
      echo "push falhou (tentativa $i)"; sleep $((2 ** i))
    done
  fi
fi
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') fim (direção ${direcao})"
