// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Arduino.h>

// MAX485 driver enable / receive enable
#define DE 3
#define RE 2
#define MAX_PKT 256

// Set to 1 to expose set_led_state Bridge RPC (Linux Blink demo)
#ifndef POOL_TEST_LED
#define POOL_TEST_LED 0
#endif

uint8_t packetBuffer[MAX_PKT];
char hexBuffer[MAX_PKT * 2 + 1];
int pIdx = 0;
int state = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
bool packetReady = false;
bool pdaConnected = false;

// Steady-State Operational Ready Packet (Answering normal runtime loops)
const uint8_t PKT_PDA_KA[] = {0x10, 0x02, 0x00, 0x01, 0x00, 0x00, 0x13, 0x10, 0x03};

// Steady-State Operational Ready Packet (Answering normal runtime loops)
const uint8_t PKT_PDA_ACK[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x00, 0x63, 0x10, 0x03};

// Steady-State Operational Ready Packet (Answering normal runtime loops)
const uint8_t PKT_PDA_CS[] = {0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x00, 0x00, 0x48, 0x10, 0x03};

// Steady-State Operational Ready Packet (Answering normal runtime loops)
const uint8_t PKT_PDA_HS[] = {0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x03, 0x30, 0x32, 0x30, 0x00, 0x00, 0x3D, 0x10, 0x03};

// Steady-State Operational Ready Packet (Answering normal runtime loops)
const uint8_t PKT_PDA_SELECT[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03};

static int hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

void parseJandyDisplayPacket(const unsigned char *packet, size_t packetLen) {
    if (packetLen < 4) return;
    if (packet[0] != 0x60) return;

    unsigned char headerLen = packet[1] - 1;
    
    if (packetLen < (size_t)(headerLen + 2)) return;

    unsigned char lineId = packet[2];
    size_t payloadStart = headerLen;
    size_t payloadEnd = packetLen - 1; // Drop the checksum byte
    
    if (payloadStart >= payloadEnd) return;
 
    size_t textLen = payloadEnd - payloadStart;
    char asciiString[36]; 
    size_t strIdx = 0;

    for (size_t i = payloadStart; i < payloadEnd && strIdx < (sizeof(asciiString) - 3); i++) {
        unsigned char c = packet[i];

        if (c == 0x60) {
            // Handle Jandy's custom degree token mapping inside standard Serial Monitor
            // Converts 0x60 into the UTF-8 multi-byte degree symbol sequence (°)
            asciiString[strIdx++] = (char)0xC2; 
            asciiString[strIdx++] = (char)0xB0; 
        } else if (c >= 32 && c <= 126) {
            // Standard printable ASCII range check
            asciiString[strIdx++] = (char)c;
        } else {
            // Replace dropped non-printable wire noise with a space
            asciiString[strIdx++] = ' ';
        }
    }
    asciiString[strIdx] = '\0'; // Ensure string is null-terminated

    if (lineId == 0x28) return;
    if (lineId == 0x00) return;
    if (lineId < 16) Monitor.print(F("0")); // Leading zero padding for hex formatting
    Monitor.print(lineId, HEX);
    Serial.print(F(" | "));
    Monitor.print(asciiString);
    Monitor.println();
}

bool validateChecksum() {
    if (pIdx < 2) {
      Monitor.print("<2 ");
      return false;
    }
    uint8_t calculatedSum = 0;
    
    for (int i = 0; i < pIdx - 1; i++) {
       calculatedSum += packetBuffer[i];
    }

    calculatedSum += 0x12;
    
    return (calculatedSum == packetBuffer[pIdx - 1]);
}

void bytesToHex(uint8_t* in, int len, char* out) {
    const char* hexChars = "0123456789ABCDEF";
    for (int i = 0; i < len; i++) {
        out[i * 2] = hexChars[(in[i] >> 4) & 0x0F];
        out[i * 2 + 1] = hexChars[in[i] & 0x0F];
    }
    out[len * 2] = '\0';
}

void printPacketBuffer(const uint8_t* buf, size_t len) {

  Monitor.print("Packet(");
  Monitor.print(len);

  Monitor.print("): ");
  
  for (size_t i = 0; i < len; i++) {
    // Print a leading zero if the byte is less than 16 (0x10)
    if (buf[i] < 16) {
      Monitor.print("0");
    }
    
    Monitor.print(buf[i], HEX);
    Monitor.print(" "); // Add a space between bytes for readability
    
    // Optional: Break into a new line every 16 bytes for large buffers
    if ((i + 1) % 16 == 0) {
      Monitor.println();
    }
  }
  Monitor.println(); // Final newline
}

void printPacketRsp(const uint8_t* buf, size_t len) {

  Monitor.print("Response (");
  Monitor.print(len);

  Monitor.print(": ");
  
  for (size_t i = 0; i < len; i++) {
    // Print a leading zero if the byte is less than 16 (0x10)
    if (buf[i] < 16) {
      Monitor.print("0");
    }
    
    Monitor.print(buf[i], HEX);
    Monitor.print(" "); // Add a space between bytes for readability
    
    // Optional: Break into a new line every 16 bytes for large buffers
    if ((i + 1) % 16 == 0) {
      Monitor.println();
    }
  }
  Monitor.println(); // Final newline
}

