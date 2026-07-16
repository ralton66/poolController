// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Arduino.h>
#include "src/utilities.h"
#include "src/pda_emul.h"

ActionListManager manager(Monitor);
uint8_t packetBuffer[MAX_PKT];
uint8_t highlighted_line = 0;
char hexBuffer[MAX_PKT * 2 + 1];
int pIdx = 0;
int state = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
int st = 0; // 0: Idle, 1: STX, 2: Data, 3: Escape/End
int cmd_seq = 0; // control command sequencing based on master responses
int delay_ctr = 0;
bool cmd_seq_delay = false;
bool packetReady = false;
bool pdaConnecting = false;
bool pdaSynced = false;
bool mainMenu = false;
unsigned long watchdog = millis();

int bidx = 0;
uint8_t pbuff[32000];

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

void set_main(bool s) {
    //Monitor.print("Main Menu: ");
    //Monitor.println(s);
    mainMenu = s;
}

void set_spa_temp(int temp) {
    Monitor.print("Spa Temp: ");
    Monitor.println(temp);
    if(temp>= 0 && temp <= 85){
        Monitor.println("Pool Temp: 0");
    }
    else if(temp>= 86 && temp <= 89){
        Monitor.println("Pool Temp: 1");
    }
    else if(temp>= 90){
        Monitor.println("Pool Temp: 2");
    }else
        Monitor.println("Pool Temp: Unknown");
}

void set_pool_temp(int temp) {
    Monitor.print("Pool Temp: ");
    Monitor.println(temp);
    
    if(temp>= 0 && temp <= 85){
        Monitor.println("Pool Temp: 0");
    }
    else if(temp>= 86 && temp <= 89){
        Monitor.println("Pool Temp: 1");
    }
    else if(temp>= 90){
        Monitor.println("Pool Temp: 2");
    }else{
        Monitor.println("Pool Temp: Unknown");
    }
}

void set_filter_rpm(int rpm) {
    Monitor.print("Pump RPM: ");
    Monitor.println(rpm);
    if(rpm>= 0 && rpm <= 2000){
        Monitor.println("Pool line 1");
    }else if (rpm>= 2001 && rpm <= 2300){
        Monitor.println("cleaner line 4");
    }else if(rpm>= 2301 && rpm <= 2999){
        Monitor.println("spa line 2");
    }else if(rpm>= 3000){
        Monitor.println("High spd line 3");
    }else{
        Monitor.println("speed7 line 7");
    }
}

void set_spa_state(bool s) {  
    //Monitor.print("Spa: ");
    //Monitor.println(s);
     // If command is recieved while porcessing then ignore input
    if((control_command == CMD_UNKNOWN)||(control_command == CMD_ALL_OFF) && s){
        control_command = CMD_SPA;
    }else{Monitor.println("Control Input ignored. Still processing last input");}
}

void set_pool_state(bool s) {
    //Monitor.print("Pool: ");
    //Monitor.println(s);
    // If command is recieved while porcessing then ignore input
    if((control_command == CMD_UNKNOWN)||(control_command == CMD_ALL_OFF) && s){
        control_command = CMD_POOL;
    }else{Monitor.println("Control Input ignored. Still processing last input");}
}

/**
 * Processes incoming bytes, steps the state machine, and orchestrates line responses.
 */
