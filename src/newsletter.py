"""O fato do dia por e-mail: o mesmo post da página do dia, mandado à lista do Resend depois que a página está no ar.

A lista e o envio ficam no Resend (Broadcasts, grátis até 1.000 contatos); a inscrição, com a confirmação por e-mail,
num Worker do Cloudflare (inscricao/). O e-mail sai do mesmo post que o site mostra (src/build_site.py, post_de) e
do mesmo topo (direcao_ctx), com o molde templates/email.html, e não passa por IA nenhuma: o texto é o que já passou
pelo editor. Regras do envio (Pedro, 7 e 10/11/2026):

- só sai com o texto do dia (post.ok); dia sem texto não manda nada, porque um e-mail dizendo que o texto não saiu é
  pior que silêncio;
- nunca dois no mesmo dia, nem com ./run.sh --forcar: o registro local (logs/envios.json) e o nome do envio no Resend
  ("fato-AAAA-MM-DD") barram o segundo;
- se o texto for refeito mais tarde no mesmo dia, o e-mail sai nessa hora, até as 20h;
- espera a página do dia estar no ar (o GitHub Pages leva uns minutos depois do push), para o link não dar em nada;
- o rastreio de abertura e de clique fica desligado no domínio: o site não mede quem lê.

A chave do Resend vem de RESEND_API_KEY (no Mac, o run.sh tira do Chaves) e nunca vai para o repositório, que é público.

Uso:
  newsletter.py --hoje               manda o post de hoje à lista (o run.sh chama depois do segundo push, quando
                                     "envio_diario" está ligado em config/newsletter.json)
  newsletter.py --previa [DIA]       grava o e-mail de um dia em logs/email-DIA.html, para ver no navegador
  newsletter.py --teste EMAIL [DIA]  manda o e-mail de um dia só para um endereço, fora da lista
  newsletter.py --saude              confere a chave do Resend, o domínio e o serviço de inscrição
  newsletter.py --limpa              apaga da lista quem saiu (a LGPD pede apagar o dado quando o consentimento acaba)
  newsletter.py --imagens            refaz as imagens do e-mail em docs/email/ (o build_site.py já faz)
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site  # noqa: E402
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "newsletter.json"
ENVIOS = ROOT / "logs" / "envios.json"
API = "https://api.resend.com"
SAIR = "{{{RESEND_UNSUBSCRIBE_URL}}}"
CORES = {"mais": "#c3102b", "menos": "#00733a", "igual": "#1e1f21"}
HORA_LIMITE = 20


def config() -> dict:
    return json.loads(CONFIG.read_text())


# ------------------------------------------------------------------ o e-mail
def _link_email(m) -> Markup:
    """Os links dos termos técnicos (a Wikipédia) com o estilo dentro do elemento, porque o Gmail ignora o <style>."""
    return Markup(str(m).replace('<a class="termo"',
                                 '<a class="termo e-tinta" style="color:#1e1f21;text-decoration:underline;'
                                 'text-decoration-style:dotted;text-decoration-color:#62666b"'))


def _texto(m) -> str:
    """Um parágrafo do post em texto puro, para a versão sem HTML."""
    t = re.sub(r"<[^>]+>", "", str(m))
    return html.unescape(t)


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["link_email"] = _link_email
    env.filters["texto"] = _texto
    return env


def rodada_do_dia(dia: str) -> dict | None:
    """A última rodada de um dia (a mesma que o site mostra na página do dia)."""
    arqs = sorted(glob.glob(str(ROOT / "runs" / f"{dia}T*.json")))
    return json.loads(Path(arqs[-1]).read_text()) if arqs else None


def montar(dia: str) -> dict | None:
    """O e-mail de um dia: assunto, HTML, texto puro e o que o envio precisa conferir. Sem texto do dia, None."""
    r = rodada_do_dia(dia)
    if not r or not (r.get("post") or {}).get("ok"):
        return None
    cfg = model.carregar_config()
    cal = model.carregar_calibracao()
    post = build_site.post_de(r, cfg)
    dr = build_site.direcao_ctx(r, cfg, cal)
    env = _env()
    ctx = {"post": post, "dir": dr, "site": build_site.SITE, "sair_url": SAIR, "cores": CORES,
           "aberta": bool(config().get("inscricao_aberta"))}  # o "Recebeu de alguém?" só com a lista aberta
    corpo = env.get_template("email.html").render(**ctx)
    # No celular, o "R$" não fica no fim de uma linha e o número no começo da outra (como no site).
    corpo = re.sub(r"\b(R|US)\$ (?=\d)", "\\1$\u00a0", corpo)
    texto = env.get_template("email.txt").render(**ctx)
    return {"dia": dia, "assunto": post["titulo"], "html": corpo, "texto": texto, "url": post["url"],
            "titulo": post["titulo"], "tipo": post["tipo"]}


# ------------------------------------------------------------------ as imagens do e-mail
def imagens(destino: Path) -> None:
    """A plaquinha de cada direção e a marca do cabeçalho, em PNG: o e-mail não gira um quadrado com CSS como o site.
    Ficam em docs/email/ e são feitas em 3 vezes o tamanho de exibição, para ficarem nítidas no celular."""
    from PIL import Image, ImageDraw

    import og_image
    destino.mkdir(parents=True, exist_ok=True)
    k = 3
    for estado, (seta, _cls, nome) in build_site.ESTADO.items():
        # A placa do celular (base.html, até 620 px): quadrado de 72 px girado, seta de 22 px e palavra de 12,5 px.
        lado = 102 * k
        im = Image.new("RGBA", (lado, lado), (255, 255, 255, 0))
        pl = og_image._placa(round(72 * k))
        im.paste(pl, ((lado - pl.width) // 2, (lado - pl.height) // 2), pl)
        d = ImageDraw.Draw(im)
        longa = len(nome) > 8
        c = lado // 2
        d.text((c, c - 8 * k), seta, font=og_image._fonte("IBMPlexSans.ttf", 22 * k, 700), fill="#000000", anchor="mm")
        d.text((c, c + 12 * k), nome, font=og_image._fonte("IBMPlexSans.ttf", round((9.5 if longa else 12.5) * k), 800),
               fill="#000000", anchor="mm")
        im.save(destino / f"placa-{estado}.png", optimize=True)
    # A marca do cabeçalho: o quadrado de 18 px girado (a .mini do site).
    lado = 26 * k
    im = Image.new("RGBA", (lado, lado), (255, 255, 255, 0))
    mini = og_image._placa(round(18 * k))
    im.paste(mini, ((lado - mini.width) // 2, (lado - mini.height) // 2), mini)
    im.save(destino / "marca.png", optimize=True)


# ------------------------------------------------------------------ o Resend
class Resend:
    """O pedaço da API do Resend que o envio usa. A chave vem de RESEND_API_KEY."""

    def __init__(self, chave: str | None = None):
        self.chave = chave or os.environ.get("RESEND_API_KEY", "")
        if not self.chave:
            raise SystemExit("falta RESEND_API_KEY (no Mac, o run.sh tira do Chaves: serviço vaidarcrise-resend)")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.chave}", "Content-Type": "application/json",
                               "User-Agent": "vaidarcrise-newsletter"})

    def pedir(self, metodo: str, caminho: str, corpo: dict | None = None, tentativas: int = 4) -> dict:
        for i in range(tentativas):
            resp = self.s.request(metodo, API + caminho, json=corpo, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:  # limite de 2 pedidos por segundo, ou falha deles
                time.sleep(2 ** i)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Resend {metodo} {caminho}: {resp.status_code} {resp.text[:300]}")
            return resp.json() if resp.content else {}
        raise RuntimeError(f"Resend {metodo} {caminho}: sem resposta depois de {tentativas} tentativas")

    def lista(self, caminho: str) -> list[dict]:
        """Uma listagem inteira, página a página."""
        out, depois = [], None
        while True:
            q = f"?limit=100" + (f"&after={depois}" if depois else "")
            r = self.pedir("GET", caminho + q)
            dados = r.get("data") or []
            out += dados
            if not r.get("has_more") or not dados:
                return out
            depois = dados[-1]["id"]

    def segmento(self, nome: str) -> str:
        """O id do segmento da lista pelo nome (config/newsletter.json, segmento)."""
        for s in self.lista("/segments"):
            if s.get("name") == nome:
                return s["id"]
        raise RuntimeError(f"o segmento {nome!r} não existe no Resend")

    def envio_do_dia(self, nome: str) -> dict | None:
        return next((b for b in self.lista("/broadcasts") if b.get("name") == nome), None)


# ------------------------------------------------------------------ o envio
def _envios() -> dict:
    try:
        return json.loads(ENVIOS.read_text())
    except (OSError, ValueError):
        return {}


def _anota(dia: str, info: dict) -> None:
    e = _envios()
    e[dia] = info
    ENVIOS.parent.mkdir(exist_ok=True)
    ENVIOS.write_text(json.dumps(e, ensure_ascii=False, indent=1))


def site_no_ar(email: dict, espera_min: int) -> bool:
    """Espera a página do dia mostrar o post: o push só publica depois do build do
    GitHub Pages. Confere pelo título, que é o que muda de um dia para o outro."""
    fim = time.time() + espera_min * 60
    marcas = [html.escape(email["titulo"], quote=False)]
    while True:
        try:
            r = requests.get(email["url"], timeout=20, headers={"User-Agent": "vaidarcrise-newsletter",
                                                                "Cache-Control": "no-cache"},
                             params={"_": int(time.time())})
            if r.ok and all(m in r.text for m in marcas):
                return True
        except requests.RequestException:
            pass
        if time.time() > fim:
            return False
        time.sleep(30)


def enviar(dia: str, agora: dt.datetime | None = None, esperar: bool = True) -> str:
    """Manda o post de um dia à lista. Devolve o que aconteceu, numa linha, para o registro do run.sh."""
    agora = agora or dt.datetime.now()
    cfg = config()
    if dia != agora.date().isoformat():
        return f"não enviado: {dia} não é hoje"
    if agora.hour >= HORA_LIMITE:
        return f"não enviado: passou das {HORA_LIMITE}h, e o e-mail do dia não sai à noite"
    if dia in _envios():
        return f"não enviado: o e-mail de {dia} já saiu ({_envios()[dia].get('id')})"
    email = montar(dia)
    if not email:
        return f"não enviado: {dia} não tem texto"
    api = Resend()
    nome = f"fato-{dia}"
    ja = api.envio_do_dia(nome)
    if ja and ja.get("status") in ("sent", "queued", "scheduled", "sending"):
        _anota(dia, {"id": ja["id"], "quando": agora.isoformat(timespec="seconds"), "obs": "já estava no Resend"})
        return f"não enviado: o Resend já tem o envio {nome} ({ja.get('status')})"
    if esperar and not site_no_ar(email, int(cfg.get("espera_site_min", 15))):
        return f"não enviado: a página {email['url']} não mostrou o post de hoje em {cfg.get('espera_site_min', 15)} min"
    seg = api.segmento(cfg["segmento"])
    if ja:  # rascunho de uma tentativa que caiu no meio: reaproveita
        bid = ja["id"]
    else:
        bid = api.pedir("POST", "/broadcasts", {
            "segment_id": seg, "name": nome, "from": cfg["remetente"], "reply_to": cfg["responder_para"],
            "subject": email["assunto"], "html": email["html"], "text": email["texto"]})["id"]
    api.pedir("POST", f"/broadcasts/{bid}/send", {})
    _anota(dia, {"id": bid, "quando": agora.isoformat(timespec="seconds"), "assunto": email["assunto"]})
    return f"enviado: {nome} ({bid}), {email['assunto']}"


def teste(para: str, dia: str) -> str:
    """O e-mail de um dia para um endereço só, fora da lista e sem link de sair (é um teste)."""
    email = montar(dia)
    if not email:
        return f"{dia} não tem texto"
    cfg = config()
    corpo = email["html"].replace(SAIR, f"{build_site.SITE}/inscricao/")
    r = Resend().pedir("POST", "/emails", {"from": cfg["remetente"], "to": [para], "reply_to": cfg["responder_para"],
                                           "subject": f"[teste] {email['assunto']}", "html": corpo,
                                           "text": email["texto"].replace(SAIR, f"{build_site.SITE}/inscricao/")})
    return f"teste enviado para {para}: {r.get('id')}"


def saude() -> list[str]:
    """O que impede o e-mail de amanhã de sair. Lista vazia: tudo certo."""
    cfg = config()
    problemas = []
    try:
        api = Resend()
        dom = cfg["remetente"].split("@")[-1].strip(">\" ")
        doms = api.lista("/domains")
        d = next((x for x in doms if x.get("name") == dom), None)
        if not d:
            problemas.append(f"o domínio {dom} não está no Resend")
        elif d.get("status") != "verified":
            problemas.append(f"o domínio {dom} está {d.get('status')} no Resend")
        api.segmento(cfg["segmento"])
    except (RuntimeError, requests.RequestException, SystemExit) as e:
        problemas.append(f"Resend: {e}")
    try:
        r = requests.get(cfg["servico"] + "/saude", timeout=20, headers={"User-Agent": "vaidarcrise-newsletter"})
        if not (r.ok and r.json().get("ok")):
            problemas.append(f"o serviço de inscrição respondeu {r.status_code}: {r.text[:200]}")
    except (requests.RequestException, ValueError) as e:
        problemas.append(f"o serviço de inscrição não respondeu ({e.__class__.__name__})")
    return problemas


def limpa() -> str:
    """Apaga da lista quem saiu: o endereço não serve para mais nada depois que a pessoa retira o consentimento."""
    api = Resend()
    saiu = [c for c in api.lista("/contacts") if c.get("unsubscribed")]
    for c in saiu:
        api.pedir("DELETE", f"/contacts/{c['id']}")
    return f"apagados {len(saiu)} contatos que saíram da lista"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hoje", action="store_true")
    g.add_argument("--previa", nargs="?", const="", metavar="DIA")
    g.add_argument("--teste", metavar="EMAIL")
    g.add_argument("--saude", action="store_true")
    g.add_argument("--limpa", action="store_true")
    g.add_argument("--imagens", action="store_true")
    ap.add_argument("dia", nargs="?", help="AAAA-MM-DD (padrão: o último dia com rodada)")
    a = ap.parse_args()
    ultimo = sorted(Path(p).name[:10] for p in glob.glob(str(ROOT / "runs" / "*.json")))[-1]
    if a.hoje:
        saida = enviar(dt.date.today().isoformat())
        print(saida)
        # O que é problema (página que não entrou no ar) sai com erro, para o run.sh avisar o Pedro; dia sem texto ou
        # e-mail que já saiu não são problema.
        sys.exit(1 if saida.startswith("não enviado: a página") else 0)
    elif a.previa is not None:
        dia = a.previa or a.dia or ultimo
        e = montar(dia)
        if not e:
            raise SystemExit(f"{dia} não tem texto")
        saida = ROOT / "logs" / f"email-{dia}.html"
        saida.parent.mkdir(exist_ok=True)
        saida.write_text(e["html"])
        print(saida)
    elif a.teste:
        print(teste(a.teste, a.dia or ultimo))
    elif a.saude:
        p = saude()
        print("\n".join(p) if p else "ok")
        sys.exit(1 if p else 0)
    elif a.limpa:
        print(limpa())
    elif a.imagens:
        imagens(build_site.DOCS / "email")


if __name__ == "__main__":
    main()
