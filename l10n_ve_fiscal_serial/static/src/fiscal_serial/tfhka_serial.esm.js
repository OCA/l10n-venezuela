/* eslint-disable no-undef */
import {
    ACK,
    ENQ,
    ETX,
    NAK,
    STX,
    TFHKA_ENQ_STS2_NINGUN_ERROR,
    buildQueryBytes,
    buildSendCmdFrame,
    decodeLatin15ish,
    describeTfhkaEnqSts1,
    describeTfhkaEnqSts2,
    doXorCommand,
    encodeLatin1,
} from "./tfhka_protocol";
import {
    mfReportzFromDailyClosureString,
    parseTfhkaS1StatusResponse,
} from "./tfhka_s1_parser";
import {
    TfhkaWebSerialTransport,
    formatWebSerialError,
    readWebSerialPortInfo,
} from "./tfhka_transport_webserial";

const ENQ_READ_OPTS = {
    byteTimeout: 280,
    totalTimeout: 6000,
    maxLen: 20,
};

const STATUS_MESSAGES = {
    0: "Unknown status",
    48: "Printer status (0x30)",
    64: describeTfhkaEnqSts1(0x40),
    66: describeTfhkaEnqSts1(0x42),
    68: describeTfhkaEnqSts1(0x44),
    96: describeTfhkaEnqSts1(0x60),
    97: describeTfhkaEnqSts1(0x61),
    128: "No response",
    137: "Incorrect response length",
    144: "Status validation failed",
    145: "Exception reading status",
};

const ERROR_MESSAGES = {
    0: "No error",
    64: describeTfhkaEnqSts2(TFHKA_ENQ_STS2_NINGUN_ERROR),
    128: "No response",
    137: "Incorrect response length",
    144: "Status validation failed",
    145: "Exception reading status",
};

export class PrinterStatus {
    constructor(status, error, erroValid, descripStatus, descripError) {
        this.status = status;
        this.error = error;
        this.erroValid = erroValid;
        this.descripStatus = descripStatus;
        this.descripError = descripError;
    }
}

export class SVPrinterData {
    constructor(raw) {
        this.raw = raw || "";
    }
}

export class TfhkaFiscal {
    constructor() {
        this.transport = new TfhkaWebSerialTransport();
        this.tempBuffer = new Uint8Array(1000);
        this.portReceiveStatus = "Espera";
        this._dataReady = false;
        this._bytesRecibidos = 0;
        this._auxBytesRecibidos = 0;
        this.serialPortReceiveTimeout = 20;
        this._serialPortReceiveTimeout = 20;
        this.sendCmdRetryAttempts = 0;
        this.sendCmdRetryInterval = 1000;
        this.usandoLineasControl = false;
        this.usandoRTS_CTS = false;
        this.usandoDSR_DTR = false;
        this.estado = "";
        this.comPort = "";
        this.mensaje = "";
        this.status = null;
        this.error = null;
        this.descripStatus = "";
        this.descripError = "";
        this.erroValid = true;
        this.dataLectorFisc = [];
        this._lastEnqByteCount = 0;
        this._lastEnqHeadHex = "";
        this.portInfo = null;
        this._lastOpenBaudRate = 9600;
        this._lastOpenParity = "even";
        this._lastPortRequested = false;
        this.auditLogger = null;
    }

    async _auditPortOpenFailure(estado) {
        if (!this.auditLogger) {
            return;
        }
        this.auditLogger.logPortOpen(this, {
            success: false,
            errorMessage: estado,
        });
        this.auditLogger.logPortClose(this, "open_failed", estado);
        await this.auditLogger.flush();
    }

    async _auditPortOpenSuccess() {
        if (!this.auditLogger) {
            return;
        }
        this.auditLogger.logPortOpen(this, {success: true});
    }

    _consoleLogCommand(step, payload) {
        console.log("[l10n_ve_fiscal_serial][tfhka_serial]", step, payload);
        if (this.auditLogger) {
            this.auditLogger.logCommandEvent(this, step, payload);
        }
    }

    reiniciarVariables() {
        this.portReceiveStatus = "Espera";
        this._dataReady = false;
        this._bytesRecibidos = 0;
        this._auxBytesRecibidos = 0;
        this.dataLectorFisc = [];
    }

    _darStatusError(st, er) {
        this.status = String(st);
        this.error = String(er);
        this.descripStatus = STATUS_MESSAGES[st] || `Estado código ${st}`;
        this.descripError = ERROR_MESSAGES[er] || `Error código ${er}`;
    }

