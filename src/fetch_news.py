"""Coleta manchetes de economia de veículos com linhas editoriais diferentes.

Guarda só título, veículo, link, data e um trecho curto da descrição do feed, que
serve de contexto para a classificação e nunca é republicado no site.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import unicodedata
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; vaidarcrise.com.br; +https://github.com/pedrojahara/vaidarcrise)"}

FEEDS = {
    "Agência Brasil": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",
    "Folha": "https://feeds.folha.uol.com.br/mercado/rss091.xml",
    "Estadão": "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/economia/",
    "Valor": "https://valor.globo.com/rss/valor",
    "InfoMoney": "https://www.infomoney.com.br/feed/",
    "Poder360": "https://www.poder360.com.br/feed/",
    "Gazeta do Povo": "https://www.gazetadopovo.com.br/feed/rss/economia.xml",
    "g1": "https://g1.globo.com/rss/g1/economia/",
}
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"

TERMOS = [
    "pib", "recess", "juro", "selic", "copom", "banco central", "inflac", "ipca", "fiscal", "divida",
    "arcabouco", "meta", "deficit", "superavit", "dolar", "cambio", "ibovespa", "bolsa", "desemprego",
    "emprego", "caged", "pnad", "credito", "inadimpl", "fazenda", "haddad", "durigan", "tesouro",
    "orcamento", "gasto", "imposto", "tribut", "tarifa", "export", "import", "china", "petroleo",
    "commodit", "investimento", "industria", "varejo", "servicos", "ibc-br", "focus", "fmi", "rating",
    "cds", "risco", "economia", "crise", "mercado", "agro", "safra", "estados unidos", "fed",
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _limpa(s: str, n: int = 280) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def _data(entry) -> dt.datetime | None:
    for k in ("published", "updated", "pubDate"):
        v = entry.get(k)
        if v:
            try:
                d = parsedate_to_datetime(v)
                return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
            except (TypeError, ValueError):
                pass
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            return dt.datetime(*v[:6], tzinfo=dt.timezone.utc)
    return None


def url_antiga(url: str, publicado_em: str, dias: int = 45) -> bool:
    """Link cujo caminho traz uma data bem anterior à publicação.

    O ao-vivo do Valor reaproveita uma URL de 2023 todo dia: o feed a publica com data de
    hoje, mas o link mostra outro conteúdo amanhã e parece uma matéria antiga.
    """
    m = re.search(r"/(20\d\d)[/-](\d\d)(?:/(\d\d))?/", url)
    if not m:
        return False
    try:
        no_link = dt.date(int(m[1]), int(m[2]), int(m[3] or 1))
    except ValueError:
        return False
    return (dt.datetime.fromisoformat(publicado_em).date() - no_link).days > dias


def rss(desde: dt.datetime) -> tuple[list[dict], dict]:
    itens, status = [], {}
    for veiculo, url in FEEDS.items():
        try:
            r = requests.get(url, headers=UA, timeout=30)
            feed = feedparser.parse(r.content)
            n = 0
            for e in feed.entries:
                d = _data(e)
                if d is None or d < desde:
                    continue
                itens.append({"veiculo": veiculo, "titulo": _limpa(e.get("title", ""), 220),
                              "url": e.get("link", ""), "publicado_em": d.isoformat(timespec="minutes"),
                              "trecho": _limpa(e.get("summary", ""))})
                n += 1
            status[veiculo] = {"http": r.status_code, "itens_no_feed": len(feed.entries), "na_janela": n}
        except Exception as ex:  # noqa: BLE001
            status[veiculo] = {"erro": str(ex)[:200]}
    return itens, status


def gdelt(horas: int) -> tuple[list[dict], dict]:
    q = '(recessão OR "PIB" OR Selic OR "arcabouço fiscal" OR "dívida pública") sourcecountry:BR sourcelang:portuguese'
    try:
        r = requests.get(GDELT, params={"query": q, "mode": "artlist", "maxrecords": 100, "format": "json",
                                        "timespan": f"{horas}h", "sort": "datedesc"}, headers=UA, timeout=40)
        if r.status_code != 200 or not r.text.startswith("{"):
            return [], {"http": r.status_code, "erro": r.text[:120]}
        arts = r.json().get("articles", [])
    except Exception as ex:  # noqa: BLE001
        return [], {"erro": str(ex)[:200]}
    itens = []
    for a in arts:
        try:
            d = dt.datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        itens.append({"veiculo": a.get("domain", "GDELT"), "titulo": _limpa(a.get("title", ""), 220),
                      "url": a.get("url", ""), "publicado_em": d.isoformat(timespec="minutes"), "trecho": ""})
    return itens, {"http": 200, "itens": len(itens)}


def coletar(horas: int = 36, limite: int = 160) -> dict:
    agora = dt.datetime.now(dt.timezone.utc)
    desde = agora - dt.timedelta(hours=horas)
    itens, status = rss(desde)
    time.sleep(1)
    g, status["GDELT"] = gdelt(horas)
    itens += g
    vistos, unicos = set(), []
    for it in sorted(itens, key=lambda x: x["publicado_em"], reverse=True):
        chave = re.sub(r"[^a-z0-9 ]", "", _norm(it["titulo"]))[:90]
        if not it["titulo"] or not it["url"] or chave in vistos or url_antiga(it["url"], it["publicado_em"]):
            continue
        texto = _norm(it["titulo"] + " " + it["trecho"])
        if not any(t in texto for t in TERMOS):
            continue
        vistos.add(chave)
        unicos.append(it)
    # Teto por veículo para a cesta não ser dominada por quem publica mais.
    por_veiculo: dict[str, int] = {}
    cesta = []
    teto = max(12, limite // 6)
    for it in unicos:
        if por_veiculo.get(it["veiculo"], 0) >= teto:
            continue
        por_veiculo[it["veiculo"]] = por_veiculo.get(it["veiculo"], 0) + 1
        cesta.append(it)
        if len(cesta) >= limite:
            break
    for i, it in enumerate(cesta, 1):
        it["id"] = f"n{i:03d}"
    return {"coletado_em": agora.isoformat(timespec="seconds"), "janela_horas": horas,
            "status_fontes": status, "por_veiculo": por_veiculo, "itens": cesta}


def main(horas: int = 36) -> Path:
    res = coletar(horas)
    out = ROOT / "data" / "raw" / dt.date.today().isoformat() / "noticias.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"notícias: {len(res['itens'])} na cesta {res['por_veiculo']} -> {out}")
    return out


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 36)
