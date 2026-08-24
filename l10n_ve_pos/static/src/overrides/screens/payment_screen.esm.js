import {onMounted, useState} from "@odoo/owl";
import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PaymentScreen.prototype, {
    _l10nVeJournalDisplayName(orderJournal, configJournal) {
        return (
            orderJournal?.display_name ||
            orderJournal?.name ||
            configJournal?.display_name ||
            configJournal?.name ||
            ""
        );
    },
    _l10nVeInitialEmissionState() {
        const orderJournal = this.currentOrder?.invoice_journal_id;
        const configJournal = this.pos.config?.invoice_journal_id;
        return {
            emission_medium:
                orderJournal?.l10n_ve_emission_medium ||
                configJournal?.l10n_ve_emission_medium ||
                "",
            journal_display_name: this._l10nVeJournalDisplayName(
                orderJournal,
                configJournal
            ),
            next_free_control_number:
                this.pos.config.l10n_ve_pos_next_free_control_number || "",
            next_fiscal_invoice_number: "",
            next_fiscal_serial: "",
            next_fiscal_report_z: "",
        };
    },
    setup() {
        super.setup(...arguments);
        this.l10nVeEmission = useState(this._l10nVeInitialEmissionState());
        onMounted(() => this.l10nVeRefreshEmissionPreview());
    },
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
        const journal = await this.pos.selectInvoiceJournal(this.currentOrder);
        if (journal) {
            await this.l10nVeRefreshEmissionPreview();
        }
    },
    _l10nVeApplyEmissionPreview(data) {
        if (!data) {
            return;
        }
        this.l10nVeEmission.emission_medium = data.emission_medium || "";
        this.l10nVeEmission.journal_display_name = data.journal_display_name || "";
        this.l10nVeEmission.next_free_control_number =
            data.next_free_control_number || "";
        this.l10nVeEmission.next_fiscal_invoice_number =
            data.next_fiscal_invoice_number || "";
        this.l10nVeEmission.next_fiscal_serial = data.next_fiscal_serial || "";
        this.l10nVeEmission.next_fiscal_report_z = data.next_fiscal_report_z || "";
    },

    _l10nVeOrderOrConfigJournal() {
        return (
            this.currentOrder?.invoice_journal_id || this.pos.config?.invoice_journal_id
        );
    },
    _l10nVeLocalEmissionPreviewFallback() {
        const journal = this._l10nVeOrderOrConfigJournal();
        return {
            emission_medium: journal?.l10n_ve_emission_medium || "",
            journal_display_name: journal?.display_name || journal?.name || "",
            next_free_control_number:
                this.pos.config?.l10n_ve_pos_next_free_control_number || "",
            next_fiscal_invoice_number:
                this.l10nVeEmission.next_fiscal_invoice_number || "",
            next_fiscal_serial: this.l10nVeEmission.next_fiscal_serial || "",
            next_fiscal_report_z: this.l10nVeEmission.next_fiscal_report_z || "",
            free_book_section_name:
                this.pos.config?.l10n_ve_pos_free_book_section_name || false,
        };
    },

    async l10nVeRefreshEmissionPreview() {
        if (!isVenezuelaCompany(this.pos)) {
            return;
        }
        const journalId = this.currentOrder?.invoice_journal_id?.id || false;
        try {
            const data = await this.pos.data.call(
                "pos.config",
                "l10n_ve_get_invoice_emission_preview",
                [[this.pos.config.id], journalId]
            );
            this._l10nVeApplyEmissionPreview(data);
        } catch {
            this._l10nVeApplyEmissionPreview(
                this._l10nVeLocalEmissionPreviewFallback()
            );
        }
    },
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
    get l10nVeInvoiceJournalDisplayName() {
        const orderJournal = this.currentOrder?.invoice_journal_id;
        if (orderJournal) {
            return (
                orderJournal.display_name || orderJournal.name || _t("Select journal")
            );
        }
        return this.l10nVeEmission.journal_display_name || _t("Select journal");
    },
    async afterOrderValidation() {
        if (isVenezuelaCompany(this.pos)) {
            this.pos.showScreen("ReceiptScreen");
            if (!this.pos.config.module_pos_restaurant) {
                this.pos.checkPreparationStateAndSentOrderInPreparation(
                    this.currentOrder
                );
            }
            return;
        }
        await super.afterOrderValidation(...arguments);
    },
    toggleIsToInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return;
        }
        super.toggleIsToInvoice(...arguments);
    },
    shouldDownloadInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },
    get l10nVeShowPaymentEmissionPanel() {
        if (!this.isVenezuelaPos || !this.currentOrder?.is_to_invoice?.()) {
            return false;
        }
        return ["free", "fiscal_machine", "digital"].includes(
            this.l10nVeJournalEmissionMedium
        );
    },
    get l10nVeJournalEmissionMedium() {
        const orderMedium =
            this.currentOrder?.invoice_journal_id?.l10n_ve_emission_medium;
        if (orderMedium) {
            return orderMedium;
        }
        return this.l10nVeEmission.emission_medium || "";
    },
    get l10nVeNextFreeControlNumber() {
        return this.l10nVeEmission.next_free_control_number || "";
    },
    get l10nVeLabelNextControl() {
        return _t("Next control number");
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
    get l10nVeDash() {
        return "—";
    },
    get l10nVeNextFreeControlNumberDisplay() {
        return this.l10nVeNextFreeControlNumber || this.l10nVeDash;
    },
    get l10nVeFiscalNextInvoiceNumberDisplay() {
        return this.l10nVeEmission.next_fiscal_invoice_number || this.l10nVeDash;
    },
    get l10nVeFiscalNextSerialDisplay() {
        return this.l10nVeEmission.next_fiscal_serial || this.l10nVeDash;
    },
    get l10nVeFiscalNextReportZDisplay() {
        return this.l10nVeEmission.next_fiscal_report_z || this.l10nVeDash;
    },
    get l10nVeLabelAmountWithoutTaxes() {
        return _t("Amount without taxes");
    },
    get l10nVeAmountWithoutTaxesDisplay() {
        if (!this.currentOrder) {
            return this.env.utils.formatCurrency(0);
        }
        return this.env.utils.formatCurrency(this.currentOrder.get_total_without_tax());
    },
});