    async _sleep(ms) {
        await new Promise((r) => setTimeout(r, ms));
    }

    async _readAckOrNakAfterCmdWrite() {
        await this._sleep(500);
        const deadline = Date.now() + 32000;
        while (Date.now() < deadline) {
            const slice = Math.min(900, Math.max(25, deadline - Date.now()));
            const b = await this.transport.readOneByte(slice);
            if (b === ACK) {
                return {n: 1, bytes: new Uint8Array([ACK])};
            }
            if (b === NAK) {
                return {n: -2, bytes: new Uint8Array([NAK])};
            }
            if (b !== null && b !== undefined) {
                const rest = await this.transport.readSome({
                    byteTimeout: 70,
                    totalTimeout: 1500,
                    maxLen: 255,
                });
                for (let i = 0; i < rest.length; i++) {
                    if (rest[i] === ACK) {
                        return {n: 1, bytes: new Uint8Array([ACK])};
                    }
                    if (rest[i] === NAK) {
                        return {n: -2, bytes: new Uint8Array([NAK])};
                    }
                }
                const out = new Uint8Array(1);
                out[0] = b;
                return {n: 1, bytes: out};
            }
        }
        const chunk = await this.transport.readSome({
            byteTimeout: 80,
            totalTimeout: 1500,
            maxLen: 256,
        });
        for (let i = 0; i < chunk.length; i++) {
            if (chunk[i] === ACK) {
                return {n: 1, bytes: new Uint8Array([ACK])};
            }
            if (chunk[i] === NAK) {
                return {n: -2, bytes: new Uint8Array([NAK])};
            }
        }
        return {n: 0, bytes: new Uint8Array(0)};
    }

    async _serialPortWriteAndRead(payload, readMode, ioOptions = {}) {
        const bulkReadOptions = ioOptions;
        if (readMode === "ack") {
            await this.transport.setSignals({
                dataTerminalReady: true,
                requestToSend: true,
            });
            await this._sleep(50);
            await this.transport.drainInput();
        }
        await this.transport.writeBytes(
            payload,
            readMode === "ack"
                ? {postWriteDelayMs: ioOptions.postWriteDelayMsAck ?? 180}
                : {}
        );
        if (readMode === "ack") {
            return this._readAckOrNakAfterCmdWrite();
        }
        const bt =
            bulkReadOptions.byteTimeout ?? Math.max(10, this._serialPortReceiveTimeout);
        const totalT =
            bulkReadOptions.totalTimeout ??
            Math.max(2000, Math.max(10, this._serialPortReceiveTimeout) * 80);
        const bytes = await this.transport.readSome({
            byteTimeout: bt,
            totalTimeout: totalT,
            maxLen: bulkReadOptions.maxLen ?? 512,
        });
        return {n: bytes.length, bytes};
    }

    async _serialPortEnqQuery(enqRead) {
        const payload = buildQueryBytes([String.fromCharCode(ENQ)]);
        let {n, bytes} = await this._serialPortWriteAndRead(payload, "bulk", enqRead);
        if (n < 0) {
            ({n, bytes} = await this._serialPortWriteAndRead(payload, "bulk", enqRead));
        }
        return {n, bytes};
    }

    async _manipulaDSRDTR() {
        try {
            await this.transport.setSignals({
                dataTerminalReady: false,
                requestToSend: true,
            });
            await this._sleep(50);
            await this.transport.setSignals({
                dataTerminalReady: true,
                requestToSend: true,
            });
            await this._sleep(50);
            return await this.checkFPrinter();
        } catch {
            return false;
        }
    }

    async _manipulaCTSRTS() {
        try {
            await this.transport.setSignals({
                dataTerminalReady: true,
                requestToSend: false,
            });
            await this._sleep(50);
            await this.transport.setSignals({
                dataTerminalReady: true,
                requestToSend: true,
            });
            await this._sleep(50);
            return await this.checkFPrinter();
        } catch {
            return false;
        }
    }

