/** @odoo-module **/

/* eslint-disable no-undef */

import {reactive} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {TfhkaWebSerialTransport} from "../fiscal_serial/tfhka_transport_webserial";

export const CONNECTION_STATUS = {
    HIDDEN: "hidden",
    UNSUPPORTED: "unsupported",
    IDLE: "idle",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    ERROR: "error",
};

const AUTH_INTERVAL_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 4000;
const PROBE_TIMEOUT_MS = 10000;
const HEARTBEAT_TIMEOUT_MS = 3500;
const CLOSE_TIMEOUT_MS = 2000;

export const l10nVeFiscalConnectionService = {
    dependencies: ["l10n_ve_fiscal_serial", "orm", "action"],
    start(env, {l10n_ve_fiscal_serial: fiscalSerial, orm, action}) {
        const state = reactive({
            visible: false,
            status: CONNECTION_STATUS.HIDDEN,
            message: "",
            machine: null,
            machines: [],
            authorizedMachines: [],
            companyName: "",
            lastCheckAt: null,
            portLabel: "",
            portOpen: false,
            portAuthorized: false,
            enqStatusLabel: "",
            enqErrorLabel: "",
            registeredSerial: "",
            busy: false,
            heartbeatCount: 0,
        });

        let driver = null;
        let authTimer = null;
        let heartbeatTimer = null;
        let checkGeneration = 0;
        let checkPromise = null;
        let bootstrapPromise = null;
        let serialListenersBound = false;
        let heartbeatPaused = false;
        let heartbeatRunning = false;
        let borrowCount = 0;

        const _setStatus = (status, message = "") => {
            state.status = status;
            state.message = message;
        };

        const _withTimeout = (promise, ms, message) => {
            let timer = null;
            const timeout = new Promise((_, reject) => {
                timer = setTimeout(() => reject(new Error(message)), ms);
            });
            return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
        };

        const _getPrimaryMachine = () => {
            if (!state.machines.length) {
                return null;
            }
            if (state.machine?.id) {
                return state.machine;
            }
            return state.machines[0];
        };

        const _isDriverOpen = () => Boolean(driver && driver.transport?.isOpen?.());

        const _clearDriverAudit = () => {
            if (!driver?.auditLogger) {
                return;
            }
            const auditLogger = driver.auditLogger;
            if (typeof auditLogger.detachDriver === "function") {
                auditLogger.detachDriver(driver);
            } else {
                driver.auditLogger = null;
                auditLogger._closed = true;
            }
        };

        const _stopHeartbeat = () => {
            if (heartbeatTimer) {
                clearInterval(heartbeatTimer);
                heartbeatTimer = null;
            }
        };

        const _closeDriver = async () => {
            state.portOpen = false;
            _stopHeartbeat();
            if (!driver) {
                return;
            }
            const current = driver;
            _clearDriverAudit();
            driver = null;
            try {
                await _withTimeout(
                    current.closeFpCtrl({
                        reason: "systray_cleanup",
                        skipAudit: true,
                    }),
                    CLOSE_TIMEOUT_MS,
                    "close-timeout"
                );
            } catch {}
        };

        const _applyAuthorizationStatus = (machine) => {
            if (!machine) {
                _setStatus(CONNECTION_STATUS.IDLE, "");
                return;
            }
            if (
                state.status === CONNECTION_STATUS.CONNECTING ||
                state.status === CONNECTION_STATUS.CONNECTED ||
                state.status === CONNECTION_STATUS.ERROR
            ) {
                return;
            }
            if (state.portAuthorized) {
                _setStatus(
                    CONNECTION_STATUS.IDLE,
                    "Puerto autorizado. Pulse el icono o «Verificar conexión» para abrir y vigilar la máquina."
                );
                state.portLabel = state.portLabel || machine.serial_port || "";
            } else {
                _setStatus(
                    CONNECTION_STATUS.IDLE,
                    "No hay puerto autorizado. Use «Conectar» y seleccione el adaptador USB."
                );
            }
        };

        const _syncAuthorizedMachines = async () => {
            if (!fiscalSerial.isSupported() || !state.machines.length) {
                state.authorizedMachines = [];
                return state.authorizedMachines;
            }
            try {
                state.authorizedMachines =
                    await TfhkaWebSerialTransport.getAuthorizedMachines(state.machines);
            } catch {
                state.authorizedMachines = [];
            }
            return state.authorizedMachines;
        };

        const refreshAuthorization = async () => {
            const machine = _getPrimaryMachine();
            if (!fiscalSerial.isSupported()) {
                state.portAuthorized = false;
                state.authorizedMachines = [];
                if (machine) {
                    _setStatus(
                        CONNECTION_STATUS.UNSUPPORTED,
                        "Web Serial no está disponible. Use Chrome o Edge con HTTPS."
                    );
                }
                return state.portAuthorized;
            }
            if (!machine) {
                state.portAuthorized = false;
                await _syncAuthorizedMachines();
                return state.portAuthorized;
            }
            try {
                const ports = await TfhkaWebSerialTransport.getAuthorizedPorts();
                state.authorizedMachines =
                    TfhkaWebSerialTransport.filterAuthorizedMachines(
                        state.machines,
                        ports
                    );
                const matched = TfhkaWebSerialTransport.matchPortToMachine(
                    ports,
                    machine,
                    {strict: true}
                );
                state.portAuthorized = Boolean(matched);
                if (matched && !state.portLabel) {
                    const info = matched.getInfo?.() || {};
                    state.portLabel =
                        machine.serial_port ||
                        fiscalSerial.formatWebSerialPortLabel?.(info) ||
                        "";
                }
            } catch {
                state.portAuthorized = false;
                state.authorizedMachines = [];
            }
            if (!_isDriverOpen()) {
                _applyAuthorizationStatus(machine);
            }
            return state.portAuthorized;
        };

        const _portMatchesMachine = (port, machine) => {
            if (!port || !machine) {
                return false;
            }
            return TfhkaWebSerialTransport.portMatchesMachine(port, machine);
        };

        const _onSerialDisconnect = (event) => {
            const machine = _getPrimaryMachine();
            if (!_portMatchesMachine(event.target, machine)) {
                return;
            }
            void _closeDriver();
            state.portAuthorized = false;
            state.enqStatusLabel = "";
            state.enqErrorLabel = "";
            state.lastCheckAt = Date.now();
            _setStatus(
                CONNECTION_STATUS.ERROR,
                "Se desconectó el adaptador USB de la máquina fiscal."
            );
        };

        const _onSerialConnect = async () => {
            if (!state.visible) {
                return;
            }
            await refreshAuthorization();
            if (state.portAuthorized && !_isDriverOpen()) {
                _setStatus(
                    CONNECTION_STATUS.IDLE,
                    "Puerto USB reconectado. Pulse «Verificar conexión» para abrir la máquina."
                );
            }
        };

        const _bindSerialListeners = () => {
            if (serialListenersBound || !fiscalSerial.isSupported()) {
                return;
            }
            navigator.serial.addEventListener("disconnect", _onSerialDisconnect);
            navigator.serial.addEventListener("connect", _onSerialConnect);
            serialListenersBound = true;
        };

        const _waitHeartbeatIdle = async () => {
            const deadline = Date.now() + HEARTBEAT_TIMEOUT_MS + 1000;
            while (heartbeatRunning && Date.now() < deadline) {
                await new Promise((resolve) => setTimeout(resolve, 25));
            }
        };

        const _runHeartbeat = async () => {
            if (
                heartbeatPaused ||
                heartbeatRunning ||
                borrowCount > 0 ||
                state.busy ||
                !_isDriverOpen()
            ) {
                return;
            }
            heartbeatRunning = true;
            state.heartbeatCount += 1;
            try {
                if (heartbeatPaused || borrowCount > 0) {
                    return;
                }
                _clearDriverAudit();
                const statusOk = await _withTimeout(
                    driver.readFpStatus(),
                    HEARTBEAT_TIMEOUT_MS,
                    "La máquina fiscal no responde (apagada o desconectada)."
                );
                if (heartbeatPaused || borrowCount > 0) {
                    return;
                }
                state.portOpen = true;
                state.lastCheckAt = Date.now();
                state.enqStatusLabel = driver.descripStatus || "";
                state.enqErrorLabel = driver.descripError || "";
                if (statusOk) {
                    state.portAuthorized = true;
                    _setStatus(
                        CONNECTION_STATUS.CONNECTED,
                        "Máquina fiscal conectada. Vigilancia ENQ activa."
                    );
                } else {
                    _setStatus(
                        CONNECTION_STATUS.ERROR,
                        driver.estado ||
                            "Puerto abierto, pero la impresora no responde (apagada o en error)."
                    );
                }
            } catch (error) {
                if (heartbeatPaused || borrowCount > 0) {
                    return;
                }
                state.portOpen = _isDriverOpen();
                state.lastCheckAt = Date.now();
                const message =
                    fiscalSerial.formatWebSerialError?.(error) ||
                    error?.message ||
                    "La máquina fiscal no responde.";
                _setStatus(CONNECTION_STATUS.ERROR, message);
            } finally {
                heartbeatRunning = false;
            }
        };

        const _startHeartbeat = () => {
            _stopHeartbeat();
            if (!_isDriverOpen()) {
                return;
            }
            void _runHeartbeat();
            heartbeatTimer = setInterval(() => {
                void _runHeartbeat();
            }, HEARTBEAT_INTERVAL_MS);
        };

        const _machinesFromPosFallback = () => {
            const pos = env.services.pos;
            const model = pos?.models?.["l10n.ve.fiscal.machine"];
            const localMachines =
                (typeof model?.getAll === "function" && model.getAll()) ||
                (typeof model?.readAll === "function" && model.readAll()) ||
                [];
            return localMachines.map((machine) => ({
                id: machine.id,
                name: machine.name,
                registered_serial: machine.registered_serial || "",
                serial_port: machine.serial_port || "",
                baudrate: machine.baudrate || "9600",
                parity: machine.parity || "even",
                webserial_usb_vendor_id: machine.webserial_usb_vendor_id || 0,
                webserial_usb_product_id: machine.webserial_usb_product_id || 0,
                webserial_usb_serial_number: machine.webserial_usb_serial_number || "",
                last_connection: false,
                enq_status_label: "",
                enq_error_label: "",
            }));
        };

        const loadSystrayData = async () => {
            let data = null;
            try {
                data = await orm.call(
                    "l10n.ve.fiscal.machine",
                    "l10n_ve_fiscal_serial_get_systray_data",
                    [],
                    {}
                );
            } catch (error) {
                const fallbackMachines =
                    state.machines.length > 0
                        ? state.machines
                        : _machinesFromPosFallback();
                if (!fallbackMachines.length) {
                    throw error;
                }
                data = {
                    visible: true,
                    company_name: state.companyName || "",
                    primary_machine_id: state.machine?.id || fallbackMachines[0].id,
                    machines: fallbackMachines,
                    offline_cache: true,
                };
            }
            const wasVisible = state.visible;
            state.visible = Boolean(data.visible);
            state.companyName = data.company_name || "";
            state.machines = data.machines || [];
            if (!state.visible) {
                await _closeDriver();
                state.machine = null;
                state.authorizedMachines = [];
                state.portAuthorized = false;
                _setStatus(CONNECTION_STATUS.HIDDEN);
                return data;
            }
            await _syncAuthorizedMachines();
            const currentId = Number(state.machine?.id || 0) || 0;
            const primaryId = Number(data.primary_machine_id || 0) || 0;
            state.machine =
                (currentId &&
                    state.machines.find(
                        (machine) => Number(machine.id) === currentId
                    )) ||
                state.machines.find((machine) => Number(machine.id) === primaryId) ||
                state.machines[0] ||
                null;
            if (!fiscalSerial.isSupported()) {
                _setStatus(
                    CONNECTION_STATUS.UNSUPPORTED,
                    "Web Serial no está disponible. Use Chrome o Edge con HTTPS."
                );
            } else if (!state.machine) {
                _setStatus(CONNECTION_STATUS.IDLE, "");
            } else if (state.status === CONNECTION_STATUS.HIDDEN) {
                _setStatus(CONNECTION_STATUS.IDLE, "");
            }
            if (wasVisible !== state.visible) {
                registry.category("systray").trigger("UPDATE");
            }
            return data;
        };

        const _openAndKeep = async (machine, {requestPort = false} = {}) => {
            const baudRate = parseInt(machine.baudrate || "9600", 10);
            const parity = machine.parity === "none" ? "none" : "even";
            if (_isDriverOpen()) {
                const statusOk = await driver.readFpStatus();
                state.portOpen = true;
                state.portLabel =
                    driver.portInfo?.label || driver.comPort || machine.serial_port;
                state.enqStatusLabel = driver.descripStatus || "";
                state.enqErrorLabel = driver.descripError || "";
                return {statusOk, alreadyOpen: true};
            }
            await _closeDriver();
            driver = fiscalSerial.createTfhkaFiscal();
            const resolved = await TfhkaWebSerialTransport.resolvePort(machine, {
                requestPort,
            });
            if (!resolved.port) {
                throw new Error(
                    "No hay puerto autorizado. Use «Conectar» y seleccione el adaptador USB."
                );
            }
            const opened = await driver.openFpCtrl({
                baudRate,
                parity,
                port: resolved.port,
            });
            if (!opened) {
                const message =
                    driver.estado || "No fue posible abrir el puerto serial.";
                await _closeDriver();
                throw new Error(message);
            }
            state.portOpen = true;
            state.portAuthorized = true;
            state.portLabel =
                driver.portInfo?.label || driver.comPort || machine.serial_port;
            const statusOk = await driver.readFpStatus();
            state.enqStatusLabel = driver.descripStatus || "";
            state.enqErrorLabel = driver.descripError || "";
            if (statusOk) {
                try {
                    const s1Result = await driver.uploadStatusCmdToString("S1");
                    if (s1Result?.ok && s1Result.content) {
                        const parsed = fiscalSerial.parseTfhkaS1StatusResponse(
                            s1Result.content
                        );
                        state.registeredSerial = parsed?.RegisteredMachineNumber || "";
                    }
                } catch {}
            }
            return {statusOk, alreadyOpen: false};
        };

        const checkConnection = async ({requestPort = false} = {}) => {
            if (!state.visible) {
                return checkPromise;
            }
            if (checkPromise && !requestPort) {
                return checkPromise;
            }

            const machine = _getPrimaryMachine();
            if (!machine) {
                _setStatus(CONNECTION_STATUS.IDLE, "");
                return;
            }
            if (!fiscalSerial.isSupported()) {
                _setStatus(
                    CONNECTION_STATUS.UNSUPPORTED,
                    "Web Serial no está disponible. Use Chrome o Edge con HTTPS."
                );
                return;
            }

            const generation = ++checkGeneration;
            state.busy = true;
            _setStatus(
                CONNECTION_STATUS.CONNECTING,
                "Comprobando conexión con la máquina fiscal…"
            );

            checkPromise = (async () => {
                try {
                    const result = await _withTimeout(
                        _openAndKeep(machine, {requestPort}),
                        PROBE_TIMEOUT_MS,
                        "Tiempo de espera agotado al abrir la máquina fiscal."
                    );
                    if (generation !== checkGeneration) {
                        return;
                    }
                    state.lastCheckAt = Date.now();
                    await _syncAuthorizedMachines();
                    state.portAuthorized = true;
                    if (result.statusOk) {
                        _setStatus(
                            CONNECTION_STATUS.CONNECTED,
                            "Máquina fiscal conectada. El puerto permanece abierto para detectar apagados."
                        );
                    } else {
                        _setStatus(
                            CONNECTION_STATUS.ERROR,
                            driver?.estado ||
                                "Puerto abierto, pero la impresora no responde (apagada o en error)."
                        );
                    }
                    _startHeartbeat();
                } catch (error) {
                    if (generation !== checkGeneration) {
                        return;
                    }
                    await _closeDriver();
                    state.enqStatusLabel = "";
                    state.enqErrorLabel = "";
                    state.registeredSerial = "";
                    state.lastCheckAt = Date.now();
                    await refreshAuthorization();
                    const message =
                        fiscalSerial.formatWebSerialError?.(error) ||
                        error?.message ||
                        String(error);
                    _setStatus(CONNECTION_STATUS.ERROR, message);
                } finally {
                    if (generation === checkGeneration) {
                        state.busy = false;
                        checkPromise = null;
                    }
                }
            })();

            return checkPromise;
        };

        const connect = async () => checkConnection({requestPort: true});

        const _resolveTargetMachine = (machine) => {
            let target = machine || _getPrimaryMachine();
            if (!target) {
                return null;
            }
            const targetId = Number(target.machine_id || target.id || 0) || 0;
            if (targetId && state.machines.length) {
                const listed = state.machines.find((item) => item.id === targetId);
                if (listed) {
                    target = {
                        ...listed,
                        ...target,
                        id: listed.id,
                        baudrate: target.baudrate || listed.baudrate,
                        parity: target.parity || listed.parity,
                        serial_port: target.serial_port || listed.serial_port,
                        webserial_usb_vendor_id:
                            target.webserial_usb_vendor_id ||
                            listed.webserial_usb_vendor_id,
                        webserial_usb_product_id:
                            target.webserial_usb_product_id ||
                            listed.webserial_usb_product_id,
                        webserial_usb_serial_number:
                            target.webserial_usb_serial_number ||
                            listed.webserial_usb_serial_number,
                    };
                }
            } else if (targetId && !target.id) {
                target = {...target, id: targetId};
            }
            return target;
        };

        const borrowDriver = async ({machine = null, requestPort = false} = {}) => {
            const target = _resolveTargetMachine(machine);
            if (!target) {
                throw new Error("No hay máquina fiscal configurada.");
            }
            const targetId = Number(target.machine_id || target.id || 0) || 0;
            const openId = Number(state.machine?.id || 0) || 0;
            if (_isDriverOpen() && targetId && openId && targetId !== openId) {
                if (borrowCount > 0) {
                    throw new Error(
                        "La máquina fiscal está en uso por otra operación. Espere e intente de nuevo."
                    );
                }
                await _closeDriver();
            }
            if (targetId && Number(state.machine?.id) !== targetId) {
                const listed = state.machines.find(
                    (item) => Number(item.id) === targetId
                );
                state.machine = listed || {...target, id: targetId};
            }
            heartbeatPaused = true;
            _stopHeartbeat();
            borrowCount += 1;
            try {
                await _waitHeartbeatIdle();
                _clearDriverAudit();
                if (!_isDriverOpen()) {
                    state.busy = true;
                    _setStatus(
                        CONNECTION_STATUS.CONNECTING,
                        "Abriendo puerto de la máquina fiscal…"
                    );
                    try {
                        const result = await _withTimeout(
                            _openAndKeep(target, {requestPort}),
                            PROBE_TIMEOUT_MS,
                            "Tiempo de espera agotado al abrir la máquina fiscal."
                        );
                        state.lastCheckAt = Date.now();
                        if (result.statusOk) {
                            _setStatus(
                                CONNECTION_STATUS.CONNECTED,
                                "Máquina fiscal conectada. El puerto permanece abierto para detectar apagados."
                            );
                        } else {
                            _setStatus(
                                CONNECTION_STATUS.ERROR,
                                driver?.estado ||
                                    "Puerto abierto, pero la impresora no responde."
                            );
                        }
                    } finally {
                        state.busy = false;
                    }
                }
                if (!_isDriverOpen()) {
                    throw new Error(
                        driver?.estado || "No fue posible abrir el puerto serial."
                    );
                }
                return driver;
            } catch (error) {
                borrowCount = Math.max(0, borrowCount - 1);
                if (borrowCount === 0) {
                    heartbeatPaused = false;
                    if (_isDriverOpen()) {
                        _startHeartbeat();
                    }
                }
                throw error;
            }
        };

        const releaseDriver = async ({close = false} = {}) => {
            borrowCount = Math.max(0, borrowCount - 1);
            if (close) {
                await _closeDriver();
                heartbeatPaused = false;
                return;
            }
            if (borrowCount === 0) {
                _clearDriverAudit();
                heartbeatPaused = false;
                if (_isDriverOpen()) {
                    _startHeartbeat();
                    void _runHeartbeat();
                }
            }
        };

        const openMachines = () =>
            action.doAction("l10n_ve_fiscal_serial.action_l10n_ve_fiscal_machine");

        const setPrimaryMachine = async (machineId) => {
            const id = Number(machineId) || 0;
            if (!id) {
                return false;
            }
            if (!state.machines.length) {
                try {
                    await loadSystrayData();
                } catch (error) {
                    console.warn(
                        "[l10n_ve_fiscal_serial] setPrimaryMachine: systray offline",
                        error
                    );
                }
            }
            let next =
                state.machines.find((machine) => Number(machine.id) === id) || null;
            if (!next) {
                const fromPos = _machinesFromPosFallback().find(
                    (machine) => Number(machine.id) === id
                );
                if (fromPos) {
                    state.machines = [...state.machines, fromPos];
                    next = fromPos;
                }
            }
            if (!next) {
                return false;
            }
            if (Number(state.machine?.id) === Number(next.id)) {
                state.machine = next;
                return true;
            }
            if (_isDriverOpen()) {
                await _closeDriver();
            }
            state.machine = next;
            state.portAuthorized = false;
            state.portLabel = next.serial_port || "";
            state.enqStatusLabel = "";
            state.enqErrorLabel = "";
            state.registeredSerial = next.registered_serial || "";
            state.heartbeatCount = 0;
            if (state.visible) {
                await refreshAuthorization();
            }
            return true;
        };

        const _clearAuthTimer = () => {
            if (authTimer) {
                clearInterval(authTimer);
                authTimer = null;
            }
        };

        const startAutoProbe = () => {
            _clearAuthTimer();
            authTimer = setInterval(() => {
                if (state.visible && !state.busy && !_isDriverOpen()) {
                    void refreshAuthorization();
                }
            }, AUTH_INTERVAL_MS);
        };

        const stopAutoProbe = () => {
            _clearAuthTimer();
            _stopHeartbeat();
        };

        const bootstrap = async () => {
            if (bootstrapPromise) {
                return bootstrapPromise;
            }
            bootstrapPromise = (async () => {
                await loadSystrayData();
                if (!state.visible) {
                    return;
                }
                _bindSerialListeners();
                startAutoProbe();
                await refreshAuthorization();
            })().finally(() => {
                bootstrapPromise = null;
            });
            return bootstrapPromise;
        };

        env.bus.addEventListener("WEB_CLIENT_READY", () => {
            void bootstrap();
        });
        void Promise.resolve().then(() => {
            void bootstrap();
        });

        return {
            state,
            loadSystrayData,
            refreshAuthorization,
            checkConnection,
            connect,
            borrowDriver,
            releaseDriver,
            openMachines,
            setPrimaryMachine,
            getAuthorizedMachines: () => state.authorizedMachines,
            startAutoProbe,
            stopAutoProbe,
            bootstrap,
        };
    },
};

registry
    .category("services")
    .add("l10n_ve_fiscal_connection", l10nVeFiscalConnectionService);
