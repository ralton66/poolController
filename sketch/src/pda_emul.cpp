#include <Arduino.h>
#include "utilities.h"
#include "pda_emul.h"


bool ActionList::AddAction(uint8_t btnId, uint8_t pushes, uint8_t delay_cycles) {
    if (count >= MAX_ACTIONS) {
        return false;
    }
    actions[count++] = { btnId, pushes, delay_cycles };
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
    poolLights = false;
    spaLights = false;
    poolHeat = false;
    spaHeat = false;
}

bool ActionListManager::cmdRxed(Command name){
    monitor.print("ActionListManager::cmdRxed: ");
    for(uint8_t i=0; i < sizeof(cmdList)/sizeof(cmdList[0]); i++){
    
        if(cmdList[i].name == name){
            monitor.println(' ');
            monitor.print("Name: ");
            monitor.print(name);
            monitor.print("index: ");
            monitor.println(i);
            
            if (name == CMD_PDA){
                monitor.println("CMD_PDA received.");
                return false;
            }

            for(uint8_t j=0; j < cmdList[i].count; j++){
                list.AddAction(cmdList[i].actions[j].btnId, cmdList[i].actions[j].num_pushes, cmdList[i].actions[j].delay_cycles);
                monitor.print(list.actions[j].btnId);
                monitor.print(',');
                monitor.println(list.actions[j].num_pushes);
            }
                
            if (name == CMD_POOL_LIGHTS){
                monitor.print("PL: ");
                monitor.println(poolLights);

                if(poolLights){
                    list.actions[3].num_pushes = 1; // select only once if on->off
                    poolLights = false;
                    monitor.print(list.actions[3].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[3].num_pushes);
                }else{
                    list.actions[3].num_pushes = 2; // select twice if off->on
                    poolLights = true;
                    monitor.print(list.actions[3].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[3].num_pushes);
                }

            }   
            if (name == CMD_SPA_LIGHT){
                monitor.print("PL: ");
                monitor.println(spaLights);

                if(spaLights){
                    list.actions[3].num_pushes = 1; // select only once if on->off
                    spaLights = false;
                    monitor.print(list.actions[3].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[3].num_pushes);
                }else{
                    list.actions[3].num_pushes = 2; // select twice if off->on
                    spaLights = true;
                    monitor.print(list.actions[3].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[3].num_pushes);
                }
            }

            if (name == CMD_POOL_HEAT){
                monitor.print("PL: ");
                monitor.println(poolHeat);

                if(poolHeat){
                    list.actions[1].num_pushes = 1; // select only once if on->off
                    poolHeat = false;
                    monitor.print(list.actions[1].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[1].num_pushes);
                }else{
                    list.actions[1].num_pushes = 2; // select twice if off->on
                    poolHeat = true;
                    monitor.print(list.actions[1].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[1].num_pushes);
                }
            }

            if (name == CMD_SPA_HEAT){
                monitor.print("PL: ");
                monitor.println(spaHeat);

                if(spaHeat){
                    list.actions[1].num_pushes = 1; // select only once if on->off
                    spaHeat = false;
                    monitor.print(list.actions[1].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[1].num_pushes);
                }else{
                    list.actions[1].num_pushes = 2; // select twice if off->on
                    spaHeat = true;
                    monitor.print(list.actions[1].btnId);
                    monitor.print(',');
                    monitor.println(list.actions[1].num_pushes);
                }
            }
            
            if (name == CMD_SPA_HEAT){
                poolHeat = false;
                spaHeat = false;
                poolLights = false;
                spaLights = false;
            }

            activeCmd = true;
            return true;
        }
    }
    return false;
}

bool ActionListManager::pushNextButton(Stream& serial1, uint8_t line){
    
    if(activeCmd == false)
        return false;

    //monitor.print("line: ");
    //monitor.println(line);
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
        //monitor.println("tick");
        return true;
    }

    if(currActionIndex >= list.count){
        if(line != 4){ // If not on the main menu, send a BACK command to return to the main menu
            rs485WriteRaw(serial1, PKT_PDA_BACK, 9);
            //monitor.print("line: ");
            //monitor.print(line);
            //monitor.println("send PKT_PDA_BACK ");
            return true;
        }

        activeCmd = false;
        currActionIndex = 0;
        list.ResetAction();        
        monitor.println("::::::CMD DONE::::::");
        return false;
    }

    ButtonAction& action = list.actions[currActionIndex];
    
    switch(action.btnId){
        case 4: // SELECT
            rs485WriteRaw(serial1, PKT_PDA_SELECT, 9);
            //monitor.print("SELECT ");
            break;
        case 5: // DOWN
            rs485WriteRaw(serial1, PKT_PDA_DOWN, 9);
            //monitor.print("DOWN ");
            break;
        case 2: // BACK
            rs485WriteRaw(serial1, PKT_PDA_BACK, 9);
            //monitor.print("BACK ");
            break;
        case 6: // UP
            rs485WriteRaw(serial1, PKT_PDA_UP, 9);
            //monitor.print("UP ");
            break;
    }

    cmd_seq_delay = true;
    delay_cycles = action.delay_cycles;
    //monitor.print(currActionIndex);
    //monitor.print(',');
    //monitor.print(action.btnId);
    //monitor.print(',');
    //monitor.println(action.num_pushes);

    pushed++;
    if(pushed >= action.num_pushes){
        currActionIndex++;
        pushed = 0;
    }
    return true;
}