    async openFpCtrl(first, second) {
        let port = null;
        let baudRate = 9600;
        let parity = "even";
        if (
            first !== null &&
            first !== undefined &&
            typeof first === "object" &&
            first.readable !== undefined
        ) {
            port = first;
            if (typeof second === "number") {
                baudRate = second;
            } else if (
                second !== null &&
                second !== undefined &&
                typeof second === "object"
            ) {
                baudRate = second.baudRate ?? baudRate;
                if (second.parity === "none") {
                    parity = "none";
                }
            }
        } else if (typeof first === "number") {
            baudRate = first;
            if (second !== null && second !== undefined && typeof second === "object") {
                baudRate = second.baudRate ?? baudRate;
                if (second.parity === "none") {
                    parity = "none";
                }
            }
        } else if (first !== null && first !== undefined && typeof first === "object") {
            const o = first;
            baudRate = o.baudRate ?? 9600;
            if (o.parity === "none") {
                parity = "none";
            }
            if (
                o.port !== null &&
                o.port !== undefined &&
                o.port.readable !== undefined
            ) {
                port = o.port;
            } else if (o.machine || o.useAuthorizedPorts) {
                const resolved = await TfhkaWebSerialTransport.resolvePort(
                    o.machine || {},
                    {
                        requestPort: o.requestPort !== false,
                        filters: o.filters || [],
                    }
                );
                port = resolved.port;
                this._lastPortRequested = resolved.requested;
            }
        }
        try {
            if (!port) {
                port = await this.transport.requestPort([]);
                this._lastPortRequested = true;
            }
            await this.transport.open(port, {
                baudRate,
                dataBits: 8,
                stopBits: 1,
                parity,
                bufferSize: 512,
                flowControl: "none",
            });
            this._lastOpenBaudRate = baudRate;
            this._lastOpenParity = parity;
            this.portInfo = readWebSerialPortInfo(port);
            this.comPort = this.portInfo.label || "web-serial";
            this.usandoLineasControl = false;
            this.usandoRTS_CTS = false;
            this.usandoDSR_DTR = false;

            const signalsSupported = await this.transport.setSignals({
                dataTerminalReady: false,
                requestToSend: true,
            });

            if (signalsSupported) {
                if (await this._manipulaDSRDTR()) {
                    this.usandoLineasControl = true;
                    this.usandoRTS_CTS = false;
                    this.usandoDSR_DTR = true;
                    await this._auditPortOpenSuccess();
                    return true;
                }
                if (await this._manipulaCTSRTS()) {
                    this.usandoLineasControl = true;
                    this.usandoRTS_CTS = true;
                    this.usandoDSR_DTR = false;
                    await this._auditPortOpenSuccess();
                    return true;
                }
            }

            if (await this._checkFPrinterEnq()) {
                this.usandoLineasControl = false;
                await this.transport.setSignals({
                    dataTerminalReady: false,
                    requestToSend: false,
                });
                await this._auditPortOpenSuccess();
                return true;
            }
            this.estado =
                this._lastEnqByteCount > 0
                    ? `ENQ devolvió ${this._lastEnqByteCount} byte(s) (${this._lastEnqHeadHex}); se requieren 5. En Linux/USB los bytes a veces llegan espaciados: use en Odoo la misma paridad y baud que en su prueba (p. ej. 8E1 si el manual indica par).`
                    : "ENQ no devolvió bytes a tiempo. Revise paridad, baudios, cable y que el puerto esté libre.";
            await this._auditPortOpenFailure(this.estado);
            await this.transport.close();
            return false;
        } catch (e) {
            this.estado = "Error..." + formatWebSerialError(e);
            await this._auditPortOpenFailure(this.estado);
            try {
                await this.transport.close();
            } catch {}
            return false;
        }
    }

    async closeFpCtrl(options = {}) {
        if (!options.skipAudit && this.auditLogger) {
            this.auditLogger.logPortClose(
                this,
                options.reason || "unknown",
                options.detail || this.estado || ""
            );
            await this.auditLogger.flush();
        }
        await this.transport.close();
    }

    async _checkFPrinterEnq() {
        if (!this.transport.isOpen()) {
            return false;
        }
        const prev = this._serialPortReceiveTimeout;
        this._serialPortReceiveTimeout = 2;
        try {
            const {n, bytes} = await this._serialPortEnqQuery(ENQ_READ_OPTS);
            this._lastEnqByteCount = n;
            this._lastEnqHeadHex =
                n > 0
                    ? Array.from(bytes.subarray(0, Math.min(n, 8)))
                          .map((b) => b.toString(16).toUpperCase().padStart(2, "0"))
                          .join("-")
                    : "";
            if (n >= 5) {
                this.reiniciarVariables();
                return true;
            }
            this.reiniciarVariables();
            return false;
        } catch (e) {
            this.estado = `Error... ${e.message || e}`;
            this.reiniciarVariables();
            return false;
        } finally {
            this._serialPortReceiveTimeout = prev;
        }
    }

    async checkFPrinter() {
        return this._checkFPrinterEnq();
    }