void handle_packet(const uint8_t* raw_bytes, uint8_t length) {
    
    if (raw_bytes == nullptr || length == 0) {
        return; 
    }
    
    if(control_command == CMD_PDA) { 
        printPacketBuffer(Monitor, raw_bytes, length);
        return;
    
    }else{

        // PDA destination Rx'ed
        //pkt_rsp[3] = 0x01; // response ACK
        if (raw_bytes[0] == 0x60) {
            if(raw_bytes[1] == 0x08)
                highlighted_line = raw_bytes[2];

            // Check Control Inputs and only push the button 
            // if the PDA is on the main menu and not busy processing a command
            if(manager.isBusy() && mainMenu) {
                //printPacketBuffer(Monitor, raw_bytes, length);
                manager.pushNextButton(Serial1, highlighted_line);
                return;
            }
                
            //Reply with simple keep alive for the first few packet acks
            if(pdaConnecting){
                rs485WriteRaw(Serial1, PKT_PDA_KA, sizeof(PKT_PDA_KA));
                //printPacketRsp(Monitor, PKT_PDA_KA, 9);
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
                    rs485WriteRaw(Serial1, PKT_PDA_KA, sizeof(PKT_PDA_KA));
                    //printPacketRsp(Monitor, PKT_PDA_KA, 9);
                    Monitor.println("-----CONNECTING-----");
                    break;
                case 0x02: // Keep Alive
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    break;
                case 0x04: // Long Message
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    //cmd_seq++;
                    break;
                case 0x08: // Highlight line
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    //Monitor.print("Line selected: ");
                    //Monitor.println(highlighted_line, HEX);
                    break;
                case 0x09: //Clear Screen
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    break;
                case 0x10: //Clear Screen
                // 1. Grab whatever token the master threw at us (0x00, 0x04, 0x0B, etc.)
                    pkt_rsp[4] = 0x54; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    pkt_rsp[4] = 0xD0; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                    break;
                case 0x1B: // Screen UI Layer Sync / Menu Token
                {
                    // 1. Grab whatever token the master threw at us (0x00, 0x04, 0x0B, etc.)
                    pkt_rsp[4] = 0xC0; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                    rs485WriteRaw(Serial1, pkt_rsp, 9);
                    pkt_rsp[4] = 0xD0; // Select Command
                    pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
                    break;
                }
                default:
                {
                    pdaConnecting = true;
                    rs485WriteRaw(Serial1, PKT_PDA_KA, sizeof(PKT_PDA_KA));
                    //printPacketRsp(Monitor, PKT_PDA_KA, 9);
                    //Monitor.println("-----default-----");
                    break;
                }
            }
            //Only print the long msgs
            if(raw_bytes[1] == 0x04){            
                printPacketBuffer(Monitor, raw_bytes, length);
                printPacketRsp(Monitor, pkt_rsp, 9);
            }

            //Send packet to MPU
            mainMenu = false;
            bytesToHex(packetBuffer, pIdx, hexBuffer);
            Bridge.notify("pda_packet", hexBuffer);  
            //delay(10);
        }
    }
}

void processByte(uint8_t c) {
    //Monitor.print(". ");
    //Monitor.print(c, HEX);
    //Monitor.print(". ");

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
                Monitor.print("--Failed STX--: ");
                Monitor.print("ESC: ");
                Monitor.println(c, HEX);
                printPacketBuffer(Monitor, packetBuffer, pIdx);
            }
            break;
        case 2: // Reading packet data, looking for ETX or escape
            if (c == 0x10) state = 3;
            else if (pIdx < MAX_PKT) packetBuffer[pIdx++] = c;
            else Monitor.println("---------MAX PACKET SIZE---------- ");
            break;
        case 3: // After escape character, determine if it's an escaped byte or end of packet
            if (c == 0x03) {
                if (validateChecksum(packetBuffer, pIdx)) packetReady = true; 
                else {
                    Monitor.println(" ");
                    Monitor.println("----Failed checksum----- ");
                    printPacketBuffer(Monitor, packetBuffer, pIdx);
                }
                state = 0;
            } else { // not really doing escapes Escaped 0x10 byte, add it to the buffer
                if (pIdx < MAX_PKT) packetBuffer[pIdx++] = 0x10;
                else {
                    Monitor.println("---------MAX PACKET SIZE---------- ");
                }
                state = 2;
            }
            break;
    }
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
        rs485WriteRaw(Serial1, buf, byteCount);
    }
}

void rs485_tx(String hex) {
    rs485SendHex(hex.c_str());
    Monitor.print("RS485 TX ");
    Monitor.println(hex);
}

