"""Liga tudo o que o e-mail do fato do dia precisa fora do repositório, e pode rodar de novo sem estragar nada.

1. Resend: o domínio de envio (com o rastreio de abertura e de clique desligado) e o segmento da lista.
2. Cloudflare: os registros DNS que o Resend pede, o DMARC, o Email Routing (fato@ cai no e-mail do Pedro), a barreira
   contra robôs (Turnstile) e o serviço de inscrição (inscricao/index.js) em inscricao.vaidarcrise.com.br.

A barreira só passa a valer no serviço quando a chave pública dela está em config/newsletter.json ("turnstile"), porque
o formulário do site precisa mostrar o quadradinho antes de o serviço passar a exigir a resposta. Na primeira vez, o
script cria a barreira e mostra a chave pública; ela vai para o config, o site é gerado de novo e o script roda outra
vez com --so-worker.

Roda no Mac, que abre a API dos dois (a nuvem não abre). Os segredos vêm do ambiente e não ficam em arquivo:
  CLOUDFLARE_API_TOKEN  token do Cloudflare. Conta: Account Settings Read, Workers Scripts Edit, Email Routing Addresses
                        Edit, Turnstile Sites Edit. Zona: Zone Read, DNS Edit, Zone Settings Edit, Email Routing Rules
                        Edit, Workers Routes Edit.
  RESEND_API_KEY        chave do Resend com acesso total
  SEGREDO_INSCRICAO     opcional: troca a chave que assina o link de confirmação (sem ela, o script sorteia uma na
                        primeira vez, que fica só no Cloudflare)
  RESPOSTAS_PARA        o e-mail do Pedro que recebe as respostas dos leitores (fica só no Cloudflare)

Uso: python inscricao/publica.py [--so-worker] [--sem-routing]
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CF = "https://api.cloudflare.com/client/v4"
RS = "https://api.resend.com"
ZONA = "vaidarcrise.com.br"
HOST = f"inscricao.{ZONA}"
SCRIPT = "vaidarcrise-inscricao"
REGIAO = "sa-east-1"  # o Resend manda de São Paulo


def cfg() -> dict:
    return json.loads((ROOT / "config" / "newsletter.json").read_text())


def env(nome: str) -> str:
    v = os.environ.get(nome, "").strip()
    if not v:
        raise SystemExit(f"falta {nome} no ambiente")
    return v


class Api:
    def __init__(self, base: str, chave: str, cloudflare: bool):
        self.base, self.cf = base, cloudflare
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {chave}", "User-Agent": "vaidarcrise-publica"})

    def __call__(self, metodo: str, caminho: str, ok=(200, 201), **kw):
        for i in range(5):
            r = self.s.request(metodo, self.base + caminho, timeout=60, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** i)
                continue
            break
        dados = r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code not in ok or (self.cf and dados and dados.get("success") is False):
            raise RuntimeError(f"{metodo} {caminho}: {r.status_code} {r.text[:500]}")
        return dados.get("result", dados) if self.cf else dados


def registros_dns(cf: Api, zona: str) -> list[dict]:
    out, pag = [], 1
    while True:
        resp = cf.s.get(f"{CF}/zones/{zona}/dns_records", params={"per_page": 100, "page": pag}, timeout=60)
        r = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not r.get("success"):
            raise RuntimeError(f"GET /zones/{zona}/dns_records: {resp.status_code} {resp.text[:500]}")
        out += r["result"]
        if pag >= r["result_info"]["total_pages"]:
            return out
        pag += 1


def garante_registro(cf: Api, zona: str, existentes: list[dict], tipo: str, nome: str, conteudo: str,
                     prioridade: int | None = None) -> str:
    """Cria o registro se ainda não há um igual. Nunca apaga nem troca o que já existe: avisa."""
    nome = nome if nome.endswith(ZONA) else (f"{nome}.{ZONA}" if nome not in ("@", "") else ZONA)
    iguais = [r for r in existentes if r["type"] == tipo and r["name"] == nome]
    if any(r["content"].strip('"') == conteudo.strip('"') for r in iguais):
        return f"já existe: {tipo} {nome}"
    if tipo == "TXT" and conteudo.startswith("v=spf1") and any(r["content"].strip('"').startswith("v=spf1") for r in iguais):
        return f"ATENÇÃO: {nome} já tem outro SPF; juntar à mão com {conteudo}"
    if tipo == "TXT" and conteudo.startswith("v=DMARC1") and iguais:
        return f"já existe outro DMARC em {nome}; mantido"
    corpo = {"type": tipo, "name": nome, "content": conteudo, "ttl": 1, "proxied": False}
    if prioridade is not None:
        corpo["priority"] = prioridade
    cf("POST", f"/zones/{zona}/dns_records", json=corpo)
    return f"criado: {tipo} {nome}"


def resend_dominio(rs: Api) -> dict:
    doms = rs("GET", "/domains").get("data", [])
    d = next((x for x in doms if x["name"] == ZONA), None)
    if not d:
        d = rs("POST", "/domains", json={"name": ZONA, "region": REGIAO, "open_tracking": False, "click_tracking": False})
        print(f"Resend: domínio {ZONA} criado ({d['id']})")
    rs("PATCH", f"/domains/{d['id']}", json={"open_tracking": False, "click_tracking": False})
    return rs("GET", f"/domains/{d['id']}")


def resend_segmento(rs: Api, nome: str) -> str:
    segs = rs("GET", "/segments").get("data", [])
    s = next((x for x in segs if x["name"] == nome), None)
    if not s:
        s = rs("POST", "/segments", json={"name": nome})
        print(f"Resend: segmento {nome!r} criado")
    return s["id"]


def email_routing(cf: Api, conta: str, zona: str, existentes: list[dict], para: str, endereco: str) -> None:
    raiz_mx = [r for r in existentes if r["type"] == "MX" and r["name"] == ZONA]
    if raiz_mx and not all("mx.cloudflare.net" in r["content"] for r in raiz_mx):
        print(f"ATENÇÃO: {ZONA} já recebe e-mail em outro lugar ({[r['content'] for r in raiz_mx]}); Email Routing não ligado")
        return
    try:
        cf("POST", f"/zones/{zona}/email/routing/dns", json={})
    except RuntimeError as e:
        print(f"aviso: registros do Email Routing: {e}")
    try:
        cf("POST", f"/zones/{zona}/email/routing/enable", json={})
    except RuntimeError as e:
        print(f"aviso: ligar o Email Routing: {e}")
    dests = cf("GET", f"/accounts/{conta}/email/routing/addresses")
    if not any(d["email"].lower() == para.lower() for d in dests):
        cf("POST", f"/accounts/{conta}/email/routing/addresses", json={"email": para})
        print("Email Routing: o Cloudflare mandou um e-mail de confirmação para o destino das respostas")
    regras = cf("GET", f"/zones/{zona}/email/routing/rules")
    if not any(m.get("value") == endereco for r in regras for m in r.get("matchers", [])):
        cf("POST", f"/zones/{zona}/email/routing/rules", json={
            "name": "respostas do fato do dia", "enabled": True,
            "matchers": [{"type": "literal", "field": "to", "value": endereco}],
            "actions": [{"type": "forward", "value": [para]}]})
        print(f"Email Routing: {endereco} encaminha para o destino das respostas")


def turnstile(cf: Api, conta: str, c: dict) -> str | None:
    """Garante a barreira contra robôs e devolve a chave secreta, mas só quando o site já mostra o quadradinho."""
    nome = "vaidarcrise inscricao"
    ws = cf("GET", f"/accounts/{conta}/challenges/widgets", params={"per_page": 50})
    w = next((x for x in ws if x["name"] == nome), None)
    if not w:
        w = cf("POST", f"/accounts/{conta}/challenges/widgets",
               json={"name": nome, "domains": [ZONA], "mode": "managed", "region": "world"})
        print(f"Turnstile: barreira criada")
    chave = w["sitekey"]
    if c.get("turnstile") != chave:
        print(f'Turnstile: ponha "turnstile": "{chave}" em config/newsletter.json, gere o site e rode de novo com '
              "--so-worker; até lá o serviço não exige a barreira")
        return None
    return cf("GET", f"/accounts/{conta}/challenges/widgets/{chave}")["secret"]


def worker(cf: Api, conta: str, zona: str, existentes: list[dict], c: dict, segmento: str) -> None:
    """Publica o código e os valores, e guarda os segredos só no Cloudflare.

    O código vai com keep_bindings, que mantém os segredos já guardados no Worker; depois, cada segredo é gravado pela
    API de segredos. A chave que assina o link de confirmação (SEGREDO) é sorteada aqui na primeira vez e vive só no
    Cloudflare: trocá-la só invalida os links de confirmação ainda não usados. SEGREDO_INSCRICAO no ambiente troca a
    chave de propósito."""
    codigo = (ROOT / "inscricao" / "index.js").read_text()
    bindings = [
        {"type": "plain_text", "name": "REMETENTE", "text": c["remetente"]},
        {"type": "plain_text", "name": "RESPONDER", "text": c["responder_para"]},
        {"type": "plain_text", "name": "SEGMENTO", "text": segmento},
        # Até 5 pedidos de inscrição por minuto para cada endereço de internet.
        {"type": "ratelimit", "name": "LIMITE", "namespace_id": "1001", "simple": {"limit": 5, "period": 60}},
    ]
    meta = {"main_module": "index.js", "compatibility_date": "2025-09-01", "bindings": bindings,
            "keep_bindings": ["secret_text"]}

    def sobe(m: dict) -> None:
        cf("PUT", f"/accounts/{conta}/workers/scripts/{SCRIPT}",
           files={"metadata": (None, json.dumps(m), "application/json"),
                  "index.js": ("index.js", codigo, "application/javascript+module")})

    try:
        sobe(meta)
    except RuntimeError as e:
        if "ratelimit" not in str(e).lower():
            raise
        print("aviso: o limite por endereço não foi aceito; publicando sem ele")
        sobe({**meta, "bindings": [b for b in bindings if b["type"] != "ratelimit"]})

    def guarda(nome: str, valor: str) -> None:
        cf("PUT", f"/accounts/{conta}/workers/scripts/{SCRIPT}/secrets",
           json={"name": nome, "text": valor, "type": "secret_text"})

    ja = {x["name"] for x in cf("GET", f"/accounts/{conta}/workers/scripts/{SCRIPT}/secrets") or []}
    guarda("RESEND_API_KEY", env("RESEND_API_KEY"))
    if os.environ.get("SEGREDO_INSCRICAO", "").strip():
        guarda("SEGREDO", os.environ["SEGREDO_INSCRICAO"].strip())
    elif "SEGREDO" not in ja:
        guarda("SEGREDO", secrets.token_urlsafe(32))
        print("chave do link de confirmação sorteada e guardada só no Cloudflare")
    segredo_robo = turnstile(cf, conta, c)
    if segredo_robo:
        guarda("TURNSTILE_SECRET", segredo_robo)
    elif "TURNSTILE_SECRET" in ja:
        cf("DELETE", f"/accounts/{conta}/workers/scripts/{SCRIPT}/secrets/TURNSTILE_SECRET")
    print(f"Worker {SCRIPT} publicado")
    if any(r["name"] == HOST for r in existentes) and not any(
            d["hostname"] == HOST for d in cf("GET", f"/accounts/{conta}/workers/domains")):
        raise SystemExit(f"{HOST} já tem um registro DNS que não é do Worker; apague ou escolha outro nome")
    cf("PUT", f"/accounts/{conta}/workers/domains",
       json={"environment": "production", "hostname": HOST, "service": SCRIPT, "zone_id": zona})
    print(f"Worker em https://{HOST}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-worker", action="store_true", help="só publica o serviço de inscrição de novo")
    ap.add_argument("--sem-routing", action="store_true", help="não mexe no Email Routing")
    a = ap.parse_args()
    c = cfg()
    cf = Api(CF, env("CLOUDFLARE_API_TOKEN"), True)
    rs = Api(RS, env("RESEND_API_KEY"), False)
    contas = cf("GET", "/accounts")
    if len(contas) != 1:
        raise SystemExit(f"o token vê {len(contas)} contas; restrinja à conta do vaidarcrise")
    conta = contas[0]["id"]
    zona = cf("GET", "/zones", params={"name": ZONA})[0]["id"]
    existentes = registros_dns(cf, zona)
    segmento = resend_segmento(rs, c["segmento"])
    if not a.so_worker:
        d = resend_dominio(rs)
        for r in d.get("records", []):
            print(garante_registro(cf, zona, existentes, r["type"], r["name"], r["value"],
                                   int(r["priority"]) if r.get("priority") not in (None, "") else None))
        print(garante_registro(cf, zona, existentes, "TXT", "_dmarc", "v=DMARC1; p=none;"))
        rs("POST", f"/domains/{d['id']}/verify", json={})
        for _ in range(40):
            d = rs("GET", f"/domains/{d['id']}")
            if d.get("status") == "verified":
                break
            time.sleep(15)
        print(f"Resend: domínio {ZONA} {d.get('status')}")
        if not a.sem_routing:
            endereco = c["responder_para"]
            email_routing(cf, conta, zona, registros_dns(cf, zona), env("RESPOSTAS_PARA"), endereco)
    worker(cf, conta, zona, registros_dns(cf, zona), c, segmento)
    for _ in range(20):
        try:
            r = requests.get(f"https://{HOST}/saude", timeout=15)
            if r.ok and r.json().get("ok"):
                print("serviço de inscrição: ok")
                return
        except (requests.RequestException, ValueError):
            pass
        time.sleep(15)
    print("ATENÇÃO: o serviço de inscrição ainda não respondeu; o certificado do domínio pode levar alguns minutos")
    sys.exit(1)


if __name__ == "__main__":
    main()
