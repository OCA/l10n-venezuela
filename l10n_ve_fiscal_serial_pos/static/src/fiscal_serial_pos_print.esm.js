/* eslint-disable complexity */
import {TfhkaWebSerialTransport} from "@l10n_ve_fiscal_serial/fiscal_serial/tfhka_transport_webserial";
import {_t} from "@web/core/l10n/translation";
import {createFiscalSerialAuditLogger} from "@l10n_ve_fiscal_serial/fiscal_serial/fiscal_serial_audit";

export function l10nVeFiscalSerialPosGetInvoiceJournal(pos) {
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    return order?.invoice_journal_id || pos.config?.invoice_journal_id || false;
}

export function l10nVeFiscalSerialPosGetEmissionMedium(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    return (
        journal?.l10n_ve_emission_medium ||
        pos.config?.l10n_ve_invoice_journal_emission_medium ||
        ""
    );
}

export function l10nVeFiscalSerialPosGetFiscalMachineId(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    if (!journal) {
        return false;
    }
    const machine = journal.l10n_ve_fiscal_machine_id;
    if (!machine) {
        return false;
    }
    if (typeof machine === "object") {
        return Number(machine.id) || false;
    }
    return Number(machine) || false;
}

export function l10nVeFiscalSerialPosIsFiscalMachine(pos) {
    const country =
        pos.company?.country_id?.code || pos.company?.account_fiscal_country_id?.code;
    return (
        country === "VE" &&
        l10nVeFiscalSerialPosGetEmissionMedium(pos) === "fiscal_machine"
    );
}

export function l10nVeFiscalSerialPosGetFiscalMachine(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    const machine = journal?.l10n_ve_fiscal_machine_id;
    if (!machine) {
        return false;
    }
    if (typeof machine === "object") {
        return machine;
    }
    const machineId = Number(machine) || 0;
    if (!machineId) {
        return false;
    }
    return pos.models?.["l10n.ve.fiscal.machine"]?.get?.(machineId) || false;
}

export function l10nVeFiscalSerialPosIncrementCounter(value, minWidth = 8) {
    const digits = String(value || "").replace(/\D/g, "");
    if (!digits) {
        return false;
    }
    const width = Math.max(digits.length, minWidth);
    return String(Number.parseInt(digits, 10) + 1).padStart(width, "0");
}

export function l10nVeFiscalSerialPosLastNumberForPlaceholders(pos, machine) {
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    if (order && typeof order._isRefundOrder === "function" && order._isRefundOrder()) {
        return machine.last_credit_note_number;
    }
    return machine.last_invoice_number;
}

export function l10nVeFiscalSerialPosGetNextPlaceholders(pos) {
    const machine = l10nVeFiscalSerialPosGetFiscalMachine(pos);
    if (!machine) {
        return {
            serial: false,
            invoice_number: false,
            report_z: false,
        };
    }
    return {
        serial: (machine.registered_serial || "").trim() || false,
        invoice_number: l10nVeFiscalSerialPosIncrementCounter(
            l10nVeFiscalSerialPosLastNumberForPlaceholders(pos, machine),
            8
        ),
        report_z: l10nVeFiscalSerialPosIncrementCounter(
            machine.daily_closure_counter,
            4
        ),
    };
}

export function l10nVeFiscalSerialPosIsOffline(pos) {
    return Boolean(pos?.data?.network?.offline);
}

export function l10nVeFiscalSerialPosMapTaxCode(taxAmount) {
    const amount = Math.abs(Number(taxAmount) || 0);
    if (amount <= 0) {
        return "0";
    }
    if (amount <= 8) {
        return "2";
    }
    if (amount <= 16) {
        return "1";
    }
    return "3";
}

export function l10nVeFiscalSerialPosPaymentCode(paymentMethod) {
    const code = String(paymentMethod?.l10n_ve_fiscal_payment_code || "").trim();
    if (code) {
        return code.padStart(2, "0");
    }
    return paymentMethod?.is_cash_count ? "01" : "02";
}

