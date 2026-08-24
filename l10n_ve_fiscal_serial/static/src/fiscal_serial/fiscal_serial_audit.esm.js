/** @odoo-module **/

/* eslint-disable no-undef */

const AUDIT_MODEL = "l10n.ve.fiscal.serial.audit";
const FLUSH_BATCH_SIZE = 15;

const COMMAND_STEP_MAP = {
    SEND_CMD_REQUEST: {command_type: "framed", direction: "request"},
    SEND_CMD_RESPONSE: {command_type: "ack", direction: "response"},
    SEND_CMD_RETRY: {command_type: "framed", direction: "retry"},
    STATUS_ENQ_REQUEST: {command_type: "enq", direction: "request"},
    STATUS_ENQ_RESPONSE: {command_type: "enq", direction: "response"},
    STATUS_COMMAND_REQUEST: {command_type: "status", direction: "request"},
    STATUS_COMMAND_RESPONSE: {command_type: "status", direction: "response"},
    REPORT_COMMAND_REQUEST: {command_type: "report", direction: "request"},
    REPORT_COMMAND_RESPONSE: {command_type: "report", direction: "response"},
};

function newSessionId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return `sess-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function inferCloseReasonFromDetail(detail) {
    const text = String(detail || "").toLowerCase();
    if (!text) {
        return null;
    }
    if (/cable|desconect|disconnect|networkerror|device (was )?lost/i.test(text)) {
        return "disconnect";
    }
    if (/apag|power|sin energ/i.test(text)) {
        return "power_off";
    }
    if (/timeout|tiempo|agotad/i.test(text)) {
        return "timeout";
    }
    return null;
}

function serializePayload(payload) {
    if (payload === null || payload === undefined) {
        return "";
    }
    if (typeof payload === "string") {
        return payload;
    }
    try {
        return JSON.stringify(payload);
    } catch {
        return String(payload);
    }
}

function buildPortSnapshot(driver) {
    const portInfo = driver?.portInfo || {};
    return {
        serial_port: driver?.comPort || portInfo.label || false,
        webserial_usb_vendor_id: portInfo.usbVendorId || 0,
        webserial_usb_product_id: portInfo.usbProductId || 0,
        webserial_usb_serial_number: portInfo.usbSerialNumber || false,
        baudrate: String(driver?._lastOpenBaudRate || ""),
        parity: driver?._lastOpenParity || false,
    };
}

function isOrmLifecycleError(error) {
    const msg = String(error?.message || error || "");
    const name = String(error?.name || "");
    return (
        /Component is destroyed/i.test(msg) ||
        /RpcAborted|ConnectionLostError|\bAborted\b|Failed to fetch|NetworkError|offline/i.test(
            msg
        ) ||
        /ConnectionLostError|TypeError/i.test(name) ||
        error?.name === "AbortError"
    );
}

export class FiscalSerialAuditLogger {
    constructor(orm, options = {}) {
        this.orm = orm;
        this.source = options.source || "other";
        this.machineId = options.machineId || false;
        this.moveId = options.moveId || false;
        this.companyId = options.companyId || false;
        this.sessionId = options.sessionId || newSessionId();
        this.buffer = [];
        this._portOpenedAt = null;
        this._flushPromise = null;
        this._closed = false;
    }

    attachDriver(driver) {
        if (!driver) {
            return;
        }
        driver.auditLogger = this;
    }

    detachDriver(driver) {
        if (driver && driver.auditLogger === this) {
            driver.auditLogger = null;
        }
        this._closed = true;
    }

    _baseEvent(driver) {
        return {
            session_id: this.sessionId,
            source: this.source,
            machine_id: this.machineId || false,
            move_id: this.moveId || false,
            company_id: this.companyId || false,
            ...buildPortSnapshot(driver),
        };
    }

    queueEvent(event) {
        if (this._closed) {
            return;
        }
        this.buffer.push(event);
        if (this.buffer.length >= FLUSH_BATCH_SIZE) {
            void this.flush();
        }
    }

    logPortOpen(driver, {success = true, errorMessage = ""} = {}) {
        this._portOpenedAt = Date.now();
        this.queueEvent({
            ...this._baseEvent(driver),
            event_type: "port_open",
            success,
            error_message: errorMessage || false,
        });
    }

    logPortClose(driver, reason = "unknown", detail = "") {
        const inferred = inferCloseReasonFromDetail(detail);
        const closeReason = inferred || reason || "unknown";
        const durationMs = this._portOpenedAt ? Date.now() - this._portOpenedAt : 0;
        this._portOpenedAt = null;
        this.queueEvent({
            ...this._baseEvent(driver),
            event_type: "port_close",
            close_reason: closeReason,
            close_reason_detail: detail || false,
            duration_ms: durationMs,
            success: closeReason !== "error" && closeReason !== "open_failed",
            error_message: detail || false,
        });
    }

    logCommandEvent(driver, step, payload = {}) {
        const mapping = COMMAND_STEP_MAP[step] || {
            command_type: "other",
            direction: "other",
        };
        const isResponse = mapping.direction === "response";
        const commandName = payload.command || payload.command_text || step;
        let responseSummary = false;
        if (payload.ack === true) {
            responseSummary = "ACK";
        } else if (payload.ack === false) {
            responseSummary = payload.code || "Sin ACK";
        } else if (
            payload.status !== null &&
            payload.status !== undefined &&
            payload.error !== null &&
            payload.error !== undefined
        ) {
            responseSummary = `STS1=${payload.status} STS2=${payload.error}`;
        } else if (payload.lines !== null && payload.lines !== undefined) {
            responseSummary = `${payload.lines} línea(s)`;
        } else if (payload.length !== null && payload.length !== undefined) {
            responseSummary = `${payload.length} byte(s)`;
        }
        this.queueEvent({
            ...this._baseEvent(driver),
            event_type: "command",
            command_step: step,
            command_type: mapping.command_type,
            command_payload: isResponse ? false : commandName,
            response_payload: isResponse ? serializePayload(payload) : false,
            response_summary: responseSummary,
            success: payload.ack !== false && payload.detail !== "INVALID_LENGTH",
        });
    }

    async flush() {
        if (!this.buffer.length) {
            return [];
        }
        if (this._flushPromise) {
            return this._flushPromise;
        }
        if (this._closed && !this.orm) {
            this.buffer.length = 0;
            return [];
        }
        const events = this.buffer.splice(0, this.buffer.length);
        this._flushPromise = this.orm
            .call(AUDIT_MODEL, "log_fiscal_serial_events", [events])
            .catch((error) => {
                if (isOrmLifecycleError(error)) {
                    console.warn(
                        "[l10n_ve_fiscal_serial][audit] flush omitido (offline/ciclo de vida)",
                        error
                    );
                    this.buffer.length = 0;
                    return [];
                }
                console.warn("[l10n_ve_fiscal_serial][audit] flush error", error);
                this.buffer.unshift(...events);
                return [];
            })
            .finally(() => {
                this._flushPromise = null;
            });
        return this._flushPromise;
    }
}

export function createFiscalSerialAuditLogger(orm, options = {}) {
    return new FiscalSerialAuditLogger(orm, options);
}

export async function closeDriverWithAudit(driver, reason, detail = "") {
    if (!driver) {
        return;
    }
    const auditLogger = driver.auditLogger;
    if (auditLogger) {
        auditLogger.logPortClose(driver, reason, detail);
        try {
            await auditLogger.flush();
        } finally {
            auditLogger.detachDriver(driver);
        }
    }
    await driver.closeFpCtrl({skipAudit: true});
}