    async checkDrawer() {
        if (!this.transport.isOpen()) {
            return false;
        }
        const prev = this._serialPortReceiveTimeout;
        this._serialPortReceiveTimeout = 2;
        try {
            const {n, bytes} = await this._serialPortEnqQuery(ENQ_READ_OPTS);
            if (n >= 5) {
                const bit = bytes[2] & 8;
                this.reiniciarVariables();
                return bit === 8;
            }
            this.reiniciarVariables();
            return false;
        } finally {
            this._serialPortReceiveTimeout = prev;
        }
    }

    async sendCmd(sCMD) {
        if (sCMD === null || sCMD === undefined) {
            return false;
        }
        const cmd = String(sCMD);
        this._consoleLogCommand("SEND_CMD_REQUEST", {command: cmd});
        const xorChar = doXorCommand(cmd);
        const bodyLatin1 = encodeLatin1(cmd);
        this.mensaje = `${String.fromCharCode(STX)}${decodeLatin15ish(bodyLatin1)}${String.fromCharCode(ETX)}${xorChar}`;
        const frame = buildSendCmdFrame(cmd);
        let num2 = null;
        let bResp = null;
        ({n: num2, bytes: bResp} = await this._serialPortWriteAndRead(
            frame,
            "ack",
            {}
        ));
        if (num2 === 1 && bResp.length && bResp[0] === ACK) {
            this._consoleLogCommand("SEND_CMD_RESPONSE", {
                command: cmd,
                ack: true,
                code: "ACK",
            });
            this.estado = "OK";
            this.reiniciarVariables();
            return true;
        }
        if (num2 === 0) {
            this._consoleLogCommand("SEND_CMD_RESPONSE", {
                command: cmd,
                ack: false,
                code: "TIMEOUT",
            });
            this.estado = `Comando ${cmd} sin respuesta ACK (timeout).`;
            return false;
        }
        let num1 = 0;
        for (
            ;
            bResp.length &&
            (bResp[0] === NAK || num2 === -2) &&
            num1 < this.sendCmdRetryAttempts;
            num1++
        ) {
            await this._sleep(this.sendCmdRetryInterval);
            this._consoleLogCommand("SEND_CMD_RETRY", {
                command: cmd,
                retry: num1 + 1,
            });
            ({n: num2, bytes: bResp} = await this._serialPortWriteAndRead(
                frame,
                "ack"
            ));
        }
        const ok = num2 === 1 && bResp.length > 0 && bResp[0] === ACK;
        const code = ok ? "ACK" : bResp[0] === NAK || num2 === -2 ? "NAK" : "UNKNOWN";
        this._consoleLogCommand("SEND_CMD_RESPONSE", {
            command: cmd,
            ack: ok,
            code,
        });
        this.estado = ok ? "OK" : `Comando ${cmd} falló (${code}).`;
        this.reiniciarVariables();
        return ok;
    }

    async sendReportCmd(sCMD, waitSeconds = 4) {
        if (sCMD === null || sCMD === undefined) {
            return false;
        }
        const cmd = String(sCMD);
        const waitMs = Math.max(0, Number(waitSeconds) || 0) * 1000;
        this._consoleLogCommand("SEND_REPORT_CMD_REQUEST", {
            command: cmd,
            waitSeconds,
        });
        const frame = buildSendCmdFrame(cmd);
        try {
            await this.transport.setSignals({
                dataTerminalReady: true,
                requestToSend: true,
            });
            await this._sleep(50);
            if (typeof this.transport.drainInput === "function") {
                await this.transport.drainInput();
            }
            await this.transport.writeBytes(frame, {postWriteDelayMs: 180});
            const early = await this.transport.readSome({
                byteTimeout: 80,
                totalTimeout: 2000,
                maxLen: 256,
            });
            let sawNak = false;
            let sawAck = false;
            for (let i = 0; i < early.length; i++) {
                if (early[i] === ACK) {
                    sawAck = true;
                }
                if (early[i] === NAK) {
                    sawNak = true;
                }
            }
            if (sawNak) {
                this.estado = `Comando de reporte ${cmd} rechazado (NAK).`;
                this._consoleLogCommand("SEND_REPORT_CMD_RESPONSE", {
                    command: cmd,
                    ack: false,
                    code: "NAK",
                });
                this.reiniciarVariables();
                return false;
            }
            if (waitMs > 0) {
                await this._sleep(waitMs);
            }
            const leftover = await this.transport.readSome({
                byteTimeout: 40,
                totalTimeout: 2500,
                maxLen: 4096,
            });
            this.estado = "OK";
            this._consoleLogCommand("SEND_REPORT_CMD_RESPONSE", {
                command: cmd,
                ack: sawAck,
                code: sawAck ? "ACK" : "FIRE_AND_WAIT",
                leftover: leftover.length,
            });
            this.reiniciarVariables();
            return true;
        } catch (error) {
            this.estado = `Error reporte ${cmd}: ${error?.message || error}`;
            this._consoleLogCommand("SEND_REPORT_CMD_RESPONSE", {
                command: cmd,
                ack: false,
                code: "ERROR",
                detail: error?.message || String(error),
            });
            this.reiniciarVariables();
            return false;
        }
    }

