"""
Simulador de coleira — publica no MQTT o mesmo payload do ESP32 (Wokwi).

Útil para testar o fluxo completo sem abrir o Wokwi ou para simular vários
pets ao mesmo tempo.

Uso:
    python simular_coleira.py                       # Bolinha em cenário normal
    python simular_coleira.py --pet Mel --cenario inativo
    python simular_coleira.py --pet Felix --cenario febre --vezes 10

Cenários: normal, febre (atenção), febre_critica, hipotermia, inativo
"""
import argparse
import json
import os
import random
import time
import uuid

import paho.mqtt.client as mqtt

from regras import classificar_temperatura

BROKER = os.getenv("AFETTO_MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("AFETTO_MQTT_PORT", "1883"))
TOPIC_BASE = os.getenv("AFETTO_MQTT_TOPIC", "afetto/coleira")

CENARIOS = {
    "normal": (38.2, 39.0, 0.9, 1.4),
    "febre": (40.2, 41.0, 0.8, 1.2),
    "febre_critica": (43.5, 44.0, 0.5, 0.9),
    "hipotermia": (32.5, 33.2, 0.3, 0.6),
    "inativo": (38.3, 38.9, 0.05, 0.2),
}


def leitura(cenario: str, pet: str) -> dict:
    tmin, tmax, amin, amax = CENARIOS[cenario]
    temp = round(random.uniform(tmin, tmax), 1)
    accel = round(random.uniform(amin, amax), 2)
    status, motivo = classificar_temperatura(temp)
    return {"status": status, "temp": temp, "accel": accel, "pet": pet, "motivo": motivo}


def main():
    parser = argparse.ArgumentParser(description="Simula a coleira Afetto via MQTT")
    parser.add_argument("--pet", default="Bolinha")
    parser.add_argument("--cenario", choices=CENARIOS, default="normal")
    parser.add_argument("--vezes", type=int, default=0, help="0 = infinito")
    parser.add_argument("--intervalo", type=float, default=3.0)
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"afetto-sim-{uuid.uuid4().hex[:8]}")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    print(f"[Simulador] {args.pet} · cenário {args.cenario} → {BROKER}:{PORT}")

    enviados = 0
    try:
        while args.vezes == 0 or enviados < args.vezes:
            d = leitura(args.cenario, args.pet)
            client.publish(f"{TOPIC_BASE}/temperatura", json.dumps({"valor": d["temp"], "pet": args.pet}))
            client.publish(f"{TOPIC_BASE}/movimento", json.dumps({"valor": d["accel"], "pet": args.pet}))
            client.publish(f"{TOPIC_BASE}/status", json.dumps(
                {"status": d["status"], "temp": d["temp"], "accel": d["accel"], "pet": args.pet}))
            if d["status"] != "normal":
                client.publish(f"{TOPIC_BASE}/alerta", json.dumps(
                    {"alerta": True, "nivel": d["status"], "motivo": d["motivo"], "pet": args.pet}))
            print(f"[Simulador] {d['temp']}°C | atividade {d['accel']} | {d['status']}")
            enviados += 1
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
