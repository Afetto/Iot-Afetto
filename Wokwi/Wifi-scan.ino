#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <MPU6050.h>
#include <ArduinoJson.h>

const char* ssid        = "Wokwi-GUEST";
const char* password    = "";
const char* mqtt_server = "broker.hivemq.com";
const int   mqtt_port   = 1883;

#define DHTPIN  4
#define DHTTYPE DHT22
#define LED_R   25
#define LED_G   26
#define LED_B   27
#define BTN_FEBRE     18  // botão 1
#define BTN_INATIVO   19  // botão 2

#define TOPIC_TEMP   "afetto/coleira/temperatura"
#define TOPIC_MOV    "afetto/coleira/movimento"
#define TOPIC_STATUS "afetto/coleira/status"
#define TOPIC_ALERTA "afetto/coleira/alerta"

DHT          dht(DHTPIN, DHTTYPE);
MPU6050      mpu;
WiFiClient   espClient;
PubSubClient client(espClient);

unsigned long ultimoEnvio = 0;

void setLED(int r, int g, int b) {
  digitalWrite(LED_R, !r);  // invertido — anodo comum
  digitalWrite(LED_G, !g);
  digitalWrite(LED_B, !b);
}

// Faixas de temperatura (°C): normal 37.5–39.2 | atenção ±4°C | crítico além disso
#define TEMP_NORMAL_MIN 37.5
#define TEMP_NORMAL_MAX 39.2
#define TEMP_ALERTA_MIN 33.5   // 37.5 - 4
#define TEMP_ALERTA_MAX 43.2   // 39.2 + 4

String classificarStatus(float temp, String &motivo) {
  if (temp >= TEMP_NORMAL_MIN && temp <= TEMP_NORMAL_MAX) {
    motivo = "";
    return "normal";
  } else if (temp >= TEMP_ALERTA_MIN && temp < TEMP_NORMAL_MIN) {
    motivo = "temperatura_baixa";
    return "atencao";
  } else if (temp > TEMP_NORMAL_MAX && temp <= TEMP_ALERTA_MAX) {
    motivo = "temperatura_elevada";
    return "atencao";
  } else if (temp > TEMP_ALERTA_MAX) {
    motivo = "febre_critica";
    return "critico";
  }
  motivo = "hipotermia_critica";
  return "critico";
}

void atualizarLED(String status) {
  if (status == "normal") {
    digitalWrite(LED_R, HIGH);  // apagado
    digitalWrite(LED_G, LOW);   // verde aceso
    digitalWrite(LED_B, HIGH);  // apagado
  }
  if (status == "atencao") {
    digitalWrite(LED_R, LOW);   // vermelho aceso
    digitalWrite(LED_G, LOW);   // verde aceso = amarelo
    digitalWrite(LED_B, HIGH);  // apagado
  }
  if (status == "critico") {
    digitalWrite(LED_R, LOW);   // vermelho aceso
    digitalWrite(LED_G, HIGH);  // apagado
    digitalWrite(LED_B, HIGH);  // apagado
  }
}

void conectarWiFi() {
  Serial.print("Conectando WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" conectado!");
}

void conectarMQTT() {
  while (!client.connected()) {
    Serial.print("Conectando MQTT...");
    if (client.connect("Afetto-Coleira")) {
      Serial.println(" ok");
    } else {
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
  pinMode(BTN_FEBRE,  INPUT_PULLUP);
  pinMode(BTN_INATIVO, INPUT_PULLUP);

  setLED(0, 0, 1); // azul = inicializando

  dht.begin();
  Wire.begin();
  mpu.initialize();

  conectarWiFi();
  client.setServer(mqtt_server, 1883);
  conectarMQTT();

  setLED(0, 1, 0); // verde = pronto
}

void loop() {
  if (!client.connected()) conectarMQTT();
  client.loop();

  if (millis() - ultimoEnvio >= 3000) {
    ultimoEnvio = millis();

    // ── Leitura base dos sensores ──────────────────
    float temperatura = dht.readTemperature();
    if (isnan(temperatura)) temperatura = 38.5;

    int16_t ax, ay, az, gx, gy, gz;
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
    float accel = sqrt(pow(ax/16384.0,2) +
                       pow(ay/16384.0,2) +
                       pow(az/16384.0,2));

    // ── Botões simulam situações críticas ──────────
    bool btnFebre   = !digitalRead(BTN_FEBRE);
    bool btnInativo = !digitalRead(BTN_INATIVO);

    if (btnFebre) {
      temperatura = 40.8; // simula febre alta
      Serial.println(">>> Modo FEBRE ativado");
    }

    if (btnInativo) {
      accel = 0.1; // simula inatividade
      Serial.println(">>> Modo INATIVO ativado");
    }

    // ── Classificação e LED ────────────────────────
    String motivo;
    String status = classificarStatus(temperatura, motivo);
    atualizarLED(status);

    // ── Publicar MQTT ──────────────────────────────
    StaticJsonDocument<128> doc;
    char buf[128];

    doc["valor"]   = temperatura;
    doc["umidade"] = dht.readHumidity();
    doc["pet"]     = "Bolinha";
    serializeJson(doc, buf);
    client.publish(TOPIC_TEMP, buf);

    doc.clear();
    doc["valor"] = accel;
    doc["pet"]   = "Bolinha";
    serializeJson(doc, buf);
    client.publish(TOPIC_MOV, buf);

    doc.clear();
    doc["status"] = status;
    doc["temp"]   = temperatura;
    doc["accel"]  = accel;
    doc["pet"]    = "Bolinha";
    serializeJson(doc, buf);
    client.publish(TOPIC_STATUS, buf);

    if (status != "normal") {
      doc.clear();
      doc["alerta"] = true;
      doc["nivel"]  = status;
      doc["motivo"] = motivo;
      doc["pet"]    = "Bolinha";
      serializeJson(doc, buf);
      client.publish(TOPIC_ALERTA, buf);
    }

    Serial.printf("[Afetto] Temp: %.1f°C | Accel: %.2f | Status: %s\n",
                  temperatura, accel, status.c_str());
  }
}