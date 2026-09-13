import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard


class GuardApiTest(unittest.TestCase):
    def setUp(self):
        self.client = guard.app.test_client()

    def analisar(self, temperatura, atividade, **extras):
        payload = {
            "nome": "Bolinha",
            "temperatura_atual": temperatura,
            "atividade_atual": atividade,
            **extras,
        }
        with patch.object(guard, "chamar_llama", return_value=None):
            return self.client.post("/pets/risco", json=payload)

    def test_pet_saudavel(self):
        resposta = self.analisar(38.5, 1.0)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["analise"]["nivel"], "baixo")

    def test_febre_critica(self):
        resposta = self.analisar(40.8, 1.0)
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")
        self.assertGreaterEqual(resposta.json["analise"]["score_risco"], 70)

    def test_febre_e_inatividade_criticas(self):
        resposta = self.analisar(40.8, 0.1)
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")
        self.assertGreaterEqual(resposta.json["analise"]["score_risco"], 70)

    def test_llm_nao_altera_decisao(self):
        with patch.object(guard, "chamar_llama", return_value="Mensagem personalizada."):
            resposta = self.client.post("/pets/risco", json={
                "nome": "Bolinha",
                "temperatura_atual": 40.8,
                "atividade_atual": 0.1,
            })
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")
        self.assertEqual(resposta.json["analise"]["mensagem_tutor"], "Mensagem personalizada.")
        self.assertEqual(resposta.json["fonte"], "motor_de_regras+llama3")

    def test_rejeita_telemetria_invalida(self):
        resposta = self.client.post("/pets/risco", json={
            "nome": "Bolinha",
            "temperatura_atual": "quente",
            "atividade_atual": 1.0,
        })
        self.assertEqual(resposta.status_code, 400)


if __name__ == "__main__":
    unittest.main()
