"""A escrita sem modelo: a troca de fornecedor e o ciclo de correção (src/escrita.py).

Rode com: .venv/bin/python -m unittest discover tests
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import classify_news  # noqa: E402
import escrita  # noqa: E402


def _ok(saida):
    return {"ok": True, "saida": saida, "meta": {}}


def _erro(msg):
    return {"ok": False, "saida": None, "meta": {"erro": msg}}


class Falso:
    """Troca os dois transportes por respostas prontas e anota quem foi chamado."""

    def __init__(self, codex, claude=None):
        self.codex, self.claude, self.chamadas = list(codex), list(claude or []), []
        self._orig = classify_news.chamar_codex, classify_news.chamar_claude_direto

    def __enter__(self):
        def codex(system, prompt, schema, etapa, timeout=600, modelo=None, raciocinio=None):
            self.chamadas.append(("codex", etapa, modelo))
            return self.codex.pop(0)

        def claude(system, prompt, schema, budget, etapa, mod, timeout=900):
            self.chamadas.append(("claude", etapa, mod))
            return self.claude.pop(0)
        classify_news.chamar_codex, classify_news.chamar_claude_direto = codex, claude
        return self

    def __exit__(self, *a):
        classify_news.chamar_codex, classify_news.chamar_claude_direto = self._orig


class Fornecedor(unittest.TestCase):
    def chamar(self, falso, reg=None):
        reg = reg if reg is not None else {"chamadas": []}
        with falso:
            r = escrita.chamar("leitor", "s", "p", {}, reg, log=lambda *a: None)
        return r, reg

    def test_cota_troca_na_hora_sem_tentar_outro_modelo(self):
        f = Falso([_erro("You've hit your usage limit")], [_ok({"x": 1})])
        r, reg = self.chamar(f)
        self.assertTrue(r["ok"])
        self.assertEqual([c[0] for c in f.chamadas], ["codex", "claude"])
        self.assertEqual(reg["provedor"], "claude")
        self.assertEqual(reg["trocas"][0]["motivo"], "cota")

    def test_falha_passageira_tenta_a_alternativa_antes(self):
        f = Falso([_erro("stream disconnected"), _ok({"x": 1})])
        r, reg = self.chamar(f)
        self.assertTrue(r["ok"])
        self.assertEqual([c[0] for c in f.chamadas], ["codex", "codex"])
        self.assertEqual(f.chamadas[1][2], escrita.PAPEIS["leitor"]["alternativa"][0])
        self.assertEqual(reg["provedor"], "openai")

    def test_as_duas_fora_passam_ao_claude(self):
        f = Falso([_erro("timeout"), _erro("timeout")], [_ok({"x": 1})])
        r, reg = self.chamar(f)
        self.assertEqual([c[0] for c in f.chamadas], ["codex", "codex", "claude"])
        self.assertEqual(reg["provedor"], "claude")

    def test_esquema_nao_troca_de_fornecedor(self):
        f = Falso([_erro("saída do codex fora do esquema: x"), _erro("saída do codex fora do esquema: y")])
        r, reg = self.chamar(f)
        self.assertFalse(r["ok"])
        self.assertEqual(reg["provedor"], "openai")

    def test_dia_no_claude_continua_no_claude(self):
        f = Falso([], [_ok({"x": 1})])
        r, reg = self.chamar(f, {"chamadas": [], "provedor": "claude"})
        self.assertEqual([c[0] for c in f.chamadas], ["claude"])
        self.assertEqual(f.chamadas[0][2], escrita.PAPEIS["leitor"]["claude"])


def artigo(n, texto=None):
    return {"plano": {}, "respostas_a_revisao": [],
            "artigo": {"titulo": f"T{n}", "pergunta_semana": "", "texto": texto or f"Texto {n}.", "argumento": "a",
                       "porque": "p"}}


def problema(pid, impacto="alto", confianca="alta"):
    return {"id": pid, "impacto": impacto, "confianca": confianca, "tipo": "fidelidade", "local": "p1", "trecho": "t",
            "problema": "x", "efeito_para_a_leitora": "y", "evidencias": [], "correcao_necessaria": "z"}


def parecer(problemas=(), resolvidas=()):
    return {"pode_publicar": not problemas, "problemas": list(problemas),
            "resolvidas": [{"id": i, "prova": "ok"} for i in resolvidas], "pendencia_da_analise": ""}


class Ciclo(unittest.TestCase):
    def rodar(self, pareceres, impedimentos=None, prazo=3600, redator_falha_em=None, alerta=None, avisos=None,
              teto=None, palavras=()):
        """Cada parecer é a resposta do aprovador a uma versão; o redator e o leitor sempre respondem. `palavras` dá o
        tamanho de cada versão do redator, na ordem."""
        pareceres, imp, palavras = list(pareceres), list(impedimentos or []), list(palavras)
        n = {"v": 0}

        def codex(system, prompt, schema, etapa, timeout=600, modelo=None, raciocinio=None):
            if etapa == "redator":
                n["v"] += 1
                if redator_falha_em and n["v"] >= redator_falha_em:
                    return _erro("saída do codex fora do esquema")
                return _ok(artigo(n["v"], " ".join(["palavra"] * palavras.pop(0)) if palavras else None))
            if etapa == "leitor":
                return _ok({"entendi": {}, "dificuldades": [], "perguntas_que_ficaram": [], "titulos_ambiguos": []})
            return _ok(pareceres.pop(0))

        orig = classify_news.chamar_codex
        classify_news.chamar_codex = codex
        try:
            conferir = lambda a: {"impedimentos": imp.pop(0) if imp else [], "diagnosticos": []}  # noqa: E731
            return escrita.produzir("material", conferir, lambda x: x, time.time() + prazo, log=lambda *a: None,
                                    alerta=alerta, avisar=(avisos.append if avisos is not None else None), teto=teto)
        finally:
            classify_news.chamar_codex = orig

    def test_primeira_versao_sem_problema_sai(self):
        reg = self.rodar([parecer()])
        self.assertEqual(reg["estado"], "aprovado")
        self.assertEqual(reg["correcoes"], 0)

    def test_melhoria_media_nao_barra_depois_da_primeira_correcao(self):
        reg = self.rodar([parecer([problema("", "medio")]), parecer([problema("R1", "medio")])])
        self.assertEqual(reg["estado"], "aprovado")
        self.assertEqual(reg["correcoes"], 1)
        self.assertEqual(reg["objecoes"][0]["estado"], "aceita_no_dia")

    def test_alto_e_certo_continua_barrando_ate_resolver(self):
        reg = self.rodar([parecer([problema("")]), parecer([problema("R1")]), parecer([problema("R1")]),
                          parecer(resolvidas=["R1"])])
        self.assertEqual(reg["estado"], "aprovado")
        self.assertEqual(reg["correcoes"], 3)
        self.assertEqual(len(reg["objecoes"]), 1)  # o mesmo id, sem duplicar
        self.assertTrue(reg["versoes"][-1]["concentrada"])  # duas correções sem progresso concentram o artigo

    def test_alto_com_confianca_media_nao_barra_na_fase_estreita(self):
        reg = self.rodar([parecer([problema("")]), parecer([problema("", "alto", "media")], resolvidas=["R1"])])
        self.assertEqual(reg["estado"], "aprovado")

    def test_impedimento_do_codigo_barra(self):
        reg = self.rodar([parecer(), parecer()], impedimentos=[["marca [c9] sem linha"], []])
        self.assertEqual(reg["estado"], "aprovado")
        self.assertEqual(reg["correcoes"], 1)
        self.assertFalse(reg["versoes"][0]["pronta"])

    def test_correcao_que_falha_deixa_sair_a_ultima_versao_aprovada(self):
        # A versão 1 só tinha melhoria média (pronta); a correção trouxe um erro grave e a seguinte falhou.
        reg = self.rodar([parecer([problema("", "medio")]), parecer([problema("")])], redator_falha_em=3)
        self.assertEqual(reg["estado"], "versao_anterior")
        self.assertEqual(reg["artigo"]["titulo"], "T1")

    def test_sem_nenhuma_aprovada_sai_a_ultima_com_aviso(self):
        reg = self.rodar([parecer([problema("")])], prazo=1000)
        self.assertEqual(reg["estado"], "sem_aprovacao")


    def test_as_8h05_a_versao_aprovada_sai_sem_mais_correcao(self):
        # A versão 1 só tem melhoria média: já pode sair; depois das 8h05 ela sai, sem a correção que a fase pediria.
        reg = self.rodar([parecer([problema("", "medio")])], alerta=time.time() - 1)
        self.assertEqual(reg["estado"], "aprovado")
        self.assertEqual((reg["artigo"]["titulo"], reg["correcoes"]), ("T1", 0))

    def test_as_8h05_sem_aprovada_avisa_concentra_e_segue(self):
        avisos = []
        reg = self.rodar([parecer([problema("")]), parecer(resolvidas=["R1"])], alerta=time.time() - 1, avisos=avisos)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(reg["estado"], "aprovado")
        self.assertTrue(reg["versoes"][-1]["concentrada"])

    def test_aprovada_longa_ganha_um_corte_que_sai_se_o_aprovador_deixar(self):
        reg = self.rodar([parecer(), parecer()], teto=300, palavras=[400, 310])
        self.assertEqual((reg["estado"], reg["artigo"]["titulo"]), ("aprovado", "T2"))
        self.assertTrue(reg["versoes"][-1]["corte"])

    def test_corte_com_erro_grave_deixa_sair_a_aprovada(self):
        reg = self.rodar([parecer(), parecer([problema("")])], teto=300, palavras=[400, 300])
        self.assertEqual((reg["estado"], reg["artigo"]["titulo"]), ("versao_anterior", "T1"))

    def test_corte_que_nao_encurta_nem_vai_ao_aprovador(self):
        reg = self.rodar([parecer()], teto=300, palavras=[400, 420])
        self.assertEqual((reg["estado"], reg["artigo"]["titulo"], len(reg["versoes"])), ("aprovado", "T1", 1))

    def test_dentro_do_teto_nao_ha_corte(self):
        reg = self.rodar([parecer()], teto=300, palavras=[320])
        self.assertEqual((reg["artigo"]["titulo"], reg["correcoes"]), ("T1", 0))

    def test_depois_das_8h05_nao_ha_corte(self):
        reg = self.rodar([parecer()], teto=300, palavras=[400], alerta=time.time() - 1)
        self.assertEqual((reg["artigo"]["titulo"], reg["correcoes"]), ("T1", 0))


if __name__ == "__main__":
    unittest.main()
