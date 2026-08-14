/** @odoo-module **/

import { InvoiceButton } from "@point_of_sale/app/screens/ticket_screen/invoice_button/invoice_button";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    l10nVeFiscalSerialPosExecutePrint,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

patch(InvoiceButton.prototype, {
    _l10nVeFiscalSerialPosIsFiscalMachine() {
        return l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
    },
    get commandName() {
        if (!this.props.order) {
            return _t("Invoice");
        }
        if (this.isAlreadyInvoiced && this._l10nVeFiscalSerialPosIsFiscalMachine()) {
            if (
                this.props.order.l10n_ve_pos_fiscal_invoice_number ||
                this.props.order.raw?.l10n_ve_pos_fiscal_invoice_number
            ) {
                return _t("Reprint document");
            }
            return _t("Print document");
        }
        return this.isAlreadyInvoiced ? _t("Reprint Invoice") : _t("Invoice");
    },
    async _invoiceOrder() {
        const order = this.props.order;
        if (!order) {
            return;
        }

        const orderId = order.id;
        if (this.isAlreadyInvoiced && this._l10nVeFiscalSerialPosIsFiscalMachine()) {
            const ok = await l10nVeFiscalSerialPosExecutePrint({
                pos: this.pos,
                env: this.env,
                orderId,
                order,
            });
            if (ok) {
                this.props.onInvoiceOrder(orderId);
            }
            return;
        }

        return super._invoiceOrder(...arguments);
    },
});
