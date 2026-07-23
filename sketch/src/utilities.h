#ifndef UTILITIES_H
#define UTILITIES_H

#include <Arduino.h> // Required for size_t and Stream types

#define TEST_LED
#define TEST_CLOUD 
#define PKT_LOG_ONLY 

// MAX485 driver enable / receive enable
#define DE 3
#define RE 2
#define MAX_PKT 256

enum Command : uint16_t {
    CMD_UNKNOWN     = 0,          // 0x0000 - No bits set
    CMD_POOL        = (1 << 0),   // 0x0001 (1)
    CMD_POOL_HEAT   = (1 << 1),   // 0x0002 (2)
    CMD_POOL_LIGHTS = (1 << 2),   // 0x0004 (4)
    CMD_SPA         = (1 << 3),   // 0x0008 (8)
    CMD_SPA_HEAT    = (1 << 4),   // 0x0010 (16)
    CMD_SPA_LIGHT   = (1 << 5),   // 0x0020 (32)
    CMD_JETS        = (1 << 6),   // 0x0040 (64)
    CMD_PUMP_SPEED  = (1 << 7),   // 0x0080 (128)
    CMD_ALL_OFF     = (1 << 8),   // 0x0100 (256)
    CMD_PDA         = (1 << 9),   // 0x0200 (512)
    CMD_INSEQ       = (1 << 10),   // 0x0400 (1024)
    CMD_RESET       = (1 << 11),
    CMD_STATUS_POLL = (1 << 12)
};

// C++ Bitwise Operator Overloads (Prevents mandatory static_cast)
inline Command operator|(Command a, Command b) {
    return static_cast<Command>(static_cast<uint16_t>(a) | static_cast<uint16_t>(b));
}

inline Command& operator|=(Command& a, Command b) {
    a = a | b;
    return a;
}

inline bool hasFlag(uint16_t mask, Command flag) {
    return (mask & static_cast<uint16_t>(flag)) != 0;
}

class PDAEmulator {
public:
    void executeCommand(uint16_t mask, int extraVal = 0);
};



// Keep Alive Packet 
const uint8_t PKT_PDA_KA[] = {0x10, 0x02, 0x00, 0x01, 0x00, 0x00, 0x13, 0x10, 0x03};

// ACK Packet with keypressed - no key 
const uint8_t PKT_PDA_ACK[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x00, 0x63, 0x10, 0x03};

// ACK Short Packet 
const uint8_t PKT_PDA_ACK_SHORT[] = {0x10, 0x02, 0x00, 0x01, 0xD0, 0x00, 0xE3, 0x10, 0x03};

// ACK Packet with no keypressed
const uint8_t PKT_PDA_ACKNK[] = {0x10, 0x02, 0x00, 0x01, 0xC0, 0x00, 0xD3, 0x10, 0x03};

// HS????
const uint8_t PKT_PDA_HS[] = {0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x03, 0x30, 0x32, 0x30, 0x00, 0x00, 0x3D, 0x10, 0x03};

// Send Select button press 
const uint8_t PKT_PDA_SELECT[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x04, 0x67, 0x10, 0x03};

// Send Back button press 
const uint8_t PKT_PDA_BACK[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x02, 0x65, 0x10, 0x03};

// Send Down button press 
const uint8_t PKT_PDA_DOWN[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x05, 0x68, 0x10, 0x03};

// Send Up button press 
const uint8_t PKT_PDA_UP[] = {0x10, 0x02, 0x00, 0x01, 0x50, 0x06, 0x69, 0x10, 0x03};

// Response to Master Probe 60 09 28... version string
const uint8_t PKT_PDA_VER[] = { 0x10, 0x02, 0x00, 0x20, 0x46, 0x00, 0x00, 0x03, 0x30, 0x30, 0x32, 0x30, 0x00, 0x00, 0x3D, 0x10, 0x03 };

// Response to Master Probe: 60 02 28 00 00 00 00 9C
// Reports Device Class 0x46 (PDA Handset)
const uint8_t PKT_PDA_ID_STANDARD[] = { 0x10, 0x02, 0x00, 0x02, 0x46, 0x00, 0x00, 0x00, 0x00, 0x48, 0x10, 0x03 };

//const uint8_t poolKeyDown[] = {0x00, 0x12, 0x3C, 0x01, 0x00, 0x61};
//const uint8_t poolKeyHold[] = {0x00, 0x12, 0x3C, 0x00, 0x60};


// Panel / AllButton destinations used in bench fixtures
const uint8_t DEST_PANEL = 0x00;
const uint8_t CMD_STATUS = 0x04;

// Max expected packets inside a single command buffer to prevent memory fragmentation
const uint8_t MAX_PACKET_COUNT = 8; 
const uint8_t MAX_PACKET_LEN   = 24; 

static int hexNibble(char c);
bool str_to_int(const char* text, int* result);
void bytesToHex(uint8_t* in, int len, char* out);
bool validateChecksum(const uint8_t* buf, size_t len);
void rs485SetTransmit(bool tx);
void rs485WriteRaw(Stream& serial1, const uint8_t* data, int len);

/**
 * Prints a raw byte buffer as formatted hex values to a specified serial interface.
 */
void printPacketRsp(Stream& monitor, const uint8_t* buf, size_t len);

/**
 * Prints an incoming raw byte buffer with an absolute millisecond timestamp prefix.
 * Example Output: [524812] RX: 0x60, 0x04, 0x04, 0x50, 
 * @param monitor Reference to the serial port object (e.g., Serial, Monitor)
 * @param buf Pointer to the raw array of bytes
 * @param len The number of bytes to read and print
 */
void printPacketBuffer(Stream& monitor, const uint8_t* buf, size_t len);

#endif // UTILITIES_H