"""
Motor de regras do Afetto — fonte oficial da decisão de risco.

As faixas de temperatura são as mesmas do firmware da coleira (Wokwi):
normal 37,5–39,2 °C | atenção até 4 °C fora da faixa | crítico além disso.
O LLM nunca altera score, nível ou recomendações calculados aqui.
"""

TEMP_NORMAL_MIN = 37.5
TEMP_NORMAL_MAX = 39.2
TEMP_ALERTA_MIN = 33.5   # 37.5 - 4
TEMP_ALERTA_MAX = 43.2   # 39.2 + 4

ATIVIDADE_SEVERA = 0.3
ATIVIDADE_BAIXA = 0.8


def classificar_temperatura(temp: float) -> tuple[str, str]:
    """Retorna (status, motivo) com a mesma lógica if/else do ESP32."""
    if TEMP_NORMAL_MIN <= temp <= TEMP_NORMAL_MAX:
        return "normal", ""
    if TEMP_ALERTA_MIN <= temp < TEMP_NORMAL_MIN:
        return "atencao", "temperatura_baixa"
    if TEMP_NORMAL_MAX < temp <= TEMP_ALERTA_MAX:
        return "atencao", "temperatura_elevada"
    if temp > TEMP_ALERTA_MAX:
        return "critico", "febre_critica"
    return "critico", "hipotermia_critica"


def calcular_score_regras(data: dict) -> dict:
    score = 0
    riscos = []
    recomendacoes = []

    if data.get("vacinas_em_dia") is False:
        score += 15
        vencidas = data.get("vacinas_vencidas") or []
        detalhe = f" ({', '.join(vencidas)})" if vencidas else ""
        riscos.append(f"Vacinas atrasadas{detalhe} — risco de doenças infecciosas")
        recomendacoes.append({"urgencia": "PREVENTIVO",
                              "acao": "Atualizar protocolo vacinal o quanto antes"})

    meses = data.get("ultima_consulta_meses")
    meses = meses if isinstance(meses, (int, float)) and not isinstance(meses, bool) else 0
    if meses > 12:
        score += 15
        riscos.append(f"Sem consulta há {meses} meses")
        recomendacoes.append({"urgencia": "PREVENTIVO", "acao": "Agendar check-up de rotina"})
    elif meses > 6:
        score += 10

    temp = data["temperatura_atual"]
    status_temp, _ = classificar_temperatura(temp)
    if status_temp == "critico" and temp > TEMP_ALERTA_MAX:
        score += 70
        riscos.append(f"Temperatura crítica: {temp}°C — febre muito alta")
        recomendacoes.append({"urgencia": "URGENTE", "acao": "Levar ao veterinário imediatamente"})
    elif status_temp == "critico":
        score += 70
        riscos.append(f"Temperatura crítica: {temp}°C — possível hipotermia")
        recomendacoes.append({"urgencia": "URGENTE",
                              "acao": "Aquecer o pet com cuidado e procurar um veterinário imediatamente"})
    elif temp > TEMP_NORMAL_MAX:
        score += 20
        riscos.append(f"Temperatura elevada: {temp}°C (normal até {TEMP_NORMAL_MAX}°C)")
        recomendacoes.append({"urgencia": "PREVENTIVO", "acao": "Monitorar temperatura nas próximas horas"})
    elif temp < TEMP_NORMAL_MIN:
        score += 20
        riscos.append(f"Temperatura baixa: {temp}°C (normal a partir de {TEMP_NORMAL_MIN}°C)")
        recomendacoes.append({"urgencia": "PREVENTIVO",
                              "acao": "Manter o pet aquecido e monitorar a temperatura"})

    atividade = data["atividade_atual"]
    if atividade < ATIVIDADE_SEVERA:
        score += 70
        riscos.append("Inatividade severa detectada")
        recomendacoes.append({"urgencia": "URGENTE",
                              "acao": "Verificar estado do pet — pode indicar dor ou letargia"})
    elif atividade < ATIVIDADE_BAIXA:
        score += 10
        riscos.append("Atividade abaixo do normal")

    idade = data.get("idade_anos")
    idade = idade if isinstance(idade, (int, float)) and not isinstance(idade, bool) else 0
    if str(data.get("especie", "")).lower() == "cão" and idade >= 7:
        score += 10
        riscos.append(f"Pet sênior ({idade} anos) — maior predisposição a doenças degenerativas")
        recomendacoes.append({"urgencia": "PREVENTIVO",
                              "acao": "Check-up semestral recomendado para pets sênior"})

    if data.get("doencas_cronicas"):
        riscos.append(f"Condição crônica em acompanhamento: {', '.join(data['doencas_cronicas'])}")

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
        "mensagem_tutor": mensagem_padrao(data["nome"], nivel, recomendacoes),
    }


def mensagem_padrao(nome: str, nivel: str, recomendacoes: list[dict]) -> str:
    """Mensagem ao tutor quando o LLM não está disponível."""
    urgentes = [r["acao"] for r in recomendacoes if r["urgencia"] == "URGENTE"]
    acao = (urgentes or [r["acao"] for r in recomendacoes] or [""])[0]
    if nivel == "baixo":
        return f"Tudo tranquilo com {nome} no momento. Continue acompanhando pela coleira."
    if nivel == "medio":
        return f"{nome} merece atenção. Recomendação: {acao.lower()}."
    if nivel == "alto":
        return f"Atenção: {nome} precisa de cuidado. Recomendação: {acao.lower()}."
    return f"Situação crítica com {nome}. {acao}."