void control_input(String cmdStr){

    Monitor.print("Control Input: ");
    Monitor.println(control_command);
    Monitor.print(" ");

    Monitor.println(cmdStr);

    // If command is recieved while porcessing then ignore input
    if(control_command == CMD_UNKNOWN){
        if (cmdStr == "pool_filter") control_command = CMD_POOL;
        if (cmdStr == "spa_on")      control_command = CMD_SPA;
        if (cmdStr == "all_off")     control_command = CMD_ALL_OFF;
        if (cmdStr == "pda")         control_command = CMD_PDA;
        if (cmdStr == "pool_lights") control_command = CMD_POOL_LIGHTS;
        if (cmdStr == "spa_lights")  control_command = CMD_SPA_LIGHT;
        if (cmdStr == "pool_heater") control_command = CMD_POOL_HEAT;
        if (cmdStr == "spa_heater")  control_command = CMD_SPA_HEAT;
        if (cmdStr == "jets")        control_command = CMD_JETS;

        manager.cmdRxed(control_command);
        if(control_command != CMD_PDA)
            control_command = CMD_UNKNOWN;
        else if(!pdaSynced)
            pdaSynced = false; // need to set this to true to enable fast dump

    }else if(control_command == CMD_PDA){

        if(bidx > 0) {
            st = 0;
            uint8_t c;
            Monitor.print("Buffer Data: ");
            for(int i = 0; i < bidx; i++){
                c = pbuff[i];

                // Print a leading zero if the byte is less than 16 (0x10)
                if (pbuff[i] < 16) 
                    Monitor.print("0");
                Monitor.print(pbuff[i], HEX);

                switch (st) {
                    case 0: // Idle state, waiting for STX
                        if (c == 0x10) st = 1;
                        break;
                    case 1: // Received STX, expecting start of packet
                        if (c == 0x02) st = 2;
                        else  st = 0;
                        break;
                    case 2: // Reading packet data, looking for ETX or escape
                        if (c == 0x10) st = 3;

                        break;
                    case 3: // After escape character, determine if it's an escaped byte or end of packet
                        if (c == 0x03) {
                            Monitor.println(" ");
                            st = 0;
                        } else st = 2;
                        break;
                }
            }
            Monitor.println();
            pdaSynced = false;
            bidx = 0;
        }
        control_command = CMD_UNKNOWN;

    }else{
        Monitor.println("Control Input ignored. Still processing last input");
    }
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
    Bridge.provide("set_main_menu", set_main);
    Bridge.provide("set_spa_state", set_spa_state);
    Bridge.provide("set_spa_temp", set_spa_temp);
    Bridge.provide("set_pool_temp", set_pool_temp);
    Bridge.provide("set_filter_rpm", set_filter_rpm);
    Bridge.provide("set_pool_state", set_pool_state);
    Bridge.provide("RS485_send", rs485_tx);
    Bridge.provide("control_cmd", control_input);
    
    delay(3000);
    Monitor.println("PoolController RS485 ready");
}

void loop() {
    // Very fast dump mode which dumps after PDA is turned off
    if(pdaSynced){
        if (Serial1.available() > 0)    
            pbuff[bidx++] = Serial1.read();
    }
    
    // Check if a byte has arrived from the RS-485 circuit
    else if (Serial1.available() > 0) {

        while (Serial1.available() && !packetReady) {
          processByte((uint8_t)Serial1.read());
        }

        // If a full packet has been received and validated, process it
        if (packetReady) {
            handle_packet(packetBuffer, pIdx);    
            packetReady = false;
            watchdog =  millis();
            pIdx = 0;
        }  
        
        if((watchdog + 400) < millis() ){
            Monitor.println("*******BITE*******");
             
            Monitor.print("[");
            Monitor.print(millis());
            Monitor.print("] buffer: ");
            printPacketBuffer(Monitor, packetBuffer, pIdx);

            pkt_rsp[4] = 0x54; //sync'ed/no keypress
            pkt_rsp[5] = 0x00; // no key 
            pkt_rsp[6] = 0x12 + 0x01 + pkt_rsp[4]; // Checksum includes the command and token, plus the fixed 0x12
            rs485WriteRaw(Serial1, pkt_rsp, 9); 
            printPacketBuffer(Monitor, pkt_rsp, 9);
            watchdog =  millis();
        }
    }
}