export function l10nVeFiscalSerialPosMachineConfig(pos) {
    const machine = l10nVeFiscalSerialPosGetFiscalMachine(pos);
    if (!machine) {
        return {};
    }
    const company = pos.company || {};
    const baud = machine.baudrate || "9600";
    return {
        machine_id: machine.id,
        name: machine.name || "",
        registered_serial: machine.registered_serial || "",
        baudrate: Number.parseInt(baud, 10) || 9600,
        parity: ["none", "even", "odd"].includes(machine.parity)
            ? machine.parity
            : "even",
        flag_21: company.l10n_ve_fiscal_flag_21 || "30",
        flag_50: company.l10n_ve_fiscal_flag_50 || "01",
        use_barcode: Boolean(company.l10n_ve_fiscal_use_barcode),
        footer_lines: [],
        payment_methods: [],
        use_emulator: Boolean(machine.use_emulator),
        send_default_code_in_name: Boolean(machine.send_default_code_in_name),
        serial_port: machine.serial_port || "",
        webserial_usb_vendor_id: machine.webserial_usb_vendor_id || 0,
        webserial_usb_product_id: machine.webserial_usb_product_id || 0,
        webserial_usb_serial_number: machine.webserial_usb_serial_number || "",
    };
}

export function l10nVeFiscalSerialPosNormalizeReprintNumber(number) {
    const digits = String(number || "").replace(/\D/g, "");
    if (!digits) {
        return "0000000";
    }
    return digits.slice(-7).padStart(7, "0");
}

export function l10nVeFiscalSerialPosOrderFiscalNumber(order) {
    return (
        order?.l10n_ve_pos_fiscal_invoice_number ||
        order?.raw?.l10n_ve_pos_fiscal_invoice_number ||
        false
    );
}

function l10nVeFiscalSerialPosIsRefundOrder(order) {
    return (
        Boolean(order) &&
        typeof order._isRefundOrder === "function" &&
        order._isRefundOrder()
    );
}

function l10nVeFiscalSerialPosRequireMachineConfig(pos) {
    const machineConfig = l10nVeFiscalSerialPosMachineConfig(pos);
    if (!machineConfig.machine_id) {
        throw new Error(
            _t("El diario de facturación no tiene máquina fiscal configurada.")
        );
    }
    return machineConfig;
}

export function l10nVeFiscalSerialPosBuildLocalReprintPayload(pos, order) {
    const machineConfig = l10nVeFiscalSerialPosRequireMachineConfig(pos);
    const fiscalNumber = l10nVeFiscalSerialPosOrderFiscalNumber(order);
    if (!fiscalNumber) {
        throw new Error(_t("La orden no tiene número fiscal para reimprimir."));
    }
    const isRefund = l10nVeFiscalSerialPosIsRefundOrder(order);
    return {
        l10n_ve_print_action: "reprint",
        type: isRefund ? "out_refund" : "out_invoice",
        reprint_document_type: isRefund ? "out_refund" : "out_invoice",
        mf_number: l10nVeFiscalSerialPosNormalizeReprintNumber(fiscalNumber),
        move_id: order?.raw?.account_move || false,
        fiscal_machine: machineConfig,
    };
}

function l10nVeFiscalSerialPosLineDiscountAmount(line, priceUnit, quantity) {
    const discountPercent = Number(line.get_discount?.() ?? line.discount) || 0;
    if (discountPercent <= 0) {
        return {discountPercent, discountAmount: 0};
    }
    if (typeof line.get_all_prices === "function") {
        const prices = line.get_all_prices();
        return {
            discountPercent,
            discountAmount: Math.max(
                0,
                Math.abs(
                    Number(prices?.priceWithoutTaxBeforeDiscount || 0) -
                        Number(prices?.priceWithoutTax || 0)
                )
            ),
        };
    }
    return {
        discountPercent,
        discountAmount: (priceUnit * quantity * discountPercent) / 100,
    };
}

