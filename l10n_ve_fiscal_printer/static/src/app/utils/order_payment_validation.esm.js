// Copyright 2026 BWEALTHICS LLC
// License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import {
    FiscalBridgeError,
    buildInvoicePayload,
    callBridge,
    clearUncertain,
    getVesRate,
    isUncertain,
    markUncertain,
    toVes,
} from "@l10n_ve_fiscal_printer/app/utils/fiscal_bridge.esm";

patch(OrderPaymentValidation.prototype, {
    async shouldHideValidationBehindFeedbackScreen() {
        if (this.pos.config.l10n_ve_bridge_url && !this.order.l10n_ve_fiscal_number) {
            try {
                await this._l10nVePrintFiscal();
            } catch (error) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Fiscal printer"),
                    body: error.message || _t("Unknown fiscal printer bridge error."),
                });
                // Do not finalize or navigate: a legal fiscal number is required.
                return;
            }
        }
        return super.shouldHideValidationBehindFeedbackScreen(...arguments);
    },

    _l10nVeLogEvent(code, detail) {
        const order = this.order;
        const stamp = luxon.DateTime.now().toFormat("HH:mm:ss");
        const cashier =
            (this.pos.getCashier && this.pos.getCashier()?.name) ||
            this.pos.user?.name ||
            "";
        const entry = `${stamp} | ${cashier} | ${detail}`;
        const previous = order.l10n_ve_fiscal_event_note || "";
        order.l10n_ve_fiscal_event = code;
        order.l10n_ve_fiscal_event_note = (previous ? previous + "\n" : "")
            .concat(entry)
            .split("\n")
            .slice(-10)
            .join("\n");
    },

    async _l10nVePrintFiscal() {
        const order = this.order;
        const config = this.pos.config;
        const rate = await getVesRate(this.pos);
        const refundLine = order.lines.find((line) => line.refunded_orderline_id);
        const original = refundLine?.refunded_orderline_id.order_id;
        if (refundLine && !original?.l10n_ve_fiscal_number) {
            throw new FiscalBridgeError(
                _t(
                    "The original order has no fiscal invoice number. Issue the credit note manually on the fiscal machine."
                )
            );
        }
        await callBridge(config, "/claim-terminal", {uuid: order.uuid});
        try {
            if (order.uiState.l10nVeUncertain || isUncertain(order)) {
                if (original) {
                    throw new FiscalBridgeError(
                        _t(
                            "The previous credit note attempt was not confirmed. Check the physical machine output before retrying."
                        )
                    );
                }
                if (await this._l10nVeTryAdoptLast(rate)) {
                    return;
                }
            }
            const payload = buildInvoicePayload(this.pos, order, rate);
            let result = null;
            if (original) {
                const fiscalDate = String(original.l10n_ve_fiscal_date || "").slice(
                    0,
                    10
                );
                result = await callBridge(config, "/print-credit-note", {
                    ...payload,
                    numero_factura_afectada: original.l10n_ve_fiscal_number,
                    serial_afectada: original.l10n_ve_fiscal_machine_serial || "",
                    fecha_afectada: fiscalDate
                        ? fiscalDate.split("-").reverse().join("")
                        : "",
                });
            } else {
                result = await callBridge(config, "/print-invoice", payload);
            }
            this._l10nVeStamp(
                result.numero_factura_fiscal,
                original ? "credit_note" : "invoice",
                result.serial
            );
        } catch (error) {
            if (error instanceof FiscalBridgeError && error.ambiguous) {
                order.uiState.l10nVeUncertain = true;
                markUncertain(order);
            }
            throw error;
        } finally {
            await callBridge(config, "/release-terminal", {uuid: order.uuid}).catch(
                () => undefined
            );
        }
    },

    async _l10nVeTryAdoptLast(rate) {
        const order = this.order;
        const last = await callBridge(this.pos.config, "/check-last-invoice", {});
        if (last.uuid && last.uuid === order.uuid) {
            this._l10nVeStamp(last.numero_factura_fiscal, "invoice", last.serial);
            this._l10nVeLogEvent(
                "adopt_uuid",
                _t(
                    "Number %s recovered from this order UUID",
                    last.numero_factura_fiscal
                )
            );
            return true;
        }
        if (last.uuid && last.uuid !== order.uuid) {
            this._l10nVeLogEvent(
                "reprint",
                _t("The last ticket belongs to another order")
            );
            return false;
        }
        const totalVes = toVes(Math.abs(order.priceIncl), rate);
        if (
            last.monto_total !== null &&
            last.monto_total !== undefined &&
            Math.abs(last.monto_total - totalVes) >= 0.011
        ) {
            this._l10nVeLogEvent("reprint", _t("The last ticket total does not match"));
            return false;
        }
        return new Promise((resolve) => {
            this.pos.dialog.add(ConfirmationDialog, {
                title: _t("Fiscal printer"),
                body: _t(
                    "The previous attempt was not confirmed. Was ticket %s for VES %s physically printed? Confirm to recover it or cancel to print again.",
                    last.numero_factura_fiscal,
                    totalVes.toFixed(2)
                ),
                confirm: () => {
                    this._l10nVeStamp(
                        last.numero_factura_fiscal,
                        "invoice",
                        last.serial
                    );
                    this._l10nVeLogEvent(
                        "adopt_manual",
                        _t(
                            "The cashier confirmed that ticket %s was printed",
                            last.numero_factura_fiscal
                        )
                    );
                    resolve(true);
                },
                cancel: () => {
                    this._l10nVeLogEvent(
                        "reprint",
                        _t("The cashier reported no ticket")
                    );
                    resolve(false);
                },
            });
        });
    },

    _l10nVeStamp(number, docType, serial) {
        const order = this.order;
        order.l10n_ve_fiscal_number = number;
        order.l10n_ve_fiscal_machine_serial =
            serial || this.pos.config.l10n_ve_machine_serial || "";
        order.l10n_ve_fiscal_date =
            luxon.DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss");
        order.l10n_ve_fiscal_doc_type = docType;
        order.uiState.l10nVeUncertain = false;
        clearUncertain(order);
    },
});
