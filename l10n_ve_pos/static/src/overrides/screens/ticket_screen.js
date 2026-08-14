import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(TicketScreen.prototype, {
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
    get ticketScreenPosReferenceHeader() {
        return this.isVenezuelaPos ? _t("POS Reference") : _t("Receipt Number");
    },
    get ticketScreenSyncedPrintLabel() {
        return this.isVenezuelaPos ? _t("Print document") : _t("Print Receipt");
    },
    async addAdditionalRefundInfo(order, destinationOrder) {
        await super.addAdditionalRefundInfo(...arguments);
        if (!isVenezuelaCompany(this.pos)) {
            return;
        }
        const originJournal = order.invoice_journal_id;
        if (originJournal && typeof destinationOrder.setInvoiceJournal === "function") {
            destinationOrder.setInvoiceJournal(originJournal);
        }
    },
    _getOrderStates() {
        const states = super._getOrderStates(...arguments);
        if (isVenezuelaCompany(this.pos)) {
            const receiptState = states.get("RECEIPT");
            if (receiptState) {
                states.set("RECEIPT", { ...receiptState, text: _t("Finalize") });
            }
        }
        return states;
    },
    _getSearchFields() {
        const fields = super._getSearchFields(...arguments);
        if (isVenezuelaCompany(this.pos) && fields.RECEIPT_NUMBER) {
            fields.RECEIPT_NUMBER = {
                ...fields.RECEIPT_NUMBER,
                displayName: _t("POS Reference"),
            };
        }
        return fields;
    },
});
