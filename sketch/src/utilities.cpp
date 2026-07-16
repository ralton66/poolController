#include "utilities.h"

static int hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}


bool validateChecksum(const uint8_t* buf, size_t len) {
    if (len < 2)
      return false;

    uint8_t calculatedSum = 0;
    
    for (int i = 0; i < len - 1; i++)
       calculatedSum += buf[i];
    return (((calculatedSum + 0x12) & 0xFF) == buf[len - 1]);
}

void bytesToHex(uint8_t* in, int len, char* out) {
    const char* hexChars = "0123456789ABCDEF";
    for (int i = 0; i < len; i++) {
        out[i * 2] = hexChars[(in[i] >> 4) & 0x0F];
        out[i * 2 + 1] = hexChars[in[i] & 0x0F];
    }
    out[len * 2] = '\0';
}

void rs485SetTransmit(bool tx) {
    digitalWrite(DE, tx ? HIGH : LOW);
    digitalWrite(RE, tx ? HIGH : LOW);
}

void rs485WriteRaw(Stream& serial1, const uint8_t* data, int len) {
    if (len <= 0) return;
    rs485SetTransmit(true);
    delay(1);
    serial1.write(data, len);
    serial1.flush();
    delay(1);
    rs485SetTransmit(false);
    //Monitor.print("T: ");
    //Monitor.println(millis());
}

void printPacketBuffer(Stream& monitor, const uint8_t* buf, size_t len) {

  unsigned long currentMillis = millis();
 
  monitor.print("[");
  monitor.print(currentMillis);
  monitor.print("] RX: ");

  for (size_t i = 0; i < len; i++) {

    // Print a leading zero if the byte is less than 16 (0x10)
    if (buf[i] < 16) {
      monitor.print("0");
    }
    
    monitor.print(buf[i], HEX);
    
  }
  monitor.println(); // Final newline
}

void printPacketRsp(Stream& monitor, const uint8_t* buf, size_t len) {

  unsigned long currentMillis = millis();
 
  monitor.print("[");
  monitor.print(currentMillis);
  monitor.print("] RX: ");

  for (size_t i = 2; i < (len-2); i++) {

    // Print a leading zero if the byte is less than 16 (0x10)
    if (buf[i] < 16) {
      monitor.print("0");
    }
    
    monitor.print(buf[i], HEX);
    
  }
  monitor.println(); // Final newline
}


void parseJandyDisplayPacket(Stream& monitor, const unsigned char *packet, size_t packetLen) {
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
    if (lineId < 16) monitor.print(F("0")); // Leading zero padding for hex formatting
    monitor.print(lineId, HEX);
    monitor.print(F(" | "));
    monitor.print(asciiString);
    monitor.println();
}
