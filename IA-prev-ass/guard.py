"""
Afetto Guard — servidor da IA do Afetto (Flask).

Rotas:
  GET  /                         painel web do tutor
  GET  /health                   status do serviço, Ollama e banco
  GET  /pets                     pets da base com última leitura e último risco
  GET  /pets/<id>                perfil, histórico clínico, telemetria e análises
  POST /pets/<id>/analisar       roda o Guard com a última leitura da coleira
  POST /pets/risco               análise de risco (usada pelo mqtt_bridge.py)
  POST /chat/mensagem            Afetto Assistente (chat com contexto)
"""
import json
import os
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import assistente
import db
import dados
from llm import chamar_llama, status_ollama
from regras import calcular_score_regras  # noqa: F401  (reexportado para os testes)

BASE_DIR = Path(__file__).resolve().parent
TELEMETRIA_MAX_IDADE = int(os.getenv("AFETTO_TELEMETRIA_MAX_IDADE", "120"))

app = Flask(__name__)
app.json.ensure_ascii = False


# ─────────────────────────────────────────────
# Apoio
# ─────────────────────────────────────────────
def erro(mensagem, status=400, **extra):
    return jsonify({"erro": mensagem, **extra}), status


@app.errorhandler(dados.DadosInvalidos)
def base_invalida(e):
    return erro("Base de pets inválida", 500, detalhes=e.erros)


def perfil_por_chave(chave):
    pet = dados.buscar_pet(chave, dados.carregar_pets())
    return dados.perfil_para_ia(pet) if pet else None


def telemetria_recente(pet_id):
    leituras = db.listar_telemetria(pet_id, limite=1)
    if leituras and db.idade_segundos(leituras[0]["recebido_em"]) <= TELEMETRIA_MAX_IDADE:
        return leituras[0]
    return None


def ultima_analise(pet_id):
    analises = db.listar_analises(pet_id, limite=1)
    return analises[0]["resultado"]["analise"] if analises else None


# ─────────────────────────────────────────────
# IA preventiva
# ─────────────────────────────────────────────
def personalizar_mensagem(data, analise_base):
    """O LLM explica a decisão; score, nível e ações nunca são alterados por ele."""
    perfil = ""
    if data.get("raca") or data.get("idade_anos") is not None:
        perfil = (f"Perfil: {data.get('especie', '?')} {data.get('raca', '')}, "
                  f"{data.get('idade_anos', '?')} anos; doenças crônicas: "
                  f"{', '.join(data.get('doencas_cronicas', [])) or 'nenhuma'}; "
                  f"medicamentos: {', '.join(data.get('medicamentos_ativos', [])) or 'nenhum'}\n")

    prompt = f"""Você é o Afetto, assistente preventivo de saúde animal.
Responda em português brasileiro, com empatia, clareza e no máximo 3 linhas.
Não diagnostique, não altere o nível de risco e não invente dados.

Pet: {data['nome']}
{perfil}Temperatura: {data['temperatura_atual']}°C
Atividade: {data['atividade_atual']}
Nível calculado pelo motor de regras: {analise_base['nivel']}
Score calculado: {analise_base['score_risco']}/100
Riscos observados: {json.dumps(analise_base['riscos'], ensure_ascii=False)}
Recomendações: {json.dumps(analise_base['recomendacoes'], ensure_ascii=False)}

Escreva somente a mensagem final para o tutor."""

    resposta = chamar_llama(prompt)
    if not resposta:
        return None
    return resposta.strip().strip('"')[:600]


