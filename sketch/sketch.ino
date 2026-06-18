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
#ifndef TEST_LED
#define TEST_LED 1
#endif

// Set to 1 to expose set_led_state Bridge RPC (Linux Blink demo)
#ifndef TEST_CLOUD
#define TEST_CLOUD 1
#endif

uint8_t packetBuffer[MAX_PKT];
char hexBuffer[MAX_PKT * 2 + 1];
int pIdx = 0;
int state = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
bool packetReady = false;
bool pdaConnected = false;

// Keep Alive Packet 
const uint8_t PKT_PDA_KA[] = {0x10, 0x02, 0x00, 0x01, 0x00, 0x00, 0x13, 0x10, 0x03};

// ACK Packet 
const uint8_t PKT_PDA_ACK[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x00, 0x63, 0x10, 0x03};

// CS????
const uint8_t PKT_PDA_CS[] = {0x10, 0x02, 0x00, 0x01, 0xC0, 0x00, 0xD3, 0x10, 0x03};

// HS????
const uint8_t PKT_PDA_HS[] = {0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x03, 0x30, 0x32, 0x30, 0x00, 0x00, 0x3D, 0x10, 0x03};

// Send Select button press ACK
const uint8_t PKT_PDA_SELECT[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03};

// Response to Master Probe 60 09 28... version string
const uint8_t PKT_PDA_VER[] = { 0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x03, 0x30, 0x30, 0x32, 0x30, 0x00, 0x00, 0x3D, 0x10, 0x03 };

// Response to Master Probe: 60 02 28 00 00 00 00 9C
// Reports Device Class 0x46 (PDA Handset)
const uint8_t PKT_PDA_ID_STANDARD[] = { 0x10, 0x02, 0x00, 0x02, 0x46, 0x00, 0x00, 0x00, 0x00, 0x48, 0x10, 0x03 };

//const uint8_t poolKeyDown[] = {0x00, 0x12, 0x3C, 0x01, 0x00, 0x61};
//const uint8_t poolKeyHold[] = {0x00, 0x12, 0x3C, 0x00, 0x60};

void set_led_state(bool state) {
    // LOW state means LED is ON
    digitalWrite(LED_BUILTIN, state ? LOW : HIGH);
    Monitor.println("LED");
}

static int hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

// Panel / AllButton destinations used in bench fixtures
const uint8_t DEST_PANEL = 0x00;
const uint8_t CMD_STATUS = 0x04;

// Max expected packets inside a single command buffer to prevent memory fragmentation
const uint8_t MAX_PACKET_COUNT = 8; 
const uint8_t MAX_PACKET_LEN   = 24; 

/**
 * Processes incoming bytes, steps the state machine, and orchestrates line responses.
 */
void handle_packet(const uint8_t* raw_bytes, uint8_t length) {

    if (raw_bytes == nullptr || length == 0) {
        return; 
    }
    if (1) {
        if((raw_bytes[0] == 0x60) && (raw_bytes[1] != 0x00)) 
            //parseJandyDisplayPacket(raw_bytes, length);
            printPacketBuffer(raw_bytes, length);
        else
            delay(20);
        return;
    }

     // PDA destination Rx'ed
    if (raw_bytes[0] == 0x60) {
       
        switch (raw_bytes[1]){
            case 0x00: // Initial Connect
                pdaConnected = true;
                delay(15);
                rs485WriteRaw(PKT_PDA_KA, sizeof(PKT_PDA_KA));
                //Monitor.println(F("Received PDA Connect"));
                break;
            case 0x02: // Keep Alive
                if(raw_bytes[2] == 0x32){ // Master Probe
                    rs485WriteRaw(PKT_PDA_ACK, sizeof(PKT_PDA_ACK));
                    //Monitor.println(F("Received PKT_PDA_ID_REV32"));
                }
                else if(raw_bytes[2] == 0x28) {
                    rs485WriteRaw(PKT_PDA_ACK, sizeof(PKT_PDA_ACK));
                    //Monitor.println(F("Received 0228"));
                }
                break;
            case 0x04: // Long Message
                rs485WriteRaw(PKT_PDA_ACK, sizeof(PKT_PDA_ACK));
                //Monitor.println(F("Received MSG LONG"));
                break;
            case 0x08: 
                rs485WriteRaw(PKT_PDA_ACK, sizeof(PKT_PDA_ACK));
                //Monitor.println(F("Received PDA 0x08"));
                break;
            case 0x09: 
                rs485WriteRaw(PKT_PDA_VER, sizeof(PKT_PDA_VER));

                //Monitor.println(F("Received PDA 0x09"));
                break;
            case 0x1B: // Screen UI Layer Sync / Menu Token
            {
                // 1. Grab whatever token the master threw at us (0x00, 0x04, 0x0B, etc.)
                uint8_t token = raw_bytes[2]; 
                uint8_t contextChecksum = 0x10 + 0x1C + token; // Checksum includes the command and token, plus the fixed 0x12
                uint8_t pkt_context_echo[] = { 
                    0x10, 0x02,         // STX
                    0x00,               // Destination (Master)
                    0x1C,               // Command (Context ACK)
                    token,              // The Echoed Token (Dynamically scales to 0x00 or any value)
                    0x00,               // Padding
                    contextChecksum,    // Calculated Checksum (Will be 0x2C when token is 0x00)
                    0x10, 0x03          // ETX
                };
                rs485WriteRaw(PKT_PDA_CS, sizeof(PKT_PDA_CS));
                //rs485WriteRaw(pkt_context_echo, sizeof(pkt_context_echo));
                //Monitor.print(F("Received PDA 0x1B (Context Sync): "));
                //printPacketBuffer(pkt_context_echo, sizeof(pkt_context_echo));
                break;
            }
        }

        //Send packet to MPU
        bytesToHex(packetBuffer, pIdx, hexBuffer);
        Bridge.notify("pda_packet", hexBuffer);  
    
        //printPacketBuffer(raw_bytes, length);
    }
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

  unsigned long currentMillis = millis();
 
  Monitor.print("[");
  Monitor.print(currentMillis);
  Monitor.print("] RX: ");

  for (size_t i = 0; i < len; i++) {
    Monitor.print("0x");

    // Print a leading zero if the byte is less than 16 (0x10)
    if (buf[i] < 16) {
      Monitor.print("0");
    }
    
    Monitor.print(buf[i], HEX);
    Monitor.print(", ");
    
  }
  Monitor.println(); // Final newline
}

