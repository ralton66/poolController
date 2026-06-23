// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include "src/utilities.h"


uint8_t packetBuffer[MAX_PKT];
uint8_t highlighted_line = 0;
char hexBuffer[MAX_PKT * 2 + 1];
int pIdx = 0;
int state = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
int cmd_seq = 0; // control command sequencing based on master responses
bool packetReady = false;
bool pdaConnecting = false;
bool pdaSynced = false;

enum Command {
    CMD_UNKNOWN,
    CMD_POOL,
    CMD_POOL_HTR,
    CMD_POOL_LIGHT,
    CMD_SPA,
    CMD_SPA_HTR,
    CMD_SPA_LIGHT,
    CMD_ALL_OFF,
    CMD_INSEQ
};

Command control_command = CMD_UNKNOWN;

uint8_t pkt_rsp[] = { 
                0x10, 0x02, 
                0x00,               
                0x01, // Command (Context ACK)
                0xD0,              
                0x00,               
                0xE3, 
                0x10, 0x03          
            };


void set_led_state(bool s) {
    // LOW state means LED is ON
    digitalWrite(LED_BUILTIN, s ? LOW : HIGH);
    Monitor.println("LED");
}

/**
 * Processes incoming bytes, steps the state machine, and orchestrates line responses.
 */