function l10nVeFiscalSerialPosFormatLineName(product, line, machineConfig) {
    let name = product.display_name || product.name || line.full_product_name || "";
    let defaultCode = product.default_code || "";
    if (machineConfig.send_default_code_in_name && defaultCode) {
        name = `[${defaultCode}] ${name}`.trim();
        defaultCode = "";
    }
    return {name, defaultCode};
}

function l10nVeFiscalSerialPosIsEwalletLine(order, line) {
    return (
        typeof order?._l10nVeIsEwalletRewardLine === "function" &&
        order._l10nVeIsEwalletRewardLine(line)
    );
}

function l10nVeFiscalSerialPosIsGlobalDiscountLine(line) {
    return (
        Boolean(line?.l10n_ve_global_discount) ||
        Boolean(line?.is_reward_line && line.reward_id?.reward_type === "discount")
    );
}

function l10nVeFiscalSerialPosBuildInvoiceLine(line, machineConfig) {
    const product = line.product_id || {};
    const tax = line.tax_ids?.[0] || line.get_taxes?.()?.[0];
    const taxAmount = tax?.amount ?? 0;
    const {name, defaultCode} = l10nVeFiscalSerialPosFormatLineName(
        product,
        line,
        machineConfig
    );
    const priceUnit = Math.abs(Number(line.get_unit_price?.() ?? line.price_unit) || 0);
    const quantity = Math.abs(Number(line.get_quantity?.() ?? line.qty) || 0);
    const {discountPercent, discountAmount} = l10nVeFiscalSerialPosLineDiscountAmount(
        line,
        priceUnit,
        quantity
    );
    return {
        tax: l10nVeFiscalSerialPosMapTaxCode(taxAmount),
        tax_percent: taxAmount,
        price_unit: priceUnit,
        quantity,
        default_code: defaultCode,
        name,
        discount: discountPercent,
        discount_amount: discountAmount,
    };
}

function l10nVeFiscalSerialPosCollectInvoiceLines(order, machineConfig) {
    let globalDiscountAmount = 0;
    if (typeof order?._l10nVeGetFiscalGlobalDiscountAmount === "function") {
        globalDiscountAmount = Math.abs(
            Number(order._l10nVeGetFiscalGlobalDiscountAmount()) || 0
        );
    }
    const invoiceLines = [];
    for (const line of order?.lines || []) {
        if (l10nVeFiscalSerialPosIsEwalletLine(order, line)) {
            continue;
        }
        if (l10nVeFiscalSerialPosIsGlobalDiscountLine(line)) {
            if (typeof order?._l10nVeGetFiscalGlobalDiscountAmount !== "function") {
                globalDiscountAmount += Math.abs(
                    Number(line.get_price_without_tax?.() ?? line.price_subtotal ?? 0)
                );
            }
            continue;
        }
        invoiceLines.push(l10nVeFiscalSerialPosBuildInvoiceLine(line, machineConfig));
    }
    return {invoiceLines, globalDiscountAmount};
}

function l10nVeFiscalSerialPosCollectPaymentLines(order) {
    const paymentLines = (order?.payment_ids || [])
        .filter(
            (payment) =>
                !payment.is_change && payment.payment_method_id?.type !== "pay_later"
        )
        .map((payment) => ({
            amount: Math.abs(Number(payment.get_amount?.() ?? payment.amount) || 0),
            payment_method: l10nVeFiscalSerialPosPaymentCode(payment.payment_method_id),
        }))
        .filter((line) => line.amount > 0);
    const ewalletPayments =
        typeof order?._l10nVeGetEwalletPaymentLines === "function"
            ? order._l10nVeGetEwalletPaymentLines() || []
            : [];
    for (const walletPayment of ewalletPayments) {
        const amount = Math.abs(Number(walletPayment.amount || 0));
        if (!amount) {
            continue;
        }
        paymentLines.push({
            amount,
            payment_method: String(
                walletPayment.payment_method ||
                    order._l10nVeEwalletFiscalPaymentCode?.() ||
                    "24"
            ).padStart(2, "0"),
        });
    }
    if (!paymentLines.length) {
        paymentLines.push({amount: 0, payment_method: "01"});
    }
    return paymentLines;
}

