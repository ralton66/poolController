#ifndef PDA_EMUL_H
#define PDA_EMUL_H

#include <Arduino.h>
#include "utilities.h"


constexpr int MAX_ACTIONS = 64;
constexpr int MAX_LISTS = 16;

struct ButtonAction{
    uint8_t btnId;
    uint8_t num_pushes;
    uint8_t delay_cycles; // Number of cycles to wait before next action
};

// Container for an operational sequence list
class ActionList {
public:
    Command name;
    ButtonAction actions[MAX_ACTIONS];
    uint8_t count;

    ActionList() : name(CMD_UNKNOWN), count(0) {};
    bool AddAction(uint8_t btnId, uint8_t pushes, uint8_t delay_cycles);
    bool ResetAction();
    bool UpdateAction(uint8_t index, uint8_t btnId, uint8_t pushes);
};

// Layout specification mapping for initialization configurations
struct ListDefinition {
    Command name;
    ButtonAction actions[MAX_ACTIONS];
    uint8_t count;
    uint8_t delay_cycles; 
};


// Inline declaration prevents cross-tab compilation duplication errors
const ListDefinition cmdList[] = {
    {
        CMD_POOL,
        { {4, 1, 4} },
        1
    },
    {
        CMD_SPA,
        {
            {5, 2, 4}, // Press DOWN twice for SPA
            {4, 1, 15}, // Press SELECT once
            {5, 1, 4}, // Press DOWN once For HEAT
            {4, 4, 15}, // Press SELECT four times select default heat
            {2, 1, 10}  // Press BACK/MENU once to clear screen
        },
        2
    },
    {
        CMD_POOL_LIGHTS,
        {
            {5, 5, 4}, // Press DOWN five times
            {4, 1, 15}, // Press SELECT once
            {5, 5, 4}, // Press DOWN once
            {4, 2, 15}, // Press SELECT four times
            {2, 1, 20}  // Press BACK/MENU once to clear screen
        },
        5
    },
    {
        CMD_SPA_LIGHT,
        {
            {5, 5, 4}, // Press DOWN five times
            {4, 1, 15}, // Press SELECT once
            {5, 6, 4}, // Press DOWN six times
            {4, 2, 15}, // Press SELECT four times
            {2, 1, 20}  // Press BACK/MENU once to clear screen
        },
        5
    },
    {
        CMD_SPA_HEAT,
        {
            {5, 3, 4}, // Press DOWN 3 times For HEAT
            {4, 2, 15}, // Press SELECT twice times select default heat
            {2, 1, 10}  // Press BACK/MENU once to clear screen
        },
        3
    },
    {
        CMD_POOL_HEAT,
        {
            {5, 1, 4}, // Press DOWN 1 time For HEAT
            {4, 2, 15}, // Press SELECT twice times select default heat
            {2, 1, 10}  // Press BACK/MENU once to clear screen
        },
        3
    },
    {
        CMD_JETS,
        {
            {5, 5, 4}, // Press DOWN five times
            {4, 1, 15}, // Press SELECT once
            {5, 7, 4}, // Press DOWN seven times
            {4, 1, 5}, // Press SELECT twice times
            {2, 2, 10}  // Press BACK/MENU once to clear screen
        },
        5
    },
    {
        CMD_ALL_OFF,
        {
            {5, 5, 4}, // Press DOWN five times
            {4, 1, 15}, // Press SELECT once
            {5, 8, 4}, // Press DOWN eight times
            {4, 2, 5}, // Press SELECT twice times
            {2, 2, 10}  // Press BACK/MENU once to clear screen
        },
        5
    }
};

// Central Manager Class tracking menu states and injection sequencing
class ActionListManager {
private:
    ActionList list;
    bool activeCmd;
    uint8_t currActionIndex;
    uint8_t pushed;
    Stream& monitor; 
    bool cmd_seq_delay;
    uint8_t delay_ctr;
    uint8_t delay_cycles;
    bool poolLights;
    bool spaLights;
    bool poolHeat;
    bool spaHeat;

public:
    ActionListManager(Stream& monitor);
    bool cmdRxed(Command name);
    bool pushNextButton(Stream& serial1, uint8_t line);

    // Helper to check if a macro sequence is actively running
    bool isBusy() const { 
        return (activeCmd); 
    }
    
};

#endif // PDA_EMUL_H
