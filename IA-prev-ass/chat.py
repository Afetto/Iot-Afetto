"""
Afetto Assistente — versão de terminal.

Usa a mesma lógica do painel web (assistente.py), os perfis da base
data/pets.json e a telemetria gravada pelo mqtt_bridge.py no SQLite.
"""
import uuid

import assistente
import dados
import db
from llm import MODEL, chamar_llama, status_ollama

TELEMETRIA_MAX_IDADE = 120


def telemetria_recente(pet_id):
    leituras = db.listar_telemetria(pet_id, limite=1)
    if leituras and db.idade_segundos(leituras[0]["recebido_em"]) <= TELEMETRIA_MAX_IDADE:
        return leituras[0]
    return None


def ultima_analise(pet_id):
    analises = db.listar_analises(pet_id, limite=1)
    return analises[0]["resultado"]["analise"] if analises else None


def escolher_pet(pets: list[dict]) -> dict:
    print("\nEscolha o pet para conversar:\n")
    for i, pet in enumerate(pets, start=1):
        perfil = dados.perfil_para_ia(pet)
        vacinas = "✅" if perfil["vacinas_em_dia"] else "⚠️"
        leitura = telemetria_recente(perfil["pet_id"])
        iot = f" · 🌡️ {leitura['temperatura']}°C" if leitura else ""
        print(f"  [{i}] {perfil['nome']} — {perfil['especie']} {perfil['raca']}, "
              f"{perfil['idade_anos']} anos, vacinas {vacinas}{iot}")
    print()
    while True:
        escolha = input("Sua escolha: ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(pets):
            return dados.perfil_para_ia(pets[int(escolha) - 1])
        print("Opção inválida. Tente novamente.")


def exibir_perfil(perfil: dict):
    vacinas = "✅ Em dia" if perfil["vacinas_em_dia"] else f"⚠️  Atrasadas ({', '.join(perfil['vacinas_vencidas'])})"
    meses = perfil.get("ultima_consulta_meses")
    print(f"\n┌─ Conversando sobre: {perfil['nome']} ─────────────────")
    print(f"│  {perfil['especie'].capitalize()} · {perfil['raca']} · {perfil['idade_anos']} anos · {perfil['peso_kg']}kg")
    print(f"│  Vacinas: {vacinas} · Última consulta: há {meses if meses is not None else '?'} meses")
    exibir_iot(perfil)
    print(f"└{'─' * 45}")
    print("\nDigite sua mensagem ou:")
    print("  :iot     → mostra a leitura atual da coleira")
    print("  :trocar  → troca de pet")
    print("  :limpar  → começa uma nova conversa")
    print("  :sair    → encerra o chat\n")


def exibir_iot(perfil: dict):
    leitura = telemetria_recente(perfil["pet_id"])
    if leitura:
        print(f"│  IoT: {leitura['temperatura']}°C · atividade {leitura['atividade']} · {leitura['status']}")
    else:
        print("│  IoT: aguardando uma leitura recente da coleira (rode o mqtt_bridge.py)")


def iniciar_chat(pets: list[dict]):
    perfil = escolher_pet(pets)
    sessao = str(uuid.uuid4())
    exibir_perfil(perfil)

    while True:
        try:
            mensagem = input("👤 Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAté mais! 🐾")
            break

        comando = mensagem.lower()
        if not mensagem:
            continue
        if comando == ":sair":
            print("\nAté mais! Cuide bem do seu pet. 🐾")
            break
        if comando == ":trocar":
            perfil, sessao = escolher_pet(pets), str(uuid.uuid4())
            exibir_perfil(perfil)
            continue
        if comando == ":limpar":
            sessao = str(uuid.uuid4())
            print("── Nova conversa iniciada ──\n")
            continue
        if comando == ":iot":
            exibir_iot(perfil)
            continue

        print("🤔 Pensando...", end="\r")
        resultado = assistente.responder(
            perfil, mensagem,
            telemetria=telemetria_recente(perfil["pet_id"]),
            analise=ultima_analise(perfil["pet_id"]),
            historico=db.historico_sessao(sessao),
            llm=lambda prompt: chamar_llama(prompt, timeout=120),
        )
        db.salvar_mensagem(sessao, perfil["pet_id"], "tutor", mensagem)
        db.salvar_mensagem(sessao, perfil["pet_id"], "afetto", resultado["resposta"], resultado["fonte"])
        origem = {"llama3": "", "regras": "  (resposta por regras — Ollama indisponível)",
                  "protocolo_emergencia": "  (protocolo de emergência)"}[resultado["fonte"]]
        print(f"\n🐾 Afetto: {resultado['resposta']}{origem}\n")


if __name__ == "__main__":
    print("\n" + "═" * 50)
    print("  🐾 Afetto Assistente — Saúde Animal")
    print("═" * 50)

    status = status_ollama()
    if status["ollama"] == "conectado":
        print(f"\n✅ Ollama conectado · modelo {MODEL}")
    else:
        print("\n⚠️  Ollama não está rodando — respostas virão do motor de regras.")
        print("   Para usar o Llama: ollama serve  e  ollama pull " + MODEL)

    try:
        iniciar_chat(dados.carregar_pets())
    except dados.DadosInvalidos as e:
        print("\n❌ Base de pets inválida:")
        for problema in e.erros:
            print(f"   • {problema}")