void printPacketRsp(const uint8_t* buf, size_t len) {

  Monitor.print("Response (");
  Monitor.print(len);

  Monitor.print(": ");
  
  for (size_t i = 0; i < len; i++) {
    // Print a leading zero if the byte is less than 16 (0x10)
    Monitor.print("0x");
    if (buf[i] < 16) {
      Monitor.print("0");
    }
    
    Monitor.print(buf[i], HEX);
    Monitor.print(", "); // Add a space between bytes for readability
   }
  Monitor.println(); // Final newline
}

void send_Rsp_Pkt(const uint8_t* packet, size_t length) {
    // Safety check to prevent passing empty or malformed pointers
    if (packet == nullptr || length <= 0) return;
    
    // Forward the predefined buffer directly to your hardware writing engine
    rs485WriteRaw(packet, length);
    //printPacketRsp(packet, length);
}

void processByte(uint8_t c) {
     
    switch (state) {
        case 0: // Idle state, waiting for STX
            if (c == 0x10) state = 1;
            break;
        case 1: // Received STX, expecting start of packet
            if (c == 0x02) { // Valid start of packet
                pIdx = 0;
                state = 2;
            } else {
                state = 0;
            }
            break;
        case 2: // Reading packet data, looking for ETX or escape
            if (c == 0x10) state = 3;
            else if (pIdx < MAX_PKT) packetBuffer[pIdx++] = c;
            break;
        case 3: // After escape character, determine if it's an escaped byte or end of packet
            if (c == 0x03) {
                if (validateChecksum()) {
                    packetReady = true; // Signal that a full packet is ready for processing
                }
                state = 0;
            } else if (c == 0x10) { // Escaped 0x10 byte, add it to the buffer
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
void rs485SendHex(const char* hex) {

    size_t byteCount = 0;
    size_t strLen = strlen(hex);
    uint8_t buf[MAX_PKT];

    // Process characters in pairs (2 hex characters = 1 raw byte)
    for (size_t i = 0; i < strLen && byteCount < MAX_PKT; i += 2) {
        
        // Handle an odd character at the end safely by stopping
        if (hex[i + 1] == '\0') {
            break; 
        }

        // Extract a two-character substring fragment
        char byteChars[3] = { hex[i], hex[i + 1], '\0' };

        // Convert the base-16 string pair into a base-10 numerical integer
        uint8_t byteVal = (uint8_t)strtol(byteChars, NULL, 16);

        // Assign the number to our buffer array
        buf[byteCount] = byteVal;
        byteCount++;
    }   
    
    if (byteCount) {
        rs485WriteRaw(buf, byteCount);
    }
}

void rs485_tx(String hex) {
    rs485SendHex(hex.c_str());
    Monitor.print("RS485 TX ");
    Monitor.println(hex);
}

void setup() {
    Monitor.begin();
    Serial1.begin(9600);
    pinMode(DE, OUTPUT);
    pinMode(RE, OUTPUT);
    rs485SetTransmit(false);
    pinMode(LED_BUILTIN, OUTPUT);

    Bridge.begin();
    Bridge.provide("set_led_state", set_led_state);
    Bridge.provide("RS485_send", rs485_tx);

    delay(3000);
    Monitor.println("PoolController RS485 ready");
}

void loop() {
  
    // Check if a byte has arrived from the RS-485 circuit
    if (Serial1.available() > 0) {
           
        while (Serial1.available() && !packetReady) {
          processByte((uint8_t)Serial1.read());
        }

        // If a full packet has been received and validated, process it
        if (packetReady) {
            handle_packet(packetBuffer, pIdx);    


            //Monitor.print("RS485 RX: ");
            //Monitor.println(hexBuffer);
            packetReady = false;
            pIdx = 0;
        }  
    }

    //check for incoming commands from UI
}



