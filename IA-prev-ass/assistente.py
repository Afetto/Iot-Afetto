"""
Afetto Assistente — lógica conversacional compartilhada pelo chat do terminal
(chat.py) e pela API/painel web (POST /chat/mensagem).

Fluxo de cada mensagem:
1. Guarda de segurança: sinais de emergência recebem resposta fixa e imediata
   (o LLM não é consultado).
2. Identificação da intenção (temperatura, vacina, remédio, consulta,
   alimentação, atividade ou geral).
3. Prompt com contexto real (perfil, histórico clínico, telemetria e última
   análise do Guard — RAG simplificado) enviado ao Llama via Ollama.
4. Se o Ollama não responder, o assistente monta a resposta com regras a
   partir dos mesmos dados (fallback), para nunca deixar o tutor sem retorno.
"""
import unicodedata

from regras import TEMP_NORMAL_MAX, TEMP_NORMAL_MIN, classificar_temperatura

EMERGENCIA = ("convuls", "sangr", "nao respira", "nao esta respirando", "desmai", "envenen",
              "atropel", "engasg", "inconsciente", "sem respirar")

INTENCOES = {
    "temperatura": ("temperatura", "febre", "quente", "frio", "graus", "tremendo"),
    "vacina": ("vacina", "vacinacao", "v10", "v8", "v4", "raiva", "antirrabica"),
    "remedio": ("remedio", "medicamento", "meloxicam", "dose", "comprimido"),
    "consulta": ("consulta", "veterinario", "check-up", "checkup", "clinica"),
    "alimentacao": ("comendo", "come ", "comer", "apetite", "racao", "vomit", "diarreia", "agua"),
    "atividade": ("atividade", "parad", "quiet", "cansad", "brincar", "passeio", "dormindo", "letarg", "mexe"),
}

MSG_EMERGENCIA = (
    "Isso pode ser uma emergência. Procure atendimento veterinário AGORA — ligue para a clínica "
    "ou vá ao pronto-atendimento mais próximo. Mantenha {nome} calm{o}, em local seguro e "
    "não ofereça comida nem remédios por conta própria."
)


def _o(perfil: dict) -> str:
    """Terminação de gênero (o/a) conforme o sexo cadastrado do pet."""
    return "a" if str(perfil.get("sexo", "")).lower().startswith("f") else "o"


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def eh_emergencia(mensagem: str) -> bool:
    texto = normalizar(mensagem)
    return any(chave in texto for chave in EMERGENCIA)


def identificar_intencao(mensagem: str) -> str:
    texto = normalizar(mensagem) + " "
    for intencao, chaves in INTENCOES.items():
        if any(chave in texto for chave in chaves):
            return intencao
    return "geral"


def _texto_telemetria(telemetria: dict | None) -> str:
    if not telemetria:
        return "sem leitura recente da coleira"
    return (f"temperatura {telemetria['temperatura']}°C, atividade {telemetria['atividade']}, "
            f"status {telemetria.get('status') or 'desconhecido'} (recebido em {telemetria.get('recebido_em', '?')})")


def _texto_vacinas(perfil: dict) -> str:
    if perfil.get("vacinas_em_dia") is None:
        return "sem registro de vacinas"
    if perfil["vacinas_em_dia"]:
        prox = perfil.get("proxima_vacina")
        return "em dia" + (f" (próxima: {prox['nome']} em {prox['proxima_dose']})" if prox else "")
    return f"ATRASADAS: {', '.join(perfil.get('vacinas_vencidas', []))}"


def montar_prompt(perfil: dict, mensagem: str, telemetria=None, analise=None, historico=None) -> str:
    ultima = perfil.get("ultima_consulta")
    consulta = (f"{ultima['data']} — {ultima['motivo']} ({ultima.get('observacao', '')})"
                if ultima else "nenhuma registrada")
    analise_txt = (f"nível {analise['nivel']} (score {analise['score_risco']}/100); "
                   f"riscos: {'; '.join(analise.get('riscos', []))}") if analise else "nenhuma análise recente"

    conversa = ""
    for msg in (historico or [])[-8:]:
        papel = "Tutor" if msg["papel"] == "tutor" else "Afetto"
        conversa += f"\n{papel}: {msg['conteudo']}"

    return f"""Você é o Afetto Assistente, apoio de saúde animal empático e acessível.
Regras:
- Responda SEMPRE em português brasileiro, no máximo 4 linhas.
- Use SOMENTE os dados abaixo; se algo não estiver nos dados, diga que não sabe.
- NUNCA diagnostique nem indique dose de remédio. Oriente procurar o veterinário quando necessário.
- Faixa normal de temperatura: {TEMP_NORMAL_MIN} a {TEMP_NORMAL_MAX}°C.

Pet: {perfil['nome']} | {perfil['especie']} {perfil.get('raca', 'SRD')} | {perfil.get('idade_anos', '?')} anos | {perfil.get('peso_kg', '?')} kg
Vacinas: {_texto_vacinas(perfil)}
Última consulta: {consulta}
Doenças crônicas: {', '.join(perfil.get('doencas_cronicas', [])) or 'nenhuma'}
Medicamentos em uso: {', '.join(perfil.get('medicamentos_ativos', [])) or 'nenhum'}
Coleira (IoT): {_texto_telemetria(telemetria)}
Última análise preventiva (Guard): {analise_txt}

Conversa até agora:{conversa or ' (início)'}

Tutor: {mensagem}
Afetto:"""


