#include "utilities.h"
#include <stdarg.h>

static int hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

bool str_to_int(const char* text, int* result) {
    if (text == NULL || result == NULL) return false;

    const char* p = text;
    bool found_number = false;
    bool is_negative = false;
    int value = 0;

    while (*p != '\0') {
        // Handle numerical digits
        if (*p >= '0' && *p <= '9') {
            found_number = true;
            value = (value * 10) + (*p - '0');
        } 
        // Handle negative sign (only if it occurs immediately before the number block begins)
        else if (*p == '-' && !found_number) {
            if (*(p + 1) >= '0' && *(p + 1) <= '9') {
                is_negative = true;
            }
        } 
        // Break instantly if we encounter any trailing noise (like 'F', 'FF', or spaces) 
        // after already beginning to parse a valid numerical block.
        else if (found_number) {
            break;
        }
        p++; // Move to next character
    }

    if (found_number) {
        *result = is_negative ? -value : value;
        return true;
    }

    return false; // No parseable digits found
}

void processCommandMask(uint16_t rawMask) {
    if (hasFlag(rawMask, CMD_POOL)) {
        // Activate Filter Pump Relay
    }
    
    if (hasFlag(rawMask, CMD_POOL_HEAT)) {
        // Arm Heater Relay
    }

    if (hasFlag(rawMask, CMD_ALL_OFF)) {
        // Emergency stop: Disengage all relays
    }
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
}

void printPacketBuffer(const uint8_t* buf, size_t len) {
    if (buf == NULL || len == 0) return;

    String hexStr = "";
    for (size_t i = 0; i < len; i++) {
        char hexByte[3];
        snprintf(hexByte, sizeof(hexByte), "%02X", buf[i]);
        hexStr += hexByte;
    }

    Logger.debug("RX: " + hexStr);
}

void printPacketRsp(const uint8_t* buf, size_t len) {
    if (buf == NULL || len < 4) return;

    // Build the formatted hex string for bytes between header (2) and checksum (len-2)
    String hexStr = "";
    for (size_t i = 2; i < (len - 2); i++) {
        char hexByte[3];
        snprintf(hexByte, sizeof(hexByte), "%02X", buf[i]);
        hexStr += hexByte;
    }

    // Pass formatted string to Logger (Logger automatically prepends [millis] and level tag)
    Logger.debug("RX: " + hexStr);
}


void PDAEmulator::executeCommand(uint16_t mask, int extraVal) {
    if (mask == CMD_UNKNOWN) return;

    // Handle RESET bit
    if (mask & CMD_RESET) {
        // Handle board reset routine
        return;
    }

    // Handle ALL OFF bit first if set
    if (mask & CMD_ALL_OFF) {
        // Turn off filter pump, spa, heaters, lights
        return;
    }

    // Check individual command bits (Multiple bits can execute in one call)
    if (mask & CMD_POOL) {
        // Toggle/Enable Pool Filter Pump
    }

    if (mask & CMD_POOL_HEAT) {
        // Enable Pool Heater
    }

    if (mask & CMD_SPA) {
        // Toggle Spa Valves / Actuators
    }

    if (mask & CMD_SPA_HEAT) {
        // Set Spa Setpoint / Enable Spa Heater
    }

    if (mask & CMD_PUMP_SPEED) {
        // Apply RPM speed passed in extraVal
    }

    if (mask & CMD_POOL_LIGHTS) {
        // Toggle Pool Lights
    }

    if (mask & CMD_SPA_LIGHT) {
        // Toggle Spa Lights
    }
}

// Define global instance
LoggerClass Logger;

LoggerClass::LoggerClass() : _port(NULL), _minLevel(LOG_INFO) {}

void LoggerClass::begin(Stream& monitorPort, LogLevel minLevel) {
    _port = &monitorPort;
    _minLevel = minLevel;
}

void LoggerClass::setLevel(LogLevel level) {
    _minLevel = level;
}

void LoggerClass::_log(LogLevel level, const char* prefix, const String& msg) {
    if (_port == NULL || level < _minLevel) return;

    // Optional: Print millisecond timestamp [ms]
    _port->print("[");
    _port->print(millis());
    _port->print("] ");

    // Print Level Tag and message
    _port->print(prefix);
    _port->println(msg);
}

// Basic String Methods
void LoggerClass::debug(const String& msg)   { _log(LOG_DEBUG, "DEBUG: ", msg); }
void LoggerClass::info(const String& msg)    { _log(LOG_INFO,  "INFO: ",  msg); }
void LoggerClass::warning(const String& msg) { _log(LOG_WARN,  "WARNING: ", msg); }
void LoggerClass::error(const String& msg)   { _log(LOG_ERROR, "ERROR: ", msg); }

// Formatted (printf-style) Helper Methods
void LoggerClass::debugf(const char* fmt, ...) {
    if (_port == NULL || LOG_DEBUG < _minLevel) return;
    char buf[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    debug(String(buf));
}

void LoggerClass::infof(const char* fmt, ...) {
    if (_port == NULL || LOG_INFO < _minLevel) return;
    char buf[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    info(String(buf));
}

void LoggerClass::warnf(const char* fmt, ...) {
    if (_port == NULL || LOG_WARN < _minLevel) return;
    char buf[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    warning(String(buf));
}

void LoggerClass::errorf(const char* fmt, ...) {
    if (_port == NULL || LOG_ERROR < _minLevel) return;
    char buf[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    error(String(buf));
}
