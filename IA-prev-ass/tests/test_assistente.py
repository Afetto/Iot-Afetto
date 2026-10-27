"""Afetto Assistente: segurança, intenção, uso de contexto e fallback."""
import unittest

import apoio  # noqa: F401
import assistente
import dados

PERFIL = dados.perfil_para_ia(dados.buscar_pet("mel"))


def leitura(temp, atividade=1.0, status="normal"):
    return {"temperatura": temp, "atividade": atividade, "status": status, "recebido_em": "agora"}


class AssistenteTest(unittest.TestCase):
    def test_emergencia_nao_consulta_o_llm(self):
        chamado = []
        r = assistente.responder(PERFIL, "Ela está tendo uma convulsão!",
                                 llm=lambda p: chamado.append(p) or "texto")
        self.assertEqual(r["fonte"], "protocolo_emergencia")
        self.assertIn("AGORA", r["resposta"])
        self.assertEqual(chamado, [])

    def test_identifica_intencoes(self):
        casos = {"A temperatura está normal?": "temperatura", "Tomou a vacina?": "vacina",
                 "Posso dar o remédio?": "remedio", "Ela não está comendo": "alimentacao",
                 "Está muito parada hoje": "atividade", "Oi!": "geral"}
        for frase, esperado in casos.items():
            self.assertEqual(assistente.identificar_intencao(frase), esperado, frase)

    def test_prompt_leva_contexto_real_do_pet(self):
        prompt = assistente.montar_prompt(PERFIL, "Como ela está?", telemetria=leitura(40.1, status="atencao"))
        for trecho in ("Golden Retriever", "artrite", "meloxicam", "40.1", "NUNCA diagnostique"):
            self.assertIn(trecho, prompt)

    def test_usa_resposta_do_llm_quando_disponivel(self):
        r = assistente.responder(PERFIL, "Oi", llm=lambda p: "Olá! A Mel está bem.")
        self.assertEqual((r["fonte"], r["resposta"]), ("llama3", "Olá! A Mel está bem."))

    def test_fallback_temperatura_por_faixa(self):
        normal = assistente.responder(PERFIL, "temperatura?", telemetria=leitura(38.4), llm=lambda p: None)
        atencao = assistente.responder(PERFIL, "tem febre?", telemetria=leitura(40.5))
        critico = assistente.responder(PERFIL, "tem febre?", telemetria=leitura(43.8))
        self.assertEqual(normal["fonte"], "regras")
        self.assertIn("dentro da faixa normal", normal["resposta"])
        self.assertIn("fora da faixa normal", atencao["resposta"])
        self.assertIn("crítico", critico["resposta"])

    def test_fallback_vacinas_usa_historico(self):
        r = assistente.responder(PERFIL, "As vacinas estão em dia?")
        if PERFIL["vacinas_em_dia"] is False:
            self.assertIn("atrasadas", r["resposta"])
            self.assertIn("V10", r["resposta"])

    def test_fallback_sem_telemetria_nao_inventa(self):
        r = assistente.responder(PERFIL, "qual a temperatura?")
        self.assertIn("Ainda não recebi", r["resposta"])


if __name__ == "__main__":
    unittest.main()
