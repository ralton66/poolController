// SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
//
// SPDX-License-Identifier: MPL-2.0

const socket = io(`http://${window.location.host}`);

const els = {
    connectionText: document.getElementById('connection-text'),
    modeBadge: document.getElementById('mode-badge'),
    airTemp: document.getElementById('air-temp'),
    poolTemp: document.getElementById('pool-temp'),
    spaTemp: document.getElementById('spa-temp'),
    poolSet: document.getElementById('pool-set'),
    spaSet: document.getElementById('spa-set'),
    filterState: document.getElementById('filter-state'),
    auxState: document.getElementById('aux-state'),
    heaterState: document.getElementById('heater-state'),
    valveState: document.getElementById('valve-state'),
    poolLightState: document.getElementById('pool-light-state'),
    spaLightState: document.getElementById('spa-light-state'),
    swgState: document.getElementById('swg-state'),
    spaTempInput: document.getElementById('spa-temp-input'),
    filterRpmInput: document.getElementById('filter-rpm-input'),
    spaOnBtn: document.getElementById('spa-on-btn'),
    filterOnBtn: document.getElementById('filter-on-btn'),
    lightsOnBtn: document.getElementById('lights-on-btn'),
    lightsOffBtn: document.getElementById('lights-off-btn'),
    allOffBtn: document.getElementById('all-off-btn'),
    debugPanel: document.getElementById('debug-panel'),
    protocolOutput: document.getElementById('protocolOutput'),
    injectButton: document.getElementById('inject-button'),
    sendTxButton: document.getElementById('send-tx-button'),
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
    els.spaOnBtn.addEventListener('click', () => {
        const temp_f = parseInt(els.spaTempInput.value, 10) || 102;
        socket.emit('set_spa', { temp_f });
    });
    els.filterOnBtn.addEventListener('click', () => {
        const rpm = parseInt(els.filterRpmInput.value, 10);
        socket.emit('set_filter', { rpm });
    });
    els.lightsOnBtn.addEventListener('click', () => {
        socket.emit('set_lights', { on: true, target: 'pool' });
    });
    els.lightsOffBtn.addEventListener('click', () => {
        socket.emit('set_lights', { on: false, target: 'pool' });
    });
    els.allOffBtn.addEventListener('click', () => socket.emit('all_off', {}));
    if (els.injectButton) {
        els.injectButton.addEventListener('click', () => socket.emit('inject_test_rx', {}));
    }
    if (els.sendTxButton) {
        els.sendTxButton.addEventListener('click', () => socket.emit('send_test_tx', {}));
    }
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
    setModeBadge(s.mode);

    els.airTemp.textContent = fmtTemp(s.air_temp_f);
    els.poolTemp.textContent = fmtTemp(s.pool_temp_f);
    els.spaTemp.textContent = fmtTemp(s.spa_temp_f);
    els.poolSet.textContent = fmtTemp(s.pool_setpoint_f);
    els.spaSet.textContent = fmtTemp(s.spa_setpoint_f);

    els.filterState.textContent = formatPump(s.filter_pump_on, s.filter_rpm);
    els.auxState.textContent = fmtBool(s.aux_pump_on);
    els.heaterState.textContent = fmtBool(s.heater_on);
    els.valveState.textContent = s.valve || '—';
    els.poolLightState.textContent = fmtBool(s.pool_light_on);
    els.spaLightState.textContent = fmtBool(s.spa_light_on);
    els.swgState.textContent = s.swg_status || '—';

    if (s.undefined_state) {
        showError('Undefined pool state — reset recommended.');
    } else if (s.last_error) {
        showError(s.last_error);
    } else {
        hideError();
    }
}

function setModeBadge(mode) {
    const m = (mode || 'off').toLowerCase();
    els.modeBadge.textContent = m.toUpperCase();
    els.modeBadge.className = 'badge badge-' + m;
}

function fmtTemp(v) {
    return v == null ? '—' : `${v}°F`;
}

function fmtBool(v) {
    if (v == null) return '—';
    return v ? 'On' : 'Off';
}

function formatPump(on, rpm) {
    if (on == null && rpm == null) return '—';
    if (rpm != null) return on ? `${rpm} RPM` : 'Off';
    return fmtBool(on);
}

function showError(msg) {
    els.errorContainer.textContent = msg;
    els.errorContainer.style.display = 'block';
}

function hideError() {
    els.errorContainer.style.display = 'none';
    els.errorContainer.textContent = '';
}
