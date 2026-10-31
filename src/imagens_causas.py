"""Imagens fixas da aba /causas/: os desenhos do site e a prévia de link.

Roda à mão, quando um desenho muda; a atualização diária NÃO chama este arquivo.

- assets/causas/<nome>.png (desenhos escolhidos) -> docs/causas/img/<nome>.webp
- docs/causas/og.png: 1200 x 630, a prévia quando alguém manda o link da aba

Uso: python src/imagens_causas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

from og_image import _fonte, _placa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORIG = ROOT / "assets" / "causas"
SAIDA = ROOT / "docs" / "causas"
PAPEL, TINTA, META, FIO, PLACA, FUNDO = "#ffffff", "#1e1f21", "#62666b", "#e4e6e8", "#ffc20e", "#f4f5f6"
DESENHOS = ["padaria-cheia", "custos", "freio-1-juro", "freio-2-prazo", "freio-3-vende-menos", "freio-4-demissao",
            "cartao-rotativo", "familia-contas"]
APARAR = {"custos"}  # desenho largo dentro de um quadrado: corta o branco em volta


def serifa(t: int):
    return _fonte("CharisSIL-Bold.ttf", t)


def sans(t: int, p: int = 500):
    return _fonte("IBMPlexSans.ttf", t, p)


def quebra(d: ImageDraw.ImageDraw, texto: str, fonte, largura: int) -> list[str]:
    linhas, atual = [], ""
    for pal in texto.split():
        teste = f"{atual} {pal}".strip()
        if d.textlength(teste, font=fonte) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = pal
    return linhas + ([atual] if atual else [])


def escreve(d, xy, texto, fonte, largura, cor=TINTA, entre=1.3) -> int:
    """Escreve com quebra de linha e devolve o y logo abaixo do texto."""
    x, y = xy
    tam = fonte.size
    for linha in quebra(d, texto, fonte, largura):
        d.text((x, y), linha, font=fonte, fill=cor)
        y += round(tam * entre)
    return y


def desenho(nome: str, lado: int) -> Image.Image:
    im = Image.open(ORIG / f"{nome}.png").convert("RGB")
    return im.resize((lado, lado), Image.Resampling.LANCZOS)


def cartao(im: Image.Image, base: Image.Image, xy: tuple[int, int]) -> None:
    """Cola o desenho com o filete cinza do site em volta."""
    x, y = xy
    base.paste(im, (x, y))
    ImageDraw.Draw(base).rounded_rectangle([x - 1, y - 1, x + im.width, y + im.height], radius=10, outline=FIO, width=2)


def marca(base: Image.Image, d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    pl = _placa(34)
    base.paste(pl, (x, y), pl)
    d.text((x + pl.width + 12, y + pl.height / 2), "Vai dar crise?", font=serifa(34), fill=TINTA, anchor="lm")


def apara(im: Image.Image, folga: int = 36) -> Image.Image:
    x0, y0, x1, y1 = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 20 else 0).getbbox()
    return im.crop((max(0, x0 - folga), max(0, y0 - folga), min(im.width, x1 + folga), min(im.height, y1 + folga)))


def webp() -> None:
    (SAIDA / "img").mkdir(parents=True, exist_ok=True)
    for nome in DESENHOS:
        im = Image.open(ORIG / f"{nome}.png").convert("RGB")
        if nome in APARAR:
            im = apara(im)
        im = im.resize((900, round(900 * im.height / im.width)), Image.Resampling.LANCZOS)
        im.save(SAIDA / "img" / f"{nome}.webp", "WEBP", quality=80, method=6)
        print(f"{nome}.webp {im.width}x{im.height}")


def og() -> Path:
    W, H, M = 1200, 630, 64
    base = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(base)
    lado = 470
    cartao(desenho("padaria-cheia", lado), base, (W - M - lado, (H - lado) // 2 - 10))
    marca(base, d, M, 64)
    larg = W - 3 * M - lado + 20
    y = escreve(d, (M, 140), "O que causa uma recessão", serifa(60), larg, entre=1.12)
    escreve(d, (M, y + 18), "Por que os preços sobem, por que o juro tira emprego e por que a dívida vira bola de neve.",
            sans(28), larg, META, 1.35)
    d.text((M, H - 64), "vaidarcrise.com.br/causas", font=sans(26, 600), fill=TINTA, anchor="lm")
    caminho = SAIDA / "og.png"
    base.save(caminho, "PNG", optimize=True)
    return caminho


def main() -> None:
    webp()
    print(og())


if __name__ == "__main__":
    main()
