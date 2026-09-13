from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

# ─────────────────────────────────────────────
# Utilitário: chama o Llama via Ollama
# ─────────────────────────────────────────────
def chamar_llama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception:
        return None


# ─────────────────────────────────────────────
# Motor de regras — fonte oficial da decisão de risco
# ─────────────────────────────────────────────
def calcular_score_regras(data):
    score = 0
    riscos = []
    recomendacoes = []

    if data.get("vacinas_em_dia") is False:
        score += 15
        riscos.append("Vacinas atrasadas — risco de doenças infecciosas")
        recomendacoes.append({
            "urgencia": "PREVENTIVO",
            "acao": "Atualizar protocolo vacinal o quanto antes"
        })

    meses = data.get("ultima_consulta_meses")
    meses = meses if isinstance(meses, (int, float)) else 0
    if meses > 12:
        score += 15
        riscos.append(f"Sem consulta há {meses} meses")
        recomendacoes.append({
            "urgencia": "PREVENTIVO",
            "acao": "Agendar check-up de rotina"
        })
    elif meses > 6:
        score += 10

    temp = data.get("temperatura_atual")
    if temp > 40.0:
        score += 70
        riscos.append(f"Temperatura crítica: {temp}°C — possível febre alta")
        recomendacoes.append({
            "urgencia": "URGENTE",
            "acao": "Levar ao veterinário imediatamente"
        })
    elif temp > 39.0:
        score += 15
        riscos.append(f"Temperatura elevada: {temp}°C")
        recomendacoes.append({
            "urgencia": "PREVENTIVO",
            "acao": "Monitorar temperatura nas próximas horas"
        })

    atividade = data.get("atividade_atual")
    if atividade < 0.3:
        score += 70
        riscos.append("Inatividade severa detectada")
        recomendacoes.append({
            "urgencia": "URGENTE",
            "acao": "Verificar estado do pet — pode indicar dor ou letargia"
        })
    elif atividade < 0.8:
        score += 10
        riscos.append("Atividade abaixo do normal")

    idade = data.get("idade_anos")
    idade = idade if isinstance(idade, (int, float)) else 0
    if data.get("especie", "").lower() == "cão" and idade >= 7:
        score += 10
        riscos.append(f"Pet sênior ({idade} anos) — maior predisposição a doenças degenerativas")
        recomendacoes.append({
            "urgencia": "PREVENTIVO",
            "acao": "Check-up semestral recomendado para pets sênior"
        })

    if score >= 70:
        nivel = "critico"
    elif score >= 40:
        nivel = "alto"
    elif score >= 20:
        nivel = "medio"
    else:
        nivel = "baixo"

    if not riscos:
        riscos = ["Nenhum risco identificado — pet saudável"]

    score = min(score, 100)
    return {
        "score_risco": score,
        "nivel": nivel,
        "riscos": riscos,
        "recomendacoes": recomendacoes,
        "mensagem_tutor": f"{data['nome']} está com score {score}/100. {'Atenção necessária!' if score >= 40 else 'Sem alteração importante neste momento.'}"
    }


def personalizar_mensagem(data, analise_base):
    """O LLM explica a decisão; score, nível e ações nunca são alterados por ele."""
    prompt = f"""Você é o Afetto, assistente preventivo de saúde animal.
Responda em português brasileiro, com empatia, clareza e no máximo 3 linhas.
Não diagnostique, não altere o nível de risco e não invente dados.

Pet: {data['nome']}
Temperatura: {data['temperatura_atual']}°C
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


# ─────────────────────────────────────────────
# Rota principal — análise de risco
# POST /pets/risco
# ─────────────────────────────────────────────
@app.route("/pets/risco", methods=["POST"])
def analisar_risco():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"erro": "O corpo deve ser um JSON válido"}), 400

    # A telemetria MQTT conhece apenas o pet/dispositivo e os sensores.
    # Dados clínicos ausentes permanecem desconhecidos, em vez de serem simulados.
    campos = ["nome", "temperatura_atual", "atividade_atual"]
    for campo in campos:
        if campo not in data:
            return jsonify({"erro": f"Campo obrigatório ausente: {campo}"}), 400

    if not isinstance(data["nome"], str) or not data["nome"].strip():
        return jsonify({"erro": "O campo nome deve ser um texto não vazio"}), 400

    for campo in ("temperatura_atual", "atividade_atual"):
        valor = data[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return jsonify({"erro": f"O campo {campo} deve ser numérico"}), 400

    if not 0 <= data["temperatura_atual"] <= 60:
        return jsonify({"erro": "temperatura_atual fora da faixa aceita"}), 400
    if not 0 <= data["atividade_atual"] <= 20:
        return jsonify({"erro": "atividade_atual fora da faixa aceita"}), 400

    analise = calcular_score_regras(data)
    mensagem_personalizada = personalizar_mensagem(data, analise)
    fonte = "motor_de_regras"
    if mensagem_personalizada:
        analise["mensagem_tutor"] = mensagem_personalizada
        fonte = "motor_de_regras+llama3"

    return jsonify({
        "pet": data["nome"],
        "analise": analise,
        "fonte": fonte,
        "metodo": {
            "decisao": "regras_deterministicas",
            "personalizacao": "llama3" if mensagem_personalizada else "fallback_local"
        }
    }), 200


# ─────────────────────────────────────────────
# Health check
# GET /health
# ─────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        ollama_ok = r.status_code == 200
        modelos = [m["name"] for m in r.json().get("models", [])]
    except:
        ollama_ok = False
        modelos = []

    return jsonify({
        "status": "ok",
        "servico": "Afetto Guard — IA Preventiva",
        "ollama": "conectado" if ollama_ok else "desconectado",
        "modelos_disponiveis": modelos
    }), 200


if __name__ == "__main__":
    print("🛡️  Afetto Guard — IA Preventiva")
    print("   POST http://localhost:5000/pets/risco")
    print("   GET  http://localhost:5000/health")
    print("─" * 45)
    app.run(debug=False, port=5000)
