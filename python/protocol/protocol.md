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
            
 The layout of the 0x01 ACK response frame.
 The explicit bit-level specification for **Byte 2** (including Bit 7, Bit 6, and Bit 4 flags).
 A matrix comparing standard working hex values (0xC0, 0xD0, 0x50) against anomalous states (0xA9, 0x54, 0xAD).
 Boundary-safe **C/C++ code snippets** implementing the bitmasking patterns and hexadecimal formatting for Arduino debugging logs.

# Jandy AquaLink PDA Serial Protocol Specification
## Target Firmware: PDA 7.1.0 / JBox 4.0

This document outlines the frame layout, bitfield specifications, and implementation guidelines for emulating or 
parsing a Jandy AquaLink PDA wireless transceiver via an RS485 serial bus interface (9600 Baud, 8N1).

---

## 1. Frame Structure: Master Response (CMD 0x01)

When the wireless PDA or JBox transceiver responds to a poll cycle from the master controller (0x00), 
it transmits an acknowledgment/status packet using command 0x01. 

A standard un-escaped packet payload follows this sequence:

| Byte Index | Field Name | Typical Values | Description |
| :--- | :--- | :--- | :--- |
| **Byte 0** | Destination Address | Always 0x00 (Master Controller) |
| **Byte 1** | Command Code | 0x01 | CMD_ACK / Status / Keypress payload announcement |
| **Byte 2** | Status Bit Field | 0xC0, 0xD0, 0x50, x040, 0x00 | Device state, sync status, identity, and data flags |
| **Byte 3** | Keypress Payload | 0x00, [Key Code] | Key code identifier; ignored if Byte 2 Bit 4 is clear |
| **Byte 4** | Checksum | 0xXX | Modulo 256 sum of framing offsets and payload bytes 

*Note: In the full network layer, these bytes are wrapped inside Link Layer framing characters 
(typically preceded by DLE STX and terminated with DLE ETX). 
Any checksum calculations must account for the specific network driver framing implementation.*

---

## 2. Byte 2: Status Bit Field Specification

Byte 2 acts as a control bitmask that defines the operational mode of the handset device. 
Modifying individual bits completely alters how the master controller routes display information.

### Bit-Level Mapping

| Bit | Hex Mask | Definition | Description |
| :--- | :--- | :--- | :--- |
| **Bit 7** | 0x80 | **Session Sync / Power State** | 0 = Wake-up / Handshake phase (un-synchronized)<br> 1 = Active session / Fully synchronized |
| **Bit 6** | 0x40 | **PDA Device Identifier** | **Must be 1** for PDA transceivers. Setting to 0 forces the controller to interpret the device as a standard hardwired keypad (AllButton/OneTouch). |
| **Bit 5** | 0x20 | *Reserved* | Always 0 |
| **Bit 4** | 0x10 | **Keypress Data Flag** | 0 = Idle heartbeat (Byte 3 is null/ignored)<br> 1 = Keypress active (Master must process code in Byte 3) |
| **Bits 3–0** | 0x0F | **Device Profile Layout** | Defines model configuration variants. Typically 0x0 for active PDA loops. |

---

## 3. Reference Values & State Matrix

### Standard Operational Values

* **0xC0 (1100 0000) — Connected Idle ACK**
    * *Status:* Online, fully synchronized session, active PDA identity, no buttons pressed. 
    * *Usage:* Standard background heartbeat response when the user is reading the menu screen.
* **0xD0 (1101 0000) — Connected Keypress ACK**
    * *Status:* Online, synchronized, active PDA identity, **with an active button event**.
    * *Usage:* Tells the master panel to parse and execute the specific raw key code sent in Byte 3.
* **0x50 (0101 0000) — Wake-up Handshake**
    * *Status:* Un-synchronized session, active PDA identity, active key flag.
    * *Usage:* Sent immediately upon a hardware wake event from deep sleep. 
    Prompts the master controller to flush previous states 
    and re-transmit the current menu tree structure.
* **0x40 (0100 0000) — Wake-up Handshake**
    * *Status:* Un-synchronized session, active PDA identity, no key flag.
    

### Non-Standard / Anomalous Values (Warning Matrix)

*
* **0x54 (0101 0100)**
    * *Result:* **State Machine Stall.** 
    Asserts an un-synchronized state (Bit 7 = 0) while simultaneously asserting a keypress event (Bit 4 = 1) without providing a valid key layout mapping in the lower nibble. This causes processing lag or freeze-exceptions on JBox 4.0 master modules.

---
Here is the additional technical specification content designed to complement your project file. It covers the downstream communications from the master controller to the PDA, detailing the framing structure, target addressing, core command codes, and an interactive breakdown of the 0x02 payload states you observed.

---

## 5. Master-to-PDA Packet Formatting

