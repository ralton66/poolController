// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

const socket = io(`http://${window.location.host}`);

const els = {
    connectionText: document.getElementById('connection-text'),
    mode: document.getElementById('mode'),
    airTemp: document.getElementById('air-temp'),
    waterTemp: document.getElementById('water-temp'),
    filterPumpOn: document.getElementById('filter-pump-on'),
    auxState: document.getElementById('aux-state'),
    heaterState: document.getElementById('heater-state'),
    poolLightState: document.getElementById('pool-light-state'),
    spaLightState: document.getElementById('spa-light-state'),
    swgPercent: document.getElementById('swg-percent'),
    saltPpm: document.getElementById('salt-ppm'),
    filterRpm: document.getElementById('filter-rpm'),
    filterWatts: document.getElementById('filter-watts'),
    spaTempInput: document.getElementById('spa-temp-input'),
    poolTempInput: document.getElementById('pool-temp-input'),
    filterRpmInput: document.getElementById('filter-rpm-input'),
    spaOnBtn: document.getElementById('spa-on-btn'),
    spaHeaterBtn: document.getElementById('spa-heater-btn'),
    poolHeaterBtn: document.getElementById('pool-heater-btn'),
    filterOnBtn: document.getElementById('filter-on-btn'),
    spaLightsBtn: document.getElementById('spa-lights-btn'),
    poolLightsBtn: document.getElementById('pool-lights-btn'),
    jetsBtn: document.getElementById('jets-btn'),
    allOffBtn: document.getElementById('all-off-btn'),
    pdaBtn:  document.getElementById('pda-btn'),
    debugPanel: document.getElementById('debug-panel'),
    protocolOutput: document.getElementById('protocolOutput'),
    errorContainer: document.getElementById('error-container'),
};

document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();
    bindControls();
    if (new URLSearchParams(window.location.search).has('debug')) {
        els.debugPanel.style.display = 'block';
    }
});

function bindControls() {
     
    els.filterOnBtn.addEventListener('click', ()    => socket.emit('set_filter', {}));
    els.spaOnBtn.addEventListener('click', ()       => socket.emit('set_spa', {}));
    els.spaOnBtn.addEventListener('click', ()       => socket.emit('set_spa', {}));
    els.spaHeaterBtn.addEventListener('click', ()   => socket.emit('set_spa_heater', {}));
    els.poolHeaterBtn.addEventListener('click', () => socket.emit('set_pool_heater', {}));
    els.poolLightsBtn.addEventListener('click', ()  => socket.emit('set_pool_lights', {}));
    els.spaLightsBtn.addEventListener('click', ()   => socket.emit('set_spa_lights', {}));
    els.jetsBtn.addEventListener('click', ()        => socket.emit('set_jets', {}));
    els.allOffBtn.addEventListener('click', ()      => socket.emit('all_off', {})); 
    els.pdaBtn.addEventListener('click', ()         => socket.emit('pda', {}));
    
    els.spaTempInput.addEventListener('change', (event) => {
        const temp_f = parseInt(event.target.value, 10);
        
        // Safety constraint validation (standard spa max is typically 104°F)
        if (!isNaN(temp_f) && temp_f >= 60 && temp_f <= 104) {
            socket.emit('set_spa_temp', { temp_f });
        } else {
            console.error("Invalid spa temperature value.");
        }
    });

    els.poolTempInput.addEventListener('change', (event) => {
        const temp_f = parseInt(event.target.value, 10);
        
        // Safety constraint validation (standard pool max is typically 101°F)
        if (!isNaN(temp_f) && temp_f >= 60 && temp_f <= 101) {
            socket.emit('set_pool_temp', { temp_f });
        } else {
            console.error("Invalid pool temperature value.");
        }
    });

    els.filterRpmInput.addEventListener('change', (event) => {
        const rpm= parseInt(event.target.value, 10);
        if (!isNaN(rpm) && rpm >= 0 && rpm <= 3600) {
            socket.emit('set_filter_rpm', { rpm });
        } else {
            console.error("Invalid rpm.");
        }
    });

}

function initSocketIO() {
    socket.on('connect', () => {
        hideError();
        socket.emit('get_initial_state', {});
    });

    socket.on('state_update', applyState);

    socket.on('protocol_update', (msg) => {
        if (els.protocolOutput) {
            els.protocolOutput.value = JSON.stringify(msg, null, 2);
        }
    });

    socket.on('protocol_tx', (msg) => {
        if (els.protocolOutput) {
            const prev = els.protocolOutput.value;
            els.protocolOutput.value = `TX:\n${JSON.stringify(msg, null, 2)}\n\n${prev}`;
        }
    });

    socket.on('disconnect', () => {
        showError('Connection to the board lost.');
        els.connectionText.textContent = 'Disconnected';
    });
}

function applyState(s) {
    els.connectionText.textContent = s.connection_ok ? 'Connected' : 'No recent RS485 data';

    els.mode.textContent = (s.mode);
    els.airTemp.textContent = fmtTemp(s.air_temp_f);
    els.waterTemp.textContent = fmtTemp(s.water_temp_f);
    els.filterPumpOn.textContent = fmtBool(s.filter_pump_on);
    els.auxState.textContent = fmtBool(s.aux_pump_on);
    els.heaterState.textContent = fmtBool(s.heater_on);
    els.poolLightState.textContent = fmtBool(s.pool_light_on);
    els.spaLightState.textContent = fmtBool(s.spa_light_on);
    els.filterWatts.textContent = fmtWatts(s.filter_watts);
    els.filterRpm.textContent = fmtRPM(s.filter_rpm);
    els.saltPpm.textContent = fmtPPM(s.salt_ppm);
    els.swgPercent.textContent = fmtPercent(s.swg_percent);

    if (s.undefined_state) {
        showError('Undefined pool state — reset recommended.');
    } else if (s.last_error) {
        showError(s.last_error);
    } else {
        hideError();
    }
}

function fmtTemp(v) {
    return v == null ? '—' : `${v}°F`;
}
/**
 * Formats Salt Water Generator Output Percentage
 * Example: 40 -> "40%"
 */

function fmtPercent(v) {
    return v == null ? '—' : `${v}%`;
}

/**
 * Formats Filter Pump Power Draw in Watts
 * Example: 328 -> "328 W" or "328 Watts"
 */
function fmtWatts(v) {
    if (v == null) return '—';
    return `${v.toLocaleString()} W`;
}

/**
 * Formats Motor Speed in Revolutions Per Minute
 * Example: 1800 -> "1,800 RPM"
 */
function fmtRPM(v) {
    if (v == null) return '—';
    return `${v.toLocaleString()} RPM`;
}

/**
 * OPTIONAL BONUS: Formats Parts Per Million for Salt measurements
 * Example: 3100 -> "3,100 PPM"
 */
function fmtPPM(v) {
    if (v == null) return '—';
    return `${v.toLocaleString()} PPM`;
}
function fmtBool(v) {
    if (v == null) return '—';
    return v ? 'On' : 'Off';
}

function showError(msg) {
    els.errorContainer.textContent = msg;
    els.errorContainer.style.display = 'block';
}

function hideError() {
    els.errorContainer.style.display = 'none';
    els.errorContainer.textContent = '';
}
