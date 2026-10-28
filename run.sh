#!/bin/zsh
# Rodada agendada: coleta, classifica, calcula, gera o site e publica (git push -> GitHub Pages).
# Uso manual: ./run.sh            (rodada normal)
#             ./run.sh --sem-llm  (só dados, sem ler notícias)
set -u
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export LANG=pt_BR.UTF-8
mkdir -p logs
exec >> "logs/run-$(date +%Y-%m).log" 2>&1
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') início"

git pull --rebase --quiet origin main || echo "aviso: git pull falhou; seguindo com a cópia local"

if ! /usr/bin/caffeinate -i .venv/bin/python src/run.py "$@"; then
  echo "ERRO: a rodada falhou; nada foi publicado"
  exit 1
fi

nota=$(jq -r '.nota' docs/data.json)
git add -A runs data docs
if git diff --cached --quiet; then
  echo "nada mudou"
else
  git commit -q -m "Atualização $(date '+%d/%m/%Y %Hh%M'): nota ${nota}"
  for i in 1 2 3 4; do
    git push -q origin main && break
    echo "push falhou (tentativa $i)"; sleep $((2 ** i))
  done
fi
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') fim (nota ${nota})"