Downstream transmissions originate from the master controller (0x00) and target wireless transceivers connected to the JBox bus loop. Packets are wrapped in Data Link Escape (DL`) boundaries to ensure frame parsing integrity across long wire lines.

### Master Wire-Layer Frame Architecture

```text
 [DLE] [STX] [ DEST ] [ CMD ] [   DATA PAYLOAD...   ] [ CHKSUM ] [DLE] [ETX]
 0x10  0x02    0x60    0x02     0x28 0x00 0x00 0x00 0x00    0x9C    0x10  0x03

```

### Downstream Addressing Space

The AquaLink RS architecture reserves an exclusive 4-channel multi-drop ID block specifically for handheld wireless PDA (AquaPalm) devices:

| Hex ID | Decimal ID | Target Wireless Channel Node |
| --- | --- | --- |
| **0x60** | `96` | Handset Node 1 (Primary / Default Base Address) |
| **0x61** | `97` | Handset Node 2 |
| **0x62** | `98` | Handset Node 3 |
| **0x63** | `99` | Handset Node 4 |

---

## 6. Downstream Command Set Specification

When addressing the 0x60–0x63 block, the master controller boundaries restrict transactions to five primary functional command routines:

### 0x00 — CMD_PROBE (Bus Polling)

* **Direction:** Master -> PDA
* **Payload Length:** 0 Bytes
* **Purpose:** Heartbeat polling sequence. Used by the controller to discover if a newly powered-on transceiver is online or to verify that an active session hasn't experienced a physical connection timeout.

### 0x01 — Display sync????

* **Direction:** Master -> PDA (Bidirectional)
* **Payload Length:** Typically 5 Bytes
* **Purpose:** Uknown but requires a keep alive ack


### 0x02 — CMD_STATUS (System State & LED Masking)

* **Direction:** Master -> PDA (Bidirectional)
* **Payload Length:** Typically 5 Bytes
* **Purpose:** Drives the underlying system operation state, sub-menu hierarchies, and execution cycles. This command tells the PDA how to orient its input processing loops.

### 0x03 — CMD_MSG (Standard 16-Byte Text Array)

* **Direction:** Master -> PDA
* **Payload Length:** Variable (Typically up to 16 characters)
* **Purpose:** Streams alphanumeric text arrays down to the device screen. Used for rendering quick status strings, line-by-line item rendering, and simple data parameters.

### 0x04 — CMD_MSG_LONG (Extended Layout / Text Frame Buffer)

* **Direction:** Master -> PDA
* **Payload Length:** Extended Array (Up to 128 Bytes)
* **Purpose:** Streams multi-line text structures, menu lists, and custom symbols. In the PDA 7.1.0 generation, this command serves to bulk-update screen content caches when scrollable navigation frameworks are initialized.

---

## 7. Deep-Dive: Decoding the 0x02 (CMD_STATUS) Payload

Based on wire logs captured from physical hardware, the 0x02 command passes a fixed **5-byte payload data block** immediately trailing the CMD byte.

### Core Payload Byte Map

```text
Byte Index:   [ Data 0 ]  [ Data 1 ]  [ Data 2 ]  [ Data 3 ]  [ Data 4 ]
Field Group:  State Mask   Ext-Flag 1  Ext-Flag 2  Reserved 1  Reserved 2

```

The master communicates vital structural execution instructions through **Data 0** (the first byte following the 0x02 command).

#### Capture Case 1: 60 02 28 00 00 00 00 9C

* **Data 0 State:** 0x28(0010 1000)
* **Interpretation:** **Auxiliary System Loop / Relay Execution Active.** This tells the PDA that primary system equipment flags (such as the main filter pump, spa circuits, or specific auxiliary accessories) are currently energized or navigating a sub-menu thread. The PDA uses this state to maintain active operational display rendering.

Bit Position:  Bit 7   Bit 6   Bit 5   Bit 4   Bit 3   Bit 2   Bit 1   Bit 0
Hex Mask:       0x80    0x40    0x20    0x10    0x08    0x04    0x02    0x01
-----------------------------------------------------------------------------
0x28 Payload:    0       0       1       0       1       0       0       0
0x32 Payload:    0       0       1       1       0       0       1       0
#### Capture Case 2: 60 02 00 00 00 00 00 74

* **Data 0 State:** 0x00 (0000 0000)
* **Interpretation:** **System Idle Heartbeat.** The controller is operating in a standard baseline maintenance state with no pending layout updates or pending circuit changes. It acts as a passive polling anchor.

#### Capture Case 3: 60 02 FF 00 00 00 00 73

* **Data 0 State:** 0xff (1111 1111)
* **Interpretation:** **Global Device Reset / Synchronization Clear.** Broadcasted by the master panel during initialization or following a dropped communication line. It commands the PDA transceiver to dump all active menu indexing, clear screen buffers, and step back into a low-level initialization handshake loop.

---
In the AquaLink RS4 / PS4 firmware mapping schema for standard keypads and display drivers, the lower bits map directly to the primary hardware relays and heating loops. For a 4-function system (Filter Pump, Spa, Aux 1, Aux 2), the map correlates to this configuration:

Bit 0 (0x01): Filter Pump Relay

Bit 1 (0x02): Spa Mode Relay (Actuates the intake/return valve combinations)

Bit 2 (0x04): Auxiliary 1 Relay

Bit 3 (0x08): Auxiliary 2 Relay

Bit 4 (0x10): Pool/Spa Heater State (Heater call for heat / firing state)