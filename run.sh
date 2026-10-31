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
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') fim (nível ${nivel})"
