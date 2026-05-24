# 🐾 Afetto — Coleira Inteligente

> **"O sistema operacional do cuidado contínuo do pet"**  
> Challenge FIAP 2026 — Empresa parceira: CLYVO VET

---

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Problema que Resolve](#problema-que-resolve)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Arquitetura da Solução](#arquitetura-da-solução)
- [Componentes e Ligações](#componentes-e-ligações)
- [Como Executar](#como-executar)
- [Tópicos MQTT](#tópicos-mqtt)
- [Dashboard Node-RED](#dashboard-node-red)
- [Lógica de Classificação](#lógica-de-classificação)
- [Equipe](#equipe)

---

## 🧠 Sobre o Projeto

O **Afetto IoT** é o módulo de hardware do ecossistema Afetto — uma plataforma digital que acompanha a jornada contínua de saúde do pet. Este módulo simula uma **coleira inteligente** capaz de monitorar em tempo real:

- 🌡️ **Temperatura corporal** do pet via sensor DHT22
- 🏃 **Nível de atividade/movimento** via acelerômetro MPU6050
- 🔴 **Status de saúde** com feedback visual via LED RGB
- ⚠️ **Alertas automáticos** enviados ao dashboard da clínica via MQTT

Os dados coletados alimentam o dashboard B2B da CLYVO VET, permitindo que clínicas veterinárias monitorem seus pacientes de forma proativa e preventiva — transformando o cuidado reativo em cuidado contínuo.

---

## 🎯 Problema que Resolve

Hoje a jornada do pet é **fragmentada e reativa**:

| Problema | Impacto |
|----------|---------|
| Tutor só leva o pet ao vet em urgências | Cuidado preventivo negligenciado |
| Clínica perde contato entre consultas | Baixa recorrência e LTV reduzido |
| Sem monitoramento contínuo em casa | Agravamentos que poderiam ser evitados |
| Dados clínicos não estruturados | Histórico perdido ao trocar de clínica |

A coleira Afetto resolve o **gap de monitoramento contínuo** — coletando dados vitais do pet em casa e gerando alertas automáticos quando algo está fora do padrão, antes que vire uma emergência.

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|------------|-----|
| **ESP32** | Microcontrolador principal |
| **DHT22** | Sensor de temperatura e umidade |
| **MPU6050** | Acelerômetro e giroscópio (nível de atividade) |
| **LED RGB** | Feedback visual do status do pet |
| **Wokwi** | Simulação do circuito |
| **MQTT** | Protocolo de comunicação IoT |
| **HiveMQ** | Broker MQTT público |
| **Node-RED** | Processamento e dashboard |
| **ArduinoJson** | Serialização dos dados |

---

## 🏗️ Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────┐
│                    WOKWI (ESP32)                         │
│                                                          │
│  DHT22 ──► Temperatura corporal                         │
│  MPU6050 ──► Nível de atividade                         │
│  LED RGB ◄── Status (verde/amarelo/vermelho)            │
│  Botão 1 ──► Simula febre (GPIO18)                      │
│  Botão 2 ──► Simula inatividade (GPIO19)                │
└──────────────────────┬──────────────────────────────────┘
                       │ MQTT (broker.hivemq.com)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   NODE-RED                               │
│                                                          │
│  Afetto/coleira/temperatura ──► Gauge temperatura        │
│  Afetto/coleira/movimento   ──► Gauge atividade          │
│  Afetto/coleira/status      ──► Card status do pet       │
│  Afetto/coleira/alerta      ──► Painel de alertas        │
└─────────────────────────────────────────────────────────┘
```

---

## ⚡ Componentes e Ligações

### Lista de componentes

| Componente | Quantidade |
|------------|-----------|
| ESP32 DevKit C V4 | 1 |
| Sensor DHT22 | 1 |
| Acelerômetro MPU6050 | 1 |
| LED RGB (catodo comum) | 1 |
| Resistor 220Ω | 3 |
| Pushbutton | 2 |
| Protoboard | 1 |

### Tabela de conexões

| Componente | Pino | ESP32 GPIO | Fio |
|------------|------|------------|-----|
| DHT22 | VCC | 3V3 | Vermelho |
| DHT22 | DATA | GPIO 4 | Roxo |
| DHT22 | GND | GND | Preto |
| MPU6050 | VCC | 3V3 | Cinza |
| MPU6050 | GND | GND | Preto |
| MPU6050 | SDA | GPIO 21 | Dourado |
| MPU6050 | SCL | GPIO 22 | Dourado |
| LED RGB | R | 220Ω → GPIO 25 | Vermelho |
| LED RGB | GND | GND | Preto |
| LED RGB | G | 220Ω → GPIO 26 | Verde |
| LED RGB | B | 220Ω → GPIO 27 | Azul |
| Botão Febre | Pino 1 | GPIO 18 | Vermelho |
| Botão Febre | Pino 2 | GND | Preto |
| Botão Inativo | Pino 1 | GPIO 19 | Azul |
| Botão Inativo | Pino 2 | GND | Preto |

---

## 🚀 Como Executar

### Pré-requisitos

- Conta no [Wokwi](https://wokwi.com)
- [Node-RED](https://nodered.org) instalado
- Pacote `node-red-dashboard` instalado no Node-RED

### Passo 1 — Simulação no Wokwi

1. Acessa [wokwi.com](https://wokwi.com) e cria um novo projeto ESP32
2. Copia o conteúdo do arquivo `diagram.json` deste repositório
3. Copia o conteúdo do arquivo `sketch.ino` deste repositório
4. Cria um arquivo `libraries.txt` com o conteúdo:

```
PubSubClient
DHT sensor library
Adafruit Unified Sensor
MPU6050
ArduinoJson
```

5. Clica em **▶ Play** para iniciar a simulação

### Passo 2 — Node-RED

1. Abre o Node-RED em `http://localhost:1880`
2. Vai em **Menu → Import**
3. Cola o conteúdo do arquivo `nodered-flow.json` deste repositório
4. Clica **Deploy**
5. Acessa o dashboard em `http://localhost:1880/ui`

### Passo 3 — Testar

Com a simulação rodando no Wokwi, os dados aparecem em tempo real no dashboard. Use os botões para simular situações:

| Botão | Ação | LED | Dashboard |
|-------|------|-----|-----------|
| Nenhum | Estado normal | 🟢 Verde | Temp ~38.5°C, atividade normal |
| Botão Vermelho (Febre) | Temperatura sobe para 40.8°C | 🔴 Vermelho | Alerta de febre disparado |
| Botão Azul (Inativo) | Movimento cai para 0.1 | 🔴 Vermelho | Alerta de inatividade disparado |

---

## 📡 Tópicos MQTT

| Tópico | Descrição | Payload exemplo |
|--------|-----------|-----------------|
| `Afetto/coleira/temperatura` | Temperatura corporal e umidade | `{"valor": 38.5, "umidade": 65}` |
| `Afetto/coleira/movimento` | Nível de aceleração/atividade | `{"valor": 0.95}` |
| `Afetto/coleira/status` | Status classificado do pet | `{"status": "normal", "temp": 38.5, "accel": 0.95}` |
| `Afetto/coleira/alerta` | Alertas críticos | `{"alerta": true, "motivo": "febre_alta", "pet": "Bolinha"}` |

### Configuração do broker

```
Broker:   broker.hivemq.com
Porta:    8083
Protocolo: MQTT V3.1.1
```

---

## 📊 Dashboard Node-RED

O dashboard exibe em tempo real:

- **Gauge de Temperatura** — faixa 0-42°C com cores (azul/amarelo/vermelho)
- **Gauge de Atividade** — nível de movimento do pet
- **Card de Status** — 🟢 Normal / 🟡 Atenção / 🔴 Crítico
- **Painel de Alertas** — mensagens de febre alta ou inatividade prolongada

---

## 🧪 Lógica de Classificação

```
Temperatura > 40°C  OU  Aceleração < 0.3  →  🔴 CRÍTICO  (LED vermelho + alerta)
Temperatura > 39°C  OU  Aceleração < 0.8  →  🟡 ATENÇÃO  (LED amarelo)
Demais casos                               →  🟢 NORMAL   (LED verde)
```

---


<div align="center">
  <p>Feito com 🐾 para o Challenge FIAP 2026</p>
  <p><strong>Afetto — O sistema operacional do cuidado contínuo do pet</strong></p>
</div>
