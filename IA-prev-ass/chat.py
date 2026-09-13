import requests
import json
import os
import time
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
TELEMETRIA_FILE = Path(
    os.getenv(
        "AFETTO_TELEMETRIA_FILE",
        str(Path(__file__).resolve().parent / "runtime" / "telemetria_atual.json"),
    )
)
TELEMETRIA_MAX_IDADE = int(os.getenv("AFETTO_TELEMETRIA_MAX_IDADE", "30"))

# ─────────────────────────────────────────────
# Perfis de pets para escolher no início
# ─────────────────────────────────────────────
PETS = {
    "1": {
        "nome": "Bolinha",
        "especie": "cão",
        "raca": "Labrador",
        "idade_anos": 3,
        "peso_kg": 28.0,
        "ultima_consulta_meses": 4,
        "vacinas_em_dia": True,
        "doencas_cronicas": [],
        "medicamentos_ativos": []
    },
    "2": {
        "nome": "Felix",
        "especie": "gato",
        "raca": "SRD",
        "idade_anos": 3,
        "peso_kg": 4.2,
        "ultima_consulta_meses": 8,
        "vacinas_em_dia": True,
        "doencas_cronicas": [],
        "medicamentos_ativos": []
    },
    "3": {
        "nome": "Mel",
        "especie": "cão",
        "raca": "Golden Retriever",
        "idade_anos": 9,
        "peso_kg": 32.0,
        "ultima_consulta_meses": 14,
        "vacinas_em_dia": False,
        "doencas_cronicas": ["artrite"],
        "medicamentos_ativos": ["meloxicam"]
    }
}


# ─────────────────────────────────────────────
# Chama o Llama via Ollama com streaming
# ─────────────────────────────────────────────
def chamar_llama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        print("🤔 Pensando...", end="\r")
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        resposta = response.json().get("response", "").strip()
        print("              ", end="\r")  # limpa o "Pensando..."
        return resposta
    except requests.exceptions.Timeout:
        return "Desculpe, demorei demais para responder. Tente novamente."
    except Exception as e:
        return "Estou com dificuldades técnicas agora. Se o seu pet estiver mal, consulte um veterinário."


def carregar_telemetria(pet: dict) -> dict:
    """Usa a última leitura MQTT somente se for recente e pertencer ao pet."""
    try:
        dados = json.loads(TELEMETRIA_FILE.read_text(encoding="utf-8"))
        idade = time.time() - float(dados.get("recebidoEmEpoch", 0))
        pet_evento = str(dados.get("pet", "")).strip().lower()
        pet_atual = str(pet.get("nome", "")).strip().lower()

        if idade > TELEMETRIA_MAX_IDADE:
            return {}
        if pet_evento and pet_evento != pet_atual:
            return {}

        return dados
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


# ─────────────────────────────────────────────
# Monta o prompt com contexto do pet
# ─────────────────────────────────────────────
def montar_prompt(pet: dict, historico: list, mensagem: str) -> str:
    doencas = ", ".join(pet.get("doencas_cronicas", [])) or "nenhuma"
    medicamentos = ", ".join(pet.get("medicamentos_ativos", [])) or "nenhum"
    vacinas = "em dia" if pet.get("vacinas_em_dia", True) else "ATRASADAS"
    telemetria = carregar_telemetria(pet)
    temp = telemetria.get("temperatura", "indisponível")
    atividade = telemetria.get("atividade", "indisponível")
    status_iot = telemetria.get("status", "indisponível")

    historico_formatado = ""
    for msg in historico[-8:]:
        role = "Tutor" if msg["role"] == "user" else "Afetto"
        historico_formatado += f"\n{role}: {msg['content']}"

    return f"""Você é o Afetto Chat, assistente de saúde animal empático e acessível.
Responda SEMPRE em português brasileiro, com tom amigável e cuidadoso.
NUNCA substitua o veterinário — oriente a consultar quando necessário.
Seja conciso — máximo 4 linhas por resposta.

Contexto do pet:
- Nome: {pet['nome']} | Espécie: {pet['especie']} | Raça: {pet.get('raca', 'SRD')}
- Idade: {pet.get('idade_anos', '?')} anos | Peso: {pet.get('peso_kg', '?')}kg
- Última consulta: há {pet.get('ultima_consulta_meses', '?')} meses
- Vacinas: {vacinas} | Medicamentos: {medicamentos}
- Doenças crônicas: {doencas}
- Dados IoT recentes — temperatura: {temp}°C | atividade: {atividade} | status: {status_iot}

Histórico da conversa:{historico_formatado if historico_formatado else ' (início da conversa)'}

Tutor: {mensagem}
Afetto:"""