    async sendFileCmdFromLines(lines) {
        let num = 0;
        try {
            for (const sCMD of lines) {
                if (sCMD === null || sCMD === undefined || sCMD === "") {
                    continue;
                }
                if (await this.sendCmd(sCMD)) {
                    num += 1;
                } else {
                    this.estado = "ERROR...";
                    return num;
                }
            }
            this.estado = "OK";
            return num;
        } catch (e) {
            this.estado = `Error... ${e.message || e}`;
            return 0;
        }
    }

    async sendFileCmdFromText(text) {
        const lines = text.split(/\r\n|\n|\r/);
        return this.sendFileCmdFromLines(lines);
    }

    async subirDataStatus(cmd) {
        this._consoleLogCommand("STATUS_COMMAND_REQUEST", {command: cmd});
        const frame = buildSendCmdFrame(cmd);
        await this.transport.writeBytes(frame);
        const raw = await this.transport.readSome({
            byteTimeout: 40,
            totalTimeout: 8000,
            maxLen: 4000,
        });
        const s = decodeLatin15ish(raw).replace(/\r/g, "").trim();
        const maxPreview = 900;
        const logPayload = {
            command: cmd,
            length: s.length,
            textPreview: s.length > maxPreview ? `${s.slice(0, maxPreview)}…` : s,
        };
        if (cmd === "S1" && s.length) {
            const p = parseTfhkaS1StatusResponse(s);
            logPayload.parsed = {
                LastInvoiceNumber: p.LastInvoiceNumber,
                LastCreditNoteNumber: p.LastCreditNoteNumber,
                RegisteredMachineNumber: p.RegisteredMachineNumber,
                DailyClosureCounter: p.DailyClosureCounter,
                mfReportz: mfReportzFromDailyClosureString(p.DailyClosureCounter),
            };
        }
        this._consoleLogCommand("STATUS_COMMAND_RESPONSE", logPayload);
        return {len: s.length, data: s};
    }

    async subirDataReport(cmd) {
        this._consoleLogCommand("REPORT_COMMAND_REQUEST", {command: cmd});
        const frame = buildSendCmdFrame(cmd);
        await this.transport.writeBytes(frame);
        const raw = await this.transport.readSome({
            byteTimeout: 40,
            totalTimeout: 20000,
            maxLen: 16000,
        });
        const text = decodeLatin15ish(raw);
        const lines = text.split(/\r\n|\n|\r/).filter((l) => l.length > 0);
        this.dataLectorFisc = lines;
        this._consoleLogCommand("REPORT_COMMAND_RESPONSE", {
            command: cmd,
            lines: lines.length,
        });
        return lines.length;
    }

    async uploadStatusCmdToString(cmd) {
        try {
            const {len, data} = await this.subirDataStatus(cmd);
            if (len > 0) {
                this.estado = "OK";
                this.reiniciarVariables();
                return {ok: true, content: data};
            }
            this.estado = "Sin repuesta.";
            this.reiniciarVariables();
            return {ok: false, content: ""};
        } catch (e) {
            this.estado = `Error... ${e.message || e}`;
            this.reiniciarVariables();
            return {ok: false, content: ""};
        }
    }

    async uploadReportCmdToString(cmd) {
        let str = "";
        try {
            const num = await this.subirDataReport(cmd);
            for (let i = 0; i < num; i++) {
                str = `${str}${this.dataLectorFisc[i]}\r\n`;
            }
            if (num > 0) {
                this.estado = "OK";
                this.reiniciarVariables();
                return {ok: true, content: str};
            }
            this.estado = "Sin repuesta.";
            this.reiniciarVariables();
            return {ok: false, content: ""};
        } catch (e) {
            this.estado = `Error... ${e.message || e}`;
            this.reiniciarVariables();
            return {ok: false, content: ""};
        }
    }

