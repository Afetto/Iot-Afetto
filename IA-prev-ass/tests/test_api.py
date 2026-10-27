"""Integração: API Flask + base de pets + SQLite + Assistente."""
import unittest

from apoio import TesteComBanco
import db


class ApiTest(TesteComBanco):
    def test_lista_pets_da_base(self):
        r = self.client.get("/pets")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["nome"] for p in r.json], ["Bolinha", "Felix", "Mel"])

    def test_detalhe_traz_historico_clinico(self):
        r = self.client.get("/pets/mel")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["perfil"]["doencas_cronicas"], ["artrite"])
        self.assertEqual(self.client.get("/pets/rex").status_code, 404)

    def test_guard_completa_telemetria_com_dados_clinicos(self):
        r = self.client.post("/pets/risco", json={"nome": "Mel", "temperatura_atual": 38.6,
                                                  "atividade_atual": 1.0})
        self.assertEqual(r.json["metodo"]["contexto_clinico"], "base_local")
        self.assertTrue(any("sênior" in risco for risco in r.json["analise"]["riscos"]))
        self.assertEqual(db.listar_analises("mel")[0]["nivel"], r.json["analise"]["nivel"])

    def test_pet_desconhecido_usa_somente_telemetria(self):
        r = self.client.post("/pets/risco", json={"nome": "Rex", "temperatura_atual": 38.6,
                                                  "atividade_atual": 1.0})
        self.assertEqual(r.json["metodo"]["contexto_clinico"], "somente_telemetria")

    def test_analisar_exige_leitura_da_coleira(self):
        self.assertEqual(self.client.post("/pets/bolinha/analisar").status_code, 409)
        db.salvar_telemetria("bolinha", "Bolinha", 40.8, 1.0, "atencao")
        r = self.client.post("/pets/bolinha/analisar")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["analise"]["nivel"], "medio")

    def test_chat_responde_com_telemetria_e_guarda_conversa(self):
        db.salvar_telemetria("bolinha", "Bolinha", 40.8, 1.0, "atencao")
        r = self.client.post("/chat/mensagem", json={"pet_id": "bolinha",
                                                     "mensagem": "A temperatura está normal?"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["fonte"], "regras")
        self.assertIn("40.8", r.json["resposta"])
        historico = db.historico_sessao(r.json["sessao_id"])
        self.assertEqual([m["papel"] for m in historico], ["tutor", "afetto"])

    def test_chat_mantem_a_sessao(self):
        primeira = self.client.post("/chat/mensagem", json={"pet_id": "felix", "mensagem": "Oi"})
        sessao = primeira.json["sessao_id"]
        self.client.post("/chat/mensagem", json={"pet_id": "felix", "mensagem": "Vacinas?", "sessao_id": sessao})
        self.assertEqual(len(db.historico_sessao(sessao)), 4)

    def test_chat_valida_entrada(self):
        self.assertEqual(self.client.post("/chat/mensagem", json={"pet_id": "felix"}).status_code, 400)
        self.assertEqual(self.client.post("/chat/mensagem", json={"pet_id": "x", "mensagem": "oi"}).status_code, 404)
        longa = {"pet_id": "felix", "mensagem": "a" * 501}
        self.assertEqual(self.client.post("/chat/mensagem", json=longa).status_code, 400)

    def test_health_e_painel(self):
        h = self.client.get("/health").json
        self.assertEqual(h["pets_cadastrados"], 3)
        self.assertIn("banco", h)
        painel = self.client.get("/")
        self.assertEqual(painel.status_code, 200)
        self.assertIn(b"Afetto", painel.data)
        painel.close()


if __name__ == "__main__":
    unittest.main()
