#include <Arduino.h>
#include "utilities.h"
#include "pda_emul.h"


bool ActionList::AddAction(uint8_t btnId, uint8_t pushes, uint8_t delay_cycles) {
    if (count >= MAX_ACTIONS) {
        return false;
    }
    actions[count++] = { btnId, pushes, delay_cycles };
    Logger.infof("  Action added -> btnId: %d, pushes: %d, delay: %d", btnId, pushes, delay_cycles);
    return true;
}

bool ActionList::ResetAction() {
    for(uint8_t j=0; j < count; j++){
        actions[j].btnId = 0;
        actions[j].num_pushes = 0;
        actions[j].delay_cycles = 0;
    }
    count = 0;
    return true;
}

bool ActionList::UpdateAction(uint8_t index, uint8_t btnId, uint8_t pushes) {
    if (index >= count) { return false; }
    actions[index].btnId = btnId;
    actions[index].num_pushes = pushes;
    return true;
}


ActionListManager::ActionListManager(Stream& mon) : monitor(mon) {
    activeCmd = false;
    currActionIndex = 0;
    pushed = 0;
    cmd_seq_delay = false;
    delay_ctr = 0;
    delay_cycles = 5;
    pumpSpdSelect = 1;
    poolLights = false;
    spaLights = false;
    poolHeat = false;
    spaHeat = false;
}

bool ActionListManager::cmdRxed(uint16_t cmdMask) {
    Logger.debugf("ActionListManager::cmdRxed Mask: 0x%04X", cmdMask);

    if (cmdMask == CMD_UNKNOWN) return false;

    bool handledAny = false;

    for (uint8_t i = 0; i < sizeof(cmdList) / sizeof(cmdList[0]); i++) {
        
        // Check if this command's bit flag is set in the incoming mask
        if (cmdList[i].name != CMD_UNKNOWN && (cmdMask & cmdList[i].name)) {
            
           Logger.infof("Matched Command Bit: 0x%04X at index %d", cmdList[i].name, i);
            
            // Handle PDA status flag
            if (cmdList[i].name == CMD_PDA) {
                Logger.debug("CMD_PDA received.");
                if (cmdMask == CMD_PDA) return false; // Return false if PDA was the sole flag
                continue;
            }

            // Track starting action index for this specific command entry
            uint8_t baseActionIdx = list.count; // Or index tracking total added actions

            // Add actions to the queue
            for (uint8_t j = 0; j < cmdList[i].count; j++) {
                list.AddAction(
                    cmdList[i].actions[j].btnId, 
                    cmdList[i].actions[j].num_pushes, 
                    cmdList[i].actions[j].delay_cycles
                );
                
                uint8_t currentIdx = baseActionIdx + j;
                
            }
                
            // Handle Pool Lights toggle
            if (cmdList[i].name == CMD_POOL_LIGHTS) {
                uint8_t selectIdx = baseActionIdx + 3; // Index of select push for this command
                
                if (poolLights) {
                    list.actions[selectIdx].num_pushes = 1; // select only once if on->off
                    poolLights = false;
                } else {
                    list.actions[selectIdx].num_pushes = 2; // select twice if off->on
                    poolLights = true;
                }
                Logger.infof("Pool Lights state -> %s (pushes: %d)", 
                    poolLights ? "ON" : "OFF", 
                    list.actions[selectIdx].num_pushes
                );
            }   

            // Handle Spa Lights toggle
            if (cmdList[i].name == CMD_SPA_LIGHT) {
                uint8_t selectIdx = baseActionIdx + 3; // Index of select push for this command

                if (spaLights) {
                    list.actions[selectIdx].num_pushes = 1; // select only once if on->off
                    spaLights = false;
                } else {
                    list.actions[selectIdx].num_pushes = 2; // select twice if off->on
                    spaLights = true;
                }
                Logger.infof("Spa Lights state -> %s (pushes: %d)", 
                    spaLights ? "ON" : "OFF", 
                    list.actions[selectIdx].num_pushes
                );
            }

            // Handle Pool Heater toggle
            if (cmdList[i].name == CMD_POOL_HEAT) 
                poolHeat = !poolHeat;

            if (cmdList[i].name == CMD_SPA_HEAT) 
                spaHeat = !spaHeat;

                
            if (cmdList[i].name == CMD_PUMP_SPEED) {
                Logger.infof("Pump Speed Action queued (Selection: %d)", pumpSpdSelect);
                if (pumpSpdSelect > 0) {
                    list.AddAction(5, pumpSpdSelect, 15);
                }
                list.AddAction(4, 5, 15);                
            }
            handledAny = true;
        }
    }

    if (handledAny) {
        activeCmd = true;
        return true;
    }
    return false;
}

bool ActionListManager::pushNextButton(Stream& serial1, uint8_t line){
    
    if(activeCmd == false)
        return false;

    // This is used to delay next KEY command for a few cycles to ensure the last KEY command is
    // recieved and acted on before proceeding
    if (cmd_seq_delay){
        rs485WriteRaw(serial1, PKT_PDA_ACKNK, 9);
        delay_ctr++;
        if(delay_ctr >= delay_cycles){
            delay_ctr = 0;
            delay_cycles = 5;
            cmd_seq_delay = false;
        }
        return true;
    }

    if(currActionIndex >= list.count){
        if(line != 4){ // If not on the main menu, send a BACK command to return to the main menu
            rs485WriteRaw(serial1, PKT_PDA_BACK, 9);
            Logger.debug("Not home yet");
            return true;
        }

        activeCmd = false;
        currActionIndex = 0;
        list.ResetAction();        
        Logger.info("::::::CMD DONE::::::");
        return false;
    }

    ButtonAction& action = list.actions[currActionIndex];
    
    switch(action.btnId){
        case 4: // SELECT
            rs485WriteRaw(serial1, PKT_PDA_SELECT, 9);
            break;
        case 5: // DOWN
            rs485WriteRaw(serial1, PKT_PDA_DOWN, 9);
            break;
        case 2: // BACK
            rs485WriteRaw(serial1, PKT_PDA_BACK, 9);
            break;
        case 6: // UP
            rs485WriteRaw(serial1, PKT_PDA_UP, 9);
            break;
    }

    cmd_seq_delay = true;
    delay_cycles = action.delay_cycles;
    Logger.debugf("Action [%d] -> btnId: %d, pushes: %d", currActionIndex, action.btnId, action.num_pushes);

    pushed++;
    if(pushed >= action.num_pushes){
        currActionIndex++;
        pushed = 0;
    }
    return true;
}

void ActionListManager::tempBtnDir(int btn){

    list.ResetAction();      
    list.AddAction(btn, 1, 5);
    list.AddAction(4, 1, 5); // press select
    currActionIndex = 0;
}

void ActionListManager::pumpSpdLine(uint8_t line){
    pumpSpdSelect = line - 1;
    Logger.debugf("Pump Speed Action queued (Selection: %d)", pumpSpdSelect);
}