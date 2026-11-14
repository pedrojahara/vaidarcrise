#!/bin/zsh
# Atualização agendada: lê as manchetes do dia anterior, calcula, escreve o post, gera o site
# e publica (git push -> GitHub Pages). Só publica uma vez por dia.
# Uso manual: ./run.sh            (atualização do dia; se já houver uma hoje, só coleta)
#             ./run.sh --forcar   (publica de novo hoje)
#             ./run.sh --sem-llm  (só dados, sem ler notícias)
#             ./run.sh --coletar  (só junta manchetes ao acervo local; sem git e sem publicar; e refaz a rodada
#                                  do dia que não terminou, ver abaixo)
set -u
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export LANG=pt_BR.UTF-8
mkdir -p logs

# O dia terminou quando o registro tem a linha "fim" de hoje e, com o e-mail diário ligado, o e-mail de hoje saiu.
dia_completo() {
  local hoje=$(date +%Y-%m-%d)
  grep -q "^=== ${hoje}T[^ ]* fim" "logs/run-$(date +%Y-%m).log" 2>/dev/null || return 1
  [[ "$(jq -r '.envio_diario' config/newsletter.json)" != "true" ]] && return 0
  jq -e --arg d "$hoje" 'has($d)' logs/envios.json > /dev/null 2>&1
}
# Uma rodada inteira está em andamento: a trava dela existe e tem menos de 4 horas. A mais velha é de uma rodada que o
# Mac interrompeu (desligou, travou) e não vale mais.
rodando() {
  [[ -n "$(find logs/.rodada -maxdepth 0 -mmin -240 2>/dev/null)" ]]
}

if [[ "${1:-}" == "--coletar" ]]; then
  exec >> "logs/coleta-$(date +%Y-%m).log" 2>&1
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $(.venv/bin/python src/run.py --coletar | tail -1)"
  # A rodada das 4h que não terminou (em 13/11/2026 o Mac ficou horas sem rede; uma rodada pode cair no meio) roda de
  # novo aqui, na hora cheia, entre 5h e 17h, até duas vezes por dia, só com rede e sem outra rodada em andamento. A
  # rodada inteira roda de novo, e o que já saiu não sai duas vezes: o post sai uma vez por dia (src/run.py), o e-mail
  # também (src/newsletter.py), e o texto que faltou tenta de novo (o guarda de src/fundo.py --hoje).
  hora=$((10#$(date +%H)))
  if (( hora >= 5 && hora < 18 )) && ! dia_completo && ! rodando; then
    feitas=$(grep -c "^=== $(date +%Y-%m-%d)T[^ ]* início (de novo" "logs/run-$(date +%Y-%m).log" 2>/dev/null)
    if (( ${feitas:-0} >= 2 )); then
      exit 0
    elif ! curl -fsS -o /dev/null --max-time 20 https://github.com; then
      echo "$(date '+%Y-%m-%dT%H:%M:%S%z') a rodada de hoje não terminou e o Mac está sem rede; tenta na próxima hora"
    else
      echo "$(date '+%Y-%m-%dT%H:%M:%S%z') a rodada de hoje não terminou; roda de novo (vez $(( ${feitas:-0} + 1 )))"
      VDC_DE_NOVO=$(( ${feitas:-0} + 1 )) exec /bin/zsh ./run.sh
    fi
  fi
  exit 0
fi

exec >> "logs/run-$(date +%Y-%m).log" 2>&1
# Uma rodada inteira por vez: a que roda de novo (acima) não começa no meio de outra.
if ! mkdir logs/.rodada 2>/dev/null; then
  if rodando; then
    echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') outra rodada em andamento; esta não roda"
    exit 0
  fi
  touch logs/.rodada
fi
trap 'rmdir logs/.rodada 2>/dev/null' EXIT
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') início${VDC_DE_NOVO:+ (de novo, vez $VDC_DE_NOVO, porque a rodada de hoje não terminou)}"

git pull --rebase --quiet origin main || echo "aviso: git pull falhou; seguindo com a cópia local"

if ! /usr/bin/caffeinate -i .venv/bin/python src/run.py "$@"; then
  echo "ERRO: a rodada falhou; nada foi publicado"
  if [[ "${VDC_DE_NOVO:-}" == "2" ]]; then
    /usr/bin/osascript -e 'display notification "A rodada de hoje falhou de novo; o post e o e-mail não saíram (veja logs/run)" with title "Vai dar crise?"' || true
  fi
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

# O texto do dia (src/fundo.py, guia em FUNDO.md) normalmente já saiu em src/run.py. Aqui, num segundo push, o Mac
# reconfere as fontes dos textos feitos na nuvem e, se o texto de hoje faltar, tenta de novo (o guarda de --hoje).
# Antes, a memória do momento junta os fatos do dia; no domingo, revê as histórias.
if [[ "${1:-}" != "--sem-llm" ]]; then
  .venv/bin/python src/memoria.py dia || echo "aviso: a memória do dia falhou"
  if [[ "$(date +%u)" == "7" ]]; then
    .venv/bin/python src/memoria.py historias --semana || echo "aviso: a revisão das histórias falhou"
  fi
  # Texto feito na nuvem (que não abre as fontes): o Mac abre as fontes e tira a frase que não confere.
  .venv/bin/python src/fundo.py --reconfere --grava || echo "aviso: a reconferência das fontes falhou"
  /usr/bin/caffeinate -i .venv/bin/python src/fundo.py --hoje --grava --limite-min 65 || echo "aviso: o texto do dia falhou"
  .venv/bin/python src/build_site.py > /dev/null || echo "aviso: o site não foi gerado de novo"
  git add -A runs base/memoria docs
  if ! git diff --cached --quiet; then
    git commit -q -m "Texto do dia conferido de $(date '+%d/%m/%Y')"
    for i in 1 2 3 4; do
      git push -q origin main && break
      echo "push falhou (tentativa $i)"; sleep $((2 ** i))
    done
  fi
fi
# O fato do dia por e-mail (src/newsletter.py): sai uma vez por dia, para a lista do Resend, depois que a página do dia
# está no ar. Só roda com "envio_diario" ligado em config/newsletter.json. A chave do Resend fica
# no Chaves do Mac (serviço vaidarcrise-resend) e só vive no ambiente destes comandos. Quem saiu da lista é apagado
# (a LGPD pede), e o --saude confere o domínio, a lista e o serviço de inscrição para o e-mail de amanhã.
avisa_email() {
  echo "aviso ao Pedro: $1"
  /usr/bin/osascript -e "display notification \"${1//\"/}\" with title \"Vai dar crise?\" subtitle \"E-mail do fato do dia\"" || true
}
if [[ "$(jq -r '.envio_diario' config/newsletter.json)" == "true" ]]; then
  if chave_resend=$(security find-generic-password -a vaidarcrise -s vaidarcrise-resend -w 2>/dev/null); then
    RESEND_API_KEY="$chave_resend" .venv/bin/python src/newsletter.py --hoje || avisa_email "o e-mail de hoje não saiu (veja logs/run)"
    RESEND_API_KEY="$chave_resend" .venv/bin/python src/newsletter.py --limpa || echo "aviso: a limpeza da lista falhou"
    saude=$(RESEND_API_KEY="$chave_resend" .venv/bin/python src/newsletter.py --saude 2>&1) || avisa_email "${saude//$'\n'/; }"
    unset chave_resend
  else
    avisa_email "a chave do Resend não está no Chaves; o e-mail de hoje não saiu"
  fi
fi
echo "=== $(date '+%Y-%m-%dT%H:%M:%S%z') fim (direção ${direcao})"
