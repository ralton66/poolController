# pool
ToDo

Add button to turn on AUX Pump.  May want to change the controlinterface on the pump itself so it just comes on when enabled.
Add capability to set rpm
Add other menus for rest off the pda tree - salt levels, boost, freeze protect, programs...



#Pool Equipment
Jandy Aquapure PLC1400
Filter S8M150
Jandy ePump JEP2.0
Hayward Heater
Valves




VSP1 SPD ADJ is line 3

POOL 1800
SPA    2750
HIGH SPEED  3450
CLEANER 2200
POOL HEAT
SPA HEAT


ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 arduino@192.168.5.129
sudo nmcli connection modify id mapleleaf1 802-11-wireless.powersave 2

git add .
git commit -m "Working web and cloud updates. sketch handle_packet in test mode though"
git push -u origin HEAD

 sudo  journalctl --vacuum-time=1s

 arduino-app-cli monitor

 arduino-app-cli app logs user:poolController --follow

arduino-app-cli app start poolController


[main]  Main Temperature Stream Complete! Parsing home view...
[main]   Line # 0x01 (001): 'AIR         POOL'
[main]   Line # 0x04 (004): 'POOL MODE     ON'
[main]   Line # 0x05 (005): 'POOL HEATER  OFF'
[main]   Line # 0x06 (006): 'SPA MODE     OFF'
[main]   Line # 0x07 (007): 'SPA HEATER   OFF'
[main]   Line # 0x08 (008): 'MENU'
[main]   Line # 0x09 (009): 'EQUIPMENT ON/OFF'
[main]   Line # 0x40 (064): 'FRI  9:34AM'
[main]   Line # 0x82 (130): '90F     83F'
[main] -----------------------------------------------
[main] 
[main] PoolMonitor: Pool mode is on, filter pump enabled.
[main] client->set main: True
[main] broadcast_state:  {'mode': 'pool', 'air_temp_f': 90, 'water_temp_f': 83, 'pool_setpoint_f': None, 'spa_setpoint_f': None, 'salt_ppm': 2900, 'swg_percent': 40, 'filter_rpm': 1800, 'filter_watts': 319, 'filter_pump_on': True, 'aux_pump_on': False, 'heater_on': False, 'pool_light_on': False, 'spa_light_on': False, 'spa': False, 'pool': True, 'valve': None, 'swg_status': None, 'undefined_state': False, 'last_error': None, 'connection_ok': True, 'last_update': 1784306204.5116532, 'last_packet': {'dest': '0x60', 'cmd': '0x04', 'text': '� 90`     83`', 'label': None, 'value': None, 'fields': {'cmd_name': 'MSG_LONG'}, 'checksum_ok': True, 'hex': '60048220393060202020202038336020202020CC'}, 'display': {'0x04': 'POOL MODE     ON', '0x05': 'POOL HEATER  OFF', '0x06': 'SPA MODE     OFF', '0x07': 'SPA HEATER   OFF', '0x08': 'MENU', '0x09': 'EQUIPMENT ON/OFF', '0x40': 'FRI  9:34AM', '0x01': 'AIR         POOL', '0x82': '90F     83F'}}
[main] 
[main]  Protocol 0x02 Terminator Frame Received! Processing equipment stats...
[main]   Line # 0x00 (000): 'EQUIPMENT STATUS'
[main]   Line # 0x02 (002): 'AQUAPURE 40%'
[main]   Line # 0x03 (003): 'SALT 2800 PPM'
[main]   Line # 0x04 (004): 'FILTER PUMP'
[main] -----------------------------------------------
[main] 
[main] broadcast_state:  {'mode': 'pool', 'air_temp_f': 90, 'water_temp_f': 83, 'pool_setpoint_f': None, 'spa_setpoint_f': None, 'salt_ppm': 2800, 'swg_percent': 40, 'filter_rpm': 1800, 'filter_watts': 319, 'filter_pump_on': True, 'aux_pump_on': False, 'heater_on': False, 'pool_light_on': False, 'spa_light_on': False, 'spa': False, 'pool': True, 'valve': None, 'swg_status': None, 'undefined_state': False, 'last_error': None, 'connection_ok': True, 'last_update': 1784306215.2369218, 'last_packet': {'dest': '0x60', 'cmd': '0x04', 'text': 'FILTER PUMP', 'label': 'FILTER', 'value': 'PUMP', 'fields': {'kind': 'filter', 'cmd_name': 'MSG_LONG'}, 'checksum_ok': True, 'hex': '600404202046494C5445522050554D5020202042'}, 'display': {'0x00': 'EQUIPMENT STATUS', '0x02': 'AQUAPURE 40%', '0x03': 'SALT 2800 PPM', '0x04': 'FILTER PUMP'}}
[main] 
[main]  Protocol 0x02 Terminator Frame Received! Processing equipment stats...
[main]   Line # 0x00 (000): 'EQUIPMENT STATUS'
[main]   Line # 0x02 (002): 'JANDY EPUMP   1'
[main]   Line # 0x03 (003): 'RPM: 1800'
[main]   Line # 0x04 (004): 'WATTS: 320'
[main] -----------------------------------------------
[ma




Method 2: Binding a Specific List of Button Elements
If you don't want to modify your HTML markup and prefer keeping button references inside an object (like your els object), you can loop over an array or map of chosen elements:



function bindControls() {
    // Map your chosen button elements to their command string
    const controlButtons = [
        { element: els.jetsBtn,      command: 'JETS' },
        { element: els.spaBtn,       command: 'SPA' },
        { element: els.poolLightBtn, command: 'POOL_LIGHT' },
        { element: els.heaterBtn,    command: 'HEATER' }
    ];

    // Attach the shared event emitter to each chosen element
    controlButtons.forEach(({ element, command }) => {
        if (element) {
            element.addEventListener('click', () => {
                socket.emit('control_cmd', { command: command });
            });
        }
    });
}


import logging

logger = logging.getLogger(__name__)

# Register a single handler for 'control_cmd'
@ui.on_message('control_cmd')  # Or socketio.on('control_cmd') depending on your framework
def handle_control_command(data):
    # 'data' will be a dict like {'command': 'SPA'}
    cmd_name = data.get('command')
    logger.info(f"[Bridge] Unified button callback triggered: {cmd_name}")

    # Pass the command string directly into your ActionListManager / PdaController logic!
    if cmd_name:
        action_manager.cmdRxed(cmd_name) # Or manager.StartSequence(cmd_name)


Benefits of this Pattern:
Zero Boilerplate: Adding a new button in the future only requires adding a data-command="AUX1" tag in HTML. No extra JavaScript socket emitters or Python socket handlers are needed!

Direct Enum Compatibility: The command string sent over the socket (e.g., 'SPA') directly matches your cmdRxed() / StartSequence() method parameters in Python.



from enum import IntFlag, auto

class Command(IntFlag):
    CMD_UNKNOWN     =




    from enum import IntFlag

class Command(IntFlag):
    CMD_UNKNOWN     = 0
    CMD_POOL        = 1 << 0
    CMD_POOL_HEAT   = 1 << 1
    CMD_POOL_LIGHTS = 1 << 2
    CMD_SPA         = 1 << 3
    CMD_SPA_HEAT    = 1 << 4
    CMD_SPA_LIGHT   = 1 << 5
    CMD_JETS        = 1 << 6
    CMD_PUMP_SPEED  = 1 << 7
    CMD_ALL_OFF     = 1 << 8
    CMD_PDA         = 1 << 9
    CMD_INSEQ       = 1 << 10

# Sending batched commands from Python:
# Command.CMD_SPA | Command.CMD_SPA_HEAT -> Sends integer 24 (0x0018) across the socket


from enum import IntFlag

class Command(IntFlag):
    # Override __new__ to unpack (bitmask_value, string_identifier)
    def __new__(cls, value: int, string_code: str = ""):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.string_code = string_code
        return obj

    # Bitmask Definition         # String Identifier (from CommandType)
    UNKNOWN        = 0,          "unknown"
    POOL           = 1 << 0,     "pool_filter"
    POOL_HEAT      = 1 << 1,     "pool_heater"
    POOL_LIGHTS    = 1 << 2,     "pool_lights"
    SPA            = 1 << 3,     "spa_on"
    SPA_HEAT       = 1 << 4,     "spa_heater"
    SPA_LIGHTS     = 1 << 5,     "spa_lights"
    JETS           = 1 << 6,     "jets"
    PUMP_SPEED     = 1 << 7,     "pump_speed"
    ALL_OFF        = 1 << 8,     "all_off"
    PDA            = 1 << 9,     "pda"
    INSEQ          = 1 << 10,    "inseq"
    
    # Non-hardware action commands (assigned high bitmask positions)
    RESET          = 1 << 11,    "reset"
    STATUS_POLL    = 1 << 12,    "status_poll"

    @classmethod
    def from_string(cls, str_code: str) -> "Command":
        """Factory method: Look up enum member from Web/API string name."""
        str_lower = str_code.lower()
        for member in cls:
            if member.string_code == str_lower:
                return member
        return cls.UNKNOWN