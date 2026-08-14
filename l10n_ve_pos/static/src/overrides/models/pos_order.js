import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isVenezuelaCompany(order) {
    return (
        order.company?.country_id?.code === "VE" ||
        order.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        if (isVenezuelaCompany(this)) {
            this.to_invoice = true;
        }
    },
    _l10nVePosOriginInvoiceJournal() {
        const originOrder = this.lines.find((line) => line.refunded_orderline_id)
            ?.refunded_orderline_id?.order_id;
        return originOrder?.invoice_journal_id || false;
    },
    canChangeInvoiceJournal() {
        return !(isVenezuelaCompany(this) && this._isRefundOrder());
    },
    setInvoiceJournal(journal) {
        if (isVenezuelaCompany(this) && this._isRefundOrder()) {
            const originJournal = this._l10nVePosOriginInvoiceJournal();
            if (originJournal) {
                if (journal && journal.id !== originJournal.id) {
                    return;
                }
                journal = originJournal;
            }
        }
        this.update({
            invoice_journal_id: journal || false,
        });
        if (typeof this.l10n_ve_pos_updateIgtf === "function") {
            this.l10n_ve_pos_updateIgtf();
        }
    },
    set_to_invoice(to_invoice) {
        if (isVenezuelaCompany(this) && !to_invoice) {
            return;
        }
        super.set_to_invoice(...arguments);
    },
    getEmailItems() {
        if (isVenezuelaCompany(this)) {
            return [_t("the invoice")];
        }
        return super.getEmailItems(...arguments);
    },
});
