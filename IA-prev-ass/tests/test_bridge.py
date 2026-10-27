"""Ponte MQTT: payloads da coleira viram registros no banco ligados ao pet."""
import json
import unittest
from types import SimpleNamespace

from apoio import TesteComBanco
import db
import mqtt_bridge


def mensagem(topico, payload):
    corpo = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return SimpleNamespace(topic=f"afetto/coleira/{topico}", payload=corpo)


class BridgeTest(TesteComBanco):
    def setUp(self):
        super().setUp()
        mqtt_bridge.TELEMETRIA_FILE = mqtt_bridge.Path(self._tmp.name) / "telemetria.json"
        mqtt_bridge.estado.update({"petId": "", "pet": "Bolinha", "status": "desconhecido"})
        while not mqtt_bridge.fila_analise.empty():
            mqtt_bridge.fila_analise.get_nowait()
            mqtt_bridge.fila_analise.task_done()

    def test_status_e_gravado_no_banco_com_o_pet(self):
        mqtt_bridge.on_message(None, None, mensagem("status", {
            "status": "atencao", "temp": 40.8, "accel": 1.1, "pet": "Mel"}))
        leitura = db.listar_telemetria("mel")[0]
        self.assertEqual((leitura["temperatura"], leitura["status"]), (40.8, "atencao"))

    def test_mudanca_de_status_agenda_analise(self):
        mqtt_bridge.on_message(None, None, mensagem("status", {
            "status": "critico", "temp": 43.9, "accel": 1.0, "pet": "Bolinha"}))
        self.assertFalse(mqtt_bridge.fila_analise.empty())
        payload = mqtt_bridge.montar_payload_guard(mqtt_bridge.fila_analise.get_nowait())
        mqtt_bridge.fila_analise.task_done()
        self.assertEqual((payload["pet_id"], payload["temperatura_atual"]), ("bolinha", 43.9))

    def test_payload_invalido_nao_derruba_a_ponte(self):
        mqtt_bridge.on_message(None, None, mensagem("status", b"isso nao e json"))
        mqtt_bridge.on_message(None, None, mensagem("status", {"status": "normal"}))
        self.assertEqual(db.resumo()["telemetria"], 0)


if __name__ == "__main__":
    unittest.main()