def resposta_por_regras(perfil: dict, intencao: str, telemetria=None, analise=None) -> str:
    """Resposta determinística a partir dos dados (usada quando o LLM não responde)."""
    nome = perfil["nome"]

    if intencao == "temperatura":
        if not telemetria:
            return f"Ainda não recebi uma leitura recente da coleira de {nome}. Verifique se ela está ligada."
        temp = telemetria["temperatura"]
        status, _ = classificar_temperatura(temp)
        if status == "normal":
            return f"A temperatura de {nome} está em {temp}°C, dentro da faixa normal ({TEMP_NORMAL_MIN}–{TEMP_NORMAL_MAX}°C)."
        if status == "atencao":
            return (f"A temperatura de {nome} está em {temp}°C, fora da faixa normal. "
                    f"Mantenha-{_o(perfil)} em repouso, ofereça água e acompanhe nas próximas horas; se persistir, procure o veterinário.")
        return (f"A temperatura de {nome} está em {temp}°C — nível crítico. "
                "Procure atendimento veterinário imediatamente.")

    if intencao == "vacina":
        if perfil.get("vacinas_em_dia") is False:
            return (f"{nome} está com vacinas atrasadas: {', '.join(perfil['vacinas_vencidas'])}. "
                    "Agende a aplicação com a clínica o quanto antes.")
        prox = perfil.get("proxima_vacina")
        if prox:
            return f"As vacinas de {nome} estão em dia. A próxima é {prox['nome']}, em {prox['proxima_dose']}."
        return f"Não encontrei registro de vacinas de {nome}. Vale cadastrar a carteirinha no app."

    if intencao == "remedio":
        remedios = perfil.get("medicamentos_ativos", [])
        if remedios:
            return (f"{nome} está usando: {', '.join(remedios)}. Siga a dose prescrita pelo veterinário "
                    "e não altere o tratamento sem orientação.")
        return f"{nome} não tem medicamentos ativos registrados. Não ofereça remédios sem orientação veterinária."

    if intencao == "consulta":
        ultima = perfil.get("ultima_consulta")
        if not ultima:
            return f"Não há consultas registradas para {nome}. Que tal agendar um check-up?"
        meses = perfil.get("ultima_consulta_meses")
        conselho = " Já passou de um ano: agende um check-up." if meses and meses > 12 else ""
        return f"A última consulta de {nome} foi em {ultima['data']} ({ultima['motivo']}).{conselho}"

    if intencao == "alimentacao":
        return (f"Mudanças no apetite de {nome} merecem atenção. Ofereça água fresca e observe por 24 horas; "
                "se houver vômito repetido, diarreia, apatia ou recusa total de comida, procure o veterinário.")

    if intencao == "atividade":
        if telemetria and telemetria["atividade"] < 0.3:
            return (f"A coleira indica que {nome} está muito parad{_o(perfil)} (atividade {telemetria['atividade']}). "
                    "Isso pode indicar dor ou cansaço; observe e, se continuar, procure o veterinário.")
        if telemetria:
            return f"A atividade de {nome} está em {telemetria['atividade']} — dentro do esperado no momento."
        return f"Ainda não tenho leitura de atividade da coleira de {nome}."

    if analise:
        return (f"Resumo de {nome}: risco {analise['nivel']} (score {analise['score_risco']}/100). "
                f"{analise.get('mensagem_tutor', '')}").strip()
    return (f"Posso ajudar com temperatura, vacinas, remédios, consultas, alimentação e atividade de {nome}. "
            "O que você quer saber?")


def responder(perfil: dict, mensagem: str, telemetria=None, analise=None,
              historico=None, llm=None) -> dict:
    """Gera a resposta do assistente. `llm` recebe o prompt e devolve texto ou None."""
    if eh_emergencia(mensagem):
        return {"resposta": MSG_EMERGENCIA.format(nome=perfil["nome"], o=_o(perfil)),
                "fonte": "protocolo_emergencia", "intencao": "emergencia"}

    intencao = identificar_intencao(mensagem)
    if llm is not None:
        texto = llm(montar_prompt(perfil, mensagem, telemetria, analise, historico))
        if texto:
            return {"resposta": texto.strip()[:800], "fonte": "llama3", "intencao": intencao}

    return {"resposta": resposta_por_regras(perfil, intencao, telemetria, analise),
            "fonte": "regras", "intencao": intencao}
