# Afetto — Cuidado que acompanha

> Assistente de IA e coleira inteligente para transformar sinais da rotina em cuidado preventivo para pets.

O Afetto conecta dados de rotina captados pela coleira a uma camada de prevenção e orientação. A proposta não substitui o médico-veterinário: ela ajuda o tutor a perceber mudanças relevantes mais cedo e encaminha informações organizadas para a clínica.

## Entrega — 3º Sprint

| Item | Acesso |
| --- | --- |
| Vídeo pitch e demonstração funcional | **Pendente:** inserir o link do YouTube em modo não listado antes da entrega. |
| Repositório do projeto | **Pendente:** inserir a URL deste repositório após o push para o GitHub. |
| Diagrama de arquitetura | [Abrir PDF](docs/arquitetura-afetto-ia.pdf) |
| Código, documentação e testes | Disponíveis neste repositório. |

> Antes de enviar o `.zip`, substitua os dois campos **Pendente** pelos links públicos exigidos na atividade.

## O problema

Na rotina do tutor, sinais de mudança de comportamento, temperatura e atividade podem passar despercebidos ou gerar dúvida: é algo pontual ou é hora de procurar a clínica? Quando o histórico está espalhado, a decisão fica ainda mais difícil e o cuidado tende a ser reativo.

Na pesquisa exploratória do projeto, com 102 tutores:

- 68% relataram dificuldade para entender se uma mudança de comportamento pode indicar um problema de saúde.
- 76% têm dúvida sobre quando procurar atendimento veterinário.
- 61% não possuem um histórico centralizado de saúde e rotina do pet.

O Afetto propõe acompanhamento contínuo, alertas contextualizados e uma conversa de apoio, preservando o diagnóstico e a conduta clínica para o profissional veterinário.

## A solução

O protótipo integra quatro partes:

1. **Coleira inteligente:** um ESP32 no Wokwi simula a leitura de temperatura e movimento do pet.
2. **Comunicação IoT:** as leituras são publicadas nos tópicos MQTT `afetto/coleira/#`.
3. **IA Preventiva (Guard):** valida telemetria, aplica regras de risco e, quando disponível, usa Ollama para gerar uma orientação curta e contextualizada.
4. **IA Assistente:** conversa com o tutor usando o perfil e a telemetria recente, sem inventar dados e sem realizar diagnóstico.

## Como a IA é usada

O projeto utiliza uma abordagem híbrida: **motor de regras + LLM local com Ollama**.

| Componente | Responsabilidade | Por que é importante |
| --- | --- | --- |
| Motor de regras | Define o nível de risco a partir de temperatura e atividade. | Mantém decisões críticas previsíveis, auditáveis e testáveis. |
| Ollama / Llama | Personaliza a explicação e a orientação ao tutor. | Torna a mensagem mais clara e adequada ao contexto do pet. |
| Assistente | Responde dúvidas considerando os dados recentes disponíveis. | Ajuda o tutor a acompanhar a rotina sem substituir a clínica. |

Em uma situação crítica, a regra determina o alerta primeiro. O modelo de linguagem apenas explica o próximo passo de forma responsável. Assim, a IA generativa não recebe a responsabilidade de diagnosticar ou decidir sozinha.

## Dados utilizados

| Dado | Origem | Uso na solução |
| --- | --- | --- |
| Temperatura | Sensor DHT22 simulado no Wokwi | Identificar possíveis picos de temperatura. |
| Movimento / aceleração | MPU6050 simulado no Wokwi | Identificar inatividade persistente ou fora do padrão. |
| Status da coleira | Firmware ESP32 | Comunicar o estado `normal`, `atencao` ou `critico`. |
| Perfil e histórico do pet | Aplicação Afetto / cadastro | Personalizar orientações e manter contexto longitudinal. |
| Vacinas, consultas e medicamentos | Aplicação e banco de dados | Apoiar o acompanhamento do tutor e da clínica. |

No protótipo atual, os dados de telemetria são persistidos localmente em arquivos JSON na pasta `runtime/`. Na evolução da arquitetura, o backend Java e o banco de dados centralizam o histórico clínico e operacional.

## Arquitetura e fluxo

