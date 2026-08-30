// Copyright 2026 BWEALTHICS LLC
// License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import {_t} from "@web/core/l10n/translation";

export class FiscalBridgeError extends Error {
    constructor(message, ambiguous = false) {
        super(message);
        this.ambiguous = ambiguous;
    }
}

const RATES = [0, 8, 16, 31];

export function ivaPct(line) {
    let taxes = line.tax_ids || [];
    const fiscalPosition = line.order_id && line.order_id.fiscal_position_id;
    if (fiscalPosition && fiscalPosition.getTaxesAfterFiscalPosition) {
        taxes = fiscalPosition.getTaxesAfterFiscalPosition(taxes) || [];
    }
    const tax =
        (taxes.find && taxes.find((item) => typeof item.amount === "number")) || null;
    const amount = (tax && tax.amount) || 0;
    return RATES.reduce((left, right) =>
        Math.abs(right - amount) < Math.abs(left - amount) ? right : left
    );
}

export function toVes(amount, rate) {
    return Math.round(amount * rate * 100) / 100;
}

async function fetchWithTimeout(url, options, milliseconds) {
    let timedOut = false;
    const controller = new AbortController();
    const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, milliseconds);
    try {
        return await fetch(url, {...options, signal: controller.signal});
    } catch (error) {
        const bridgeError = error || new Error("fetch failed");
        bridgeError.l10nVeTimeout = timedOut;
        throw bridgeError;
    } finally {
        clearTimeout(timer);
    }
}

export async function callBridge(config, endpoint, payload = {}) {
    let response = null;
    try {
        response = await fetchWithTimeout(
            config.l10n_ve_bridge_url.replace(/\/$/, "") + endpoint,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Bridge-Token": config.l10n_ve_bridge_token || "",
                },
                body: JSON.stringify(payload),
            },
            90000
        );
    } catch (error) {
        throw new FiscalBridgeError(
            error && error.l10nVeTimeout
                ? _t("The fiscal printer timed out; the document MAY have printed.")
                : _t("Cannot connect to the local fiscal printer bridge."),
            Boolean(error && error.l10nVeTimeout)
        );
    }
    const data = await response.json().catch(() => ({}));
    if (data.estado !== "exito") {
        throw new FiscalBridgeError(
            data.mensaje || _t("Fiscal printer error (HTTP %s).", response.status)
        );
    }
    return data;
}

let lastGoodRate = null;

export async function getVesRate(pos) {
    try {
        const rate = await pos.data.call("pos.config", "l10n_ve_get_ves_rate", [
            [pos.config.id],
        ]);
        if (rate > 0) {
            lastGoodRate = rate;
        }
    } catch {
        // An offline register can keep using the last rate fetched in this tab.
    }
    if (!lastGoodRate) {
        throw new FiscalBridgeError(_t("No VES exchange rate is available in Odoo."));
    }
    return lastGoodRate;
}

const UNCERTAIN_PREFIX = "l10nVeUncertain:";

export function markUncertain(order) {
    try {
        localStorage.setItem(UNCERTAIN_PREFIX + order.uuid, "1");
    } catch {
        // The in-memory uiState remains available when localStorage is blocked.
    }
}

export function clearUncertain(order) {
    try {
        localStorage.removeItem(UNCERTAIN_PREFIX + order.uuid);
    } catch {
        // Nothing else is required when localStorage is blocked.
    }
}

export function isUncertain(order) {
    try {
        return Boolean(localStorage.getItem(UNCERTAIN_PREFIX + order.uuid));
    } catch {
        return false;
    }
}

export function buildInvoicePayload(pos, order, rate) {
    const isRefund = order.lines.some((line) => line.refunded_orderline_id);
    const sign = isRefund ? -1 : 1;
    const round2 = (value) => Math.round(value * 100) / 100;
    const items = order.lines
        .filter((line) => line.qty)
        .map((line) => ({
            descripcion: (line.getFullProductName() || "").slice(0, 40),
            precio: round2(toVes(line.prices.total_included / line.qty, rate)),
            cantidad: sign * line.qty,
            iva_porcentaje: ivaPct(line),
        }));
    const machineTotal = round2(
        items.reduce((total, item) => total + item.precio * item.cantidad, 0)
    );
    const payments = order.payment_ids
        .map((payment) => ({
            metodo: payment.payment_method_id?.l10n_ve_fiscal_payment_code || "01",
            monto: round2(toVes(sign * payment.amount, rate)),
            divisa: Boolean(payment.payment_method_id?.l10n_ve_igtf_applies),
        }))
        .filter((payment) => payment.monto > 0);
    const paid = round2(payments.reduce((total, payment) => total + payment.monto, 0));
    const delta = round2(machineTotal - paid);
    if (payments.length && Math.abs(delta) <= 0.02 * items.length + 0.03) {
        payments[payments.length - 1].monto = round2(
            payments[payments.length - 1].monto + delta
        );
    }
    const igtfBase = payments
        .filter((payment) => payment.divisa)
        .reduce((total, payment) => total + payment.monto, 0);
    const company = pos.company || {};
    const partner = order.getPartner();
    return {
        uuid: order.uuid,
        cliente_nombre: partner?.name || "CONSUMIDOR FINAL",
        cliente_rif: (partner?.vat || "").replace(/-/g, "").toUpperCase(),
        serial_impresora: pos.config.l10n_ve_machine_serial || "",
        tasa_dolar: rate,
        monto_total: machineTotal,
        monto_igtf:
            company.l10n_ve_is_spe && igtfBase > 0
                ? Math.round(igtfBase * (company.l10n_ve_igtf_pct || 3.0)) / 100
                : 0,
        items,
        pagos: payments,
    };
}
