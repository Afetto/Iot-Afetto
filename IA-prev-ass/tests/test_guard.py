import unittest
from unittest.mock import patch

from apoio import TesteComBanco
import guard


class GuardApiTest(TesteComBanco):

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

    def test_temperatura_elevada_e_atencao(self):
        resposta = self.analisar(40.8, 1.0)
        self.assertEqual(resposta.json["analise"]["nivel"], "medio")

    def test_limites_da_faixa_normal(self):
        for temp in (37.5, 39.2):
            self.assertEqual(self.analisar(temp, 1.0).json["analise"]["nivel"], "baixo")

    def test_temperatura_baixa_e_atencao(self):
        resposta = self.analisar(35.0, 1.0)
        self.assertEqual(resposta.json["analise"]["nivel"], "medio")

    def test_febre_critica(self):
        resposta = self.analisar(43.5, 1.0)
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")
        self.assertGreaterEqual(resposta.json["analise"]["score_risco"], 70)

    def test_hipotermia_critica(self):
        resposta = self.analisar(32.0, 1.0)
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")

    def test_febre_e_inatividade_criticas(self):
        resposta = self.analisar(40.8, 0.1)
        self.assertEqual(resposta.json["analise"]["nivel"], "critico")
        self.assertGreaterEqual(resposta.json["analise"]["score_risco"], 70)

    def test_llm_nao_altera_decisao(self):
        with patch.object(guard, "chamar_llama", return_value="Mensagem personalizada."):
            resposta = self.client.post("/pets/risco", json={
                "nome": "Bolinha",
                "temperatura_atual": 43.5,
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
