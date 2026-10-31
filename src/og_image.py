"""Imagem de prévia de links 1200×630: repete o topo do site (plaquinha com o nível e a escala de cinco níveis)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTES = ROOT / "assets" / "fonts"
PAPEL, TINTA, META, FIO, PLACA = "#ffffff", "#1e1f21", "#62666b", "#e4e6e8", "#ffc20e"


def _fonte(nome: str, tam: int, peso: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTES / nome), tam)
    if peso is not None:
        try:
            eixos = f.get_variation_axes()
        except OSError:  # fonte sem eixos variáveis
            return f
        f.set_variation_by_axes([peso if (a["name"] in (b"Weight", "Weight")) else a["default"] for a in eixos])
    return f


def _placa(lado: int) -> Image.Image:
    """A plaquinha do site em escala: quadrado amarelo de cantos redondos, filete preto por dentro, girado 45°."""
    k = lado / 78  # o desenho do CSS tem 78 px
    im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=round(9 * k), fill=PLACA)
    a, b = round(4 * k), round(7 * k)
    d.rounded_rectangle([a, a, lado - 1 - a, lado - 1 - a], radius=round(6 * k), fill="#000000")
    d.rounded_rectangle([b, b, lado - 1 - b, lado - 1 - b], radius=round(4 * k), fill=PLACA)
    return im.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)


def gerar(caminho: Path, ctx: dict) -> None:
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(im)
    serifa = lambda t: _fonte("CharisSIL-Bold.ttf", t)  # noqa: E731
    sans = lambda t, p=500: _fonte("IBMPlexSans.ttf", t, p)  # noqa: E731

    # O topo do site: a plaquinha com o nível.
    niv = ctx["nivel"]
    cx, cy = 290, 290
    pl = _placa(300)
    im.paste(pl, (cx - pl.width // 2, cy - pl.height // 2), pl)
    palavras = niv["nome"].split(" ") if niv["nome"].startswith("Muito") else [niv["nome"]]
    tam = 66 if len(palavras) == 1 else 58
    for i, pal in enumerate(palavras):
        d.text((cx, cy + (i - (len(palavras) - 1) / 2) * tam * 1.05), pal, font=sans(tam, 700), fill="#000000", anchor="mm")

    x = 580
    d.text((x, 120), "Vai dar crise?", font=serifa(64), fill=TINTA)
    d.text((x, 222), niv["rot"].capitalize() if niv["nome"] == "Normal" else f"{niv['nome']} do normal",
           font=sans(56, 700), fill=TINTA)
    for i, l in enumerate(["de recessão no Brasil", "nos próximos 12 meses."]):
        d.text((x, 310 + i * 44), l, font=sans(32), fill=TINTA)
    # A escala de cinco níveis, com o de hoje marcado.
    nomes = niv["nomes"]
    x0, x1, y = x, W - 64, 430
    w = (x1 - x0 - 4 * 6) / 5
    for i, n in enumerate(nomes):
        a = x0 + i * (w + 6)
        d.rectangle([a, y, a + w, y + 14], fill=TINTA if i == niv["indice"] else FIO)
        d.text((a + w / 2, y + 26), n, font=sans(19, 700 if i == niv["indice"] else 500),
               fill=TINTA if i == niv["indice"] else META, anchor="ma")

    d.line([(64, 548), (W - 64, 548)], fill=FIO, width=2)
    # A semana e o mês vão para o WhatsApp: a prévia diz que tipo de post é.
    tipo = ctx.get("tipo_nome") if ctx.get("tipo") in ("semana", "mes") else None
    d.text((64, 570), f"{tipo}, em poucas linhas." if tipo else "Medido com dados todo dia.", font=sans(26, 600 if tipo else 500),
           fill=TINTA if tipo else META)
    d.text((W - 64, 570), f"vaidarcrise.com.br  |  {ctx['data_curta'](ctx['dia'])}", font=sans(26, 600),
           fill=TINTA, anchor="ra")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im.save(caminho, "PNG", optimize=True)
