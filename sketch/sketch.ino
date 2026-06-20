// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include "src/utilities.h"


uint8_t packetBuffer[MAX_PKT];
char hexBuffer[MAX_PKT * 2 + 1];
int pIdx = 0;
int state = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
int cmd_seq = 0; // control command sequencing based on master responses
bool packetReady = false;
bool pdaConnected = false;

enum Command {
    CMD_UNKNOWN,
    CMD_POOL,
    CMD_POOL_HTR,
    CMD_POOL_LIGHT,
    CMD_SPA,
    CMD_SPA_HTR,
    CMD_SPA_LIGHT,
    CMD_ALL_OFF
};

Command control_command = CMD_UNKNOWN;

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
    uint8_t contextChecksum = 0;
    uint8_t pkt_select[9];

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
        if (raw_bytes[0] == 0x60) {
            //if(raw_bytes[2] == 0x00)
            //    ack_ptr = PKT_PDA_ACK_SHORT;
            //else
            //    ack_ptr = PKT_PDA_ACK;
                    // 1. Grab whatever token the master threw at us (0x00, 0x04, 0x0B, etc.)
             
            if(raw_bytes[2] == 0x00)
                token = 0xD0;
            else
                token = 0x50;
            contextChecksum = 0x12 + 0x01 + token; // Checksum includes the command and token, plus the fixed 0x12
            uint8_t pkt_rsp[] = { 
                0x10, 0x02,         // STX
                0x00,               // Destination (Master)
                0x01,               // Command (Context ACK)
                token,              // The Echoed Token (Dynamically scales to 0x00 or any value)
                0x00,               // Padding
                contextChecksum,    // Calculated Checksum (Will be 0x2C when token is 0x00)
                0x10, 0x03          // ETX
            };

            //Check Control Inputs
            if(control_command != CMD_UNKNOWN)
            {
                switch(control_command){
                    case CMD_POOL: {
                        contextChecksum = 0x12 + 0x01 + 0x04 + token; // Checksum includes the command and token, plus the fixed 0x12
                        // Assign the index positions explicitly
                        pkt_select[0] = 0x10; // STX
                        pkt_select[1] = 0x02; // STX
                        pkt_select[2] = 0x00; // Destination
                        pkt_select[3] = 0x01; // Command
                        pkt_select[4] = token; 
                        pkt_select[5] = 0x04; // Select Command
                        pkt_select[6] = contextChecksum;
                        pkt_select[7] = 0x10; // ETX
                        pkt_select[8] = 0x03; // ETX

                        rs485WriteRaw(pkt_select, 9);
                        printPacketRsp(Monitor, pkt_select, 9);

                        rsp_len = 9;
                        rsp_ptr = pkt_select;
                        //Monitor.print("CMD_POOL: send select");
                        //Monitor.println(control_command);
                        control_command = CMD_UNKNOWN;
                        break;
                    }
                    default:
                        control_command = CMD_UNKNOWN;
                        break;
                }
                return;
            }


            switch (raw_bytes[1]){
                case 0x00: // Initial Connect
                    pdaConnected = true;
                    delay(15);
                    rsp_len = sizeof(pkt_rsp);
                    rs485WriteRaw(pkt_rsp, rsp_len);
                    rsp_ptr = pkt_rsp;
                    break;
                case 0x02: // Keep Alive
                    rsp_len = sizeof(pkt_rsp);
                    rs485WriteRaw(pkt_rsp, rsp_len);
                    rsp_ptr = pkt_rsp;
                    break;
                case 0x04: // Long Message
                    rsp_len = sizeof(pkt_rsp);
                    rs485WriteRaw(pkt_rsp, rsp_len);
                    rsp_ptr = pkt_rsp;
                    break;
                case 0x08: // Highlight line
                    rsp_len = sizeof(pkt_rsp);
                    rs485WriteRaw(pkt_rsp, rsp_len);
                    rsp_ptr = pkt_rsp;
                    break;
                case 0x09: //Clear Screen
                    rsp_len = sizeof(pkt_rsp);
                    rs485WriteRaw(pkt_rsp, rsp_len);
                    rsp_ptr = pkt_rsp;
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
                    rsp_len = sizeof(PKT_PDA_CS);
                    rs485WriteRaw(PKT_PDA_CS, rsp_len);
                    rsp_ptr = PKT_PDA_CS;
                    break;
                }
            }


            //Send packet to MPU
            bytesToHex(packetBuffer, pIdx, hexBuffer);
            Bridge.notify("pda_packet", hexBuffer);  
            printPacketRsp(Monitor, rsp_ptr, rsp_len);

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



