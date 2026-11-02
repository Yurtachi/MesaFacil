/*
 * ESP32 Sinuca POC — circuito apenas ilustrativo.
 * Wokwi: ESP32 DevKit, botão em GPIO27 para GND, relé GPIO26.
 * DEMO_OFFLINE=1: 'p' no monitor serial simula pagamento; clique botão para liberar.
 * DEMO_OFFLINE=0: recebe pedido REAL do backend local (pagamento fictício).
 *                     Wokwi Private Gateway (plano pago) com host.wokwi.internal.
 *                     Nunca use credenciais reais no gateway público.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define DEMO_OFFLINE 1
const int PIN_BLUE_BUTTON = 27;
const int PIN_RELAY = 26;
const int PIN_LED = 2;
const unsigned long PULSE_MS = 350;
const unsigned long POLL_MS = 2000;
const char *SERVER = "http://host.wokwi.internal:8765";
const char *MESA = "01";
const char *TOKEN = "COLE_TOKEN_DA_MESA_01_AQUI";

String currentCommand = "";
String toAcknowledge = "";
unsigned long lastPoll = 0;
unsigned long pulseStart = 0;
unsigned long lastButtonPress = 0;
bool relayOn = false;
bool lastButton = HIGH;

void setRelay(bool on) {
  // O módulo de relé do Wokwi (padrão NPN) é ativo em nível BAIXO.
  // Não transportar essa suposição para o circuito físico sem medir.
  digitalWrite(PIN_RELAY, on ? LOW : HIGH);
  digitalWrite(PIN_LED, on ? HIGH : LOW);
  relayOn = on;
  if (on) pulseStart = millis();
}

bool postAck(const String &id) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  String url = String(SERVER) + "/api/dispositivos/" + MESA + "/confirmar";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + TOKEN);
  JsonDocument payload;
  payload["comando"] = id;
  String text;
  serializeJson(payload, text);
  int code = http.POST(text);
  http.end();
  Serial.printf("ACK do comando %s: HTTP %d\n", id.c_str(), code);
  return code == 200;
}

void fetchCommand() {
  if (WiFi.status() != WL_CONNECTED || currentCommand.length() || toAcknowledge.length()) return;
  HTTPClient http;
  String url = String(SERVER) + "/api/dispositivos/" + MESA + "/proximo";
  http.begin(url);
  http.addHeader("Authorization", String("Bearer ") + TOKEN);
  int code = http.GET();
  if (code == 200) {
    JsonDocument data;
    DeserializationError error = deserializeJson(data, http.getStream());
    if (!error && !data["comando"].isNull()) {
      String received = data["comando"]["id"].as<String>();
      String tipo = data["comando"]["tipo"].as<String>();
      if (tipo == "PULSO" && received.length()) {
        currentCommand = received;
        Serial.printf("Mesa %s: pagamento confirmado. APERTE O BOTÃO AZUL.\n", MESA);
      }
    }
  } else {
    Serial.printf("Erro ao consultar servidor: HTTP %d\n", code);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, HIGH); // relé OFF desde o começo (somente Wokwi)
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_BLUE_BUTTON, INPUT_PULLUP);
  Serial.println("=== MESAFACIL — DEMO SINUCA ===");
#if DEMO_OFFLINE
  Serial.println("Modo SEM SERVIDOR: escreva p no Monitor Serial para simular Pix aprovado.");
#else
  WiFi.begin("Wokwi-GUEST", "", 6);
  Serial.print("Conectando ao WiFi");
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 12000) {
    delay(250); Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "\nWiFi conectado" : "\nSem WiFi; aguardando reconexão");
#endif
}

void loop() {
#if DEMO_OFFLINE
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'p' || c == 'P') {
      if (!currentCommand.length() && !toAcknowledge.length()) {
        currentCommand = "COMANDO_DEMO_OFFLINE";
        Serial.println("Pagamento FICTÍCIO aprovado. Clique no botão azul!");
      } else Serial.println("Já existe um crédito pendente.");
    }
  }
#else
  if (millis() - lastPoll >= POLL_MS) {
    lastPoll = millis();
    if (toAcknowledge.length() && !relayOn) {
      if (postAck(toAcknowledge)) toAcknowledge = "";
    } else fetchCommand();
  }
#endif
  bool button = digitalRead(PIN_BLUE_BUTTON);
  if (!button && lastButton && (millis() - lastButtonPress > 75)) {
    lastButtonPress = millis();
    if (currentCommand.length() && !relayOn && !toAcknowledge.length()) {
      Serial.println("Botão pressionado COM crédito: PULSO!");
      setRelay(true);
      toAcknowledge = currentCommand;
      currentCommand = "";
    } else Serial.println("Botão SEM crédito: não liberar fichas.");
  }
  lastButton = button;
  if (relayOn && millis() - pulseStart >= PULSE_MS) {
    setRelay(false);
    Serial.println("Pulso finalizado — relé desenergizado.");
#if DEMO_OFFLINE
    toAcknowledge = "";
    Serial.println("Pronto para próximo pagamento simulado.");
#endif
  }
  delay(10);
}
