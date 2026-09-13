# 🐾 Afetto — IoT & IA
> Challenge FIAP 2026 — Sprint 1 e Sprint 3 | Empresa parceira: CLYVO VET

---

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Módulo IoT — Coleira Inteligente](#módulo-iot--coleira-inteligente)
- [Módulo IA — Afetto Guard e Chat](#módulo-ia--afetto-guard-e-chat)
- [Dashboard Node-RED](#dashboard-node-red)
- [Como Executar](#como-executar)
- [Tópicos MQTT](#tópicos-mqtt)
- [Repositórios do Projeto](#repositórios-do-projeto)
- [Equipe](#equipe)

---

## 🧠 Sobre o Projeto

O **Afetto** é uma plataforma digital que acompanha a jornada contínua de saúde do pet, criando uma experiência proativa e personalizada para o tutor e para a clínica veterinária.

Este repositório contém dois módulos integrados:

| Módulo | Descrição |
|--------|-----------|
| **IoT** | Coleira inteligente com ESP32 simulada no Wokwi |
| **IA** | Microserviço Python com Llama 3 para análise preventiva e chat assistente |

---

## 📁 Estrutura do Repositório

```
Afetto-IOT/
│
├── Wokwi/                        # Módulo IoT
│   ├── Wifi-scan.ino             # Código principal do ESP32
│   ├── diagrem.json              # Circuito completo do Wokwi
│   └── libraries.txt             # Bibliotecas necessárias
│
├── IA-prev-ass/                  # Módulo de IA
│   ├── guard.py                  # Afetto Guard — IA preventiva (Flask)
│   ├── chat.py                   # Afetto Chat — assistente via terminal
│   ├── mqtt_bridge.py            # Bridge MQTT → dados IoT em tempo real
│   ├── requirements.txt          # Dependências Python
│   ├── docs/
│   │   └── arquitetura-afetto-ia.pdf  # Diagrama arquitetural
│   ├── runtime/                  # Dados em tempo real (gerado em execução)
│   └── tests/
│       └── test_guard.py         # Testes automatizados do Guard
│
├── Node-red/
│   └── Fluxo.json                # Fluxo do dashboard Node-RED
│
├── LinkYouTube.txt               # Link do vídeo de demonstração
└── README.md
```

---

## 🔌 Módulo IoT — Coleira Inteligente

### O que faz

Simula uma **coleira inteligente** que monitora o pet em tempo real e envia dados via MQTT para o dashboard da clínica.

### Componentes

| Componente | Função |
|------------|--------|
| ESP32 DevKit C V4 | Microcontrolador principal |
| DHT22 | Temperatura e umidade corporal |
| MPU6050 | Acelerômetro — nível de atividade |
| LED RGB | Feedback visual do status (verde/amarelo/vermelho) |
| Botão vermelho | Simula febre alta (GPIO 18) |
| Botão azul | Simula inatividade (GPIO 19) |
| Resistores 220Ω | Proteção do LED RGB |

### Conexões

| Componente | Pino | ESP32 |
|------------|------|-------|
| DHT22 VCC | — | 3V3 |
| DHT22 DATA | — | GPIO 4 |
| DHT22 GND | — | GND |
| MPU6050 VCC | — | 3V3 |
| MPU6050 GND | — | GND |
| MPU6050 SDA | — | GPIO 21 |
| MPU6050 SCL | — | GPIO 22 |
| LED R | 220Ω | GPIO 25 |
| LED GND | — | GND |
| LED G | 220Ω | GPIO 26 |
| LED B | 220Ω | GPIO 27 |
| Botão Febre | — | GPIO 18 + GND |
| Botão Inativo | — | GPIO 19 + GND |

### Lógica de classificação

| Condição | Status | LED |
|----------|--------|-----|
| Temp ≤ 39°C e atividade ≥ 0.8 | 🟢 Normal | Verde |
| Temp 39-40°C ou atividade 0.3-0.8 | 🟡 Atenção | Amarelo |
| Temp > 40°C ou atividade < 0.3 | 🔴 Crítico | Vermelho |

### Simulação de situações

| Botão | Efeito | LED | Alerta |
|-------|--------|-----|--------|
| Nenhum | Estado normal | 🟢 Verde | — |
| Vermelho (Febre) | Temperatura → 40.8°C | 🔴 Vermelho | Febre alta |
| Azul (Inativo) | Atividade → 0.1 | 🔴 Vermelho | Inatividade |

---

## 🤖 Módulo IA — Afetto Guard e Chat

### Afetto Guard — IA Preventiva

Servidor Flask que analisa o perfil completo do pet e gera um **score de risco de 0 a 100** com recomendações priorizadas por urgência.

**Como funciona:**
```
Dados do pet (API Java + IoT)
        ↓
Motor de regras (classifica riscos)
        ↓
Llama 3 via Ollama (enriquece com linguagem natural)
        ↓
Score + riscos + recomendações + mensagem para o tutor
```

**Níveis de risco:**

| Score | Nível | Significado |
|-------|-------|-------------|
| 0–19 | 🟢 Baixo | Pet saudável |
| 20–39 | 🟡 Médio | Atenção preventiva |
| 40–69 | 🟠 Alto | Ação recomendada |
| 70–100 | 🔴 Crítico | Atenção urgente |

**Fallback automático:** se o Llama não responder, o motor de regras entra automaticamente — o sistema nunca falha.

---

### Afetto Chat — IA Assistente

Chat conversacional direto no terminal. O tutor escolhe um pet e conversa com a IA, que responde com base no histórico clínico real do animal — não respostas genéricas.

**Recursos:**
- 3 perfis de pets pré-cadastrados (Bolinha, Felix, Mel)
- Cadastro manual de pets
- Memória da conversa (últimas 8 mensagens)
- Dados IoT em tempo real injetados no contexto
- Comandos `:sair`, `:trocar`, `:limpar`

---

## 📊 Dashboard Node-RED

O arquivo `Node-red/Fluxo.json` contém o fluxo completo para importar no Node-RED.

**O que exibe em tempo real:**

| Widget | Dado |
|--------|------|
| Gauge | Temperatura corporal (°C) |
| Gauge | Nível de atividade |
| Card | Status do pet (🟢/🟡/🔴) |
| Painel | Alertas de febre ou inatividade |

**Broker MQTT configurado:**
```
Servidor: broker.hivemq.com
Porta:    8083
```

---

## 🚀 Como Executar

### Pré-requisitos

- [Wokwi](https://wokwi.com) (conta gratuita)
- [Node-RED](https://nodered.org) instalado localmente
- Python 3.10+
- [Ollama](https://ollama.com) instalado com Llama 3

---

### 1. Coleira IoT (Wokwi)

1. Acessa [wokwi.com](https://wokwi.com) e cria um novo projeto ESP32
2. Copia o conteúdo de `Wokwi/diagrem.json` para o `diagram.json`
3. Copia o conteúdo de `Wokwi/Wifi-scan.ino` para o sketch
4. Cria um arquivo `libraries.txt` com o conteúdo de `Wokwi/libraries.txt`
5. Clica **▶ Play**

---

### 2. Dashboard Node-RED

```bash
# Abre o Node-RED
node-red

# Acessa http://localhost:1880
# Menu → Import → cola o conteúdo de Node-red/Fluxo.json
# Deploy
# Dashboard em http://localhost:1880/ui
```

---

### 3. IA Preventiva — Afetto Guard

**Terminal 1 — instala dependências e inicia o servidor:**
```bash
cd IA-prev-ass
pip install -r requirements.txt
python guard.py
```

**Terminal 2 — roda os testes visuais:**
```bash
cd IA-prev-ass
python tests/test_guard.py
```

---

### 4. IA Assistente — Afetto Chat

```bash
# Garante que o Ollama está rodando
ollama pull llama3

# Inicia o chat no terminal
cd IA-prev-ass
python chat.py
```

Escolha o pet no menu e comece a conversar!

---

### Ordem recomendada para demonstração

```
1. ollama serve         → já roda em segundo plano (checar com ollama list)
2. python guard.py      → Terminal 1 (servidor IA preventiva)
3. python test_guard.py → Terminal 2 (testa os 3 pets)
4. python chat.py       → Terminal 3 (conversa com a IA)
5. Wokwi ▶ Play         → simulação da coleira
6. Node-RED /ui         → dashboard em tempo real
```

---

## 📡 Tópicos MQTT

| Tópico | Descrição | Payload |
|--------|-----------|---------|
| `afetto/coleira/temperatura` | Temperatura e umidade | `{"valor": 38.5, "umidade": 65}` |
| `afetto/coleira/movimento` | Nível de atividade | `{"valor": 0.95}` |
| `afetto/coleira/status` | Status classificado | `{"status": "normal", "temp": 38.5}` |
| `afetto/coleira/alerta` | Alertas críticos | `{"alerta": true, "motivo": "febre_alta"}` |

---

## 🔗 Repositórios do Projeto

| Repositório | Stack | Descrição |
|-------------|-------|-----------|
| [java-afetto](https://github.com/Afetto/java-afetto) | Java + Spring Boot | API REST principal |
| [front-end-afetto](https://github.com/Afetto/front-end-afetto) | React Native + Expo | App mobile |
| [Iot-Afetto](https://github.com/Afetto/Iot-Afetto) *(este)* | C++ + Python + ESP32 | Coleira IoT + IA |

---

## 👥 Equipe

| Nome | RM |
|------|----|
| Gustavo Souto de Melo | 558595 |
| Iago Liziero Pereira | 564063 |
| Ícaro José dos Santos | 562403 |
| Leonardo Barbosa Santos | 558230 |

---

<div align="center">
  <p>Feito com 🐾 para o Challenge FIAP 2026</p>
  <p><strong>Afetto — O sistema operacional do cuidado contínuo do pet</strong></p>
</div>