```text
ESP32 + DHT22/MPU6050 (Wokwi)
            │ publica telemetria MQTT
            ▼
     Broker MQTT (HiveMQ)
            │ afetto/coleira/#
            ▼
      mqtt_bridge.py
            │ salva a última leitura
            ├──────────────────────► runtime/telemetria_atual.json
            │ envia evento de risco
            ▼
       guard.py (Flask)
            │ regras de prevenção + Ollama
            ▼
   runtime/ultima_analise.json
            │
            ▼
      chat.py (Assistente)
            │ orientação contextual
            ▼
       Tutor / Clínica
```

Consulte o diagrama completo em [docs/arquitetura-afetto-ia.pdf](docs/arquitetura-afetto-ia.pdf).

## Tecnologias

- Python 3.10+
- Flask
- MQTT com `paho-mqtt`
- Ollama com um modelo Llama local
- ESP32, DHT22 e MPU6050 no Wokwi
- Broker público HiveMQ para a demonstração
- `unittest` para testes automatizados

## Estrutura do projeto

```text
Afetto-Iot/
├── chat.py                     # Assistente conversacional
├── guard.py                    # API e motor preventivo
├── mqtt_bridge.py              # Ponte MQTT → IA preventiva
├── requirements.txt            # Dependências Python
├── tests/
│   └── test_guard.py           # Testes do motor de risco
├── docs/
│   └── arquitetura-afetto-ia.pdf
└── runtime/                    # Dados locais gerados durante a execução
```

## Como executar

### 1. Pré-requisitos

- Python 3.10 ou superior
- Ollama instalado e em execução
- Um modelo local compatível, por exemplo `llama3.2:3b`
- Simulação Wokwi configurada para publicar em `broker.hivemq.com:1883`

### 2. Instalar dependências

```bash
python -m venv .venv
```

No Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Preparar o Ollama

```bash
ollama pull llama3.2:3b
```

Se desejar usar outro modelo, defina a variável de ambiente `OLLAMA_MODEL` antes de iniciar os serviços.

### 4. Iniciar o fluxo

Em terminais separados, execute nesta ordem:

```bash
python guard.py
python mqtt_bridge.py
python chat.py
```

Em seguida, inicie a simulação no Wokwi. O bridge recebe os tópicos MQTT, atualiza a telemetria local e chama o Guard quando houver uma situação de risco.

## Como testar

Execute os testes automatizados do motor preventivo:

```bash
python -m unittest discover -s tests -v
```

O conjunto valida cenários de rotina saudável, febre, inatividade, dados inválidos e a regra de que uma resposta do LLM não pode rebaixar uma decisão crítica do motor determinístico.

Para uma demonstração manual, use os botões da simulação Wokwi para provocar febre ou inatividade e acompanhe os logs dos três processos. Os arquivos `runtime/telemetria_atual.json` e `runtime/ultima_analise.json` permitem conferir o dado recebido e a análise gerada.

## Resultados parciais

- Integração funcional entre telemetria simulada, MQTT e serviços Python.
- Identificação preventiva de temperatura elevada e baixa atividade.
- Geração de orientação contextual com LLM local, quando Ollama está disponível.
- Separação entre decisão de risco determinística e texto generativo.
- Cinco testes automatizados do componente preventivo concluídos com sucesso.

## Limites e evolução

Este é um protótipo acadêmico e não é um dispositivo médico. Os limiares de risco são demonstrativos e precisam de validação veterinária antes de qualquer uso real. As próximas etapas previstas são integrar a API Java e o banco de dados da plataforma, cadastrar múltiplos pets, substituir o armazenamento local por persistência centralizada e validar alertas com profissionais da CLYVO VET.

## Roteiro sugerido para o vídeo

1. Apresente o problema: sinais da rotina são sutis e o histórico fica fragmentado.
2. Mostre a coleira no Wokwi enviando temperatura e movimento por MQTT.
3. Demonstre uma condição de atenção ou crítica e o alerta produzido pelo Guard.
4. Mostre a orientação da IA Assistente e explique que ela apoia, não diagnostica.
5. Feche com o benefício: mais contexto para o tutor e informações organizadas para a clínica.

---

Projeto acadêmico de **Disruptive Architectures: IoT, IoB & Generative IA**, proposto para a jornada de cuidado contínuo da **CLYVO VET**.
