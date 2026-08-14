import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.invoiceService = useService("account_move");
    },
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
    get receiptFullPrintLabel() {
        return this.isVenezuelaPos ? _t("Print complete") : _t("Print Full Receipt");
    },
    get receiptBasicPrintLabel() {
        return this.isVenezuelaPos ? _t("Print simplified") : _t("Print Basic Receipt");
    },
    get l10nVeShowReceiptInvoiceDetails() {
        return this.isVenezuelaPos && Boolean(this.currentOrder.raw?.account_move);
    },
    get l10nVeJournalEmissionMedium() {
        const orderJournal = this.currentOrder?.invoice_journal_id;
        return (
            orderJournal?.l10n_ve_emission_medium ||
            this.pos.config?.invoice_journal_id?.l10n_ve_emission_medium ||
            ""
        );
    },
    get l10nVeLabelAccountingInvoiceNumber() {
        return _t("Accounting invoice number");
    },
    get l10nVeLabelFiscalInvoiceNo() {
        return _t("Fiscal invoice number");
    },
    get l10nVeLabelFiscalSerial() {
        return _t("Fiscal machine serial");
    },
    get l10nVeLabelFiscalZ() {
        return _t("Z report number");
    },
    get l10nVeLabelControlNumber() {
        return _t("Control number");
    },
    get l10nVeShowFormaLibreDownload() {
        return (
            this.l10nVeJournalEmissionMedium === "free" &&
            Boolean(this.currentOrder.raw?.account_move)
        );
    },
    get l10nVeDownloadFormaLibreLabel() {
        return _t("Download free-form PDF");
    },
    get l10nVeDash() {
        return "—";
    },
    async l10nVeDownloadFormaLibre() {
        const moveId = this.currentOrder.raw?.account_move;
        if (!moveId) {
            return;
        }
        try {
            await this.invoiceService.downloadPdf(moveId);
        } catch {
            this.notification.add(_t("Could not download the invoice."), { type: "danger" });
        }
    },
});