function l10nVeFiscalSerialPosApplyRefundOrigin(payload, order, machineConfig) {
    const originLine = (order.lines || []).find((line) => line.refunded_orderline_id);
    const originOrder =
        originLine?.refunded_orderline_id?.order_id ||
        originLine?.refunded_orderline_id?.order ||
        false;
    const originNumber =
        originOrder?.l10n_ve_pos_fiscal_invoice_number ||
        originOrder?.raw?.l10n_ve_pos_fiscal_invoice_number ||
        false;
    if (!originNumber) {
        throw new Error(
            _t(
                "La devolución requiere el N° fiscal de la factura origen. No está disponible offline."
            )
        );
    }
    const originDate =
        originOrder?.date_order || originOrder?.creation_date || new Date();
    const dateObj = originDate instanceof Date ? originDate : new Date(originDate);
    const dd = String(dateObj.getDate()).padStart(2, "0");
    const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
    const yyyy = dateObj.getFullYear();
    payload.invoice_affected = {
        number: String(originNumber),
        serial_machine:
            originOrder?.l10n_ve_pos_fiscal_serial ||
            machineConfig.registered_serial ||
            "",
        date: `${dd}/${mm}/${yyyy}`,
    };
}

export function l10nVeFiscalSerialPosBuildLocalPayload(pos, order) {
    if (l10nVeFiscalSerialPosOrderFiscalNumber(order)) {
        return l10nVeFiscalSerialPosBuildLocalReprintPayload(pos, order);
    }
    const machineConfig = l10nVeFiscalSerialPosRequireMachineConfig(pos);
    const partner = order?.get_partner?.() || order?.partner_id || {};
    const isRefund = l10nVeFiscalSerialPosIsRefundOrder(order);
    const {invoiceLines, globalDiscountAmount} =
        l10nVeFiscalSerialPosCollectInvoiceLines(order, machineConfig);
    const payload = {
        l10n_ve_print_action: isRefund ? "print_out_refund" : "print_out_invoice",
        company_id: pos.company?.id || false,
        partner_id: {
            name: partner.name || "",
            vat: partner.vat || "",
            address: partner.street || "",
            phone: partner.phone || partner.mobile || "",
        },
        invoice_lines: invoiceLines,
        payment_lines: l10nVeFiscalSerialPosCollectPaymentLines(order),
        global_discount_amount: globalDiscountAmount,
        flag_21: machineConfig.flag_21,
        flag_50: machineConfig.flag_50,
        use_barcode: machineConfig.use_barcode,
        barcode: false,
        fiscal_machine: machineConfig,
        aditional_lines: [],
        has_cashbox: false,
        use_emulator: machineConfig.use_emulator,
        move_type: isRefund ? "out_refund" : "out_invoice",
        move_id: false,
    };
    if (isRefund) {
        l10nVeFiscalSerialPosApplyRefundOrigin(payload, order, machineConfig);
    }
    return payload;
}

function l10nVeFiscalSerialPosCounterVals(pos, data) {
    const vals = {};
    const sequence =
        data.sequence !== undefined && data.sequence !== null
            ? String(data.sequence)
            : false;
    if (sequence) {
        const order = typeof pos.get_order === "function" ? pos.get_order() : null;
        if (l10nVeFiscalSerialPosIsRefundOrder(order)) {
            vals.last_credit_note_number = sequence;
        } else {
            vals.last_invoice_number = sequence;
        }
    }
    if (data.serial_machine) {
        vals.registered_serial = String(data.serial_machine);
    }
    const closure =
        data.parsed_post?.DailyClosureCounter || data.daily_closure_counter || false;
    if (closure) {
        vals.daily_closure_counter = String(closure);
    }
    return vals;
}

export function l10nVeFiscalSerialPosSyncMachineCounters(pos, response) {
    const machine = l10nVeFiscalSerialPosGetFiscalMachine(pos);
    if (!machine?.update || !response?.data) {
        return;
    }
    const vals = l10nVeFiscalSerialPosCounterVals(pos, response.data);
    if (Object.keys(vals).length) {
        machine.update(vals);
    }
}