# ─────────────────────────────────────────────
# Interface do terminal
# ─────────────────────────────────────────────
def exibir_cabecalho():
    print("\n" + "═" * 50)
    print("  🐾 Afetto Chat — Assistente de Saúde Animal")
    print("═" * 50)


def escolher_pet() -> dict:
    print("\nEscolha o pet para conversar:\n")
    for key, pet in PETS.items():
        vacinas = "✅" if pet["vacinas_em_dia"] else "⚠️"
        print(f"  [{key}] {pet['nome']} — {pet['especie']} {pet['raca']}, "
              f"{pet['idade_anos']} anos, vacinas {vacinas}")
    print("  [0] Cadastrar pet manualmente\n")

    while True:
        escolha = input("Sua escolha: ").strip()
        if escolha in PETS:
            return PETS[escolha]
        elif escolha == "0":
            return cadastrar_pet_manual()
        else:
            print("Opção inválida. Tente novamente.")


def cadastrar_pet_manual() -> dict:
    print("\n── Cadastro manual do pet ──")
    nome = input("Nome do pet: ").strip()
    especie = input("Espécie (cão/gato/outro): ").strip()
    raca = input("Raça (ou SRD): ").strip()

    try:
        idade = int(input("Idade em anos: ").strip())
    except:
        idade = 0

    try:
        peso = float(input("Peso em kg: ").strip())
    except:
        peso = 0.0

    try:
        meses = int(input("Última consulta há quantos meses: ").strip())
    except:
        meses = 0

    vacinas_input = input("Vacinas em dia? (s/n): ").strip().lower()
    vacinas = vacinas_input == "s"

    return {
        "nome": nome,
        "especie": especie,
        "raca": raca,
        "idade_anos": idade,
        "peso_kg": peso,
        "ultima_consulta_meses": meses,
        "vacinas_em_dia": vacinas,
        "doencas_cronicas": [],
        "medicamentos_ativos": []
    }


def exibir_perfil_pet(pet: dict):
    vacinas = "✅ Em dia" if pet["vacinas_em_dia"] else "⚠️  Atrasadas"
    print(f"\n┌─ Conversando sobre: {pet['nome']} ─────────────────")
    print(f"│  {pet['especie'].capitalize()} · {pet['raca']} · {pet['idade_anos']} anos · {pet['peso_kg']}kg")
    print(f"│  Vacinas: {vacinas} · Última consulta: há {pet['ultima_consulta_meses']} meses")
    telemetria = carregar_telemetria(pet)
    if telemetria:
        print(f"│  IoT: {telemetria['temperatura']}°C · atividade {telemetria['atividade']} · {telemetria['status']}")
    else:
        print("│  IoT: aguardando uma leitura recente da coleira")
    print(f"└{'─' * 45}")
    print("\nDigite sua mensagem ou:")
    print("  :sair    → encerra o chat")
    print("  :trocar  → troca de pet")
    print("  :limpar  → limpa o histórico\n")


def iniciar_chat(pet: dict):
    historico = []
    exibir_perfil_pet(pet)

    while True:
        try:
            mensagem = input("👤 Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAté mais! 🐾")
            break

        if not mensagem:
            continue

        if mensagem.lower() == ":sair":
            print("\nAté mais! Cuide bem do seu pet. 🐾")
            break

        if mensagem.lower() == ":trocar":
            pet = escolher_pet()
            historico = []
            exibir_perfil_pet(pet)
            continue

        if mensagem.lower() == ":limpar":
            historico = []
            print("── Histórico limpo ──\n")
            continue

        prompt = montar_prompt(pet, historico, mensagem)
        resposta = chamar_llama(prompt)

        print(f"\n🐾 Afetto: {resposta}\n")

        historico.append({"role": "user", "content": mensagem})
        historico.append({"role": "assistant", "content": resposta})

        # Limita histórico a 20 mensagens
        if len(historico) > 20:
            historico = historico[-20:]


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    exibir_cabecalho()

    # Verifica se o Ollama está rodando
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        modelos = [m["name"] for m in r.json().get("models", [])]
        if "llama3:latest" in modelos or "llama3" in modelos:
            print(f"\n✅ Ollama conectado · Llama 3 disponível")
        else:
            print(f"\n⚠️  Ollama conectado mas Llama 3 não encontrado")
            print("   Rode: ollama pull llama3")
    except:
        print("\n❌ Ollama não está rodando!")
        print("   Rode: ollama serve")
        exit(1)

    pet = escolher_pet()
    iniciar_chat(pet)
