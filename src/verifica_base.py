"""Verificador da base de conhecimento (base/), a parte do código.

Confere, sem inteligência artificial:
  1. ligações: toda afirmação e episódio citado existe;
  2. dados: cada número de uma afirmação do tipo "dado" bate com as séries do próprio site
     (data/historico e data/raw), com a mesma conta do topo (direcao.mensais), e cada número de uma afirmação do
     tipo "conta" sai do comando de src/conta.py que ela guarda, rodado com os dados do dia dela (VDC_ATE);
  3. números do texto: todo número de um texto da pergunta-mãe está nas afirmações que ele cita;
  4. trechos: o trecho literal de cada afirmação do tipo "documento" está na página da fonte
     (precisa de rede: no Mac; na nuvem a rede bloqueia esses sites), e o do tipo "site" está no arquivo;
  5. regras de leitura: toda leitura tem a melhor objeção com fonte; nenhuma leitura leva nome de partido
     ou de presidente; consenso não se apoia só em notícia; episódios cobrem governos e causas diferentes;
     nenhuma pergunta guarda teste, e nenhum texto promete conferir, testar ou voltar ao assunto depois (decisão
     do Pedro em 8/11/2026, repetida em 9/11: o site faz a análise e para aí);
  6. escrita: frase de até 30 palavras, moldes de piloto automático, sigla sem link (src/revisa_texto.py); no passo
     "O que isso muda para você?", parágrafos de até 50 palavras e quatro números e o passo com até 200 palavras.

Uso:
  .venv/bin/python src/verifica_base.py              # tudo, com rede
  .venv/bin/python src/verifica_base.py --offline    # sem abrir as fontes
  .venv/bin/python src/verifica_base.py --json       # o relatório inteiro em JSON
O resultado só aparece na tela: o site não guarda registro de conferência.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import html
import io
import ipaddress
import json
import os
import re
import sys
import threading
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import direcao  # noqa: E402
import revisa_texto  # noqa: E402

BASE = ROOT / "base"
CACHE = BASE / "cache"
ROTULOS = {"consenso", "maioria_com_dissenso", "em_disputa"}
# Nome de empresa que se escreve em maiúsculas e não é sigla: o texto diz o que ela é ("a corretora XP").
NOMES_DE_EMPRESA = {"XP"}
STATUS_LEITURA = {"em_pe", "maioria", "em_disputa", "minoria", "pouco_testada", "testada_e_nao_confirmada"}
# O texto para a leitora diz o mecanismo, nunca o lado (PERSONA.md, teste da troca).
NOMES_COM_LADO = re.compile(r"\b(PT|PL|PSDB|MDB|PSOL|Novo|União Brasil|Lula|Bolsonaro|Dilma|Temer|FHC|Fernando Henrique|"
                            r"Haddad|Tarcísio|esquerda|direita|petista|bolsonarista|oposição|governista)\b")
# O site não guarda teste nem placar e não volta para conferir nada (decisão do Pedro em 8/11/2026, repetida em 9/11):
# além da promessa que src/revisa_texto.py já barra nos posts ("o site vai acompanhar"), a página não diz que o site
# confere, testa ou revisita uma explicação, nem marca data para isso.
MESES_RX = "janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
PROMESSA = re.compile(r"\bo site\s+(confere|conferirá|testa|testará|revisita|revisitará)\b|"
                      rf"\bconfer(e|em|ido|ida|idos|idas|ir|irá|imos)\s+(se\b|em\s+(\d|{MESES_RX}))|"
                      r"\btestes?\b[^.]{0,80}\b(vai|vão|irá|irão)\s+(mostrar|dizer|decidir)\b|"
                      r"\btestes?\b[^.]{0,40}\b(registrad\w*|segue|seguem|continua|continuam)\b|"
                      r"\bdatas? de conferência\b|\bregistrad\w* antes do resultado|\brevisit\w*", re.I)
# O passo da vida (PERSONA.md, "O que a notícia muda na vida"): até 50 palavras e quatro números por parágrafo, e o
# passo inteiro em até 200 palavras.
PASSO_DA_VIDA = "o_que_vem_depois"
UA ="Mozilla/5.0 (compatible; vaidarcrise-verificador/0.1; +https://vaidarcrise.com.br)"


# ---------- carga ----------

def carregar() -> dict:
    afs = json.loads((BASE / "afirmacoes.json").read_text())["afirmacoes"]
    eps = json.loads((BASE / "episodios.json").read_text())["episodios"]
    perguntas = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(BASE / "perguntas" / "*.json")))]
    return {"afirmacoes": {a["id"]: a for a in afs}, "lista_afirmacoes": afs,
            "episodios": {e["id"]: e for e in eps}, "perguntas": perguntas}


def series_do_site() -> tuple[dict, dict]:
    """(mensal, diário). Mensal: {serie: {"AAAA-MM": valor}}, com a conta do topo (direcao.mensais) para as
    séries do topo e o juro descontado da inflação esperada; as outras, o último valor de cada mês.
    Diário: {serie: {"AAAA-MM-DD": valor}} do histórico longo e de todas as coletas em data/raw."""
    hist = json.loads((ROOT / "data" / "historico" / "series.json").read_text())["series"]
    brutos = sorted((ROOT / "data" / "raw").glob("*/indicadores.json"))
    snaps = [json.loads(b.read_text()) for b in brutos]
    rodadas = [json.loads(x.read_text()) for x in sorted((ROOT / "runs").glob("*.json"))]
    m = direcao.mensais(snaps[-1] if snaps else None, rodadas, hist)
    # direcao.mensais também guarda, ao lado de cada série, o título do juro de 10 anos de cada dia e as trocas de
    # título: aqui ficam só as séries de verdade, mês -> (dia, valor).
    mensal = {k: {mes: x[1] for mes, x in d.items()} for k, d in m.items()
              if isinstance(d, dict) and d and all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], (int, float))
                                                   for x in d.values())}
    diario: dict[str, dict[str, float]] = {}

    def junta(k: str, pontos: list[dict]) -> None:
        d = diario.setdefault(k, {})
        for x in pontos:
            if x.get("valor") is not None:
                d[x.get("dia") or x["data"]] = float(x["valor"])

    for k, pts in hist.items():
        junta("dolar_ptax" if k == "dolar_ptax_diario" else k, pts)
    for s in snaps:
        for k, v in s.get("series", {}).items():
            junta(k, v.get("dados", []))
    for k, d in diario.items():
        if k not in mensal:
            mm: dict[str, float] = {}
            for dia in sorted(d):
                mm[dia[:7]] = d[dia]
            mensal[k] = mm
    return mensal, diario


def valor_em(serie: str, quando: str, mensal: dict, diario: dict) -> float | None:
    if len(quando) == 7:
        return mensal.get(serie, {}).get(quando)
    return diario.get(serie, {}).get(quando)


# ---------- texto das fontes ----------

def normalizar(t: str) -> str:
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t).replace("\u00ad", "")
    t = re.sub("[\u200b\u200c\u200d\u2060\ufeff]", "", t)  # caracteres invisíveis no meio do texto
    t = re.sub(r"\\[nrt]", " ", t)  # quebra de linha escrita como texto, como na API do Banco Central
    t = re.sub(r"[‘’´`]", "'", t)
    t = re.sub(r"[“”«»]", '"', t)
    t = re.sub(r"[‐-―−]", "-", t)
    t = re.sub(r"-\s*\n\s*", "", t)  # palavra quebrada no fim da linha do PDF
    # O espaço antes do ponto sai ("R$ 5,508 ."). Os espaços se juntam antes: numa página com milhares de espaços
    # seguidos, procurar o ponto depois de cada um levava minutos.
    t = re.sub(r"\s+", " ", t)
    return re.sub(r" ([.,;:!?)])", r"\1", t).strip().lower()


def texto_da_pagina(conteudo: bytes, tipo: str) -> str:
    if b"%PDF" in conteudo[:1024] or "pdf" in tipo:
        try:
            from pypdf import PdfReader  # opcional: pip install pypdf
            return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(conteudo)).pages)
        except Exception:  # noqa: BLE001
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(conteudo)
                f.flush()
                try:
                    return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, timeout=120).stdout
                except Exception:  # noqa: BLE001
                    return ""
    t = _decodificar(conteudo, tipo)
    if "json" in tipo or t.lstrip()[:1] in ("{", "["):
        try:  # API que devolve a página dentro de um JSON (Banco Central): junta os textos e os números
            j = json.loads(t)
            # O número entra como a página o escreve ("13.75"): sem ele, a lista das reuniões vinha sem a taxa.
            t = " ".join(_texto_da_norma(j) if _e_norma(j)
                         else _textos_json(json.loads(t, parse_int=str, parse_float=str)))
        except ValueError:
            pass
    return _sem_etiquetas(_sem_blocos(t))


_ABRE_BLOCO = re.compile(r"(?i)<(script|style|noscript)")
_FECHA_BLOCO = {n: re.compile(rf"(?i)</{n}>") for n in ("script", "style", "noscript")}


def _sem_blocos(t: str) -> str:
    """A página sem os blocos de programa e de estilo (<script>, <style>, <noscript>), cada um da abertura ao fim. Anda
    pelo texto uma vez só: o bloco que não fecha fica como está e o nome dele não é procurado de novo, porque uma
    página com milhares de aberturas sem fim levava minutos."""
    out, i, sem_fim, maior = [], 0, set(), -1
    for m in _ABRE_BLOCO.finditer(t):
        nome = m.group(1).lower()
        if m.start() < i or nome in sem_fim:
            continue
        if maior < m.end():  # o ">" que fecha a etiqueta de abertura
            maior = t.find(">", m.end())
            if maior < 0:
                break
        fim = _FECHA_BLOCO[nome].search(t, maior + 1)
        if not fim:
            sem_fim.add(nome)
            continue
        out.append(t[i:m.start()])
        i = fim.end()
    out.append(t[i:])
    return " ".join(out)


def _sem_etiquetas(t: str) -> str:
    """O texto sem as etiquetas (<p>, <a href="...">), cada uma trocada por um espaço. Depois do último ">" não há
    etiqueta para tirar, e procurar ali o fim de cada "<" levava minutos numa página com milhares deles."""
    fim = t.rfind(">") + 1
    return re.sub(r"(?s)<[^>]+>", " ", t[:fim]) + t[fim:]


def _decodificar(conteudo: bytes, tipo: str) -> str:
    """Lê a página na codificação que ela diz ter (cabeçalho ou <meta>); sem isso, UTF-8 e, se falhar, windows-1252,
    a do site do Planalto."""
    m = re.search(r"charset=[\"']?([\w-]+)", tipo or "", re.I) or re.search(rb"charset=[\"']?([\w-]+)", conteudo[:4096], re.I)
    nomes = [m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)] if m else []
    for nome in [*nomes, "utf-8", "cp1252"]:
        try:
            return conteudo.decode(nome)
        except (LookupError, UnicodeDecodeError):
            continue
    return conteudo.decode("utf-8", errors="replace")


def _textos_json(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for v in x.values() for t in _textos_json(v)]
    if isinstance(x, list):
        return [t for v in x for t in _textos_json(v)]
    return []


def _e_norma(j) -> bool:
    return isinstance(j, dict) and j.get("@type") == "Legislation" and "hasPart" in j


def _texto_da_norma(j) -> list[str]:
    """O texto de uma lei como normas.leg.br (o portal de normas do Congresso) a devolve: o título, a ementa e cada
    dispositivo, em ordem, sem os endereços e os rótulos que vêm no meio."""
    out = [str(j.get(k)) for k in ("headline", "alternateName", "abstract") if isinstance(j.get(k), str)]

    def anda(x) -> None:
        if isinstance(x, list):
            for y in x:
                anda(y)
        elif isinstance(x, dict):
            ex = x.get("workExample")
            for w in ex if isinstance(ex, list) else [ex]:
                if isinstance(w, dict):
                    out.extend(str(w[k]) for k in ("name", "text") if isinstance(w.get(k), str))
            anda(x.get("hasPart"))
    anda(j.get("hasPart"))
    return out


# O arquivo que não é página nem PDF, pelos primeiros bytes: o leitor não tira texto dele.
_BINARIOS = ((b"PK\x03\x04", "planilha, documento do Office ou arquivo compactado: .xlsx, .docx, .zip"),
             (b"\xd0\xcf\x11\xe0", "planilha ou documento antigo do Office: .xls, .doc"),
             (b"\x1f\x8b", "arquivo compactado: .gz"), (b"Rar!", "arquivo compactado: .rar"),
             (b"7z\xbc\xaf", "arquivo compactado: .7z"), (b"\x89PNG", "imagem"), (b"\xff\xd8\xff", "imagem"),
             (b"GIF8", "imagem"))
# O aviso que o site devolve no lugar do documento, com resposta de página boa. Só vale na página curta: a matéria
# que cita uma destas frases é mais longa.
_AVISOS = ((re.compile(r"verifica[cç][aã]o de seguran[cç]a.{0,120}verificando sua conex[aã]o", re.I),
            "o site pediu uma verificação de segurança no lugar do documento (barra robô)"),
           (re.compile(r"estamos em manuten[cç][aã]o", re.I), "o site está em manutenção"),
           (re.compile(r"falha na integra[cç][aã]o", re.I),
            "o site não conseguiu buscar o documento (falha na integração com o sistema de publicações)"))
_AVISO_ATE = 1500  # caracteres


def formato_que_nao_le(conteudo: bytes, tipo: str) -> str | None:
    """Por que o leitor não lê um arquivo; None quando é página, PDF ou texto. A planilha, o arquivo compactado e a
    imagem viravam um texto de lixo, e a leitura passava por boa."""
    if b"%PDF" in conteudo[:1024] or "pdf" in tipo:
        return None
    nome = next((n for marca, n in _BINARIOS if conteudo.startswith(marca)), None)
    if not nome and b"\x00" in conteudo[:1024] and not conteudo.startswith((b"\xff\xfe", b"\xfe\xff")):
        nome = "arquivo que não é texto"
    return f"formato que o leitor não lê ({nome}); procure o mesmo documento em PDF ou em página" if nome else None


def aviso_do_site(texto: str) -> str | None:
    """O aviso que veio no lugar do documento (manutenção, verificação de segurança, falha do sistema de publicações
    do Tesouro); None na página normal."""
    t = re.sub(r"\s+", " ", html.unescape(texto)).strip()
    if len(t) > _AVISO_ATE:
        return None
    return next((motivo for rx, motivo in _AVISOS if rx.search(t)), None)


TAMANHO_MAXIMO = 60 * 1024 * 1024  # um documento maior que isto não é lido (o projeto do Orçamento inteiro, por exemplo)
# O prazo de uma página: quatro minutos para baixar, com os redirecionamentos, e mais o tempo de tirar o texto (o PDF
# mais demorado leva dois minutos). Sem prazo, um site que segura a conexão segurava a conferência inteira.
PRAZO_PARA_BAIXAR = 240  # segundos
PRAZO_DA_PAGINA = PRAZO_PARA_BAIXAR + 150
DEMOROU = "a página demorou demais para abrir"
SO_HTTP = "só abre endereço http ou https, sem senha e na porta de costume"
# A barra invertida e os caracteres de controle não existem em endereço de verdade, e cada programa lê um computador
# diferente no endereço que os traz: em "http://127.0.0.1\.site.com", um lê site.com e o que abre a página lê 127.0.0.1.
_FORA_DE_ENDERECO = re.compile(r"[\\\x00-\x1f\x7f]")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def endereco_publico(url: str) -> str | None:
    """Por que um endereço não pode ser aberto; None quando pode. O endereço vem da IA, que o tira das páginas que leu,
    e uma página pode pedir o que não deve: só abre http e https, nas portas de costume, e nunca um computador da
    rede de dentro. O computador é lido no endereço como o lê o programa que abre a página (requests)."""
    from urllib.parse import urlparse
    if not isinstance(url, str) or _FORA_DE_ENDERECO.search(url):
        return "endereço inválido"
    try:
        if urlparse(url).scheme not in ("http", "https"):
            return SO_HTTP
        import requests
        from urllib3.util import parse_url
        pronto = requests.Request("GET", url).prepare().url
        u, v = urlparse(pronto), parse_url(pronto)
        porta, host = u.port, (u.hostname or "").lower()
    except Exception:  # noqa: BLE001
        return "endereço inválido"
    if (u.scheme, host, porta) != (v.scheme, (v.host or "").lower().strip("[]"), v.port):
        return "endereço inválido"
    if u.scheme not in ("http", "https") or not host or u.username or u.password or v.auth or porta not in (None, 80, 443):
        return SO_HTTP
    host = host.rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".intranet")):
        return "endereço da rede interna"
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        ips = _numeros_do_nome(host)
        if ips is None:
            # Com a rede por trás de um intermediário (a nuvem), o nome não se resolve aqui: quem abre é ele. Em
            # conexão direta, o nome que não se resolve não abre.
            if _vai_direto(pronto):
                return "o nome do endereço não foi achado na rede"
            ips = []
    return None if all(_de_fora(ip) for ip in ips) else "endereço da rede interna"


def _numeros_do_nome(host: str) -> list | None:
    """Os endereços numéricos de um nome; None quando ele não se resolve (tenta duas vezes: a falha pode ser da rede)."""
    import socket
    for _ in range(2):
        try:
            return [ipaddress.ip_address(x[4][0].split("%")[0]) for x in socket.getaddrinfo(host, None)]
        except (OSError, ValueError):
            continue
    return None


def _de_fora(ip) -> bool:
    """O endereço numérico é de um computador da internet pública? O IPv4 embrulhado num IPv6 vale pelo de dentro:
    "::ffff:10.0.0.1" e "64:ff9b::a00:1" chegam ao 10.0.0.1 da rede de dentro."""
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped.is_global
        dentro = ip.sixtofour or (ipaddress.ip_address(int(ip) & 0xFFFFFFFF) if ip in _NAT64 else None)
        if dentro is not None and not dentro.is_global:
            return False
    return ip.is_global


def _vai_direto(url: str) -> bool:
    """O pedido sai daqui direto para o site, sem intermediário (proxy)?"""
    try:
        from requests.utils import get_environ_proxies, select_proxy
        return not select_proxy(url, get_environ_proxies(url))
    except Exception:  # noqa: BLE001
        return False


def _par_de_fora(sock) -> bool:
    """O computador do outro lado da conexão é da internet pública? Quando não dá para saber, vale a conferência do
    nome, feita antes."""
    try:
        return _de_fora(ipaddress.ip_address(sock.getpeername()[0].split("%")[0]))
    except (OSError, ValueError, IndexError, TypeError, AttributeError):
        return True


_ADAPTADOR = None


def _adaptador():
    """O encaixe que confere o computador do outro lado logo depois de conectar e antes de mandar o pedido. O nome que
    passou na conferência pode apontar para a rede de dentro um instante depois; o número de quem atendeu não muda.
    Só vale na conexão direta: com intermediário (a nuvem), quem atende é ele, e a conexão dele usa outro encaixe."""
    global _ADAPTADOR
    if _ADAPTADOR is None:
        from requests.adapters import HTTPAdapter
        from urllib3.connection import HTTPConnection, HTTPSConnection
        from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

        class Confere:
            def _new_conn(self):
                sock = super()._new_conn()
                if not getattr(self, "proxy", None) and not _par_de_fora(sock):
                    sock.close()
                    raise ValueError("endereço da rede interna")
                return sock

        class Http(Confere, HTTPConnection):
            pass

        class Https(Confere, HTTPSConnection):
            pass

        class FilaHttp(HTTPConnectionPool):
            ConnectionCls = Http

        class FilaHttps(HTTPSConnectionPool):
            ConnectionCls = Https

        class Adaptador(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                super().init_poolmanager(*args, **kwargs)
                self.poolmanager.pool_classes_by_scheme = {"http": FilaHttp, "https": FilaHttps}

        _ADAPTADOR = Adaptador
    return _ADAPTADOR()


def _sessao():
    """A sessão que abre uma página: guarda os cookies de um redirecionamento para o outro (o site que só responde a
    quem volta com o cookie que ele deu) e confere o computador do outro lado (_adaptador)."""
    import requests
    s = requests.Session()
    # Quem segue o redirecionamento é o baixar(). A biblioteca não precisa ler o destino, e parava com erro no destino
    # com acento escrito fora do UTF-8 (os endereços antigos do governo).
    s.get_redirect_target = lambda resposta: None
    try:
        for esquema in ("http://", "https://"):
            s.mount(esquema, _adaptador())
    except Exception:  # noqa: BLE001  (a biblioteca mudou por dentro: a página abre só com a conferência do nome)
        pass
    return s


def _destino(atual: str, para: str) -> str:
    """O endereço para onde o site manda. O cabeçalho chega lido byte a byte, e a letra com acento ("notícias") viria
    trocada: cada byte fora do alfabeto básico volta a ser o que o site mandou, escrito como %XX."""
    from urllib.parse import urljoin
    return urljoin(atual, "".join(f"%{ord(c):02X}" if "\x80" <= c <= "\xff" else c for c in para.strip()))


def baixar(url: str, limite: int = TAMANHO_MAXIMO, ate: float | None = None) -> tuple[bytes, str, str]:
    """(conteúdo, tipo, endereço final). Segue os redirecionamentos um a um, conferindo cada endereço, e para de ler
    no tamanho máximo ou no fim do prazo (`ate`, na contagem de time.monotonic). Levanta ValueError com o motivo
    quando não abre."""
    import time
    from urllib.parse import urlparse
    ate = ate or time.monotonic() + PRAZO_PARA_BAIXAR
    atual, pedido, vazias = url, {"User-Agent": UA}, 0
    with _sessao() as sessao:
        for _ in range(8):
            motivo = endereco_publico(atual)
            if motivo:
                raise ValueError(motivo)
            resta = ate - time.monotonic()
            if resta <= 0:
                raise ValueError(DEMOROU)
            r = sessao.get(atual, headers=pedido, timeout=min(40, resta + 1), allow_redirects=False, stream=True)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                r.close()
                atual = _destino(atual, r.headers["location"])
                continue
            # O gov.br responde 404 ao endereço que mudou de lugar quando o pedido não diz que quer uma página; dizendo,
            # ele manda para o endereço novo. Só o 404 é pedido de novo: a página que já abria recebe o mesmo pedido.
            if r.status_code == 404 and "Accept" not in pedido:
                r.close()
                pedido = {**pedido, "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"}
                continue
            if r.status_code >= 400:
                r.close()
                raise ValueError(f"HTTP {r.status_code}")
            dados = bytearray()
            for parte in r.iter_content(1 << 16):
                dados += parte
                if len(dados) > limite:
                    r.close()
                    raise ValueError("documento grande demais para ler inteiro")
                if time.monotonic() > ate:
                    r.close()
                    raise ValueError(DEMOROU)
            # O servidor do Supremo devolve o documento vazio a parte dos pedidos, mesmo a um pedido de cada vez: a
            # resposta boa sem nada dentro é pedida de novo, até três vezes.
            if not dados and vazias < 3 and ate - time.monotonic() > 10:
                vazias += 1
                time.sleep(2)
                continue
            # O site que manda todo endereço para a página inicial (o do Planalto, fora do Brasil) não abriu o documento.
            # A página inicial de um órgão no gov.br tem duas partes, o órgão e a língua (gov.br/planalto/pt-br).
            a, b = urlparse(url), urlparse(atual)
            partes = [x for x in a.path.split("/") if x]
            finais = [x for x in b.path.split("/") if x]
            inicial = len(finais) <= 1 or (len(finais) == 2 and finais[1].lower() in ("pt-br", "en", "es"))
            if atual != url and len(partes) >= 2 and inicial and partes[-1] not in atual:
                raise ValueError("o endereço leva à página inicial do site, e não ao documento")
            return bytes(dados), r.headers.get("content-type", ""), atual
    raise ValueError("redirecionamentos demais")


# Um pedido por endereço de cada vez. As linhas do caderno abrem em paralelo, e várias citam o mesmo documento: pedido
# em rajada, o servidor do Supremo devolve o PDF vazio a parte dos pedidos. Em fila, a primeira linha baixa e as outras
# leem a cópia. O endereço que demorou a falhar não é tentado de novo por dois minutos, para a fila não somar as esperas.
_TRAVAS: dict[str, threading.Lock] = {}
_TRAVA_DAS_TRAVAS = threading.Lock()
_FALHAS_LENTAS: dict[str, tuple[str, float]] = {}
_LENTA_DESDE, _LENTA_VALE = 10, 120  # segundos
_ABRINDO: dict[str, threading.Thread] = {}  # o ajudante que passou do prazo e ainda está abrindo o endereço


def abrir(url: str, validade_h: float | None = None) -> tuple[str | None, str | None]:
    """(texto, erro). Guarda a página em base/cache para não abrir de novo; com `validade_h`, a cópia mais velha que
    isso é aberta de novo (a página de lista, que muda)."""
    import time
    CACHE.mkdir(parents=True, exist_ok=True)
    # ".v4": a cópia guardada até 12/11/2026 podia ser a página inicial ou um aviso do site (manutenção, verificação de
    # segurança) no lugar do documento, ou o lixo de uma planilha, e a resposta em JSON vinha sem os números
    arq = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".v4.txt")
    with _TRAVA_DAS_TRAVAS:
        trava = _TRAVAS.setdefault(url, threading.Lock())
    with trava:
        if arq.exists() and (validade_h is None or time.time() - arq.stat().st_mtime < validade_h * 3600):
            return arq.read_text(), None
        lenta = _FALHAS_LENTAS.get(url)
        if lenta and time.time() - lenta[1] < _LENTA_VALE:
            return None, lenta[0]
        inicio = time.time()
        t, erro = _com_prazo(url, arq)
        if erro:
            if time.time() - inicio > _LENTA_DESDE:
                _FALHAS_LENTAS[url] = (erro, time.time())
            return None, erro
        return t, None


def _com_prazo(url: str, arq: Path) -> tuple[str | None, str | None]:
    """(texto, erro) do endereço aberto agora, em até PRAZO_DA_PAGINA segundos. Quem abre é um ajudante: se o site
    segurar a conexão, a conferência segue sem a página, e o ajudante guarda a cópia quando terminar, para a tentativa
    seguinte achar."""
    antes = _ABRINDO.get(url)
    if antes is not None and antes.is_alive():
        return None, DEMOROU
    saida: list[tuple[str | None, str | None]] = []

    def busca() -> None:
        try:
            saida.append(_da_rede(url))
        except Exception as e:  # noqa: BLE001
            saida.append((None, f"{type(e).__name__}: {str(e)[:120]}"))
        if saida[0][0] is not None and not saida[0][1]:
            # A cópia só aparece inteira, para outro programa que abra o mesmo endereço não ler um arquivo pela metade.
            try:
                tmp = arq.with_name(f"{arq.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_text(saida[0][0])
                tmp.replace(arq)
            except OSError:  # sem a cópia, a página é aberta de novo na próxima vez
                pass

    ajudante = threading.Thread(target=busca, daemon=True)
    try:
        ajudante.start()
    except RuntimeError:  # o computador não abre mais um ajudante: abre aqui mesmo
        busca()
        return saida[0]
    ajudante.join(PRAZO_DA_PAGINA)
    if ajudante.is_alive():
        _ABRINDO[url] = ajudante
        return None, DEMOROU
    _ABRINDO.pop(url, None)
    return saida[0] if saida else (None, DEMOROU)


def _da_rede(url: str) -> tuple[str | None, str | None]:
    """(texto, erro) do endereço aberto agora, sem a cópia."""
    try:
        dados, tipo, _ = baixar(url)
        motivo = formato_que_nao_le(dados, tipo)
        t = "" if motivo else texto_da_pagina(dados, tipo)
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:160] if isinstance(e, ValueError) else f"{type(e).__name__}: {str(e)[:120]}"
    # O que não é o documento não vira texto nem fica guardado: a conferência tenta de novo na rodada seguinte.
    motivo = motivo or aviso_do_site(t)
    if motivo:
        return None, motivo
    if len(t.strip()) < 200:
        return None, "página sem texto (talvez só JavaScript ou paywall)"
    return t, None


def conferir_trecho(a: dict, offline: bool) -> dict:
    """Status do trecho de uma afirmação: conferido, trecho_nao_achado, sem_trecho, sem_endereco,
    fonte_inacessivel, nao_aberta (modo offline)."""
    if a["tipo"] == "site":
        alvo = (ROOT / a["arquivo"]).read_text()
        faltam = [t for t in (a.get("trecho"), a.get("trecho_2")) if t and normalizar(t) not in normalizar(alvo)]
        return {"status": "trecho_nao_achado" if faltam else "conferido", "onde": a["arquivo"]}
    trecho = a.get("trecho") or a.get("trecho_candidato")
    url = (a.get("fonte") or {}).get("url")
    if not url:
        return {"status": "sem_endereco"}
    if not trecho:
        return {"status": "sem_trecho"}
    if offline:
        return {"status": "nao_aberta"}
    # O endereço principal primeiro; depois as cópias da mesma fonte (repositório, PDF da revista).
    tentativas = []
    for u in [url, *((a.get("fonte") or {}).get("urls_alternativas") or [])]:
        texto, erro = abrir(u)
        if erro:
            tentativas.append({"url": u, "erro": erro})
            continue
        if normalizar(trecho) in normalizar(texto):
            return {"status": "conferido", "url": u, "era_candidato": not a.get("trecho")}
        tentativas.append({"url": u, "erro": "trecho não está na página"})
    abriu_alguma = any(t["erro"] == "trecho não está na página" for t in tentativas)
    return {"status": "trecho_nao_achado" if abriu_alguma else "fonte_inacessivel", "tentativas": tentativas,
            "era_candidato": not a.get("trecho")}


def _sem_mil(t: str) -> str:
    """"R$ 300 mil" escrito como a saída da conta escreve ("R$ 300.000"), para comparar os números."""
    return re.sub(r"(?<![\d.,])(\d{1,3})(?:,(\d))?\s+mil\b",
                  lambda m: f"{int(m[1]) * 1000 + int(m[2] or 0) * 100:,}".replace(",", "."), t)


def conferir_conta(a: dict) -> dict:
    """Status de uma afirmação do tipo "conta" (a tradução de TRADUCAO.md feita por src/conta.py): roda o comando com
    os dados como eram no dia `ate` (VDC_ATE; sem `ate`, a conta só depende dos números do comando, como a parcela) e
    confere que todo número e data do texto está na saída, com a folga da casa decimal usada no texto. Números que
    saem dos do comando sem estar na saída (30 anos para 360 meses) vão em `numeros_derivados`."""
    import contextlib
    import os
    import conta
    antes = os.environ.get("VDC_ATE")
    try:
        if a.get("ate"):
            os.environ["VDC_ATE"] = a["ate"]
        else:
            os.environ.pop("VDC_ATE", None)
        with contextlib.redirect_stdout(io.StringIO()):
            saida = conta.rodar(a["comando"])
    except Exception as e:  # noqa: BLE001
        return {"status": "conta_falhou", "comando": a["comando"], "erro": f"{type(e).__name__}: {str(e)[:120]}"}
    finally:
        if antes is None:
            os.environ.pop("VDC_ATE", None)
        else:
            os.environ["VDC_ATE"] = antes
    r = {"comando": a["comando"], "ate": a.get("ate")}
    if not saida.strip() or saida.lstrip().startswith(("Sem dado", "traduz:", "série desconhecida", "usage:")):
        return {**r, "status": "conta_falhou", "saida": saida.strip()[:200]}
    extra = " ".join(a.get("numeros_derivados", []))
    fora = [n for n in revisa_texto.numeros_fora([_sem_mil(a["texto"])], f"{saida} {extra}")
            if not re.fullmatch(r"(19|20)\d\d", n)]
    return {**r, "status": "conta_nao_bate" if fora else "conferido", **({"fora": fora} if fora else {})}


# ---------- regras ----------

def textos_da_pergunta(p: dict) -> list[tuple[str, str, list[str]]]:
    """(onde, texto, afirmações citadas) de cada texto que a leitora lê."""
    out = []
    if p.get("resposta_curta"):
        out.append(("resposta_curta", p["resposta_curta"]["texto"], p["resposta_curta"]["afirmacoes"]))
    for parte in ("medida", "governo", "agora"):
        if p.get(parte):
            out.append((parte, (p[parte].get("pergunta", "") + " " + p[parte]["texto"]).strip(), p[parte]["afirmacoes"]))
    for d in p["escada"]:
        nome = d.get("id") or d["degrau"]
        if d.get("texto"):
            out.append((nome, d["texto"], d.get("afirmacoes", [])))
        if d.get("consenso"):
            out.append((f"{nome}/consenso", d["consenso"]["texto"], d["consenso"]["afirmacoes"]))
        if d.get("em_disputa"):
            out.append((f"{nome}/em_disputa", d["em_disputa"], d.get("em_disputa_afirmacoes", [])))
        if d.get("peso_da_evidencia") and d.get("peso_afirmacoes"):
            out.append((f"{nome}/peso", d["peso_da_evidencia"], d["peso_afirmacoes"]))
        for lt in d.get("leituras", []):
            base = f"{nome}/{lt['id']}"
            out.append((f"{base}/o_que_diz", lt["o_que_diz"], lt.get("o_que_diz_afirmacoes", [])))
            if lt.get("resumo"):
                out.append((f"{base}/o_que_diz_resumo", lt["resumo"], lt.get("o_que_diz_afirmacoes", [])))
            if lt.get("titulo"):
                out.append((f"{base}/o_que_diz_titulo", lt["titulo"], []))
            for i, x in enumerate(lt.get("a_favor", []) + lt.get("estudos", [])):
                out.append((f"{base}/a_favor{i}", x["texto"], x["afirmacoes"]))
            for parte in ("melhor_objecao", "resposta"):
                if lt.get(parte):
                    out.append((f"{base}/{parte}", lt[parte]["texto"], lt[parte]["afirmacoes"]))
    return out


def _texto_ok(onde: str, texto: str, ids: list[str], A: dict, pe: list[str], pa: list[str]) -> None:
    """Regras 1, 3 e 6 num texto que a leitora lê: afirmações citadas existem, todo número está nelas, e a escrita
    segue o guia (frase de até 30 palavras, sem molde, sigla com link, sem nome de lado)."""
    for i in ids:
        if i not in A:
            pe.append(f"{onde}: cita afirmação que não existe ({i})")
    if ids:
        fontes = " ".join(A[i]["texto"] for i in ids if i in A)
        fora = [n for n in revisa_texto.numeros_fora([texto], fontes) if not re.fullmatch(r"(19|20)\d\d", n)]
        if fora:
            pe.append(f"{onde}: número sem afirmação que o sustente ({', '.join(fora)})")
    elif re.search(r"\d", revisa_texto._sem_datas(texto)) and not onde.rsplit("/", 1)[-1].startswith("o_que_diz"):
        pa.append(f"{onde}: texto com número e sem afirmação citada")
    for f in revisa_texto.FRASE.split(texto):
        if len(f.split()) > 30:
            pa.append(f"{onde}: frase com {len(f.split())} palavras: {f[:60]}")
    # "Como o topo mede esta pressão?" explica a linha do topo com as palavras dela, e o topo diz "vaivém normal"
    # (src/build_site.py); o resto do molde vale ali também.
    pa += [f"{onde}: {m}" for m in
           revisa_texto._moldes(texto.replace("vaivém normal", "vaivém") if onde.endswith("medida") else texto)]
    sig = [x for x in revisa_texto.siglas_soltas(texto) if x not in NOMES_DE_EMPRESA]
    if sig:
        pa.append(f"{onde}: sigla sem link ({', '.join(sig)})")
    if NOMES_COM_LADO.search(texto):
        pe.append(f"{onde}: nome de partido, presidente ou lado no texto ({NOMES_COM_LADO.search(texto).group(0)})")
    if onde == PASSO_DA_VIDA:
        pars = [x for x in texto.split("\n\n") if x.strip()]
        for k, x in enumerate(pars):
            if len(x.split()) > 50:
                pa.append(f"{onde}: parágrafo {k + 1} com {len(x.split())} palavras (até 50)")
            if len(revisa_texto.NUMERO.findall(x)) > 4:
                pa.append(f"{onde}: parágrafo {k + 1} com {len(revisa_texto.NUMERO.findall(x))} números (até quatro)")
        if len(texto.split()) > 200:
            pa.append(f"{onde}: passo com {len(texto.split())} palavras (até 200)")


def promessas(x, onde: str = "") -> list[str]:
    """Toda promessa de conferir, testar ou voltar ao assunto depois em qualquer texto de uma pergunta (ou de um post),
    com o caminho dela: as partes que a página mostra, as divisões que ela não mostra e o registro de mudanças. A
    regra do Pedro vale para o site inteiro, e não só para o que a página mostra hoje."""
    if isinstance(x, str):
        m = _promessa(x)
        return [f"{onde or 'texto'}: promete conferir, testar ou voltar ao assunto depois ({m}): o site faz a análise "
                "e para aí"] if m else []
    if isinstance(x, dict):
        return [e for k, v in x.items() for e in promessas(v, f"{onde}/{k}" if onde else k)]
    if isinstance(x, list):
        return [e for i, v in enumerate(x) for e in promessas(v, f"{onde}[{i}]")]
    return []


def _promessa(texto: str) -> str | None:
    """O trecho que promete conferir, testar ou acompanhar depois, se houver (PROMESSA e a regra dos posts)."""
    for rx in [PROMESSA, *(rx for rx, nome in revisa_texto.GRAVES if nome.startswith("promete"))]:
        m = rx.search(texto)
        if m:
            return m.group(0)
    return None


def checar(base: dict, offline: bool) -> dict:
    A, E = base["afirmacoes"], base["episodios"]
    mensal, diario = series_do_site()
    erros: list[str] = []
    avisos: list[str] = []
    afirm: dict[str, dict] = {}

    # 2 e 4: cada afirmação
    for a in base["lista_afirmacoes"]:
        r: dict = {"tipo": a["tipo"], "nivel": a["fonte"]["nivel"]}
        if a["tipo"] == "dado":
            ruins = []
            for c in a["dados"]:
                v = valor_em(c["serie"], c["quando"], mensal, diario)
                if v is None or abs(v - c["valor"]) > c["tol"] + 1e-9:
                    ruins.append(f"{c['serie']} em {c['quando']}: texto {c['valor']}, dado {None if v is None else round(v, 4)}")
            nums_dados = " ".join(str(c["valor"]).replace(".", ",") for c in a["dados"])
            # As datas dos dados no jeito do texto (26/10) e os números que saem da conta dos dados (0,25).
            datas = " ".join(f"{int(c['quando'][8:])}/{int(c['quando'][5:7])}" for c in a["dados"] if len(c["quando"]) == 10)
            extra = " ".join(a.get("numeros_derivados", []))
            fora = revisa_texto.numeros_fora([a["texto"]], f"{nums_dados} {datas} {extra}")
            fora = [n for n in fora if not re.fullmatch(r"(19|20)\d\d", n)]
            r["status"] = "conferido" if not ruins else "dado_errado"
            if ruins:
                r["problemas"] = ruins
                erros.append(f"{a['id']}: dado não bate ({'; '.join(ruins)})")
            if fora:
                avisos.append(f"{a['id']}: número do texto sem conferência no campo dados ({', '.join(fora)})")
        elif a["tipo"] == "conta":
            r.update(conferir_conta(a))
            if r["status"] != "conferido":
                erros.append(f"{a['id']}: a conta não sustenta o texto ({r['status']}; {a['comando']}"
                             + (f"; números fora da saída: {', '.join(r['fora'])}" if r.get("fora") else "")
                             + (f"; {r.get('erro') or r.get('saida')}" if r.get("erro") or r.get("saida") else "") + ")")
        else:
            r.update(conferir_trecho(a, offline))
            if r["status"] in ("trecho_nao_achado",) and a["tipo"] == "site":
                erros.append(f"{a['id']}: trecho não está em {a['arquivo']}")
        afirm[a["id"]] = r

    perguntas = []
    nomes = json.loads((ROOT / "config" / "modelo.json").read_text())["direcao"]["nomes"]
    pressoes: dict[str, str] = {}
    for p in base["perguntas"]:
        pe: list[str] = []
        pa: list[str] = []
        citadas: set[str] = set()
        publicada = p.get("publicada", True)
        # 7: uma página por pressão do topo
        if p.get("pressao") not in nomes:
            pe.append(f"pressão desconhecida ({p.get('pressao')}); use uma chave de direcao.nomes")
        elif publicada:
            if p["pressao"] in pressoes:
                pe.append(f"a pressão {p['pressao']} já tem página ({pressoes[p['pressao']]})")
            pressoes[p["pressao"]] = p["id"]
        if publicada and not p.get("resposta_curta"):
            pe.append("página publicada sem resposta curta")
        # 1 e 3: ligações e números
        for onde, texto, ids in textos_da_pergunta(p):
            citadas |= set(ids)
            _texto_ok(onde, texto, ids, A, pe, pa)
        for e in p.get("episodios", []):
            if e not in E:
                pe.append(f"episódio que não existe: {e}")
        # 5: o site não guarda teste nem resultado, e nenhum texto da pergunta, nem o registro de mudanças, promete um.
        if p.get("testes"):
            pe.append(f"a pergunta guarda {len(p['testes'])} teste(s): o site não guarda teste nem confere depois")
        pe += promessas(p)
        # 5: regras de leitura
        for d in p["escada"]:
            if d.get("rotulo") and d["rotulo"] not in ROTULOS:
                pe.append(f"{d['degrau']}: rótulo desconhecido {d['rotulo']}")
            if d.get("rotulo") == "consenso" and d["degrau"] != "fato" and d.get("afirmacoes"):
                niveis = [A[i]["fonte"]["nivel"] for i in d["afirmacoes"] if i in A]
                if niveis and min(niveis) >= 5:
                    pa.append(f"{d['degrau']}: consenso apoiado só em notícia ou banco (nível {min(niveis)} ou pior)")
            if d.get("leituras"):
                if not d.get("peso_da_evidencia"):
                    pe.append(f"{d.get('id')}: divisão sem peso da evidência")
                for lt in d["leituras"]:
                    if lt.get("status") not in STATUS_LEITURA:
                        pe.append(f"{lt['id']}: status desconhecido {lt.get('status')}")
                    if NOMES_COM_LADO.search(lt["nome"]):
                        pe.append(f"{lt['id']}: leitura com nome de lado ({lt['nome']})")
                    mo = lt.get("melhor_objecao") or {}
                    if not mo.get("afirmacoes"):
                        pe.append(f"{lt['id']}: leitura sem a melhor objeção com fonte")
                    apoio = [i for x in lt.get("a_favor", []) + lt.get("estudos", []) for i in x["afirmacoes"]]
                    if not apoio:
                        pe.append(f"{lt['id']}: leitura sem nada a favor")
                    if any(A[i]["fonte"]["nivel"] == 7 for i in apoio if i in A):
                        pe.append(f"{lt['id']}: comentarista (nível 7) usado como prova")
                    if lt.get("status") == "maioria" and not any(A[i]["fonte"]["nivel"] <= 3 for i in apoio if i in A):
                        pe.append(f"{lt['id']}: leitura de maioria sem estudo ou fonte oficial (níveis 1 a 3)")
                    if (lt.get("resposta") or {}).get("fonte_pendente"):
                        pa.append(f"{lt['id']}: resposta com fonte pendente: {lt['resposta']['fonte_pendente']}")
            if d.get("teste"):
                pe.append(f"{d.get('id') or d['degrau']}: degrau com teste ({d['teste']}): o site não guarda teste")
        eps = [E[e] for e in p.get("episodios", []) if e in E]
        governos = {g for e in eps for g in e.get("governo", [])}
        causas = {e.get("causa") for e in eps}
        if publicada and len(governos) < 3:
            pa.append(f"episódios de só {len(governos)} governos: o teste da troca pede mais")
        if publicada and not {"daqui", "de fora"} <= causas:
            pa.append("episódios sem caso daqui e caso de fora")
        for e in eps:
            fontes = " ".join(A[i]["texto"] for i in e["afirmacoes"] if i in A)
            fora = [n for n in revisa_texto.numeros_fora([e["resumo"]], fontes) if not re.fullmatch(r"(19|20)\d\d", n)]
            if fora:
                pe.append(f"{e['id']}: número do resumo sem afirmação ({', '.join(fora)})")
            if NOMES_COM_LADO.search(e["resumo"]):
                pe.append(f"{e['id']}: nome de presidente ou partido no resumo")
            for i in e["afirmacoes"]:
                citadas.add(i)
        cont: dict[str, int] = {}
        for i in sorted(citadas):
            if i in afirm:
                cont[afirm[i]["status"]] = cont.get(afirm[i]["status"], 0) + 1
        perguntas.append({"id": p["id"], "erros": pe, "avisos": pa, "afirmacoes_citadas": len(citadas), "status": cont})
        erros += [f"{p['id']}: {x}" for x in pe]
        avisos += [f"{p['id']}: {x}" for x in pa]

    soltas = sorted(set(A) - {i for _, _, ids in
                    (t for p in base["perguntas"] for t in textos_da_pergunta(p)) for i in ids}
                    - {i for e in E.values() for i in e["afirmacoes"]})
    if soltas:
        avisos.append(f"afirmações que nenhum texto cita: {', '.join(soltas)}")
    resumo: dict[str, int] = {}
    for r in afirm.values():
        resumo[r["status"]] = resumo.get(r["status"], 0) + 1
    return {"em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "offline": offline,
            "resumo": resumo, "erros": erros, "avisos": avisos, "perguntas": perguntas, "afirmacoes": afirm}


def main() -> None:
    offline = "--offline" in sys.argv
    rel = checar(carregar(), offline)
    if "--json" in sys.argv:
        print(json.dumps(rel, ensure_ascii=False, indent=1))
        return
    print(f"afirmações: {sum(rel['resumo'].values())} | " + ", ".join(f"{k} {v}" for k, v in sorted(rel["resumo"].items())))
    print(f"erros: {len(rel['erros'])}")
    for e in rel["erros"]:
        print("  ERRO", e)
    print(f"avisos: {len(rel['avisos'])}")
    for a in rel["avisos"]:
        print("  aviso", a)
    sys.exit(1 if rel["erros"] else 0)


if __name__ == "__main__":
    main()
