"""Estudo: Ibovespa diário da B3 (estatísticas do índice, ano a ano) desde 2002, para testar a bolsa na conta."""
import base64
import json
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent / "ibovespa_b3.json"
UA = {"User-Agent": "vaidarcrise.com.br (+https://github.com/pedrojahara/vaidarcrise)"}
res = {}
for ano in range(2002, 2027):
    q = base64.b64encode(json.dumps({"language": "pt-br", "index": "IBOV", "year": str(ano)}).encode()).decode()
    url = f"https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{q}"
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                res[str(ano)] = r.json()
                break
        except Exception as e:  # noqa: BLE001
            print(ano, e)
        time.sleep(3)
    print(ano, "ok" if str(ano) in res else "falhou")
    time.sleep(1)
OUT.write_text(json.dumps(res, ensure_ascii=False))
