"""Imagens fixas da aba /causas/: desenhos do site, o resumo em uma imagem e a prévia de link.

Roda à mão, uma vez; a atualização diária NÃO chama este arquivo. O resumo mostra a
situação do dia em que foi feito (31/10/2026) e fica assim até alguém decidir refazê-lo.

- assets/causas/<nome>.png (desenhos escolhidos) -> docs/causas/img/<nome>.webp
- docs/causas/resumo-<dia>.png: 1080 x 1560, para baixar e mandar no WhatsApp
- docs/causas/og.png: 1200 x 630, a prévia quando alguém manda o link da aba

Uso: python src/resumo_causas.py 2026-10-31
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

import causas  # noqa: E402
from og_image import _fonte, _placa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORIG = ROOT / "assets" / "causas"
SAIDA = ROOT / "docs" / "causas"
PAPEL, TINTA, META, FIO, PLACA, FUNDO = "#ffffff", "#1e1f21", "#62666b", "#e4e6e8", "#ffc20e", "#f4f5f6"
ATENCAO = "#965a00"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
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


def resumo(dia: str, perguntas: list[dict]) -> Path:
    W, H, M = 1080, 1560, 60
    base = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(base)
    marca(base, d, M, 48)
    y = escreve(d, (M, 118), "O que causa uma recessão", serifa(64), W - 2 * M) + 8
    y = escreve(d, (M, y + 4), "Quase sempre, o mesmo caminho:", sans(32), W - 2 * M, META) + 18

    passos = [("padaria-cheia", "Gente demais para pouco pão: o preço sobe."),
              ("freio-1-juro", "O Banco Central sobe o juro para segurar os preços."),
              ("freio-3-vende-menos", "Comprar a prazo fica caro, e as vendas caem."),
              ("freio-4-demissao", "Sem venda, vem a demissão. Muitas juntas são a recessão.")]
    lado, col = 200, (W - 2 * M - 24) // 2
    for i, (nome, txt) in enumerate(passos):
        x0, y0 = M + (i % 2) * (col + 24), y + (i // 2) * (lado + 26)
        cartao(desenho(nome, lado), base, (x0, y0))
        tx = x0 + lado + 18
        d.text((tx, y0 + 2), str(i + 1), font=sans(30, 700), fill=TINTA)
        escreve(d, (tx, y0 + 44), txt, sans(27, 500), col - lado - 18, entre=1.28)
    y += 2 * lado + 26 + 30

    cartao(desenho("cartao-rotativo", 150), base, (M, y))
    ty = escreve(d, (M + 172, y + 6), "E a dívida do governo?", sans(30, 700), W - 2 * M - 172)
    escreve(d, (M + 172, ty + 2), "Com juro alto, ela cresce sozinha, como o rotativo do cartão.", sans(28), W - 2 * M - 172)
    y += 150 + 34

    d.line([(M, y), (W - M, y)], fill=FIO, width=2)
    y += 26
    dd = f"{int(dia[8:10])} de {MESES[int(dia[5:7]) - 1]} de {dia[:4]}"
    y = escreve(d, (M, y), f"Como está hoje, {dd}", serifa(36), W - 2 * M) + 8
    for q in perguntas:
        cor = {"atencao": ATENCAO, "meio": TINTA}.get(q["tom"], META)
        pil = sans(26, 700)
        wp = d.textlength(q["resposta"], font=pil) + 32
        d.rounded_rectangle([W - M - wp, y, W - M, y + 42], radius=21, outline=cor, width=3)
        d.text((W - M - wp / 2, y + 21), q["resposta"], font=pil, fill=cor, anchor="mm")
        yq = escreve(d, (M, y + 2), q["pergunta"], sans(30, 700), W - 2 * M - wp - 20)
        frases = [f.rstrip(".") + "." for f in q["texto"].split(". ")]
        linha = frases[0] if len(frases[0].split()) >= 12 or len(frases) == 1 else f"{frases[0]} {frases[1]}"
        y = escreve(d, (M, max(yq, y + 46) + 2), linha, sans(25), W - 2 * M, META, 1.32) + 16

    d.line([(M, H - 92), (W - M, H - 92)], fill=FIO, width=2)
    d.text((M, H - 62), "vaidarcrise.com.br/causas", font=sans(30, 700), fill=TINTA, anchor="lm")
    d.text((W - M, H - 62), "Desenhos feitos com IA", font=sans(22), fill=META, anchor="rm")
    caminho = SAIDA / f"resumo-{dia}.png"
    base.save(caminho, "PNG", optimize=True)
    if y > H - 110:
        print(f"aviso: o texto passou do espaço (y={y})")
    return caminho


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
    dia = sys.argv[1] if len(sys.argv) > 1 else None
    runs = sorted((ROOT / "runs").glob("*.json"))
    rodada = next(json.loads(p.read_text()) for p in reversed(runs) if dia is None or p.name[:10] <= dia)
    dia = dia or rodada["gerado_em"][:10]
    series = json.loads(causas.HIST.read_text())["series"]
    brutos = sorted(p for p in (ROOT / "data" / "raw").glob("*/indicadores.json") if p.parent.name <= dia)
    bruto = json.loads(brutos[-1].read_text()) if brutos else None
    webp()
    print(resumo(dia, causas.perguntas_hoje(series, rodada["resultado"], bruto)))
    print(og())


if __name__ == "__main__":
    main()
