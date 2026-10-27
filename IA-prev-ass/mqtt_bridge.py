import json
import os
import queue
import signal
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt
import requests

import dados
import db


BROKER = os.getenv("AFETTO_MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("AFETTO_MQTT_PORT", "1883"))
TOPIC_BASE = os.getenv("AFETTO_MQTT_TOPIC", "afetto/coleira")
GUARD_URL = os.getenv("AFETTO_GUARD_URL", "http://localhost:5000/pets/risco")
PET_ID = os.getenv("AFETTO_PET_ID", "")
PET_NAME = os.getenv("AFETTO_PET_NAME", "Bolinha")
DEVICE_ID = os.getenv("AFETTO_DEVICE_ID", "coleira-001")

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
TELEMETRIA_FILE = Path(
    os.getenv("AFETTO_TELEMETRIA_FILE", str(RUNTIME_DIR / "telemetria_atual.json"))
)
ANALISE_FILE = Path(
    os.getenv("AFETTO_ANALISE_FILE", str(RUNTIME_DIR / "ultima_analise.json"))
)

INTERVALO_NORMAL = int(os.getenv("AFETTO_INTERVALO_NORMAL", "300"))
INTERVALO_ALERTA = int(os.getenv("AFETTO_INTERVALO_ALERTA", "60"))

estado = {
    "petId": PET_ID,
    "pet": PET_NAME,
    "deviceId": DEVICE_ID,
    "temperatura": None,
    "atividade": None,
    "status": "desconhecido",
}

fila_analise: queue.Queue[dict] = queue.Queue(maxsize=1)
parar = threading.Event()
ultimo_status = None
ultima_analise = 0.0


def salvar_json_atomico(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(caminho)


def identificar_pet(leitura: dict) -> dict | None:
    """Liga a leitura da coleira ao pet da base (por id, nome ou device_id)."""
    try:
        pets = dados.carregar_pets()
    except dados.DadosInvalidos as erro:
        print(f"[Dados] base de pets inválida: {erro}")
        return None
    for chave in (leitura.get("petId"), leitura.get("pet"), leitura.get("deviceId")):
        pet = dados.buscar_pet(chave, pets) if chave else None
        if pet:
            return pet
    return None


def persistir_leitura(leitura: dict) -> None:
    pet = identificar_pet(leitura)
    if pet:
        leitura["petId"] = pet["id"]
    db.salvar_telemetria(
        pet_id=leitura.get("petId") or None,
        pet_nome=leitura.get("pet") or PET_NAME,
        temperatura=leitura["temperatura"],
        atividade=leitura["atividade"],
        status=leitura.get("status"),
        device_id=leitura.get("deviceId"),
        alerta=leitura.get("alerta"),
    )


def montar_payload_guard(leitura: dict) -> dict:
    """Envia somente fatos conhecidos; o Guard não inventa o restante."""
    return {
        "pet_id": leitura.get("petId") or None,
        "nome": leitura.get("pet") or PET_NAME,
        "temperatura_atual": leitura["temperatura"],
        "atividade_atual": leitura["atividade"],
        "device_id": leitura.get("deviceId") or DEVICE_ID,
        "capturado_em": leitura.get("recebidoEm"),
        "status_sensor": leitura.get("status"),
    }


def trabalhador_guard() -> None:
    while not parar.is_set():
        try:
            leitura = fila_analise.get(timeout=1)
        except queue.Empty:
            continue

        try:
            response = requests.post(
                GUARD_URL, json=montar_payload_guard(leitura), timeout=90
            )
            response.raise_for_status()
            resultado = response.json()
            resultado["telemetria"] = leitura
            resultado["analisadoEm"] = time.strftime(
                "%Y-%m-%dT%H:%M:%S%z", time.localtime()
            )
            salvar_json_atomico(ANALISE_FILE, resultado)

            analise = resultado.get("analise", {})
            print(
                f"[Guard] {resultado.get('pet', '?')}: "
                f"{analise.get('nivel', '?')} "
                f"({analise.get('score_risco', '?')}/100)"
            )
        except requests.RequestException as erro:
            print(f"[Guard] indisponível: {erro}")
        except (ValueError, OSError) as erro:
            print(f"[Guard] resposta inválida: {erro}")
        finally:
            fila_analise.task_done()


def agendar_analise(leitura: dict) -> None:
    global ultimo_status, ultima_analise

    if leitura.get("temperatura") is None or leitura.get("atividade") is None:
        return

    agora = time.time()
    status = leitura.get("status", "desconhecido")
    mudou = status != ultimo_status
    intervalo = INTERVALO_ALERTA if status in {"atencao", "critico"} else INTERVALO_NORMAL

    if mudou or agora - ultima_analise >= intervalo:
        copia = dict(leitura)
        try:
            fila_analise.put_nowait(copia)
            ultima_analise = agora
        except queue.Full:
            # Uma análise já está em andamento; a telemetria continua sendo atualizada.
            pass

    ultimo_status = status


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if not reason_code.is_failure:
        print(f"[MQTT] conectado a {BROKER}:{PORT}")
        client.subscribe(f"{TOPIC_BASE}/#")
    else:
        print(f"[MQTT] conexão recusada: {reason_code}")


def on_message(client, userdata, message) -> None:
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        sufixo = message.topic.rsplit("/", 1)[-1]

        if sufixo == "temperatura":
            estado["temperatura"] = float(payload["valor"])
        elif sufixo == "movimento":
            estado["atividade"] = float(payload["valor"])
        elif sufixo == "status":
            estado["temperatura"] = float(payload["temp"])
            estado["atividade"] = float(payload["accel"])
            estado["status"] = payload.get("status", "desconhecido")
            if estado["status"] == "normal":
                estado.pop("alerta", None)
        elif sufixo == "alerta":
            estado["alerta"] = payload.get("motivo")
        else:
            return

        estado["petId"] = payload.get("petId", estado.get("petId"))
        estado["pet"] = payload.get("pet", estado.get("pet"))
        estado["deviceId"] = payload.get("deviceId", estado.get("deviceId"))
        estado["sequencia"] = payload.get("sequencia", estado.get("sequencia"))
        estado["recebidoEm"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S%z", time.localtime()
        )
        estado["recebidoEmEpoch"] = time.time()

        salvar_json_atomico(TELEMETRIA_FILE, estado)

        if sufixo == "status":
            persistir_leitura(estado)
            salvar_json_atomico(TELEMETRIA_FILE, estado)
            print(
                f"[IoT] {estado['temperatura']:.1f}°C | "
                f"atividade {estado['atividade']:.2f} | {estado['status']}"
            )
            agendar_analise(estado)

    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
        print(f"[MQTT] payload inválido em {message.topic}: {erro}")
    except (OSError, sqlite3.Error) as erro:
        print(f"[MQTT] não foi possível salvar a telemetria: {erro}")


def encerrar(signum=None, frame=None) -> None:
    parar.set()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, encerrar)
    signal.signal(signal.SIGTERM, encerrar)

    worker = threading.Thread(target=trabalhador_guard, daemon=True)
    worker.start()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"afetto-ai-{uuid.uuid4().hex[:10]}",
    )
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] escutando {TOPIC_BASE}/#")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()

    try:
        while not parar.wait(1):
            pass
    finally:
        client.disconnect()
        client.loop_stop()
        print("[MQTT] encerrado")
