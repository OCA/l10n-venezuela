/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import {
    l10nVeFiscalSerialPosExecutePrint,
    l10nVeFiscalSerialPosGetNextPlaceholders,
    l10nVeFiscalSerialPosIsFiscalMachine,
    l10nVeFiscalSerialPosIsOffline,
} from "../../fiscal_serial_pos_print";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PaymentScreen.prototype, {
    _l10nVeApplyLocalFiscalPlaceholders() {
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return;
        }
        const placeholders = l10nVeFiscalSerialPosGetNextPlaceholders(this.pos);
        if (placeholders.invoice_number) {
            this.l10nVeEmission.next_fiscal_invoice_number = placeholders.invoice_number;
        }
        if (placeholders.serial) {
            this.l10nVeEmission.next_fiscal_serial = placeholders.serial;
        }
        if (placeholders.report_z) {
            this.l10nVeEmission.next_fiscal_report_z = placeholders.report_z;
        }
    },

    async l10nVeRefreshEmissionPreview() {
        if (l10nVeFiscalSerialPosIsOffline(this.pos)) {
            const fallback =
                typeof this._l10nVeLocalEmissionPreviewFallback === "function"
                    ? this._l10nVeLocalEmissionPreviewFallback()
                    : false;
            if (fallback && typeof this._l10nVeApplyEmissionPreview === "function") {
                this._l10nVeApplyEmissionPreview(fallback);
            }
            this._l10nVeApplyLocalFiscalPlaceholders();
            return;
        }
        await super.l10nVeRefreshEmissionPreview(...arguments);
        this._l10nVeApplyLocalFiscalPlaceholders();
    },

    _l10nVeFiscalSerialNeedsPrint() {
        if (!isVenezuelaCompany(this.pos)) {
            return false;
        }
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return false;
        }
        const order = this.currentOrder;
        if (!order?.is_to_invoice()) {
            return false;
        }
        if (
            order.l10n_ve_pos_fiscal_invoice_number ||
            order.raw?.l10n_ve_pos_fiscal_invoice_number
        ) {
            return false;
        }
        return true;
    },

    _l10nVeFiscalSerialPrintSucceededForCurrentOrder() {
        const uuid = this.currentOrder?.uuid;
        if (!uuid) {
            return false;
        }
        this._l10nVeFiscalSerialPrintOkByOrderUuid =
            this._l10nVeFiscalSerialPrintOkByOrderUuid || {};
        return Boolean(this._l10nVeFiscalSerialPrintOkByOrderUuid[uuid]);
    },

    _l10nVeFiscalSerialMarkPrintSucceeded() {
        const uuid = this.currentOrder?.uuid;
        if (!uuid) {
            return;
        }
        this._l10nVeFiscalSerialPrintOkByOrderUuid =
            this._l10nVeFiscalSerialPrintOkByOrderUuid || {};
        this._l10nVeFiscalSerialPrintOkByOrderUuid[uuid] = true;
    },

    _l10nVeFiscalSerialAwaitingFiscalPrint() {
        return (
            this._l10nVeFiscalSerialNeedsPrint() &&
            !this._l10nVeFiscalSerialPrintSucceededForCurrentOrder()
        );
    },

    async _l10nVeFiscalSerialPrintCurrentOrder() {
        if (!this._l10nVeFiscalSerialNeedsPrint()) {
            return true;
        }
        return l10nVeFiscalSerialPosExecutePrint({
            pos: this.pos,
            env: this.env,
            orderId: this.currentOrder.id,
            order: this.currentOrder,
        });
    },

    async validateOrder(isForceValidate) {
        if (
            this.currentOrder.is_paid() &&
            this._l10nVeFiscalSerialAwaitingFiscalPrint()
        ) {
            const ok = await this._l10nVeFiscalSerialPrintCurrentOrder();
            if (!ok) {
                return;
            }
            this._l10nVeFiscalSerialMarkPrintSucceeded();
        }
        return super.validateOrder(isForceValidate);
    },

    async afterOrderValidation(...args) {
        if (this._l10nVeFiscalSerialAwaitingFiscalPrint()) {
            const ok = await this._l10nVeFiscalSerialPrintCurrentOrder();
            if (!ok) {
                return;
            }
            this._l10nVeFiscalSerialMarkPrintSucceeded();
        }
        return super.afterOrderValidation(...args);
    },
});