export function l10nVeFiscalSerialPosSyncOrderFiscalFields(order, response) {
    if (!order?.update || !response?.data || typeof order.update !== "function") {
        return;
    }
    const data = response.data;
    const vals = {};
    if (data.sequence !== undefined && data.sequence !== null) {
        vals.l10n_ve_pos_fiscal_invoice_number = String(data.sequence);
    }
    if (data.serial_machine) {
        vals.l10n_ve_pos_fiscal_serial = String(data.serial_machine);
    }
    if (data.mf_reportz !== undefined && data.mf_reportz !== null) {
        vals.l10n_ve_pos_fiscal_report_z = String(data.mf_reportz);
    }
    if (Object.keys(vals).length) {
        order.update(vals);
    }
}

function l10nVeFiscalSerialPosPrintSource(printAction) {
    if (printAction === "print_out_refund") {
        return "refund_print";
    }
    if (printAction === "print_debit_note") {
        return "debit_note";
    }
    if (printAction === "reprint") {
        return "reprint";
    }
    return "invoice_print";
}

async function l10nVeFiscalSerialPosLoadServerPayload(pos, orderId) {
    try {
        return await pos.data.call(
            "pos.order",
            "l10n_ve_fiscal_serial_pos_fiscal_action_payload",
            [[orderId]]
        );
    } catch (error) {
        globalThis.console.warn(
            "[l10n_ve_fiscal_serial_pos] Payload servidor no disponible, usando local.",
            error
        );
        return false;
    }
}

async function l10nVeFiscalSerialPosRegisterResult(pos, orderId, response, delayed) {
    try {
        await pos.data.call(
            "pos.order",
            "l10n_ve_fiscal_serial_register_print_result",
            [[orderId], response]
        );
    } catch (error) {
        const message = delayed
            ? "[l10n_ve_fiscal_serial_pos] Registro diferido; la orden local conserva los datos fiscales."
            : "[l10n_ve_fiscal_serial_pos] No se pudo registrar en servidor; queda en la orden local.";
        globalThis.console.warn(message, error);
    }
}

function l10nVeFiscalSerialPosSuccessMessage(printAction, usedLocalPayload, offline) {
    if (printAction === "reprint") {
        return _t("Reimpresión fiscal completada.");
    }
    if (usedLocalPayload || offline) {
        return _t("Impresión fiscal completada (modo local/offline).");
    }
    return _t("Impresión fiscal completada.");
}

function l10nVeFiscalSerialPosErrorMessage(error) {
    return (
        error?.data?.message ||
        error?.data?.arguments?.[0] ||
        error?.message ||
        String(error || _t("Error en impresión fiscal."))
    );
}

async function l10nVeFiscalSerialPosBorrowDriver(
    connection,
    machineConfig,
    notification
) {
    await connection.setPrimaryMachine(machineConfig.machine_id);
    const authorized = await TfhkaWebSerialTransport.resolvePort(machineConfig, {
        requestPort: false,
    });
    const needPortPicker = !authorized.port && !connection.state.portOpen;
    if (needPortPicker) {
        notification.add(
            _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
            {type: "warning"}
        );
    }
    return connection.borrowDriver({
        machine: machineConfig,
        requestPort: needPortPicker,
    });
}

async function l10nVeFiscalSerialPosVerifyMachine(
    fiscalSerial,
    driver,
    machineConfig,
    notification
) {
    const verification = await fiscalSerial.verifyConnectedFiscalMachine(
        driver,
        machineConfig,
        {
            parseTfhkaS1StatusResponse: fiscalSerial.parseTfhkaS1StatusResponse,
        }
    );
    if (verification.training_mode || verification.emulator_mode) {
        notification.add(verification.message, {type: "warning"});
    }
}

