"""Imagem de prévia de links 1200×630: repete o topo do site (plaquinha com o multiplicador e a seta)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTES = ROOT / "assets" / "fonts"
PAPEL, TINTA, META, FIO, PLACA = "#ffffff", "#1e1f21", "#62666b", "#e4e6e8", "#ffc20e"
SOBE, DESCE = "#c3102b", "#00733a"


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

    # O topo do site: a plaquinha com o multiplicador e a seta ao lado.
    cx, cy = 290, 300
    pl = _placa(300)
    im.paste(pl, (cx - pl.width // 2, cy - pl.height // 2), pl)
    d.text((cx, cy), ctx["mult_fmt"], font=sans(104, 700), fill="#000000", anchor="mm")

    x = 580
    d.text((x, 130), "Vai dar crise?", font=serifa(64), fill=TINTA)
    s_ = ctx.get("seta")
    if s_:
        cor = {"sobe": SOBE, "desce": DESCE}.get(s_["tipo"], TINTA)
        d.text((x, 228), f"{s_['simbolo']} {s_['palavra']}", font=sans(64, 700), fill=cor)
    linhas = ["Risco de recessão no Brasil nos", "próximos 12 meses, comparado", "ao de um ano normal."]
    for i, l in enumerate(linhas):
        d.text((x, 330 + i * 44), l, font=sans(32), fill=TINTA)

    d.line([(64, 548), (W - 64, 548)], fill=FIO, width=2)
    d.text((64, 570), f"Normal: {ctx['num'](ctx['normal'], 0)}% de chance em 12 meses. Hoje: {ctx['num'](ctx['curto'], 0)}%.",
           font=sans(26), fill=META)
    d.text((W - 64, 570), f"vaidarcrise.com.br  |  {ctx['data_curta'](ctx['dia'])}", font=sans(26, 600),
           fill=TINTA, anchor="ra")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im.save(caminho, "PNG", optimize=True)
