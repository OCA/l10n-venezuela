/* eslint-disable complexity */
const TFHKA_SV_MODEL_CODES = {
    Z1F: {printer_type: "other", name: "SRP812"},
};

const TFHKA_PRINTER_TYPE_HINTS = [
    {pattern: /hka\s*80|hka80/i, printer_type: "hka80", name: "HKA 80"},
    {pattern: /vmax\s*801|vmax801|elepos/i, printer_type: "vmax801", name: "VMAX801"},
];

function normalizeSvRaw(raw) {
    let text = String(raw || "").replace(/\r/g, "");
    text = text.split(String.fromCharCode(2)).join("");
    const etxIndex = text.indexOf(String.fromCharCode(3));
    if (etxIndex >= 0) {
        text = text.slice(0, etxIndex);
    }
    return text.trim();
}

function inferPrinterType(modelCode, modelName) {
    const code = String(modelCode || "").toUpperCase();
    if (TFHKA_SV_MODEL_CODES[code]) {
        return TFHKA_SV_MODEL_CODES[code];
    }
    const label = `${modelCode || ""} ${modelName || ""}`;
    for (const hint of TFHKA_PRINTER_TYPE_HINTS) {
        if (hint.pattern.test(label)) {
            return {printer_type: hint.printer_type, name: hint.name};
        }
    }
    return {
        printer_type: "other",
        name: modelName || modelCode || null,
    };
}

export function parseTfhkaSvStatusResponse(raw) {
    const text = normalizeSvRaw(raw);
    const out = {
        raw: text,
        modelCode: null,
        modelName: null,
        countryCode: null,
        printer_type: "hka80",
    };
    if (!text) {
        return out;
    }
    let body = text;
    if (/^SV/i.test(body)) {
        body = body.slice(2).trim();
    }
    if (body.length >= 2) {
        out.countryCode = body.slice(-2).toUpperCase();
        out.modelCode = body.length > 2 ? body.slice(0, -2).trim() : null;
    } else {
        out.modelCode = body || null;
    }
    const inferred = inferPrinterType(out.modelCode, out.modelName);
    out.printer_type = inferred.printer_type;
    out.modelName = inferred.name || out.modelCode;
    return out;
}

function extractFiscalRif(raw) {
    const match = String(raw || "").match(/[JVGE]-?\d{8,11}/i);
    return match ? match[0].toUpperCase() : null;
}

export async function autoDetectFiscalMachine(driver, helpers = {}) {
    const {parseTfhkaS1StatusResponse, describeTfhkaEnqSts1, describeTfhkaEnqSts2} =
        helpers;
    if (!driver) {
        throw new Error("Driver fiscal no disponible.");
    }
    const statusOk = await driver.readFpStatus();
    if (!statusOk) {
        throw new Error(
            driver.estado || "No se pudo leer el estado ENQ de la impresora."
        );
    }
    const s1Result = await driver.uploadStatusCmdToString("S1");
    if (!s1Result?.ok || !s1Result.content) {
        throw new Error("No se pudo leer el estado S1 de la impresora.");
    }
    const svResult = await driver.getSVPrinterData();
    const s1Parsed = parseTfhkaS1StatusResponse
        ? parseTfhkaS1StatusResponse(s1Result.content)
        : null;
    const svParsed = parseTfhkaSvStatusResponse(svResult?.raw || "");
    const sts1 = parseInt(driver.status || "0", 10);
    const sts2 = parseInt(driver.error || "0", 10);
    const portInfo = driver.portInfo || {};
    const registeredSerial = s1Parsed?.RegisteredMachineNumber || null;
    const fiscalRif = extractFiscalRif(s1Result.content);
    const isTrainingMode = sts1 === 64;
    const printerModelName = svParsed.modelName || svParsed.modelCode || null;
    const name =
        registeredSerial && printerModelName
            ? `${printerModelName} (${registeredSerial})`
            : registeredSerial || portInfo.label || "Máquina fiscal";
    return {
        name,
        connection_type: "web_serial",
        serial_port: portInfo.label || driver.comPort || "Web Serial",
        baudrate: String(driver._lastOpenBaudRate || 9600),
        parity: driver._lastOpenParity || "even",
        data_bits: "8",
        stop_bits: "1",
        webserial_usb_vendor_id: portInfo.usbVendorId || 0,
        webserial_usb_product_id: portInfo.usbProductId || 0,
        webserial_usb_serial_number: portInfo.usbSerialNumber || null,
        printer_type: svParsed.printer_type || "hka80",
        printer_model_code: svParsed.modelCode,
        printer_model_name: printerModelName,
        country_code: svParsed.countryCode,
        registered_serial: registeredSerial,
        fiscal_rif: fiscalRif,
        last_invoice_number: s1Parsed?.LastInvoiceNumber || null,
        last_credit_note_number: s1Parsed?.LastCreditNoteNumber || null,
        last_debit_note_number: s1Parsed?.LastDebitNoteNumber || null,
        daily_closure_counter: s1Parsed?.DailyClosureCounter || null,
        enq_status: Number.isFinite(sts1) ? sts1 : null,
        enq_error: Number.isFinite(sts2) ? sts2 : null,
        enq_status_label:
            describeTfhkaEnqSts1 && Number.isFinite(sts1)
                ? describeTfhkaEnqSts1(sts1)
                : driver.descripStatus || null,
        enq_error_label:
            describeTfhkaEnqSts2 && Number.isFinite(sts2)
                ? describeTfhkaEnqSts2(sts2)
                : driver.descripError || null,
        s1_raw: s1Result.content,
        sv_raw: svParsed.raw || svResult?.raw || null,
        detect_state: "done",
        detect_message:
            isTrainingMode && (!registeredSerial || !fiscalRif)
                ? "Modo entrenamiento: complete manualmente el serial fiscal y el RIF antes de guardar."
                : "Máquina fiscal detectada correctamente.",
    };
}
