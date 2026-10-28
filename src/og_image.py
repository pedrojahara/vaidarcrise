"""Imagem de prévia de links 1200×630, com nota, variação e data."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTES = ROOT / "assets" / "fonts"
PAPEL, TINTA, TINTA2, QUENTE, MORNO, FRIO, LINHA = "#f4efe4", "#1d1a16", "#5b544a", "#b8361e", "#d98a2b", "#3f7d5c", "#d6ccb8"


def _fonte(nome: str, tam: int, peso: int, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTES / nome), tam)
    eixos = []
    for a in f.get_variation_axes():
        n = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
        eixos.append({"Weight": peso, "Optical Size": opsz or min(144, tam), "Width": 100,
                      "Softness": 0, "Wonky": 0}.get(n, a["default"]))
    f.set_variation_by_axes(eixos)
    return f


def _grad(x0: int, x1: int) -> list[tuple[int, int, int]]:
    def rgb(h: str) -> tuple[int, int, int]:
        return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
    a, b, c = rgb(FRIO), rgb(MORNO), rgb(QUENTE)
    out = []
    for i in range(x1 - x0):
        t = i / (x1 - x0 - 1)
        p, q, u = (a, b, t * 2) if t < .5 else (b, c, (t - .5) * 2)
        out.append(tuple(int(p[k] + (q[k] - p[k]) * u) for k in range(3)))
    return out


def gerar(caminho: Path, ctx: dict) -> None:
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(im)
    titulo = _fonte("Fraunces.ttf", 64, 900)
    numero = _fonte("Fraunces.ttf", 300, 900)
    frase = _fonte("Fraunces.ttf", 40, 500, 36)
    sans = _fonte("IBMPlexSans.ttf", 26, 500)
    sans_b = _fonte("IBMPlexSans.ttf", 26, 600)
    peq = _fonte("IBMPlexSans.ttf", 22, 500)

    d.text((64, 52), "PROBABILIDADE DE RECESSÃO NO BRASIL ATÉ 2030", font=sans_b, fill=QUENTE)
    d.text((64, 88), "Vai dar crise?", font=titulo, fill=TINTA)

    n = str(ctx["nota_int"])
    d.text((52, 150), n, font=numero, fill=QUENTE)
    nw = d.textlength(n, font=numero)
    d.text((52 + nw + 8, 352), "%", font=_fonte("Fraunces.ttf", 90, 700), fill=TINTA2)

    x = 64 + nw + 110
    linhas = ["Em 100 Brasis", "como este,", f"{n} entram em", "recessão até 2030."]
    for i, l in enumerate(linhas):
        d.text((max(x, 600), 196 + i * 50), l, font=frase, fill=TINTA)

    # Medidor
    x0, x1, y = 64, W - 64, 492
    for i, c in enumerate(_grad(x0, x1)):
        d.line([(x0 + i, y), (x0 + i, y + 16)], fill=c)
    px = x0 + (x1 - x0) * ctx["nota"] / 100
    bx = x0 + (x1 - x0) * ctx["base"] / 100
    d.line([(bx, y - 10), (bx, y + 26)], fill=TINTA, width=3)
    d.text((bx, y - 14), f"história: {ctx['num'](ctx['base'], 0)}", font=peq, fill=TINTA2, anchor="md")
    d.ellipse([px - 16, y - 8, px + 16, y + 24], fill=PAPEL, outline=TINTA, width=5)
    for v in (0, 50, 100):
        tx = x0 + (x1 - x0) * v / 100
        d.text((tx, y + 34), str(v), font=peq, fill=TINTA2, anchor="ma")

    var = ctx.get("variacao")
    if var:
        txt = f"{ctx['sinal'](var['delta'])} pontos desde a última atualização"
    else:
        txt = f"Só a história dá {ctx['num'](ctx['base'], 0)}; dados e notícias explicam o resto"
    d.text((64, 572), txt, font=sans, fill=TINTA2)
    d.text((W - 64, 572), f"vaidarcrise.com.br · {ctx['data_curta'](ctx['dia'])}", font=sans_b, fill=TINTA, anchor="ra")
    d.line([(64, 556), (W - 64, 556)], fill=LINHA, width=2)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im.save(caminho, "PNG", optimize=True)