export async function l10nVeFiscalSerialPosExecutePrint({
    pos,
    env,
    orderId,
    order,
    logTag = "[l10n_ve_fiscal_serial_pos]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const connection = env.services.l10n_ve_fiscal_connection;
    const notification = env.services.notification;
    const orm = env.services.orm;
    const ui = env.services.ui;

    if (!fiscalSerial || !connection) {
        notification.add(
            _t("El servicio de máquina fiscal no está disponible en el POS."),
            {type: "danger"}
        );
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir fiscalmente desde el POS."
            ),
            {type: "danger"}
        );
        return false;
    }

    const offline = l10nVeFiscalSerialPosIsOffline(pos);
    const hasServerOrder = Boolean(orderId && Number(orderId) > 0);
    let payload = false;
    let usedLocalPayload = false;
    if (!offline && hasServerOrder) {
        payload = await l10nVeFiscalSerialPosLoadServerPayload(pos, orderId);
    }
    if (!payload) {
        try {
            payload = l10nVeFiscalSerialPosBuildLocalPayload(pos, order);
            usedLocalPayload = true;
        } catch (error) {
            notification.add(
                error?.message || _t("No se pudo preparar la impresión fiscal."),
                {type: "danger"}
            );
            return false;
        }
    }

    const printAction = payload?.l10n_ve_print_action || "print_out_invoice";
    const data = {...payload};
    delete data.l10n_ve_print_action;
    const machineConfig = data.fiscal_machine || {};
    const progressLabel =
        printAction === "reprint"
            ? _t("Reimprimiendo fiscalmente")
            : _t("Imprimiendo fiscalmente");

    let borrowed = false;
    let auditLogger = null;
    let blocked = false;
    const setProgress = (percent, message) => {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (blocked) {
            ui.unblock();
            blocked = false;
        }
        ui.block({message: `${message || progressLabel} ${pct}%`});
        blocked = true;
    };

    try {
        setProgress(0, progressLabel);
        auditLogger = createFiscalSerialAuditLogger(orm, {
            source: l10nVeFiscalSerialPosPrintSource(printAction),
            moveId: data.move_id || false,
            machineId: machineConfig.machine_id || false,
        });
        if (!machineConfig.machine_id) {
            throw new Error(
                _t("El diario de facturación no tiene máquina fiscal configurada.")
            );
        }
        const driver = await l10nVeFiscalSerialPosBorrowDriver(
            connection,
            machineConfig,
            notification
        );
        borrowed = true;
        auditLogger.attachDriver(driver);
        setProgress(15, progressLabel);
        await l10nVeFiscalSerialPosVerifyMachine(
            fiscalSerial,
            driver,
            machineConfig,
            notification
        );
        setProgress(20, progressLabel);
        const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await machine.runAction({
            action: printAction,
            data,
            onProgress: ({percent, message}) => {
                setProgress(percent, message || progressLabel);
            },
        });
        if (!response?.valid) {
            throw new Error(response?.message || _t("Falló la impresión fiscal."));
        }
        setProgress(95, progressLabel);
        if (order) {
            l10nVeFiscalSerialPosSyncOrderFiscalFields(order, response);
        }
        if (printAction !== "reprint") {
            l10nVeFiscalSerialPosSyncMachineCounters(pos, response);
        }
        if (printAction !== "reprint" && !offline && hasServerOrder) {
            await l10nVeFiscalSerialPosRegisterResult(
                pos,
                orderId,
                response,
                usedLocalPayload
            );
        }
        setProgress(100, progressLabel);
        notification.add(
            response.message ||
                l10nVeFiscalSerialPosSuccessMessage(
                    printAction,
                    usedLocalPayload,
                    offline
                ),
            {type: "success"}
        );
        return true;
    } catch (error) {
        globalThis.console.error(`${logTag} Error impresión fiscal POS:`, error);
        notification.add(l10nVeFiscalSerialPosErrorMessage(error), {type: "danger"});
        return false;
    } finally {
        if (borrowed) {
            await connection.releaseDriver({close: false});
        }
        if (auditLogger) {
            try {
                await auditLogger.flush();
            } catch (error) {
                globalThis.console.warn(
                    `${logTag} Auditoría no enviada (posible offline).`,
                    error
                );
            }
        }
        if (blocked) {
            ui.unblock();
        }
    }
}
