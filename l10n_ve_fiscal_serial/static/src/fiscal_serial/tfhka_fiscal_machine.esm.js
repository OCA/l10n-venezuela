/** @odoo-module **/

/* eslint-disable no-undef */

import {isTfhkaEnqSts1Operativa, isTfhkaEnqSts2SinErrorFiscal} from "./tfhka_protocol";
import {
    mfReportzFromDailyClosureString,
    parseTfhkaS1StatusResponse,
} from "./tfhka_s1_parser";

const FLAG_21 = {
    30: {
        maxAmountInt: 14,
        maxAmountDecimal: 2,
        maxPaymentAmountInt: 15,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 14,
        maxQtyDecimal: 3,
        discInt: 15,
        discDecimal: 2,
    },
    0: {
        maxAmountInt: 8,
        maxAmountDecimal: 2,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
    1: {
        maxAmountInt: 7,
        maxAmountDecimal: 3,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
    2: {
        maxAmountInt: 6,
        maxAmountDecimal: 4,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
};

const TAX_MAP = {
    0: " ",
    1: "!",
    2: '"',
    3: "#",
};

const STATUS_CODES = new Set(["1", "4", "48"]);
let EMULATOR_INVOICE_SEQUENCE = 0;
let EMULATOR_CREDIT_NOTE_SEQUENCE = 0;
let EMULATOR_LAST_REPORT_Z = 0;
const EMULATOR_MACHINE_SERIAL = "EMULADOR-TFHKA-001";

function toArray(value) {
    return Array.isArray(value) ? value : [];
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function cleanText(value, max = 127) {
    return String(value || "")
        .slice(0, max)
        .trim()
        .replaceAll("Ñ", "N")
        .replaceAll("ñ", "n");
}

function asNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}

function normalizePaymentMethod(value) {
    const txt = String(value || "").trim();
    if (!txt) {
        return "01";
    }
    return txt.padStart(2, "0");
}

function maybeDataWrapper(value) {
    if (value && typeof value === "object" && value.data) {
        return value.data;
    }
    return value || {};
}

function formatReprintFiscalNumber(mfNumber) {
    const digits = String(mfNumber || "").replace(/\D/g, "");
    if (!digits) {
        return "0000000";
    }
    return digits.slice(-7).padStart(7, "0");
}

function mapTaxCodeFromLine(line) {
    const directTax = line.tax ?? line.tax_code ?? line.taxCode;
    if (directTax !== undefined && directTax !== null && String(directTax) !== "") {
        const v = Math.max(0, Math.min(4, parseInt(directTax, 10) || 0));
        return String(v);
    }
    const percent = asNumber(
        line.tax_percent ?? line.taxPercent ?? line.tax_rate ?? 0,
        0
    );
    if (percent <= 0) {
        return "0";
    }
    if (percent <= 8) {
        return "2";
    }
    if (percent <= 16) {
        return "1";
    }
    return "3";
}

export class TfhkaFiscalMachine {
    constructor(driver, options = {}) {
        this.driver = driver;
        this.commandDelayMs = options.commandDelayMs ?? 200;
        this.s1Parser = options.s1Parser || parseTfhkaS1StatusResponse;
        this.actions = {
            status: this.getStatusMachine.bind(this),
            status1: this.getS1PrinterData.bind(this),
            logger: this.logger.bind(this),
            logger_multi: this.loggerMulti.bind(this),
            programacion: this.programacion.bind(this),
            print_out_invoice: this.printOutInvoice.bind(this),
            print_out_refund: this.printOutRefund.bind(this),
            reprint: this.reprint.bind(this),
            reprint_type: this.reprintType.bind(this),
            reprint_date: this.reprintDate.bind(this),
            print_resume: this.printResume.bind(this),
            test: this.test.bind(this),
            report_x: this.printXReport.bind(this),
            report_z: this.printZReport.bind(this),
            get_last_invoice_number: this.getLastInvoiceNumber.bind(this),
            get_last_out_refund_number: this.getLastOutRefundNumber.bind(this),
            configure_device: this.configureDevice.bind(this),
            pre_invoice: this.preInvoice.bind(this),
            print_debit_note: this.printDebitNote.bind(this),
        };
    }

    async runAction(payload = {}) {
        const action = payload.action;
        if (!action || !this.actions[action]) {
            return {valid: false, message: `Acción no soportada: ${action || ""}`};
        }
        return this.actions[action](payload.data ?? payload, {
            onProgress: payload.onProgress,
        });
    }

    _notifyProgress(options, percent, message) {
        if (typeof options?.onProgress === "function") {
            const bounded = Math.max(0, Math.min(100, Math.round(percent)));
            options.onProgress({percent: bounded, message});
        }
    }

    async _ensureStatusReady() {
        if (!this.driver || typeof this.driver.readFpStatus !== "function") {
            throw new Error("No hay driver fiscal disponible.");
        }
        const ok = await this.driver.readFpStatus();
        if (!ok) {
            throw new Error(this.driver.estado || "No se pudo leer el estado fiscal.");
        }
        const errorCode = String(this.driver.error ?? "");
        const fiscalSts2 = parseInt(errorCode, 10);
        if (Number.isFinite(fiscalSts2) && !isTfhkaEnqSts2SinErrorFiscal(fiscalSts2)) {
            throw new Error(
                this.driver.descripError ||
                    `Estado fiscal STS2 no admite operación (byte ${errorCode})`
            );
        }
        const statusCode = String(this.driver.status ?? "");
        const sts1 = parseInt(statusCode, 10);
        if (
            !STATUS_CODES.has(statusCode) &&
            !(Number.isFinite(sts1) && isTfhkaEnqSts1Operativa(sts1))
        ) {
            throw new Error(
                this.driver.descripStatus ||
                    `Estado impresora STS1 no permitido (${statusCode})`
            );
        }
        return true;
    }

    async _sendCommand(command) {
        const sent = await this.driver.sendCmd(String(command));
        if (!sent) {
            throw new Error(this.driver.estado || `Fallo al enviar comando ${command}`);
        }
        await sleep(this.commandDelayMs);
        return true;
    }

    async _sendReportCommand(command, waitSeconds) {
        if (typeof this.driver.sendReportCmd === "function") {
            const sent = await this.driver.sendReportCmd(String(command), waitSeconds);
            if (!sent) {
                throw new Error(
                    this.driver.estado || `Fallo al enviar reporte ${command}`
                );
            }
            await sleep(this.commandDelayMs);
            return true;
        }
        return this._sendCommand(command);
    }

    splitAmount(amount, dec = 2) {
        const factor = 10 ** dec;
        const normalized = (Math.round(asNumber(amount, 0) * factor) / factor).toFixed(
            dec
        );
        const parts = normalized.split(".");
        return [parts[0] || "0", parts[1] || "".padEnd(dec, "0")];
    }

    _limitDecimals(value, decimals) {
        const n = asNumber(value, 0);
        const factor = 10 ** decimals;
        return Math.round(n * factor) / factor;
    }

    groupPayments(paymentLines) {
        const grouped = new Map();
        for (const payment of toArray(paymentLines)) {
            const method = normalizePaymentMethod(
                payment.payment_method ?? payment.paymentMethod
            );
            const amount = asNumber(payment.amount, 0);
            grouped.set(method, asNumber(grouped.get(method), 0) + amount);
        }
        return [...grouped.entries()].map(([payment_method, amount]) => ({
            payment_method,
            amount: Math.abs(amount),
        }));
    }

    _appendGroupedPaymentCommands(cmd, paymentLines, config) {
        const rawLines = toArray(paymentLines);
        const grouped = this.groupPayments(rawLines);
        if (!grouped.length) {
            return grouped;
        }
        const firstRawAmount = asNumber(rawLines[0]?.amount, 0);
        const allMethod20 =
            grouped.length > 1 &&
            grouped.every((payment) => payment.payment_method === "20");
        if (grouped.length === 1 || firstRawAmount === 0 || allMethod20) {
            const method = grouped[0].payment_method || "01";
            cmd.push(`1${method}`);
            return grouped;
        }
        for (const payment of grouped) {
            if (payment.amount <= 0) {
                continue;
            }
            const [amountI, amountD] = this.splitAmount(
                this._limitDecimals(payment.amount, config.maxPaymentAmountDecimal),
                config.maxPaymentAmountDecimal
            );
            cmd.push(
                `2${payment.payment_method}${amountI.padStart(
                    config.maxPaymentAmountInt,
                    "0"
                )}${amountD}`
            );
        }
        return grouped;
    }

    formatInvoiceLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return {line: null, discount: Math.abs(priceUnit)};
        }
        const taxValue = TAX_MAP[mapTaxCodeFromLine(item)] || "";
        const code = item.default_code
            ? `|${item.default_code}|`
            : item.code
              ? `|${item.code}|`
              : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            taxValue,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return {line, discount: 0};
    }

    formatRefundLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return {line: null, discount: Math.abs(priceUnit)};
        }
        const taxCode = mapTaxCodeFromLine(item);
        const code = item.default_code
            ? `|${item.default_code}|`
            : item.code
              ? `|${item.code}|`
              : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            "d",
            taxCode,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return {line, discount: 0};
    }

    formatDebitLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return {line: null, discount: Math.abs(priceUnit)};
        }
        const taxCode = mapTaxCodeFromLine(item);
        const code = item.default_code
            ? `|${item.default_code}|`
            : item.code
              ? `|${item.code}|`
              : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            "`",
            taxCode,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return {line, discount: 0};
    }

    _resolveFlag21(flag21) {
        const key = String(flag21 ?? "30").replace(/^0+(\d)$/, "$1");
        if (FLAG_21[key] !== undefined) {
            return FLAG_21[key];
        }
        return FLAG_21[30];
    }

    _normalizeFlag21Value(flag21) {
        const txt = String(flag21 ?? "30").trim();
        if (txt === "00" || txt === "0") {
            return "00";
        }
        if (txt === "01" || txt === "1") {
            return "01";
        }
        if (txt === "02" || txt === "2") {
            return "02";
        }
        return "30";
    }

    _normalizePartner(partner = {}) {
        return {
            vat: String(partner.vat || partner.rif || "").trim(),
            name: String(partner.name || partner.display_name || "").trim(),
            address: String(partner.address || partner.street || "").trim(),
            phone: String(partner.phone || partner.mobile || "").trim(),
        };
    }

    _formatLineDiscountCommand(item, config) {
        let discountAmount = asNumber(item.discount_amount, 0);
        if (discountAmount <= 0) {
            const discountPercent = asNumber(item.discount, 0);
            const priceUnit = asNumber(item.price_unit, 0);
            const quantity = asNumber(item.quantity, 0);
            if (discountPercent > 0 && priceUnit > 0 && quantity > 0) {
                discountAmount =
                    (Math.abs(priceUnit) * Math.abs(quantity) * discountPercent) / 100;
            }
        }
        if (discountAmount <= 0) {
            return null;
        }
        const [amountI, amountD] = this.splitAmount(
            this._limitDecimals(Math.abs(discountAmount), config.discDecimal),
            config.discDecimal
        );
        return `q-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
            config.discDecimal,
            "0"
        )}`;
    }

    _formatGlobalDiscountCommand(amount, config) {
        if (amount <= 0) {
            return null;
        }
        const [amountI, amountD] = this.splitAmount(
            this._limitDecimals(amount, config.discDecimal),
            config.discDecimal
        );
        return `q-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
            config.discDecimal,
            "0"
        )}`;
    }

    _normalizeAccountMoveInvoiceLines(move) {
        const lines =
            move.invoice_lines || move.invoiceLineIds || move.invoice_line_ids || [];
        const out = [];
        for (const line of toArray(lines)) {
            if (line.display_type && line.display_type !== "product") {
                continue;
            }
            out.push({
                default_code: line.default_code || line.code || "",
                name: line.name || line.product_name || "",
                quantity: asNumber(line.quantity, 0),
                price_unit: asNumber(line.price_unit, 0),
                discount: asNumber(line.discount, 0),
                discount_amount: asNumber(line.discount_amount, 0),
                tax: mapTaxCodeFromLine(line),
            });
        }
        return out;
    }

    _normalizeInvoiceFromAccountMove(move, options = {}) {
        const partner = this._normalizePartner(
            options.partner || move.partner || move.partner_id || {}
        );
        const paymentLines = toArray(
            options.payment_lines || options.paymentLines || move.payment_lines
        );
        const data = {
            company_id: options.company_id || move.company_id || move.company || null,
            flag_21: String(options.flag_21 || options.flag21 || move.flag_21 || "30"),
            partner_id: partner,
            invoice_lines:
                options.invoice_lines || this._normalizeAccountMoveInvoiceLines(move),
            payment_lines: paymentLines,
            info: toArray(options.info || move.info),
            aditional_lines: toArray(
                options.aditional_lines ||
                    options.additional_lines ||
                    move.aditional_lines
            ),
            has_cashbox: Boolean(options.has_cashbox || move.has_cashbox),
            global_discount_amount: asNumber(
                options.global_discount_amount ?? move.global_discount_amount,
                0
            ),
            invoice_affected: options.invoice_affected || move.invoice_affected || null,
            use_barcode: Boolean(
                options.use_barcode ??
                    move.use_barcode ??
                    options.fiscal_machine?.use_barcode
            ),
            barcode: options.barcode || move.barcode || null,
        };
        return {data};
    }

    _resolveBarcodeValue(invoice) {
        if (!invoice?.use_barcode) {
            return null;
        }
        const raw = invoice.barcode;
        if (Array.isArray(raw)) {
            return raw.length ? String(raw[0] || "").trim() : null;
        }
        if (raw === null || raw === undefined || raw === false) {
            return null;
        }
        return String(raw).trim() || null;
    }

    _appendBarcodeCommand(cmd, invoice) {
        const barcode = this._resolveBarcodeValue(invoice);
        if (barcode) {
            cmd.push(`y${barcode}`);
        }
    }

    normalizeInvoicePayload(input, options = {}) {
        const normalized = maybeDataWrapper(input);
        const configuredFlag21 = options.flag_21 || options.flag21;
        if (normalized.invoice_lines && normalized.payment_lines) {
            return {
                data: {
                    ...normalized,
                    flag_21: this._normalizeFlag21Value(
                        configuredFlag21 || normalized.flag_21
                    ),
                },
            };
        }
        if (
            normalized.move_type ||
            normalized.invoice_line_ids ||
            normalized.invoice_lines
        ) {
            const movePayload = this._normalizeInvoiceFromAccountMove(
                normalized,
                options
            );
            movePayload.data.flag_21 = this._normalizeFlag21Value(
                configuredFlag21 || movePayload.data.flag_21
            );
            return movePayload;
        }
        return {
            data: {
                ...normalized,
                flag_21: this._normalizeFlag21Value(
                    configuredFlag21 || normalized.flag_21
                ),
            },
        };
    }

    validateInvoiceParameter(invoicePayload) {
        const msg = [];
        let valid = true;
        const invoice = this.normalizeInvoicePayload(invoicePayload).data;
        if (!invoice || Object.keys(invoice).length === 0) {
            return {valid: false, message: ["No se recibió información de la factura"]};
        }
        const required = {
            company_id: "No se encontró la empresa",
            partner_id: "No se recibió información del cliente",
            invoice_lines: "No se recibió información de los productos",
            payment_lines: "No se recibió información de los pagos",
        };
        for (const [field, error] of Object.entries(required)) {
            const value = invoice[field];
            if (!value || (Array.isArray(value) && value.length === 0)) {
                valid = false;
                msg.push(error);
            }
        }
        const partner = invoice.partner_id || {};
        if (!partner.vat) {
            valid = false;
            msg.push("El cliente no tiene cédula");
        }
        if (!partner.name) {
            valid = false;
            msg.push("El cliente no tiene nombre");
        }
        for (const line of toArray(invoice.invoice_lines)) {
            if (line.price_unit === undefined) {
                valid = false;
                msg.push("No se encontró el precio del producto");
            }
            if (line.quantity === undefined) {
                valid = false;
                msg.push("No se encontró la cantidad del producto");
            }
            if (!line.name) {
                valid = false;
                msg.push("No se encontró el nombre del producto");
            }
            const tax = parseInt(mapTaxCodeFromLine(line), 10);
            if (!Number.isFinite(tax) || tax < 0 || tax > 4) {
                valid = false;
                msg.push("El impuesto no es válido");
            }
        }
        for (const line of toArray(invoice.payment_lines)) {
            if (line.amount === undefined) {
                valid = false;
                msg.push("No se recibió el monto del pago");
            }
            const paymentMethod = parseInt(
                normalizePaymentMethod(line.payment_method),
                10
            );
            if (
                !Number.isFinite(paymentMethod) ||
                paymentMethod < 1 ||
                paymentMethod > 24
            ) {
                valid = false;
                msg.push("El método de pago no es aceptado o no se recibió");
            }
        }
        return {valid, message: msg};
    }

    validateOutRefundParameter(invoicePayload) {
        const msg = [];
        let valid = true;
        const invoice = this.normalizeInvoicePayload(invoicePayload).data;
        if (!invoice || Object.keys(invoice).length === 0) {
            return {
                valid: false,
                message: ["No se recibió información de la nota de crédito"],
            };
        }
        if (!invoice.company_id) {
            valid = false;
            msg.push("No se encontró la empresa");
        }
        if (!invoice.partner_id) {
            return {valid: false, message: ["No se recibió información del cliente"]};
        }
        if (!invoice.invoice_affected) {
            return {
                valid: false,
                message: ["No se recibió información de la factura afectada"],
            };
        }
        const partner = invoice.partner_id || {};
        if (!partner.vat) {
            valid = false;
            msg.push("El cliente no tiene cédula");
        }
        if (!partner.name) {
            valid = false;
            msg.push("El cliente no tiene nombre");
        }
        const affected = invoice.invoice_affected || {};
        if (!affected.number) {
            valid = false;
            msg.push("No se recibió una factura afectada");
        }
        if (!affected.serial_machine) {
            valid = false;
            msg.push("No se recibió el serial de la máquina fiscal");
        }
        if (!affected.date) {
            valid = false;
            msg.push("No se recibió la fecha de la factura afectada");
        }
        if (!toArray(invoice.invoice_lines).length) {
            valid = false;
            msg.push("No se recibió información de los productos");
        }
        if (!toArray(invoice.payment_lines).length) {
            valid = false;
            msg.push("No se recibió información de los pagos");
        }
        return {valid, message: msg};
    }

    prepareInvoiceData(invoicePayload, options = {}) {
        try {
            const {data: invoice} = this.normalizeInvoicePayload(
                invoicePayload,
                options
            );
            const config = this._resolveFlag21(invoice.flag_21);
            const cmd = [];
            const partner = this._normalizePartner(invoice.partner_id || {});
            cmd.push(`iR*${partner.vat}`);
            cmd.push(`iS*${cleanText(partner.name, 120)}`);
            let nextIndex = 0;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`
                );
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`
                );
                nextIndex += 1;
            }
            let discount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const {line, discount: lineDiscount} = this.formatInvoiceLine(
                    item,
                    config
                );
                if (line) {
                    cmd.push(line);
                }
                if (lineDiscount) {
                    discount += lineDiscount;
                }
                const discountCmd = this._formatLineDiscountCommand(item, config);
                if (discountCmd) {
                    cmd.push(discountCmd);
                }
            }
            cmd.push("3");
            const globalDiscountAmount =
                discount + asNumber(invoice.global_discount_amount, 0);
            const globalDiscountCmd = this._formatGlobalDiscountCommand(
                globalDiscountAmount,
                config
            );
            if (globalDiscountCmd) {
                cmd.push(globalDiscountCmd);
            }
            const paymentLines = this._appendGroupedPaymentCommands(
                cmd,
                invoice.payment_lines,
                config
            );
            this._appendBarcodeCommand(cmd, invoice);
            if (invoice.has_cashbox) {
                cmd.push("w");
            }
            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");
            return {valid: true, cmd, discount, payment_lines: paymentLines};
        } catch (error) {
            return {valid: false, message: error.message || String(error)};
        }
    }

    prepareOutRefundData(invoicePayload, options = {}) {
        try {
            const {data: invoice} = this.normalizeInvoicePayload(
                invoicePayload,
                options
            );
            const config = this._resolveFlag21(invoice.flag_21);
            const affected = invoice.invoice_affected || {};
            const partner = this._normalizePartner(invoice.partner_id || {});
            const cmd = [
                `iF*${String(affected.number || "").padStart(8, "0")}`,
                `iD*${String(affected.date || "")}`,
                `iI*${String(affected.serial_machine || "")}`,
                `iR*${partner.vat}`,
                `iS*${cleanText(partner.name, 120)}`,
            ];
            let nextIndex = 1;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`
                );
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`
                );
                nextIndex += 1;
            }
            let discountAmount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const {line, discount} = this.formatRefundLine(item, config);
                if (line) {
                    cmd.push(line);
                }
                if (discount) {
                    discountAmount += discount;
                }
                const discountCmd = this._formatLineDiscountCommand(item, config);
                if (discountCmd) {
                    cmd.push(discountCmd);
                }
            }
            cmd.push("3");
            const globalDiscountAmount =
                discountAmount + asNumber(invoice.global_discount_amount, 0);
            const globalDiscountCmd = this._formatGlobalDiscountCommand(
                globalDiscountAmount,
                config
            );
            if (globalDiscountCmd) {
                cmd.push(globalDiscountCmd);
            }
            const paymentLines = this._appendGroupedPaymentCommands(
                cmd,
                invoice.payment_lines,
                config
            );
            this._appendBarcodeCommand(cmd, invoice);
            if (invoice.has_cashbox) {
                cmd.push("w");
            }
            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");
            return {valid: true, cmd, payment_lines: paymentLines};
        } catch (error) {
            return {valid: false, message: error.message || String(error)};
        }
    }

    prepareDebitNoteData(invoicePayload, options = {}) {
        try {
            const {data: invoice} = this.normalizeInvoicePayload(
                invoicePayload,
                options
            );
            const config = this._resolveFlag21(invoice.flag_21);
            const affected = invoice.invoice_affected || {};
            const partner = this._normalizePartner(invoice.partner_id || {});
            const cmd = [
                `iR*${partner.vat}`,
                `iS*${cleanText(partner.name, 120)}`,
                `iF*${String(affected.number || "").padStart(8, "0")}`,
                `iI*${String(affected.serial_machine || "")}`,
                `iD*${String(affected.date || "")}`,
            ];

            let nextIndex = 0;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`
                );
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`
                );
                nextIndex += 1;
            }

            let discountAmount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const {line, discount} = this.formatDebitLine(item, config);
                if (line) {
                    cmd.push(line);
                }
                if (discount) {
                    discountAmount += discount;
                }
                const discountCmd = this._formatLineDiscountCommand(item, config);
                if (discountCmd) {
                    cmd.push(discountCmd);
                }
            }

            cmd.push("3");

            const globalDiscountAmount =
                discountAmount + asNumber(invoice.global_discount_amount, 0);
            const globalDiscountCmd = this._formatGlobalDiscountCommand(
                globalDiscountAmount,
                config
            );
            if (globalDiscountCmd) {
                cmd.push(globalDiscountCmd);
            }

            const paymentLines = this._appendGroupedPaymentCommands(
                cmd,
                invoice.payment_lines,
                config
            );
            this._appendBarcodeCommand(cmd, invoice);

            if (invoice.has_cashbox) {
                cmd.push("w");
            }

            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");

            return {valid: true, cmd, payment_lines: paymentLines};
        } catch (error) {
            return {valid: false, message: error.message || String(error)};
        }
    }

    async sendInvoiceCommands(commandPayload, options = {}) {
        try {
            const cmd = toArray(commandPayload?.cmd || commandPayload);
            const start = options.progressStart ?? 0;
            const end = options.progressEnd ?? 100;
            const span = end - start;
            this._notifyProgress(options, start, "Enviando comandos...");
            const skipStatus =
                Boolean(commandPayload?.use_emulator) ||
                Boolean(commandPayload?.useEmulator);
            if (!skipStatus) {
                await this._ensureStatusReady();
            }
            const msg = [];
            for (let index = 0; index < cmd.length; index++) {
                const command = cmd[index];
                const sent = await this.driver.sendCmd(String(command));
                if (!sent && !["101", "199"].includes(String(command))) {
                    msg.push(`Fallo al enviar comando: ${command}`);
                    await this.driver.sendCmd("199");
                    return {valid: false, message: msg, continue: false};
                }
                await sleep(this.commandDelayMs);
                const progressIndex = index + 1;
                const ratio = cmd.length ? progressIndex / cmd.length : 1;
                this._notifyProgress(
                    options,
                    start + ratio * span,
                    `Imprimiendo... ${progressIndex}/${cmd.length} comandos`
                );
            }
            return {valid: true, msg, continue: true};
        } catch (error) {
            return {
                valid: false,
                message: error.message || String(error),
                continue: false,
            };
        }
    }

    _s1Trace(stage, s1, extra = {}) {
        const parsed = s1
            ? {
                  LastInvoiceNumber: s1.LastInvoiceNumber,
                  LastCreditNoteNumber: s1.LastCreditNoteNumber,
                  RegisteredMachineNumber: s1.RegisteredMachineNumber,
                  DailyClosureCounter: s1.DailyClosureCounter,
                  DailySalesTotal: s1.DailySalesTotal,
                  CashierCode: s1.CashierCode,
                  InvoicesCountDay: s1.InvoicesCountDay,
              }
            : null;
        const rawStr = s1?.raw !== null && s1?.raw !== undefined ? String(s1.raw) : "";
        console.log("[l10n_ve_fiscal_serial][s1]", stage, {
            ...extra,
            parsed,
            rawLineCount: rawStr ? rawStr.split("\n").length : 0,
            rawPreview: rawStr ? rawStr.slice(0, 800) : null,
        });
    }

    _toIntOrNull(value) {
        if (value === undefined || value === null || value === "") {
            return null;
        }
        const n = parseInt(String(value), 10);
        return Number.isFinite(n) ? n : null;
    }

    _isEmulatorMode(invoicePayload) {
        return Boolean(
            invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator
        );
    }

    _nextEmulatorInvoiceSequence(baseValue = null) {
        const base = this._toIntOrNull(baseValue);
        if (base !== null && base > EMULATOR_INVOICE_SEQUENCE) {
            EMULATOR_INVOICE_SEQUENCE = base;
        }
        EMULATOR_INVOICE_SEQUENCE += 1;
        return EMULATOR_INVOICE_SEQUENCE;
    }

    _nextEmulatorCreditNoteSequence(baseValue = null) {
        const base = this._toIntOrNull(baseValue);
        if (base !== null && base > EMULATOR_CREDIT_NOTE_SEQUENCE) {
            EMULATOR_CREDIT_NOTE_SEQUENCE = base;
        }
        EMULATOR_CREDIT_NOTE_SEQUENCE += 1;
        return EMULATOR_CREDIT_NOTE_SEQUENCE;
    }

    _nextEmulatorReportZ(baseClosureCounter = null) {
        const base = this._toIntOrNull(baseClosureCounter);
        if (base !== null) {
            const nextFromS1 = base + 1;
            if (nextFromS1 > EMULATOR_LAST_REPORT_Z) {
                EMULATOR_LAST_REPORT_Z = nextFromS1;
            } else {
                EMULATOR_LAST_REPORT_Z += 1;
            }
        } else {
            EMULATOR_LAST_REPORT_Z += 1;
        }
        return EMULATOR_LAST_REPORT_Z;
    }

    async getS1PrinterData(debugStage) {
        const traceLabel = typeof debugStage === "string" ? debugStage : null;
        if (!this.driver || typeof this.driver.uploadStatusCmdToString !== "function") {
            return null;
        }
        const result = await this.driver.uploadStatusCmdToString("S1");
        if (!result?.ok || !result.content) {
            if (traceLabel) {
                this._s1Trace(`${traceLabel}_empty`, null, {
                    ok: result?.ok,
                    contentLength:
                        result?.content !== null && result?.content !== undefined
                            ? String(result.content).length
                            : 0,
                });
            }
            return null;
        }
        const parsed = this.s1Parser(result.content);
        if (traceLabel) {
            this._s1Trace(traceLabel, parsed, {
                contentLength: String(result.content).length,
            });
        }
        return parsed;
    }

    async finalizeInvoice() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastInvoiceNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz: mfReportzFromDailyClosureString(s1?.DailyClosureCounter),
            },
            message: "Factura impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async finalizeOutRefund() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastCreditNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz: mfReportzFromDailyClosureString(s1?.DailyClosureCounter),
            },
            message: "Nota de crédito impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async finalizeDebitNote() {
        const s1 = await this.getS1PrinterData("print_debit_note_post");
        return {
            valid: true,
            data: {
                sequence: s1?.LastDebitNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz: mfReportzFromDailyClosureString(s1?.DailyClosureCounter),
                parsed_post: s1,
            },
            message: "Nota de débito impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async printOutInvoice(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateInvoiceParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const isEmulator = this._isEmulatorMode(invoicePayload);
        this._notifyProgress(options, 10, "Consultando S1 inicial...");
        const preS1 = await this.getS1PrinterData("print_out_invoice_pre");
        const preSequence = this._toIntOrNull(preS1?.LastInvoiceNumber);
        const prepared = this.prepareInvoiceData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator = isEmulator;
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 20,
            progressEnd: 80,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 90, "Consultando S1 final...");
        const postS1 = await this.getS1PrinterData("print_out_invoice_post");
        let postSequence = this._toIntOrNull(postS1?.LastInvoiceNumber);
        let serialMachine =
            postS1?.RegisteredMachineNumber || preS1?.RegisteredMachineNumber || null;
        let reportZ =
            mfReportzFromDailyClosureString(postS1?.DailyClosureCounter) ||
            mfReportzFromDailyClosureString(preS1?.DailyClosureCounter) ||
            null;

        if (isEmulator) {
            postSequence = this._nextEmulatorInvoiceSequence(
                preSequence ?? postSequence
            );
            if (!serialMachine) {
                serialMachine = EMULATOR_MACHINE_SERIAL;
            }
            const closureCounter =
                postS1?.DailyClosureCounter ?? preS1?.DailyClosureCounter ?? null;
            reportZ = String(this._nextEmulatorReportZ(closureCounter)).padStart(
                4,
                "0"
            );
        } else {
            if (
                preSequence !== null &&
                postSequence !== null &&
                postSequence <= preSequence
            ) {
                const detailMsg = `No se imprimió el documento fiscal: correlativo factura S1 antes=${preSequence} después=${postSequence}. Revise [l10n_ve_fiscal_serial][s1] en consola (pre/post).`;
                console.warn(
                    "[l10n_ve_fiscal_serial][s1] validación correlativo fallida",
                    {
                        preSequence,
                        postSequence,
                        preParsed: preS1,
                        postParsed: postS1,
                    }
                );
                return {
                    valid: false,
                    message: detailMsg,
                    data: {
                        sequence_before: preSequence,
                        sequence_after: postSequence,
                        parsed_pre: preS1,
                        parsed_post: postS1,
                        raw_pre: preS1?.raw || null,
                        raw_post: postS1?.raw || null,
                    },
                };
            }

            if (preSequence === null && postSequence === null) {
                console.warn("[l10n_ve_fiscal_serial][s1] sin correlativo parseado", {
                    preParsed: preS1,
                    postParsed: postS1,
                });
                return {
                    valid: false,
                    message:
                        "No se pudo validar la impresión fiscal: S1 no devolvió correlativo de factura antes ni después. Revise consola [s1] y el preview del comando S1.",
                    data: {
                        parsed_pre: preS1,
                        parsed_post: postS1,
                        raw_pre: preS1?.raw || null,
                        raw_post: postS1?.raw || null,
                    },
                };
            }
        }

        this._notifyProgress(options, 100, "Imprimiendo... 100%");

        this._s1Trace("print_out_invoice_ok", postS1, {
            preSequence,
            postSequence,
            serialMachine,
            reportZ,
            emulator: isEmulator,
        });

        const sequenceDisplay = isEmulator
            ? String(postSequence).padStart(8, "0")
            : postS1?.LastInvoiceNumber ||
              (postSequence !== null && postSequence !== undefined
                  ? String(postSequence).padStart(8, "0")
                  : null) ||
              preS1?.LastInvoiceNumber ||
              null;

        return {
            valid: true,
            data: {
                sequence: sequenceDisplay,
                serial_machine: serialMachine,
                mf_reportz: reportZ,
                parsed_pre: preS1,
                parsed_post: postS1,
            },
            message: "Factura impresa correctamente",
            raw_status: {
                pre_s1: preS1?.raw || null,
                post_s1: postS1?.raw || null,
            },
        };
    }

    async printOutRefund(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateOutRefundParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const isEmulator = this._isEmulatorMode(invoicePayload);
        this._notifyProgress(options, 8, "Consultando S1 inicial (NC)…");
        const preS1 = await this.getS1PrinterData("print_out_refund_pre");
        const preNc = this._toIntOrNull(preS1?.LastCreditNoteNumber);
        const prepared = this.prepareOutRefundData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator =
            Boolean(
                invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator
            ) || isEmulator;
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 15,
            progressEnd: 85,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 90, "Consultando S1 final (NC)…");
        const postS1 = await this.getS1PrinterData("print_out_refund_post");
        let postNc = this._toIntOrNull(postS1?.LastCreditNoteNumber);
        let serialMachine =
            postS1?.RegisteredMachineNumber || preS1?.RegisteredMachineNumber || null;
        let reportZ =
            mfReportzFromDailyClosureString(postS1?.DailyClosureCounter) ||
            mfReportzFromDailyClosureString(preS1?.DailyClosureCounter) ||
            null;

        if (isEmulator) {
            postNc = this._nextEmulatorCreditNoteSequence(preNc ?? postNc);
            if (!serialMachine) {
                serialMachine = EMULATOR_MACHINE_SERIAL;
            }
            const closureCounter =
                postS1?.DailyClosureCounter ?? preS1?.DailyClosureCounter ?? null;
            reportZ = String(this._nextEmulatorReportZ(closureCounter)).padStart(
                4,
                "0"
            );
        } else {
            if (preNc !== null && postNc !== null && postNc <= preNc) {
                const detailMsg = `No se imprimió la nota de crédito fiscal: correlativo NC en S1 antes=${preNc} después=${postNc}. Revise [l10n_ve_fiscal_serial][s1] en consola (pre/post).`;
                console.warn(
                    "[l10n_ve_fiscal_serial][s1] validación correlativo NC fallida",
                    {
                        preNc,
                        postNc,
                        preParsed: preS1,
                        postParsed: postS1,
                    }
                );
                return {
                    valid: false,
                    message: detailMsg,
                    data: {
                        sequence_before: preNc,
                        sequence_after: postNc,
                        parsed_pre: preS1,
                        parsed_post: postS1,
                        raw_pre: preS1?.raw || null,
                        raw_post: postS1?.raw || null,
                    },
                };
            }

            if (preNc === null && postNc === null) {
                console.warn(
                    "[l10n_ve_fiscal_serial][s1] sin correlativo NC parseado",
                    {
                        preParsed: preS1,
                        postParsed: postS1,
                    }
                );
                return {
                    valid: false,
                    message:
                        "No se pudo validar la impresión fiscal: S1 no devolvió correlativo de nota de crédito antes ni después.",
                    data: {
                        parsed_pre: preS1,
                        parsed_post: postS1,
                        raw_pre: preS1?.raw || null,
                        raw_post: postS1?.raw || null,
                    },
                };
            }
        }

        this._notifyProgress(options, 100, "Imprimiendo... 100%");

        const ncDisplay = isEmulator
            ? String(postNc).padStart(8, "0")
            : postS1?.LastCreditNoteNumber ||
              (postNc !== null && postNc !== undefined
                  ? String(postNc).padStart(8, "0")
                  : null) ||
              preS1?.LastCreditNoteNumber;

        this._s1Trace("print_out_refund_ok", postS1, {
            preNc,
            postNc,
            serialMachine,
            reportZ,
            ncDisplay,
        });

        return {
            valid: true,
            data: {
                sequence: ncDisplay,
                serial_machine: serialMachine,
                mf_reportz: reportZ,
                parsed_pre: preS1,
                parsed_post: postS1,
            },
            message: "Nota de crédito impresa correctamente",
            raw_status: {
                pre_s1: preS1?.raw || null,
                post_s1: postS1?.raw || null,
            },
        };
    }

    async printDebitNote(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateOutRefundParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const prepared = this.prepareDebitNoteData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator = Boolean(
            invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator
        );
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 10,
            progressEnd: 90,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 100, "Imprimiendo... 100%");
        return this.finalizeDebitNote();
    }

    async logger(data) {
        await this._ensureStatusReady();
        await this._sendCommand(String(maybeDataWrapper(data)));
        return {valid: true};
    }

    async loggerMulti(data) {
        for (const line of toArray(maybeDataWrapper(data))) {
            await this._sendCommand(String(line));
        }
        return {valid: true};
    }

    _normalizeFlag50Value(value) {
        const key = String(value ?? "01").padStart(2, "0");
        return key === "00" ? "00" : "01";
    }

    _paymentMethodCommands(payload = {}) {
        const methods = toArray(payload.payment_methods || payload.paymentMethods);
        if (methods.length) {
            return methods
                .map((method) => {
                    const code = String(method.code || method.payment_method || "")
                        .trim()
                        .padStart(2, "0")
                        .slice(-2);
                    const name = cleanText(method.name || "", 14);
                    if (!code || Number(code) < 1 || Number(code) > 24 || !name) {
                        return null;
                    }
                    return `PE${code}${name}`;
                })
                .filter(Boolean);
        }
        return [
            "PE01EFECTIVO 01",
            "PE02EFECTIVO 02",
            "PE03PAGO MOVIL 01",
            "PE04PAGO MOVIL 02",
            "PE05PAGO MOVIL 03",
            "PE06PAGO MOVIL 04",
            "PE07TRANSFERENCIA 01",
            "PE08TRANSFERENCIA 02",
            "PE09TRANSFERENCIA 03",
            "PE10TRANSFERENCIA 04",
            "PE11PDV 01",
            "PE12PDV 02",
            "PE13PDV 03",
            "PE14PDV 04",
            "PE15CREDITO 01",
            "PE16CREDITO 02",
            "PE17CREDITO 03",
            "PE18CREDITO 04",
            "PE19DIVISA 02",
            "PE20DIVISA 01",
            "PE21ZELLE",
            "PE22DIVISA 03",
            "PE23DIVISA 04",
            "PE24OTRO",
        ];
    }

    _footerCommands(payload = {}) {
        const lines = toArray(payload.footer_lines || payload.footerLines);
        return lines
            .slice(0, 8)
            .map((line, index) => {
                const text = cleanText(line, 40);
                if (!text) {
                    return null;
                }
                return `PH${String(91 + index).padStart(2, "0")}${text}`;
            })
            .filter(Boolean);
    }

    async configureDevice(data, options = {}) {
        const payload = maybeDataWrapper(data);
        const flag21 = payload.flag_21
            ? this._normalizeFlag21Value(payload.flag_21)
            : null;
        const flag50 = payload.flag_50
            ? this._normalizeFlag50Value(payload.flag_50)
            : null;
        const paymentCommands = this._paymentMethodCommands(payload);
        const footerCommands = this._footerCommands(payload);
        const totalSteps =
            (flag21 ? 1 : 0) +
            (flag50 ? 1 : 0) +
            (payload.flag_24 ? 1 : 0) +
            (payload.show_version ? 1 : 0) +
            1 +
            paymentCommands.length +
            footerCommands.length;
        let step = 0;
        const advance = (message) => {
            step += 1;
            const percent = totalSteps ? Math.round((step / totalSteps) * 100) : 100;
            this._notifyProgress(options, percent, message);
        };

        this._notifyProgress(options, 0, "Configurando máquina fiscal...");
        await this._ensureStatusReady();
        if (flag21) {
            await this._sendCommand(`PJ21${flag21}`);
            advance("Enviando FLAG 21...");
        }
        if (flag50) {
            await this._sendCommand(`PJ50${flag50}`);
            advance("Enviando FLAG 50...");
        }
        if (payload.flag_24) {
            await this._sendCommand(`PJ24${payload.flag_24}`);
            advance("Enviando FLAG 24...");
        }
        if (payload.show_version) {
            await this._sendCommand(`PJ77${payload.show_version}`);
            advance("Enviando versión...");
        }
        await this._sendCommand("PJ6300");
        advance("Aplicando parámetros...");
        for (const line of paymentCommands) {
            await this._sendCommand(line);
            advance("Programando métodos de pago...");
        }
        for (const line of footerCommands) {
            await this._sendCommand(line);
            advance("Programando pie de página...");
        }
        this._notifyProgress(options, 100, "Configuración enviada");
        return {
            valid: true,
            message:
                `Configuración enviada: FLAG_21=${flag21 || "-"}, ` +
                `FLAG_50=${flag50 || "-"}, ` +
                `${paymentCommands.length} métodos de pago` +
                (footerCommands.length
                    ? `, ${footerCommands.length} líneas de pie`
                    : "") +
                ".",
            flag_21: flag21,
            flag_50: flag50,
            payment_methods: paymentCommands.length,
            footer_lines: footerCommands.length,
        };
    }

    async configureMachineFlag21(flag21, options = {}) {
        const normalizedFlag = this._normalizeFlag21Value(flag21);
        const flag50 = this._normalizeFlag50Value(options.flag_50 || options.flag50);
        this._notifyProgress(options, 0, "Imprimiendo...");
        await this._sendCommand(`PJ21${normalizedFlag}`);
        this._notifyProgress(options, 30, "Imprimiendo... 30%");
        await this._sendCommand(`PJ50${flag50}`);
        this._notifyProgress(options, 60, "Imprimiendo... 60%");
        await this._sendCommand("PJ1701");
        this._notifyProgress(options, 85, "Imprimiendo... 85%");
        await this._sendCommand("D");
        this._notifyProgress(options, 100, "Imprimiendo... 100%");
        return {
            valid: true,
            message: `Configuración fiscal enviada con FLAG_21=${normalizedFlag}, FLAG_50=${flag50}.`,
            flag_21: normalizedFlag,
            flag_50: flag50,
        };
    }

    async test() {
        await this._ensureStatusReady();
        await this._sendCommand("7");
        await this._sendCommand("800");
        await this._sendCommand("80$Binaural Test");
        await this._sendCommand("80!Documento de pruebas");
        await this._sendCommand("810");
        return {valid: true, message: "Test impreso correctamente."};
    }

    async printResume(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const from = String(payload.resume_range_from || "");
        const to = String(payload.resume_range_to || "");
        await this._sendCommand(`I2S${from}${to}`);
        return {valid: true, message: "Resumen impreso correctamente."};
    }

    async reprintDate(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const mode = payload.mode || "Rs";
        const from = String(payload.reprint_range_from || "").padStart(7, "0");
        const to = String(payload.reprint_range_to || "").padStart(7, "0");
        await this._sendCommand(`${mode}${from}${to}`);
        return {valid: true, message: "Reimpresión por fecha enviada."};
    }

    async reprintType(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const mode = payload.mode || "R@";
        const from = String(payload.reprint_range_from || "").padStart(7, "0");
        const to = String(payload.reprint_range_to || "").padStart(7, "0");
        await this._sendCommand(`${mode}${from}${to}`);
        return {valid: true, message: "Reimpresión por tipo enviada."};
    }

    async reprint(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const docType = payload.reprint_document_type || payload.type;
        let mode = "";
        if (docType === "debit_note") {
            mode = "RD";
        } else if (docType === "out_invoice") {
            mode = "RF";
        } else if (docType === "out_refund") {
            mode = "RC";
        }
        if (!mode) {
            return {valid: false, message: "Datos no válidos"};
        }
        const number = formatReprintFiscalNumber(payload.mf_number);
        await this._sendCommand(`${mode}${number}${number}`);
        return {valid: true, message: "Reimpresión enviada correctamente."};
    }

    async _waitUntilReadyAfterReport({attempts = 60, delayMs = 500} = {}) {
        let lastError = null;
        for (let index = 0; index < attempts; index++) {
            try {
                await this._ensureStatusReady();
                return true;
            } catch (error) {
                lastError = error;
                await sleep(delayMs);
            }
        }
        if (lastError) {
            throw lastError;
        }
        return false;
    }

    _nextDailyClosureCounter(value) {
        const digits = String(value || "").replace(/\D/g, "");
        if (!digits) {
            return null;
        }
        const width = Math.max(digits.length, 4);
        return String(Number.parseInt(digits, 10) + 1).padStart(width, "0");
    }

    async printXReport() {
        await this._ensureStatusReady();
        await this._sendReportCommand("I0X", 4);
        await this._waitUntilReadyAfterReport({attempts: 40, delayMs: 500});
        return {valid: true, message: "Reporte X impreso correctamente."};
    }

    async printZReport() {
        const preS1 = await this.getS1PrinterData("report_z_pre");
        await this._ensureStatusReady();
        await this._sendReportCommand("I0Z", 9);
        await this._waitUntilReadyAfterReport({attempts: 90, delayMs: 500});
        const postS1 = await this.getS1PrinterData("report_z_post");
        let dailyClosure = postS1?.DailyClosureCounter || null;
        if (!dailyClosure && preS1?.DailyClosureCounter) {
            dailyClosure = this._nextDailyClosureCounter(preS1.DailyClosureCounter);
        }
        return {
            valid: true,
            message: "Reporte Z impreso correctamente.",
            data: {
                daily_closure_counter: dailyClosure,
                report_z: dailyClosure,
                mf_reportz: mfReportzFromDailyClosureString(dailyClosure),
                serial_machine:
                    postS1?.RegisteredMachineNumber ||
                    preS1?.RegisteredMachineNumber ||
                    null,
                last_invoice_number: postS1?.LastInvoiceNumber || null,
                last_credit_note_number: postS1?.LastCreditNoteNumber || null,
                last_debit_note_number: postS1?.LastDebitNoteNumber || null,
                parsed_post: postS1,
            },
        };
    }

    async programacion() {
        await this._ensureStatusReady();
        await this._sendCommand("D");
        return {valid: true, message: "Programación impresa correctamente."};
    }

    preInvoice(invoicePayload) {
        const validation = this.validateInvoiceParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        return {valid: true, message: "Factura validada."};
    }

    async getLastInvoiceNumber() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastInvoiceNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                number: s1?.LastInvoiceNumber || null,
                report_z: mfReportzFromDailyClosureString(s1?.DailyClosureCounter),
            },
            raw_status: s1?.raw || null,
        };
    }

    async getLastOutRefundNumber() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastCreditNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                number: s1?.LastCreditNoteNumber || null,
                report_z: mfReportzFromDailyClosureString(s1?.DailyClosureCounter),
            },
            raw_status: s1?.raw || null,
        };
    }

    async getStatusMachine() {
        await this._ensureStatusReady();
        return {
            valid: true,
            message: `Estado de la impresora: ${this.driver.descripStatus || this.driver.status || ""}`,
            data: {
                status: this.driver.status,
                error: this.driver.error,
                descripStatus: this.driver.descripStatus,
                descripError: this.driver.descripError,
                erroValid: this.driver.erroValid,
            },
        };
    }

    split_amount(amount, dec = 2) {
        return this.splitAmount(amount, dec);
    }

    group_payments(paymentLines) {
        return this.groupPayments(paymentLines);
    }

    format_invoice_line(item, config) {
        return this.formatInvoiceLine(item, config);
    }

    format_refund_line(item, config) {
        return this.formatRefundLine(item, config);
    }

    prepare_invoice_data(invoicePayload, options = {}) {
        return this.prepareInvoiceData(invoicePayload, options);
    }

    prepare_out_refund_data(invoicePayload, options = {}) {
        return this.prepareOutRefundData(invoicePayload, options);
    }

    prepare_debit_note_data(invoicePayload, options = {}) {
        return this.prepareDebitNoteData(invoicePayload, options);
    }

    validate_invoice_parameter(invoicePayload) {
        return this.validateInvoiceParameter(invoicePayload);
    }

    validate_out_refund_parameter(invoicePayload) {
        return this.validateOutRefundParameter(invoicePayload);
    }

    send_invoice_commands(commandPayload) {
        return this.sendInvoiceCommands(commandPayload);
    }

    print_out_invoice(invoicePayload, options = {}) {
        return this.printOutInvoice(invoicePayload, options);
    }

    print_out_refund(invoicePayload, options = {}) {
        return this.printOutRefund(invoicePayload, options);
    }

    print_debit_note(invoicePayload, options = {}) {
        return this.printDebitNote(invoicePayload, options);
    }

    print_resume(data) {
        return this.printResume(data);
    }

    reprint_date(data) {
        return this.reprintDate(data);
    }

    reprint_type(data) {
        return this.reprintType(data);
    }

    print_x_report() {
        return this.printXReport();
    }

    print_z_report() {
        return this.printZReport();
    }

    get_last_invoice_number() {
        return this.getLastInvoiceNumber();
    }

    get_last_out_refund_number() {
        return this.getLastOutRefundNumber();
    }

    get_status_machine() {
        return this.getStatusMachine();
    }
}

export function createTfhkaFiscalMachine(driver, options = {}) {
    return new TfhkaFiscalMachine(driver, options);
}

export {FLAG_21, TAX_MAP};
export {
    mfReportzFromDailyClosureString,
    parseTfhkaS1StatusResponse,
} from "./tfhka_s1_parser";