void sendJandyResponse(const uint8_t* packet, size_t length) {
    // Safety check to prevent passing empty or malformed pointers
    if (packet == nullptr || length <= 0) return;
    
    // Forward the predefined buffer directly to your hardware writing engine
    rs485WriteRaw(packet, length);
    //printPacketRsp(packet, length);
}

void processByte(uint8_t c) {
     
    switch (state) {
        case 0:
            if (c == 0x10) state = 1;
            break;
        case 1:
            if (c == 0x02) {
                pIdx = 0;
                state = 2;
            } else {
                state = 0;
            }
            break;
        case 2:
            if (c == 0x10) state = 3;
            else if (pIdx < MAX_PKT) packetBuffer[pIdx++] = c;
            break;
        case 3:
            if (c == 0x03) {
                if (validateChecksum()) {
                    packetReady = true;
                }
                state = 0;
            } else if (c == 0x10) {
                if (pIdx < MAX_PKT) packetBuffer[pIdx++] = 0x10;
                state = 2;
            } else {
               state = 0;
            }
            break;
    }
}

void rs485SetTransmit(bool tx) {
    digitalWrite(DE, tx ? HIGH : LOW);
    digitalWrite(RE, tx ? HIGH : LOW);
}

void rs485WriteRaw(const uint8_t* data, int len) {
    if (len <= 0) return;
    rs485SetTransmit(true);
    delay(2);
    Serial1.write(data, len);
    Serial1.flush();
    delay(2);
    rs485SetTransmit(false);
}

// Send full on-wire Jandy frame (hex string from Linux)
void rs485SendHex(const String& hex) {
    uint8_t buf[MAX_PKT];
    int n = 0;
    for (unsigned int i = 0; i + 1 < hex.length() && n < MAX_PKT; i += 2) {
        while (i < hex.length() && hex.charAt(i) == ' ') i++;
        if (i + 1 >= hex.length()) break;
        int hi = hexNibble(hex.charAt(i));
        int lo = hexNibble(hex.charAt(i + 1));
        if (hi < 0 || lo < 0) {
            Monitor.println("RS485_send: bad hex");
            return;
        }
        buf[n++] = (uint8_t)((hi << 4) | lo);
    }
    if (n > 0) {
        rs485WriteRaw(buf, n);
    }
}

void injectTestPacket() {
    uint8_t mockData[] = {0x08, 0x04, 0x41, 0x49, 0x52, 0x20, 0x54, 0x45,
                          0x4D, 0x50, 0x20, 0x37, 0x35, 0x46, 0x10};
    memcpy(packetBuffer, mockData, sizeof(mockData));
    pIdx = sizeof(mockData);
    packetReady = true;
}

void rs485_tx(String hex) {
    Monitor.print("RS485 TX ");
    Monitor.println(hex);
    rs485SendHex(hex);
}

void inject_test_packet() {
    injectTestPacket();
}

#if POOL_TEST_LED
void set_state(bool state) {
    digitalWrite(LED_BUILTIN, state ? LOW : HIGH);
}
#endif

void setup() {
    Monitor.begin();
    Serial1.begin(9600);
    pinMode(DE, OUTPUT);
    pinMode(RE, OUTPUT);
    rs485SetTransmit(false);

    
#if POOL_TEST_LED
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);
#endif

    Bridge.begin();
    Bridge.provide("RS485_send", rs485_tx);
    Bridge.provide("inject_test_packet", inject_test_packet);
#if POOL_TEST_LED
    Bridge.provide("set_led_state", set_state);
#endif
    delay(3000);
    Monitor.println("PoolController RS485 ready");
}

void loop() {
  
    // Check if a byte has arrived from the RS-485 circuit
    if (Serial1.available() > 0) {
           
        while (Serial1.available() && !packetReady) {
          processByte((uint8_t)Serial1.read());
        }

        if (packetReady) {

          
          if (packetBuffer[0] == 0x90) {
                        
            delay(2);
            sendJandyResponse(PKT_PDA_KA, sizeof(PKT_PDA_ACK));
            parseJandyDisplayPacket(packetBuffer, pIdx);
          
          }else if (packetBuffer[0] == 0x90 && packetBuffer[1] == 0x02) {
              //printPacketBuffer(packetBuffer, pIdx);
              sendJandyResponse(PKT_PDA_CS, sizeof(PKT_PDA_CS));

          }else if (packetBuffer[0] == 0x90 && packetBuffer[1] == 0x09) {
              printPacketBuffer(packetBuffer, pIdx);
              sendJandyResponse(PKT_PDA_HS, sizeof(PKT_PDA_HS));
             
          }
          //else{
          //  printPacketBuffer(packetBuffer, pIdx); 
          //}
          
          bytesToHex(packetBuffer, pIdx, hexBuffer);
          Bridge.notify("pda_packet", hexBuffer);

          packetReady = false;
          pIdx = 0;
        }  
    }
}
