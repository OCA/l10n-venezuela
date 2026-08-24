/* eslint-disable complexity */
import {Component, onWillUnmount, useState} from "@odoo/owl";
import {createFiscalSerialAuditLogger} from "../fiscal_serial/fiscal_serial_audit";
import {useService} from "@web/core/utils/hooks";

const TFHKA_COMMAND_DELAY_MS = 200;

const PHASE = {
    DISCONNECTED: "disconnected",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    ERROR: "error",
};

export class FiscalMachineDebugConsole extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachineDebugConsole";
    static props = {
        record: {type: Object, optional: true},
        embedded: {type: Boolean, optional: true},
    };

    setup() {
        this.fiscalSerial = useService("l10n_ve_fiscal_serial");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.ui = useService("ui");
        const defaults = this._getRecordDefaults();
        this.machineId = defaults.machineId;
        this.state = useState({
            phase: PHASE.DISCONNECTED,
            busy: false,
            estado: "",
            commandText: "",
            lastCmdResult: "",
            logLines: [],
            serialBaud: defaults.baud,
            serialParity: defaults.parity,
            fpStatus: "",
            fpError: "",
            fpDescripStatus: "",
            fpDescripError: "",
            fpLrcValid: null,
            flag21: defaults.flag21,
            machineName: defaults.machineName,
            serialPortHint: defaults.serialPort,
        });
        this.driver = null;
        this.auditLogger = null;
        this._isUIBlocked = false;
        onWillUnmount(() => {
            this._cleanupOnUnmount();
        });
    }

    _getRecordDefaults() {
        const record = this.props.record;
        if (!record) {
            return {
                baud: "9600",
                parity: "even",
                flag21: "30",
                machineId: false,
                machineName: "",
                serialPort: "",
            };
        }
        return {
            baud: String(record.data.baudrate || "9600"),
            parity:
                record.data.parity === "none" ? "none" : record.data.parity || "even",
            flag21: record.data.flag_21 || "30",
            machineId: record.resId || false,
            machineName: record.data.name || "",
            serialPort: record.data.serial_port || "",
        };
    }

    get embedded() {
        return Boolean(this.props.embedded);
    }

    get machineTitle() {
        return this.state.machineName || "Máquinas fiscales";
    }

    get statusLabel() {
        switch (this.state.phase) {
            case PHASE.CONNECTING:
                return "Conectando…";
            case PHASE.CONNECTED:
                return "Puerto abierto";
            case PHASE.ERROR:
                return "Error";
            default:
                return "Desconectado";
        }
    }

    get statusClass() {
        switch (this.state.phase) {
            case PHASE.CONNECTING:
                return "bg-warning text-dark";
            case PHASE.CONNECTED:
                return "bg-success";
            case PHASE.ERROR:
                return "bg-danger";
            default:
                return "bg-secondary";
        }
    }

    get canSendCommands() {
        return (
            this.state.phase === PHASE.CONNECTED &&
            !this.state.busy &&
            this.driver !== null
        );
    }

    get isSendDisabled() {
        return this.state.busy || !this.canSendCommands;
    }

    get logDisplayText() {
        if (!this.state.logLines.length) {
            return "Pulse «Abrir conexión»; aquí aparecerán los pasos. La misma información sale en la consola (F12) con el prefijo [l10n_ve_fiscal_serial].";
        }
        return this.state.logLines.join("\n");
    }

    get fpStatusHex() {
        const n = parseInt(this.state.fpStatus, 10);
        if (Number.isNaN(n)) {
            return "";
        }
        return n.toString(16).toUpperCase();
    }

    get fpMachineLine() {
        if (this.state.phase !== PHASE.CONNECTED) {
            return "";
        }
        if (this.state.fpStatus === "" && this.state.fpError === "") {
            return "";
        }
        const hx = this.fpStatusHex ? `0x${this.fpStatusHex}` : "—";
        const lrc =
            this.state.fpLrcValid === true
                ? "válido"
                : this.state.fpLrcValid === false
                  ? "no válido"
                  : "—";
        return `Estado: ${this.state.fpStatus || "—"} (${hx}) — ${this.state.fpDescripStatus || "—"} · Error: ${this.state.fpError || "—"} — ${this.state.fpDescripError || "—"} · LRC: ${lrc}`;
    }

    async _cleanupOnUnmount() {
        if (!this.driver) {
            return;
        }
        try {
            await this.driver.closeFpCtrl({
                reason: "user_request",
                detail: "Salió del formulario de la máquina fiscal.",
            });
        } catch {
            /* Ignore serial port cleanup errors. */
        }
        this.driver = null;
        this.auditLogger = null;
        this._clearBlockingProgress();
    }

    _resetFpStatusFields() {
        this.state.fpStatus = "";
        this.state.fpError = "";
        this.state.fpDescripStatus = "";
        this.state.fpDescripError = "";
        this.state.fpLrcValid = null;
    }

    _syncFpStatusFromDriver() {
        if (!this.driver) {
            this._resetFpStatusFields();
            return;
        }
        const st = this.driver.status;
        const er = this.driver.error;
        this.state.fpStatus =
            st !== null && st !== undefined && String(st) !== "" ? String(st) : "";
        this.state.fpError =
            er !== null && er !== undefined && String(er) !== "" ? String(er) : "";
        this.state.fpDescripStatus = this.driver.descripStatus || "";
        this.state.fpDescripError = this.driver.descripError || "";
        this.state.fpLrcValid =
            typeof this.driver.erroValid === "boolean" ? this.driver.erroValid : null;
    }

    _log(line) {
        const stamp = new Date().toISOString().split("T")[1].slice(0, 12);
        const entry = `[${stamp}] ${line}`;
        console.info("[l10n_ve_fiscal_serial]", entry);
        const next = [...this.state.logLines, entry];
        this.state.logLines = next.slice(-24);
    }

    _setBlockingProgress(percent, message = "Imprimiendo...") {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (this._isUIBlocked) {
            this.ui.unblock();
            this._isUIBlocked = false;
        }
        this.ui.block({message: `${message} ${pct}%`});
        this._isUIBlocked = true;
    }

    _clearBlockingProgress() {
        if (this._isUIBlocked) {
            this.ui.unblock();
            this._isUIBlocked = false;
        }
    }

    async _loadMachineConfig() {
        const record = this.props.record;
        if (record?.data?.flag_21) {
            this.state.flag21 = record.data.flag_21;
        } else {
            this.state.flag21 = "30";
        }
        this._log(`FLAG_21 de la máquina: ${this.state.flag21}`);
        return {
            flag_21: this.state.flag21,
            use_emulator: Boolean(record?.data?.use_emulator),
            send_default_code_in_name: Boolean(record?.data?.send_default_code_in_name),
        };
    }

    async onOpenConnection() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.phase = PHASE.CONNECTING;
        this.state.estado = "Esperando puerto y comprobación ENQ…";
        this.state.logLines = [];
        this._log("Inicio: comprobar Web Serial API");
        try {
            await this._loadMachineConfig();
            if (!this.fiscalSerial.isSupported()) {
                this.state.phase = PHASE.ERROR;
                this.state.estado =
                    "Este navegador no expone Web Serial. Use Chrome o Edge y acceda por HTTPS.";
                this._log("ERROR: Web Serial no disponible");
                this.notification.add(this.state.estado, {type: "danger"});
                return;
            }
            if (this.state.serialPortHint) {
                this._log(`Puerto registrado: ${this.state.serialPortHint}`);
            }
            this._log("Web Serial OK. Se abrirá el selector de puerto del navegador");
            this.auditLogger = createFiscalSerialAuditLogger(this.orm, {
                source: "debug_console",
                machineId: this.machineId,
            });
            this.driver = this.fiscalSerial.createTfhkaFiscal();
            this.auditLogger.attachDriver(this.driver);
            const baud = parseInt(this.state.serialBaud, 10) || 9600;
            const parity = this.state.serialParity === "none" ? "none" : "even";
            this._log(
                `openFpCtrl baud=${baud} parity=${parity} — elija el adaptador USB-Serie`
            );
            const ok = await this.driver.openFpCtrl({
                baudRate: baud,
                parity,
            });
            if (ok) {
                this._resetFpStatusFields();
                this._log("openFpCtrl: OK — leyendo estado fiscal (ENQ, 5 bytes)…");
                const stOk = await this.driver.readFpStatus();
                this._syncFpStatusFromDriver();
                this.state.phase = PHASE.CONNECTED;
                this.state.estado =
                    this.driver.estado ||
                    (stOk
                        ? "Listo. Puerto abierto; estado y error fiscal leídos (ENQ)."
                        : "Puerto abierto; la lectura ENQ de estado no devolvió 5 bytes válidos. Revise paridad/baudios o pulse «Estado impresora (ENQ)».");
                this._log(
                    stOk
                        ? `ENQ inicial: estado=${this.driver.status} error=${this.driver.error} LRC=${this.driver.erroValid}`
                        : `ENQ inicial: fallo — ${this.driver.estado || "sin detalle"}`
                );
                this.notification.add("Puerto abierto.", {type: "success"});
            } else {
                this.state.phase = PHASE.ERROR;
                const detail =
                    this.driver.estado ||
                    "No se pudo completar la conexión con la impresora fiscal.";
                this.state.estado = detail;
                this._log(`openFpCtrl: fallo — ${detail}`);
                this.notification.add(detail, {type: "danger"});
                this.driver = null;
                this.auditLogger = null;
            }
        } catch (e) {
            this.state.phase = PHASE.ERROR;
            const detail = this.fiscalSerial.formatWebSerialError(e);
            this.state.estado = detail;
            this._log(`EXCEPCIÓN: ${detail}`);
            this.notification.add(detail, {type: "danger"});
            this._resetFpStatusFields();
            this.driver = null;
            this.auditLogger = null;
        } finally {
            this.state.busy = false;
        }
    }

    async onCloseConnection() {
        if (this.state.busy || !this.driver) {
            return;
        }
        this.state.busy = true;
        this._log("Cerrando puerto…");
        try {
            await this.driver.closeFpCtrl({
                reason: "user_request",
                detail: "Cierre solicitado desde la consola de depuración.",
            });
            this.state.phase = PHASE.DISCONNECTED;
            this.state.estado = "";
            this.state.lastCmdResult = "";
            this._resetFpStatusFields();
            this.driver = null;
            this.auditLogger = null;
            this._log("Puerto cerrado");
            this.notification.add("Puerto cerrado.", {type: "success"});
        } catch (e) {
            const msg = e.message || String(e);
            this._log(`ERROR al cerrar: ${msg}`);
            this.notification.add(msg, {type: "danger"});
        } finally {
            this.state.busy = false;
        }
    }

    async onSendCommand() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        const raw = this.state.commandText ?? "";
        const normalized = raw.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        const lines = normalized.split("\n").filter((l) => l.length > 0);
        if (!lines.length) {
            this.notification.add("Indique al menos un comando.", {type: "warning"});
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        await this._loadMachineConfig();
        this._log(`Enviar ${lines.length} línea(s) de comando`);
        this._log(`FLAG_21 configurada para esta sesión: ${this.state.flag21}`);
        try {
            let okCount = 0;
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                this._log(
                    `sendCmd: «${line.length > 80 ? line.slice(0, 80) + "…" : line}»`
                );
                const sent = await this.driver.sendCmd(line);
                if (sent) {
                    okCount += 1;
                    this._log(`Línea ${okCount}: ACK OK`);
                    this._setBlockingProgress(
                        (okCount / lines.length) * 100,
                        "Imprimiendo..."
                    );
                } else {
                    const errDetail = `Error en comando. Estado driver: ${this.driver.estado || "NAK/sin ACK"}`;
                    this.state.lastCmdResult = errDetail;
                    this._log(`ERROR: ${errDetail}`);
                    this.notification.add(errDetail, {type: "danger"});
                    return;
                }
            }
            this.state.lastCmdResult = `Enviados ${okCount} comando(s) en Latin-1 (OK).`;
            this._log("Todos los comandos respondieron ACK");
            this.notification.add("Comando(s) enviado(s).", {type: "success"});
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN envío: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onSendSampleInvoice() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        const lines = this.fiscalSerial.getSampleHkaInvoiceLines(this.state.flag21);
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        await this._loadMachineConfig();
        this._log(
            `Secuencia de prueba: ${lines.length} línea(s) (pausa ${TFHKA_COMMAND_DELAY_MS} ms entre líneas)`
        );
        try {
            let okCount = 0;
            for (let i = 0; i < lines.length; i++) {
                if (i > 0) {
                    await new Promise((r) => setTimeout(r, TFHKA_COMMAND_DELAY_MS));
                }
                const line = lines[i];
                this._log(
                    `sendCmd: «${line.length > 80 ? line.slice(0, 80) + "…" : line}»`
                );
                const sent = await this.driver.sendCmd(line);
                if (sent) {
                    okCount += 1;
                    this._log(`Línea ${okCount}: ACK OK`);
                    this._setBlockingProgress(
                        (okCount / lines.length) * 100,
                        "Imprimiendo..."
                    );
                } else {
                    const errDetail = `Error en secuencia de prueba. Estado driver: ${this.driver.estado || "NAK/sin ACK"}`;
                    this.state.lastCmdResult = errDetail;
                    this._log(`ERROR: ${errDetail}`);
                    this.notification.add(errDetail, {type: "danger"});
                    return;
                }
            }
            this.state.lastCmdResult = `Secuencia de prueba: ${okCount} comando(s) enviados (4 alícuotas, p- montos por línea, q- monto global tras subtotal, cierre 199).`;
            this._log("Secuencia de prueba completada (ACK en todas las líneas)");
            this.notification.add("Secuencia de prueba enviada.", {type: "success"});
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN secuencia: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onReadFpStatusEnq() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        this._log(
            "Consulta estado TFHKA: ENQ (0x05) — respuesta 5 bytes STX, estado, error, ETX, LRC"
        );
        try {
            const ok = await this.driver.readFpStatus();
            this._syncFpStatusFromDriver();
            const st = this.driver.status;
            const er = this.driver.error;
            const valid = this.driver.erroValid;
            const ds = this.driver.descripStatus || "";
            const de = this.driver.descripError || "";
            if (ok) {
                const line = `ENQ OK — estado=${st} (${ds}); error=${er} (${de}); LRC válido=${valid}`;
                this.state.lastCmdResult = line;
                if (this.driver.estado) {
                    this.state.estado = this.driver.estado;
                }
                this._log(line);
                this.notification.add("Estado leído (ENQ).", {type: "success"});
                this._setBlockingProgress(100, "Imprimiendo...");
            } else {
                const detail =
                    this.driver.estado ||
                    `ENQ sin 5 bytes válidos (estado=${st}, error=${er}). Revise COM, paridad y cable.`;
                this.state.lastCmdResult = detail;
                this.state.estado = detail;
                this._log(`ERROR estado ENQ: ${detail}`);
                this.notification.add(detail, {type: "danger"});
                this._setBlockingProgress(100, "Imprimiendo...");
            }
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN ENQ: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async _readStatusCommand(cmd) {
        const result = await this.driver.uploadStatusCmdToString(cmd);
        const content = (result?.content || "").trim();
        if (!result?.ok || !content) {
            this._log(`${cmd}: sin respuesta`);
            return {cmd, ok: false, content: ""};
        }
        const preview = content.length > 500 ? `${content.slice(0, 500)}…` : content;
        this._log(`${cmd} OK (${content.length} chars):\n${preview}`);
        return {cmd, ok: true, content};
    }

    async onReadAllStatuses() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Leyendo status…");
        this._log("Obtener todos los status: ENQ + S1/S2/S3/S4/S5/S25 + SV");
        const statusCmds = ["S1", "S2", "S3", "S4", "S5", "S25"];
        try {
            const enqOk = await this.driver.readFpStatus();
            this._syncFpStatusFromDriver();
            if (enqOk) {
                this._log(
                    `ENQ OK — ${this.driver.descripStatus || ""} / ${this.driver.descripError || ""}`
                );
            } else {
                this._log(`ENQ: ${this.driver.estado || "sin respuesta válida"}`);
            }
            this._setBlockingProgress(15, "Leyendo status…");

            const results = [];
            for (let i = 0; i < statusCmds.length; i++) {
                const cmd = statusCmds[i];
                results.push(await this._readStatusCommand(cmd));
                this._setBlockingProgress(
                    15 + Math.round(((i + 1) / (statusCmds.length + 1)) * 70),
                    "Leyendo status…"
                );
                await new Promise((resolve) =>
                    setTimeout(resolve, TFHKA_COMMAND_DELAY_MS)
                );
            }

            const sv = await this.driver.getSVPrinterData();
            const svRaw = (sv?.raw || "").trim();
            if (svRaw) {
                this._log(`SV OK:\n${svRaw}`);
                results.push({cmd: "SV", ok: true, content: svRaw});
            } else {
                this._log("SV: sin respuesta");
                results.push({cmd: "SV", ok: false, content: ""});
            }
            this._setBlockingProgress(95, "Leyendo status…");

            const s1 = results.find((item) => item.cmd === "S1" && item.ok);
            if (s1?.content && this.machineId) {
                const parsed = this.fiscalSerial.parseTfhkaS1StatusResponse(s1.content);
                await this.orm.call(
                    "l10n.ve.fiscal.machine",
                    "apply_port_update_from_detect",
                    [
                        [this.machineId],
                        {
                            registered_serial: parsed?.RegisteredMachineNumber || null,
                            last_invoice_number: parsed?.LastInvoiceNumber || null,
                            last_credit_note_number:
                                parsed?.LastCreditNoteNumber || null,
                            last_debit_note_number: parsed?.LastDebitNoteNumber || null,
                            daily_closure_counter: parsed?.DailyClosureCounter || null,
                            enq_status: parseInt(this.driver.status || "0", 10),
                            enq_error: parseInt(this.driver.error || "0", 10),
                            enq_status_label: this.driver.descripStatus || "",
                            enq_error_label: this.driver.descripError || "",
                            s1_raw: s1.content,
                            sv_raw: svRaw || null,
                        },
                    ]
                );
                if (this.props.record?.model?.root?.load) {
                    await this.props.record.model.root.load();
                }
            }

            const okCount = results.filter((item) => item.ok).length + (enqOk ? 1 : 0);
            const total = results.length + 1;
            this.state.lastCmdResult = `Status leídos: ${okCount}/${total} (ENQ + ${statusCmds.join(", ")}, SV).`;
            this.state.estado = this.state.lastCmdResult;
            this.notification.add(this.state.lastCmdResult, {
                type: okCount ? "success" : "warning",
            });
            this._setBlockingProgress(100, "Leyendo status…");
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN status: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onSendProbeSeven() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        this._log(
            "Prueba HKA: sendCmd «7» (comando mínimo del ejemplo de prueba del manual/driver)"
        );
        try {
            const sent = await this.driver.sendCmd("7");
            if (sent) {
                this.state.lastCmdResult =
                    "Comando «7» respondió ACK. El enlace de comandos enmarcados funciona; si fallan las líneas i*, revise estado fiscal y secuencia del documento en el manual.";
                this._log("ACK en comando 7");
                this.notification.add("Comando 7: ACK OK.", {type: "success"});
                this._setBlockingProgress(100, "Imprimiendo...");
            } else {
                const errDetail = `Prueba «7»: ${this.driver.estado || "sin ACK"}`;
                this.state.lastCmdResult = errDetail;
                this._log(`ERROR: ${errDetail}`);
                this.notification.add(errDetail, {type: "danger"});
                this._setBlockingProgress(100, "Imprimiendo...");
            }
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onPrintXReport() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        await this._loadMachineConfig();
        this._log("Iniciar reporte X desde consola de depuración");
        try {
            const machine = this.fiscalSerial.createTfhkaFiscalMachine(this.driver);
            const response = await machine.printXReport();
            if (!response?.valid) {
                throw new Error(response?.message || "No se pudo imprimir reporte X.");
            }
            this.state.lastCmdResult =
                response.message || "Reporte X impreso correctamente.";
            this._log(this.state.lastCmdResult);
            this.notification.add(this.state.lastCmdResult, {type: "success"});
            this._setBlockingProgress(100, "Imprimiendo...");
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`ERROR reporte X: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onPrintZReport() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        await this._loadMachineConfig();
        this._log("Iniciar reporte Z desde consola de depuración");
        try {
            const machine = this.fiscalSerial.createTfhkaFiscalMachine(this.driver);
            const response = await machine.printZReport();
            if (!response?.valid) {
                throw new Error(response?.message || "No se pudo imprimir reporte Z.");
            }
            this.state.lastCmdResult =
                response.message || "Reporte Z impreso correctamente.";
            this._log(this.state.lastCmdResult);
            this.notification.add(this.state.lastCmdResult, {type: "success"});
            this._setBlockingProgress(100, "Imprimiendo...");
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`ERROR reporte Z: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }

    async onConfigureFiscalMachine() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    {type: "warning"}
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._setBlockingProgress(0, "Imprimiendo...");
        const cfg = await this._loadMachineConfig();
        const flag21 = cfg?.flag_21 || this.state.flag21 || "30";
        const flag50 = cfg?.flag_50 || "01";
        this._log(`Configurar máquina fiscal con FLAG_21=${flag21}, FLAG_50=${flag50}`);
        try {
            const machine = this.fiscalSerial.createTfhkaFiscalMachine(this.driver);
            const response = await machine.configureMachineFlag21(flag21, {
                flag_50: flag50,
                onProgress: ({percent}) => {
                    this._setBlockingProgress(percent, "Imprimiendo...");
                },
            });
            if (!response?.valid) {
                throw new Error(
                    response?.message || "No se pudo configurar la máquina fiscal."
                );
            }
            this.state.lastCmdResult =
                response.message ||
                `Configuración enviada con FLAG_21=${flag21}, FLAG_50=${flag50}.`;
            this._log(this.state.lastCmdResult);
            this.notification.add(this.state.lastCmdResult, {type: "success"});
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`ERROR configuración fiscal: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, {type: "danger"});
        } finally {
            this.state.busy = false;
            this._clearBlockingProgress();
        }
    }
}
