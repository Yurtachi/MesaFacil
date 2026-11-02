/*
 MesaFacil Local v0.3 - APENAS demonstracao, sem pagamentos reais ou rele fisico.
 ESP32 DevKit V1 Velxio: botao GPIO27 -> GND, LED com resistor GPIO2 -> GND.
 GPIO26 = pulso de comando em nivel BAIXO (validar interface real ANTES de conectar).
 Uma tentativa por pagamento; ID persistido antes do pulso, ACK apos o pulso.
 ATENCAO: reinicio entre marcacao e pulso gera ESTADO INCERTO e requer intervencao.
 Nao utilizar em equipamento de producao.
*/
#include <Arduino.h>
#include <ctype.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>

static constexpr uint8_t PIN_BUTTON = 27;
static constexpr uint8_t PIN_RELAY  = 26;
static constexpr uint8_t PIN_LED    = 2;
static constexpr unsigned long PULSE_MS = 350;
static constexpr unsigned long POLL_MS  = 2000;
static constexpr unsigned long DEBOUNCE_MS = 80;

const char* WIFI_SSID = "Velxio-GUEST";
const char* WIFI_PASSWORD = "";
const char* SERVER = "{{SERVER}}";
const char* MESA = "{{MESA}}";
const char* DEVICE_TOKEN = "{{TOKEN}}";

Preferences prefs;
String pendingCommand = "";
String ackPending = "";
String lastStarted = "";
String lastDone = "";
bool pulseRunning = false;
bool lastButtonLevel = HIGH;
unsigned long pulseStarted = 0;
unsigned long lastPressed = 0;
unsigned long lastPoll = 0;
unsigned long lastReconnect = 0;

bool isUuid(const String &s) {
  if (s.length() != 36) return false;
  for (int i = 0; i < 36; i++) {
    char c = s[i];
    if (i == 8 || i == 13 || i == 18 || i == 23) { if (c != '-') return false; }
    else if (!isxdigit((unsigned char)c)) return false;
  }
  return true;
}

void stopOutput() {
  digitalWrite(PIN_RELAY, HIGH); // SOMENTE simulador: saida ativa em LOW
  digitalWrite(PIN_LED, LOW);
  pulseRunning = false;
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastReconnect < 5000) return;
  lastReconnect = millis();
  Serial.println("WiFi: conectando...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void sendAck(const String &id) {
  if (WiFi.status() != WL_CONNECTED || !id.length()) return;
  HTTPClient http;
  http.setTimeout(3000);
  String url = String(SERVER) + "/api/dispositivos/" + MESA + "/confirmar";
  if (!http.begin(url)) { Serial.println("ACK: erro iniciando HTTP"); return; }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
  int code = http.POST(String("{\"comando\":\"") + id + "\"}");
  http.end();
  Serial.printf("ACK: HTTP %d\n", code);
  if (code == 200) {
    ackPending = "";
    Serial.println("Mesa liberada confirmada no painel.");
  }
}

void pollServer() {
  if (WiFi.status() != WL_CONNECTED || pulseRunning) return;
  if (ackPending.length()) { sendAck(ackPending); return; }
  if (pendingCommand.length()) return;
  HTTPClient http;
  http.setTimeout(3000);
  String url = String(SERVER) + "/api/dispositivos/" + MESA + "/proximo.txt";
  if (!http.begin(url)) { Serial.println("POLL: falha de configuracao HTTP"); return; }
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
  int status = http.GET();
  String cmd = (status == 200) ? http.getString() : "";
  http.end();
  cmd.trim();
  if (status != 200) { Serial.printf("POLL: HTTP %d (sem liberar)\n", status); return; }
  if (cmd == "NONE" || cmd.isEmpty()) return;
  if (!isUuid(cmd)) { Serial.println("POLL: ID invalido, ignorando"); return; }

  if (cmd == lastDone) {
    Serial.println("Comando concluido antes de reiniciar. Reenviando ACK sem novo pulso.");
    ackPending = cmd;
    return;
  }
  if (cmd == lastStarted) {
    // Crash antes de completar o ciclo. Falha segura: jamais repetir o pulso automaticamente.
    Serial.println("ATENCAO: ESTADO INCERTO, verificar manualmente antes de nova autorizacao.");
    return;
  }
  pendingCommand = cmd;
  Serial.printf("Mesa %s: pagamento de TESTE confirmado. Pressione o botao.\n", MESA);
}

void beginPulse() {
  if (pendingCommand.isEmpty() || pulseRunning || ackPending.length()) {
    Serial.println("BOTAO: sem credito liberado; nenhuma acao.");
    return;
  }
  // persistir a tentativa ANTES da saida; nao assumir que grava e aciona atomicamente
  lastStarted = pendingCommand;
  if (!prefs.putString("started", lastStarted)) {
    Serial.println("ERRO ao registrar tentativa: liberacao bloqueada.");
    return;
  }
  pendingCommand = "";
  pulseRunning = true;
  pulseStarted = millis();
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_LED, HIGH);
  Serial.println("FICHAS LIBERADAS (simuladas): iniciando pulso 350ms.");
}

void setup() {
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  stopOutput();
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  Serial.begin(115200);
  prefs.begin("mesa_facil", false);
  lastStarted = prefs.getString("started", "");
  lastDone = prefs.getString("done", "");
  lastButtonLevel = digitalRead(PIN_BUTTON);
  Serial.printf("MesaFacil v0.3, mesa %s - SOMENTE SIMULACAO\n", MESA);
  Serial.printf("Servidor: %s\n", SERVER);
  Serial.println("Conectando ao WiFi do Velxio...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastReconnect = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) ensureWifi();
  static bool connectedPrinted = false;
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !connectedPrinted) {
    Serial.printf("WiFi conectado: %s, gateway %s\n", WiFi.localIP().toString().c_str(), WiFi.gatewayIP().toString().c_str());
  }
  connectedPrinted = connected;

  if (pulseRunning && millis() - pulseStarted >= PULSE_MS) {
    stopOutput();
    Serial.println("Saida desligada: 350 ms encerrados.");
    lastDone = lastStarted;
    if (prefs.putString("done", lastDone)) {
      ackPending = lastDone;
    } else {
      Serial.println("ERRO persistindo fim do pulso: BLOQUEADO ate verificacao.");
    }
  }
  bool buttonLevel = digitalRead(PIN_BUTTON);
  if (lastButtonLevel == HIGH && buttonLevel == LOW && millis() - lastPressed >= DEBOUNCE_MS) {
    lastPressed = millis();
    beginPulse();
  }
  lastButtonLevel = buttonLevel;
  if (millis() - lastPoll >= POLL_MS) {
    lastPoll = millis();
    pollServer();
  }
  delay(10);
}
