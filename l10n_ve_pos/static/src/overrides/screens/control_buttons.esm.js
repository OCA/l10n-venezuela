import {ControlButtons} from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(ControlButtons.prototype, {
    get availableInvoiceJournals() {
        if (!isVenezuelaCompany(this.pos)) {
            return [];
        }
        return this.pos.getAvailableInvoiceJournals();
    },
    get canChangeInvoiceJournal() {
        return (
            !this.currentOrder ||
            typeof this.currentOrder.canChangeInvoiceJournal !== "function" ||
            this.currentOrder.canChangeInvoiceJournal()
        );
    },
    async clickInvoiceJournal() {
        if (!this.canChangeInvoiceJournal) {
            return;
        }
        await this.pos.selectInvoiceJournal(this.currentOrder);
    },
});