def validar_telemetria(data):
    if not isinstance(data, dict):
        return "O corpo deve ser um JSON válido"
    for campo in ("nome", "temperatura_atual", "atividade_atual"):
        if campo not in data:
            return f"Campo obrigatório ausente: {campo}"
    if not isinstance(data["nome"], str) or not data["nome"].strip():
        return "O campo nome deve ser um texto não vazio"
    for campo in ("temperatura_atual", "atividade_atual"):
        valor = data[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return f"O campo {campo} deve ser numérico"
    if not 0 <= data["temperatura_atual"] <= 60:
        return "temperatura_atual fora da faixa aceita"
    if not 0 <= data["atividade_atual"] <= 20:
        return "atividade_atual fora da faixa aceita"
    return None


def executar_analise(data: dict) -> dict:
    """Completa a telemetria com o histórico clínico da base, decide e persiste."""
    perfil = perfil_por_chave(data.get("pet_id") or data.get("nome"))
    if perfil:
        # Dados enviados na requisição têm prioridade; o restante vem da base.
        data = {**perfil, **{k: v for k, v in data.items() if v is not None}}

    analise = calcular_score_regras(data)
    mensagem = personalizar_mensagem(data, analise)
    if mensagem:
        analise["mensagem_tutor"] = mensagem

    resultado = {
        "pet": data["nome"],
        "pet_id": perfil["pet_id"] if perfil else data.get("pet_id"),
        "analise": analise,
        "fonte": "motor_de_regras+llama3" if mensagem else "motor_de_regras",
        "metodo": {
            "decisao": "regras_deterministicas",
            "personalizacao": "llama3" if mensagem else "fallback_local",
            "contexto_clinico": "base_local" if perfil else "somente_telemetria",
        },
    }
    db.salvar_analise(resultado["pet_id"], resultado["pet"], resultado)
    return resultado


@app.route("/pets/risco", methods=["POST"])
def analisar_risco():
    data = request.get_json(silent=True)
    problema = validar_telemetria(data)
    if problema:
        return erro(problema)
    return jsonify(executar_analise(data)), 200


@app.route("/pets/<pet_id>/analisar", methods=["POST"])
def analisar_pet(pet_id):
    perfil = perfil_por_chave(pet_id)
    if not perfil:
        return erro("Pet não encontrado", 404)
    leituras = db.listar_telemetria(perfil["pet_id"], limite=1)
    if not leituras:
        return erro("Ainda não há leitura da coleira para este pet", 409)
    leitura = leituras[0]
    return jsonify(executar_analise({
        "pet_id": perfil["pet_id"], "nome": perfil["nome"],
        "temperatura_atual": leitura["temperatura"], "atividade_atual": leitura["atividade"],
    })), 200


# ─────────────────────────────────────────────
# Consulta de dados (painel e integrações)
# ─────────────────────────────────────────────
@app.route("/pets", methods=["GET"])
def listar_pets():
    itens = []
    for pet in dados.carregar_pets():
        perfil = dados.perfil_para_ia(pet)
        leitura = db.listar_telemetria(perfil["pet_id"], limite=1)
        analise = ultima_analise(perfil["pet_id"])
        itens.append({
            "pet_id": perfil["pet_id"], "nome": perfil["nome"], "especie": perfil["especie"],
            "raca": perfil["raca"], "idade_anos": perfil["idade_anos"],
            "vacinas_em_dia": perfil["vacinas_em_dia"],
            "ultima_leitura": leitura[0] if leitura else None,
            "risco": {"nivel": analise["nivel"], "score": analise["score_risco"]} if analise else None,
        })
    return jsonify(itens), 200


@app.route("/pets/<pet_id>", methods=["GET"])
def detalhar_pet(pet_id):
    perfil = perfil_por_chave(pet_id)
    if not perfil:
        return erro("Pet não encontrado", 404)
    return jsonify({
        "perfil": perfil,
        "telemetria": db.listar_telemetria(perfil["pet_id"], limite=20),
        "telemetria_recente": telemetria_recente(perfil["pet_id"]) is not None,
        "analises": [a["resultado"] | {"criado_em": a["criado_em"]}
                     for a in db.listar_analises(perfil["pet_id"], limite=5)],
    }), 200


# ─────────────────────────────────────────────
# Afetto Assistente
# ─────────────────────────────────────────────
@app.route("/chat/mensagem", methods=["POST"])
def chat_mensagem():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return erro("O corpo deve ser um JSON válido")
    mensagem = str(data.get("mensagem", "")).strip()
    if not mensagem:
        return erro("Campo obrigatório ausente: mensagem")
    if len(mensagem) > 500:
        return erro("A mensagem deve ter no máximo 500 caracteres")

    perfil = perfil_por_chave(data.get("pet_id"))
    if not perfil:
        return erro("Pet não encontrado", 404)

    sessao_id = str(data.get("sessao_id") or uuid.uuid4())
    historico = db.historico_sessao(sessao_id)
    resultado = assistente.responder(
        perfil, mensagem,
        telemetria=telemetria_recente(perfil["pet_id"]),
        analise=ultima_analise(perfil["pet_id"]),
        historico=historico,
        llm=lambda prompt: chamar_llama(prompt, timeout=120),
    )
    db.salvar_mensagem(sessao_id, perfil["pet_id"], "tutor", mensagem)
    db.salvar_mensagem(sessao_id, perfil["pet_id"], "afetto", resultado["resposta"], resultado["fonte"])
    return jsonify({"sessao_id": sessao_id, "pet": perfil["nome"], **resultado}), 200


# ─────────────────────────────────────────────
# Painel e health check
# ─────────────────────────────────────────────
@app.route("/", methods=["GET"])
def painel():
    return send_from_directory(BASE_DIR / "web", "painel.html")


@app.route("/health", methods=["GET"])
def health():
    try:
        pets = len(dados.carregar_pets())
        base = "ok"
    except dados.DadosInvalidos as e:
        pets, base = 0, f"inválida: {e}"
    return jsonify({
        "status": "ok",
        "servico": "Afetto Guard — IA Preventiva e Assistente",
        **status_ollama(),
        "base_pets": base,
        "pets_cadastrados": pets,
        "banco": db.resumo(),
    }), 200


if __name__ == "__main__":
    print("🛡️  Afetto Guard — IA Preventiva e Assistente")
    print("   Painel  http://localhost:5000/")
    print("   API     POST /pets/risco · POST /chat/mensagem · GET /pets")
    print("─" * 45)
    app.run(host=os.getenv("AFETTO_HOST", "127.0.0.1"), debug=False, port=5000)