void handle_packet(const uint8_t* raw_bytes, uint8_t length) {

    if (raw_bytes == nullptr || length == 0) {
        return; 
    }
    
    const uint8_t* rsp_ptr = NULL;
    const uint8_t* ack_ptr = NULL;
    uint8_t rsp_len = 0;
    uint8_t token = 0;
    
    #ifdef PKT_LOG_ONLY
        //if((raw_bytes[0] == 0x60) && (raw_bytes[1] != 0x00)) 
        //if((raw_bytes[0] == 0x60) ) 
            //parseJandyDisplayPacket(raw_bytes, length);
        printPacketBuffer(Monitor, raw_bytes, length);
        //else
        //    delay(20);
        return;
    
    #else
        printPacketBuffer(Monitor, raw_bytes, length);

        // PDA destination Rx'ed
        //pkt_rsp[3] = 0x01; // response ACK
        if (raw_bytes[0] == 0x60) {
            if(raw_bytes[1] == 0x08)
                highlighted_line = raw_bytes[2];

            //Check Control Inputs
            if(control_command != CMD_UNKNOWN) {
                switch(control_command){
                    case CMD_POOL: {
                        if (highlighted_line == 4){ //Send Down command
                            pkt_rsp[4] = 0xD0; // sync'd, PDA, key pressed
                            pkt_rsp[5] = 0x04; // Select Command
                            pkt_rsp[6] = 0x12 + 0x01 + 0x04 + pkt_rsp[4];
                            rs485WriteRaw(pkt_rsp, 9);
                            printPacketRsp(Monitor, pkt_rsp, 9);

                            //Monitor.print("CMD_POOL: send select");
                            //Monitor.println(control_command);
                            control_command = CMD_UNKNOWN;
                            break;
                        }else{
                            pkt_rsp[4] = 0xD0; // sync'd, PDA, key pressed
                            pkt_rsp[5] = 0x05; // DOWN Command
                            pkt_rsp[6] = 0x12 + 0x01 + 0x05 + pkt_rsp[4];
                            rs485WriteRaw(pkt_rsp, 9);
                            printPacketRsp(Monitor, pkt_rsp, 9);
                            break;
                        }
                    }
                    case CMD_SPA: {

                        if ((highlighted_line != 6) && (cmd_seq == 0)){ //Send Down command
                            pkt_rsp[4] = 0xD0; // sync'd, PDA, key pressed
                            pkt_rsp[5] = 0x05; // DOWN Command
                            pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4] + pkt_rsp[5];
                            rs485WriteRaw(pkt_rsp, 9);
                            printPacketRsp(Monitor, pkt_rsp, 9);
                            cmd_seq = 1;
                            break;
                        }
                        else if((highlighted_line == 6) && (cmd_seq == 0)){
                            pkt_rsp[4] = 0xD0; // sync'd, PDA, key pressed
                            pkt_rsp[5] = 0x04; // SELECT Command
                            pkt_rsp[6] = 0x12 + 0x01 + 0x04 + pkt_rsp[4];
                            rs485WriteRaw(pkt_rsp, 9);
                            printPacketRsp(Monitor, pkt_rsp, 9);
                            cmd_seq == 0;
                            control_command = CMD_UNKNOWN;
                            break;
                        }
                        else if (cmd_seq >= 1){
                            pkt_rsp[4] = 0xC0; //sync'ed/no keypress
                            pkt_rsp[5] = 0x00; // no key 
                            pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                             rs485WriteRaw(pkt_rsp, 9);
                            printPacketRsp(Monitor, pkt_rsp, 9);
                            cmd_seq++;
                            if(cmd_seq >= 5)
                                cmd_seq = 0;
                            break;
                        }
                    }
                    default:
                        control_command = CMD_UNKNOWN;
                        break;
                }
                Monitor.print("Line selected: ");
                Monitor.print(highlighted_line, HEX);
                Monitor.print("Seq: ");
                Monitor.println(cmd_seq, HEX);
                
                return;
            }
          
            /*
            Bit,Hex Mask,Definition,Description for Byte 2 response
            Bit 7,0x80,
            Session Sync / Power State,
            0 = Handshake / Wake-up phase (un-synced)
            1 = Active session / Fully synchronized

            Bit 6,0x40,
            PDA Device Identifier,
            Always 1 for PDA transceivers. 
            Distinguishes it from standard hardwired keypads (which use 0x00).

            Bit 5,0x20,
            Reserved,
            Always 0.

            Bit 4,0x10,
            Keypress Data Flag,
            0 = Idle ACK (Byte 3 is empty/ignored) 
            1 = Keypress active (Master must parse Byte 3)

            Bits 3–0,0x0F,
            Reserved / Unused,
            Always 0 in this firmware generation.

            Byte 3 from Master
            0x00 (System Idle): No equipment relays are active, no heaters 
            are engaged, and the system is in a baseline background state.

            0x28 (0010 1000): Specific equipment flags are active. In the 
            AquaLink RS architecture, this bit combination typically indicates 
            that certain primary relays (like the Filter Pump or a specific 
            auxiliary circuit) are energized, or the master is signaling a 
            specific sub-menu state.

            0xFF (1111 1111 - Broadcast / Sync Reset): This is a global 
            status override. The master sends this during a cold boot, 
            a soft reset, or when it loses track of device presence on 
            the JBox transceiver loop. It is the master command for: 
            "All display devices re-initialize, flush your screen caches, 
            and declare your current state."
            */

            //Reply with simple keep alive for the first few packet acks
            if(pdaConnecting){
                rs485WriteRaw(PKT_PDA_KA, sizeof(PKT_PDA_KA));
                printPacketRsp(Monitor, PKT_PDA_KA, 9);
                cmd_seq++;
                if(cmd_seq >= 3){
                    pdaConnecting = false;
                    cmd_seq = 0;
                }
                return;
            }
                        
            // Configure basic ack packet based on request
            if((raw_bytes[2] & 0x80) != 0){
                pkt_rsp[4] = 0x40; //unsync'ed/no keypress
                pkt_rsp[5] = 0x00; // no key
            }else{
                pkt_rsp[4] = 0xC0; //sync'ed/no keypress
                pkt_rsp[5] = 0x00; // no key 
            }
            pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12

            // determine ACK type and send
            switch (raw_bytes[1]){
                case 0x00: // Initial Connect
                    pdaConnecting = true;
                    rs485WriteRaw(PKT_PDA_KA, sizeof(PKT_PDA_KA));
                    printPacketRsp(Monitor, PKT_PDA_KA, 9);
                    break;
                case 0x02: // Keep Alive
                    rs485WriteRaw(pkt_rsp, 9);
                    break;
                case 0x04: // Long Message
                    //if(cmd_seq == 1){
                    //    pkt_rsp[4] = 0x36;
                    //    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4];
                    //    cmd_seq=0;
                    //}
                    //else{
                    //    pkt_rsp[4] = 0xD0; // Select Command
                    //    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4];
                    //}
                    rs485WriteRaw(pkt_rsp, 9);
                    //cmd_seq++;
                    break;
                case 0x08: // Highlight line
                    //pkt_rsp[4] = 0x36;
                    //pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4];
                    
                    rs485WriteRaw(pkt_rsp, 9);
                    Monitor.print("Line selected: ");
                    Monitor.println(highlighted_line, HEX);
                    break;
                case 0x09: //Clear Screen
                    rs485WriteRaw(pkt_rsp, 9);
                    break;
                case 0x1B: // Screen UI Layer Sync / Menu Token
                {
                    // 1. Grab whatever token the master threw at us (0x00, 0x04, 0x0B, etc.)
                    pkt_rsp[4] = 0xC0; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                    rs485WriteRaw(pkt_rsp, 9);
                    pkt_rsp[4] = 0xD0; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12

                    break;
                }
            }

            //Send packet to MPU
            bytesToHex(packetBuffer, pIdx, hexBuffer);
            Bridge.notify("pda_packet", hexBuffer);  
            printPacketRsp(Monitor, pkt_rsp, 9);

        }
    #endif
}

void send_Rsp_Pkt(const uint8_t* packet, size_t length) {
    // Safety check to prevent passing empty or malformed pointers
    if (packet == nullptr || length <= 0) return;
    
    // Forward the predefined buffer directly to your hardware writing engine
    rs485WriteRaw(packet, length);
    //printPacketRsp(Monitor, packet, length);
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
                if (validateChecksum(packetBuffer, pIdx)) {
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
    delay(3);
    Serial1.write(data, len);
    Serial1.flush();
    delay(3);
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

void control_input(String cmdStr){

    Monitor.print("Control Input: ");
    Monitor.println(cmdStr);

    // If command is recieved while porcessing then ignore input
    if(control_command == CMD_UNKNOWN){
        if (cmdStr == "pool_filter") control_command = CMD_POOL;
        if (cmdStr == "spa_on")      control_command = CMD_SPA;
        if (cmdStr == "all_off")     control_command = CMD_ALL_OFF;
    }else{Monitor.println("Control Input ignored. Still processing last input");}

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
    Bridge.provide("control_cmd", control_input);

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
            packetReady = false;
            pIdx = 0;
        }  
    }

    //check for incoming commands from UI
}