    async readFpStatus() {
        this._consoleLogCommand("STATUS_ENQ_REQUEST", {command: "ENQ(0x05)"});
        try {
            const prev = this._serialPortReceiveTimeout;
            this._serialPortReceiveTimeout = 2;
            let num1 = null;
            let bResp = null;
            try {
                ({n: num1, bytes: bResp} =
                    await this._serialPortEnqQuery(ENQ_READ_OPTS));
            } finally {
                this._serialPortReceiveTimeout = prev;
            }
            let st = 0;
            let er = 0;
            let num2 = 0;
            if (num1 === 5) {
                for (let index = 0; index < 5; index++) {
                    if (index === 1) {
                        st = bResp[index];
                    } else if (index === 2) {
                        er = bResp[index];
                    } else if (index === 4) {
                        num2 = bResp[index];
                    }
                }
                if ((st ^ er ^ 3) !== num2) {
                    this.erroValid = false;
                    this._darStatusError(0, 144);
                } else {
                    this.erroValid = true;
                    this._darStatusError(st, er);
                }
                if (
                    this.status !== null &&
                    this.status !== undefined &&
                    this.error !== null &&
                    this.error !== undefined
                ) {
                    this._consoleLogCommand("STATUS_ENQ_RESPONSE", {
                        status: this.status,
                        error: this.error,
                        lrcValid: this.erroValid,
                    });
                    this.estado = `Last known Fiscal Printer Status: ${this.descripStatus} - ${this.descripError}`;
                    this.reiniciarVariables();
                    return true;
                }
                this.estado = "No answer to ReadFpStatus.";
                this._darStatusError(0, 128);
                this.reiniciarVariables();
                return false;
            }
            this._darStatusError(0, 137);
            this.estado = "No se pudo leer ENQ: respuesta con longitud incorrecta.";
            this._consoleLogCommand("STATUS_ENQ_RESPONSE", {
                status: this.status,
                error: this.error,
                lrcValid: false,
                detail: "INVALID_LENGTH",
            });
            this.reiniciarVariables();
            return false;
        } catch (e) {
            const nm = e?.name || "";
            const ioOrNull =
                nm === "NetworkError" ||
                nm === "InvalidStateError" ||
                nm === "NotAllowedError" ||
                (nm === "TypeError" &&
                    String(e.message || "")
                        .toLowerCase()
                        .includes("null"));
            this._darStatusError(0, ioOrNull ? 128 : 145);
            this.estado = `Error al leer ENQ: ${e.message || e}`;
            this._consoleLogCommand("STATUS_ENQ_RESPONSE", {
                status: this.status,
                error: this.error,
                lrcValid: false,
                detail: e.message || String(e),
            });
            this.reiniciarVariables();
            return false;
        }
    }

    async getPrinterStatus() {
        const flag = await this.readFpStatus();
        if (
            ((this.status === null || this.status === undefined) &&
                (this.error === null || this.error === undefined)) ||
            (!flag &&
                this.error !== "128" &&
                this.error !== "145" &&
                this.error !== "137")
        ) {
            this._darStatusError(48, 128);
        }
        return new PrinterStatus(
            parseInt(this.status || "0", 10),
            parseInt(this.error || "0", 10),
            this.erroValid,
            this.descripStatus,
            this.descripError
        );
    }

    async getSVPrinterData() {
        const {len, data} = await this.subirDataStatus("SV");
        let sv = null;
        if (len > 0) {
            sv = new SVPrinterData(data);
            this.reiniciarVariables();
        } else {
            this.reiniciarVariables();
            sv = new SVPrinterData(null);
        }
        return sv;
    }

    async stringReportCmd(cmd) {
        try {
            const num = await this.subirDataReport(cmd);
            let str = "";
            for (let i = 0; i < num; i++) {
                str = `${str}${this.dataLectorFisc[i]}\r\n`;
            }
            return str;
        } catch (e) {
            this.estado = `Error... ${e.message || e}`;
            this.reiniciarVariables();
            return "";
        }
    }

    static get STX() {
        return STX;
    }
    static get ETX() {
        return ETX;
    }
    static get ENQ() {
        return ENQ;
    }
    static get ACK() {
        return ACK;
    }
    static get NAK() {
        return NAK;
    }
}

export function createTfhkaFiscal() {
    return new TfhkaFiscal();
}

export {TfhkaFiscal as TfhkaCommon};
export {encodeLatin1} from "./tfhka_protocol";
