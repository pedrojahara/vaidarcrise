"""Imagem de prévia de links 1200×630: repete o topo do site (a plaquinha com a direção do risco e o desde quando)."""
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

    # O topo do site: a plaquinha com a seta e a direção.
    dr = ctx["dir"]
    cx, cy = 290, 290
    pl = _placa(300)
    im.paste(pl, (cx - pl.width // 2, cy - pl.height // 2), pl)
    tam = 44 if dr["longa"] else 56
    d.text((cx, cy - 40), dr["seta"], font=sans(96, 700), fill="#000000", anchor="mm")
    d.text((cx, cy + 46), dr["placa"], font=sans(tam, 700), fill="#000000", anchor="mm")

    x = 580
    d.text((x, 120), "Vai dar crise?", font=serifa(64), fill=TINTA)
    if dr["estado"] == "encolhendo":
        linhas = [("A economia", 56, 700), ("está encolhendo", 56, 700)]
    else:
        linhas = [("O risco de recessão", 44, 700), (f"está {dr['estado']}", 56, 700)]
    y = 222
    for txt, t, peso in linhas:
        d.text((x, y), txt, font=sans(t, peso), fill=TINTA)
        y += t + 14
    d.text((x, y + 6), dr["desde"].capitalize() + ".", font=sans(32), fill=META)
    pres = dr["pressoes"]
    ap = sum(1 for p in pres if p["palavra"] == "Apertou")
    fo = sum(1 for p in pres if p["palavra"] == "Folgou")
    nums = ["nenhuma", "uma", "duas", "três", "quatro", "cinco"]

    def conta(n: int, um: str, varios: str) -> str:
        return f"{nums[n]} {um if n <= 1 else varios}"
    d.text((x, y + 62), f"{conta(ap, 'apertou', 'apertaram').replace(' ', ' das 5 pressões ', 1).capitalize()}.",
           font=sans(30), fill=TINTA)
    d.text((x, y + 102), f"{conta(fo, 'folgou', 'folgaram').capitalize()}.", font=sans(30), fill=TINTA)

    d.line([(64, 548), (W - 64, 548)], fill=FIO, width=2)
    # A semana e o mês vão para o WhatsApp: a prévia diz que tipo de post é.
    tipo = ctx.get("tipo_nome") if ctx.get("tipo") in ("semana", "mes") else None
    d.text((64, 570), f"{tipo}, em poucas linhas." if tipo else "Medido com dados todo dia.", font=sans(26, 600 if tipo else 500),
           fill=TINTA if tipo else META)
    d.text((W - 64, 570), f"vaidarcrise.com.br  |  {ctx['data_curta'](ctx['dia'])}", font=sans(26, 600),
           fill=TINTA, anchor="ra")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    im.save(caminho, "PNG", optimize=True)
