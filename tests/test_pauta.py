"""O tipo do dia sem modelo: a novidade (src/pauta.py) e o modo do texto (src/fundo.py).

Rode com: .venv/bin/python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import fundo  # noqa: E402
import pauta  # noqa: E402

NOMES = {"contas": "Contas do governo", "juro": "Juro", "inflacao": "Inflação esperada", "emprego": "Emprego"}


def _rodada(**refs):
    """Uma rodada com as medidas mensais de cada pressão no mês dado (contas="2026-09")."""
    partes = [{"id": pid, "medidas": {"m": {"ref": ref}}} for pid, ref in refs.items()]
    return {"resultado": {"direcao": {"partes": partes}}}


def _c(cid, estagio="dado", tamanho=1, fator="contas", historia="contas_governo", titulo="Notícia", **kw):
    return {"id": cid, "estagio": estagio, "tamanho": tamanho, "fator": fator, "historia": historia, "titulo": titulo,
            "descartado": None, "jornais": ["Folha"], "n_manchetes": 1, "origem": None, "evento": None, **kw}


def _g(hid, pontos, candidatos, pressao=None):
    return {"id": hid, "titulo": hid, "pressao": pressao, "pressoes": [pressao] if pressao else [], "pontos": pontos,
            "candidatos": candidatos, "jornais": 1, "fato_grande": False}


class DadosNovos(unittest.TestCase):
    def test_a_medida_mensal_que_passa_de_mes_e_numero_novo(self):
        n = pauta.dados_novos(_rodada(contas="2026-10", parcelas="2026-08"), _rodada(contas="2026-09", parcelas="2026-08"))
        self.assertEqual([x["pressao"] for x in n], ["contas"])

    def test_sem_rodada_anterior_nao_ha_numero_novo(self):
        self.assertEqual(pauta.dados_novos(_rodada(contas="2026-10"), None), [])

    def test_medida_diaria_nao_conta(self):
        self.assertEqual(pauta.dados_novos(_rodada(mercado="2026-11"), _rodada(mercado="2026-10")), [])


class Novidades(unittest.TestCase):
    def test_numero_novo_entra_na_historia_da_noticia_do_dado(self):
        cands = [_c("E1", "previsao", 2), _c("E2", "dado", 1)]
        somas = [_g("contas_governo", 2.0, ["E1", "E2"], "contas")]
        n = pauta.novidades(cands, [], [{"pressao": "contas", "ref": "2026-10"}], {}, somas, NOMES)
        self.assertEqual(len(n), 1)
        self.assertEqual((n[0]["candidato"], n[0]["historia"]), ("E2", "contas_governo"))
        self.assertIn("outubro", n[0]["o_que"])

    def test_data_da_inflacao_acha_a_noticia_do_ipca_e_nao_a_da_guerra(self):
        cands = [_c("E1", fator="juro", historia="juro_inflacao", titulo="IPCA de outubro sobe 0,14%"),
                 _c("E2", fator="externo", historia="guerra_petroleo", titulo="Petróleo sobe")]
        somas = [_g("guerra_petroleo", 2.0, ["E2"], "inflacao"), _g("juro_inflacao", 1.0, ["E1"], "juro")]
        n = pauta.novidades(cands, [{"tipo": "ipca"}], [], {}, somas, NOMES)
        self.assertEqual(n[0]["historia"], "juro_inflacao")

    def test_marco_que_chega_vazio_nao_faz_dia_de_novidade(self):
        cands = [_c("E1", "anuncio", 1, marco=True)]
        self.assertEqual(pauta.novidades(cands, [], [], {}, [_g("contas_governo", 1.0, ["E1"])], NOMES), [])

    def test_decisao_publica_grande_e_novidade(self):
        cands = [_c("E1", "decidido", 2, fator="juro", historia="juro_inflacao", origem="banco_central")]
        n = pauta.novidades(cands, [], [], {}, [_g("juro_inflacao", 2.0, ["E1"], "juro")], NOMES)
        self.assertEqual([(x["tipo"], x["historia"]) for x in n], [("decisao", "juro_inflacao")])

    def test_decisao_de_empresa_nao_e_novidade(self):
        cands = [_c("E1", "decidido", 2, fator="externo", historia="acoes", origem="mundo")]
        self.assertEqual(pauta.novidades(cands, [], [], {}, [_g("acoes", 2.0, ["E1"])], NOMES), [])

    def test_a_mesma_noticia_nao_conta_duas_vezes(self):
        cands = [_c("E1", "decidido", 2, fator="juro", historia="juro_inflacao", origem="banco_central")]
        n = pauta.novidades(cands, [{"tipo": "copom"}], [], {}, [_g("juro_inflacao", 2.0, ["E1"], "juro")], NOMES)
        self.assertEqual(len(n), 1)


class Escolha(unittest.TestCase):
    def test_a_historia_da_novidade_ganha_mesmo_com_menos_pontos(self):
        somas = [_g("credito", 4.0, ["E1"]), _g("juro_inflacao", 1.0, ["E2"])]
        novas = [{"tipo": "dado", "o_que": "o IPCA", "pressao": "inflacao", "candidato": "E2", "historia": "juro_inflacao"}]
        esc = pauta.escolher(somas, [], {"direcao": False, "pressoes": []}, [], novas)
        self.assertEqual(esc["historia"]["id"], "juro_inflacao")
        self.assertFalse(esc["calmo"])

    def test_sem_novidade_vale_a_maior_soma(self):
        somas = [_g("credito", 4.0, ["E1"]), _g("juro_inflacao", 1.0, ["E2"])]
        esc = pauta.escolher(somas, [], {"direcao": False, "pressoes": []}, [], [])
        self.assertEqual(esc["historia"]["id"], "credito")


class Modo(unittest.TestCase):
    def test_tipos_do_dia(self):
        self.assertEqual(fundo.modo({"escolha": {"historia": "x", "calmo": False}}), "comum")
        self.assertEqual(fundo.modo({"escolha": {"historia": "x", "calmo": True}}), "calmo")
        self.assertEqual(fundo.modo({"escolha": {"historia": "x", "novidade": [{"o_que": "o IPCA"}]}}), "aprofundar")
        self.assertEqual(fundo.modo({"escolha": {"historia": "x"}, "pressoes_mudaram": [{"id": "juro"}]}), "aprofundar")
        self.assertEqual(fundo.modo({"semana": {"de": "2026-11-09"}, "escolha": {"historia": "x"}}), "pergunta")


if __name__ == "__main__":
    unittest.main()
