"""Datas importantes: divulgações do IBGE (API de calendário) e decisões de juros (config/datas.json).

A busca no IBGE roda na atualização diária e grava data/calendario.json; o site só lê o
arquivo. Se a API falhar, ficam as datas já gravadas e as de reserva da config.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ARQUIVO = ROOT / "data" / "calendario.json"
CONFIG = ROOT / "config" / "datas.json"
API = "https://servicodados.ibge.gov.br/api/v3/calendario/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; vaidarcrise.com.br; +https://github.com/pedrojahara/vaidarcrise)"}
PRODUTOS = {
    "Sistema de Contas Nacionais Trimestrais": "pib",
    "Índice Nacional de Preços ao Consumidor Amplo": "ipca",
    "Índice Nacional de Preços ao Consumidor Amplo 15": "ipca15",
    "Pesquisa Nacional por Amostra de Domicílios Contínua Mensal": "pnad",
    "Pesquisa Industrial Mensal: Produção Física - Brasil": "pim",
    "Pesquisa Mensal de Comércio": "pmc",
}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
JUROS = {"copom": "Copom decide a Selic", "fed": "Fed decide os juros"}


def _mes(d: dt.date, atras: int) -> str:
    return MESES[(d.month - 1 - atras) % 12]


def rotulo(tipo: str, d: dt.date) -> str:
    """O mês de referência sai da data de divulgação, pelo atraso habitual de cada pesquisa."""
    if tipo == "pib":
        q = (d.month - 1) // 3 or 4
        return f"PIB do {q}º trimestre (IBGE)"
    return {"ipca": f"Inflação de {_mes(d, 1)}, IPCA (IBGE)",
            "ipca15": f"Prévia da inflação de {_mes(d, 0)}, IPCA-15 (IBGE)",
            "pnad": f"Desemprego até {_mes(d, 1)} (IBGE)",
            "pim": f"Produção industrial de {_mes(d, 2)} (IBGE)",
            "pmc": f"Vendas do varejo de {_mes(d, 2)} (IBGE)"}.get(tipo, tipo)


def buscar_ibge(de: dt.date, ate: dt.date) -> list[dict]:
    r = requests.get(API, params={"de": de.strftime("%m-%d-%Y"), "ate": ate.strftime("%m-%d-%Y"), "qtd": 200},
                     headers=UA, timeout=40)
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        tipo = PRODUTOS.get((it.get("titulo") or "").strip())
        if tipo:
            d = dt.datetime.strptime(it["data_divulgacao"][:10], "%d/%m/%Y").date()
            out.append({"data": d.isoformat(), "tipo": tipo})
    return out


def atualizar(hoje: dt.date) -> None:
    """Junta as divulgações dos próximos 90 dias ao arquivo. Nunca levanta exceção."""
    salvo = json.loads(ARQUIVO.read_text()) if ARQUIVO.exists() else {"ibge": []}
    try:
        novos = buscar_ibge(hoje, hoje + dt.timedelta(days=90))
    except Exception as e:  # noqa: BLE001
        print(f"calendário do IBGE: falhou ({str(e)[:120]}); ficam as datas já gravadas")
        return
    # O que já passou fica (páginas antigas mostram as datas da época); o futuro vem da API.
    passado = [x for x in salvo["ibge"] if x["data"] < hoje.isoformat()]
    ibge = sorted({(x["data"], x["tipo"]) for x in passado + novos})
    ARQUIVO.write_text(json.dumps({"atualizado_em": hoje.isoformat(),
                                   "ibge": [{"data": d, "tipo": t} for d, t in ibge]}, indent=1))
    print(f"calendário do IBGE: {len(novos)} divulgações nos próximos 90 dias")


def carregar() -> list[dict]:
    cfg = json.loads(CONFIG.read_text())
    salvo = json.loads(ARQUIVO.read_text())["ibge"] if ARQUIVO.exists() else []
    ibge = {(x["data"], x["tipo"]) for x in cfg["ibge_reserva"] + salvo}
    juros = {(x["data"], x["tipo"]) for x in cfg["juros"]}
    return [{"data": d, "tipo": t} for d, t in sorted(ibge | juros)]


def janela(eventos: list[dict], dia: dt.date) -> list[dict]:
    """De hoje até 30 dias à frente ou até o próximo PIB, o que vier depois, e daí até a decisão de juros seguinte."""
    futuros = [e for e in eventos if e["data"] >= dia.isoformat()]
    pib = next((e["data"] for e in futuros if e["tipo"] == "pib"), None)
    fim = max((dia + dt.timedelta(days=30)).isoformat(), pib or "")
    juros = next((e["data"] for e in futuros if e["tipo"] in JUROS and e["data"] >= fim), None)
    if juros and juros <= (dt.date.fromisoformat(fim) + dt.timedelta(days=45)).isoformat():
        fim = juros
    linhas: dict[str, list[str]] = {}
    for e in futuros:
        if e["data"] <= fim:
            linhas.setdefault(e["data"], []).append(e["tipo"])
    out = []
    for d, tipos in linhas.items():
        data = dt.date.fromisoformat(d)
        decide = [t for t in tipos if t in JUROS]
        if len(decide) > 1:
            out.append({"data": d, "dia": f"{data.day}/{data.month}", "rotulo": "Copom e Fed decidem os juros",
                        "tipo": "juros"})
        elif decide:
            out.append({"data": d, "dia": f"{data.day}/{data.month}", "rotulo": JUROS[decide[0]], "tipo": "juros"})
        for t in tipos:
            if t not in JUROS:
                out.append({"data": d, "dia": f"{data.day}/{data.month}", "rotulo": rotulo(t, data), "tipo": t})
    return out
