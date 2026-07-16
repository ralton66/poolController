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

enum Command {
    CMD_UNKNOWN,
    CMD_POOL,
    CMD_POOL_HEAT,
    CMD_POOL_LIGHTS,
    CMD_SPA,
    CMD_SPA_HEAT,
    CMD_SPA_LIGHT,
    CMD_JETS,
    CMD_ALL_OFF,
    CMD_PDA,
    CMD_INSEQ
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