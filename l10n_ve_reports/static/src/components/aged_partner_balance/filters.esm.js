import {AccountReport} from "@l10n_ve_reports/components/account_report/account_report";
import {AccountReportFilters} from "@l10n_ve_reports/components/account_report/filters/filters";
import {WarningDialog} from "@web/core/errors/error_dialogs";
import {_t} from "@web/core/l10n/translation";

export class AgedPartnerBalanceFilters extends AccountReportFilters {
    static template = "l10n_ve_reports.AgedPartnerBalanceFilters";

    // ------------------------------------------------------------------------------------------------------------------
    // Aging Interval
    // ------------------------------------------------------------------------------------------------------------------
    async setAgingInterval(ev) {
        const agingInterval = parseInt(ev.target.value, 10);
        if (agingInterval < 1) {
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Intervals cannot be smaller than 1"),
            });
            return;
        }

        await this.filterClicked({
            optionKey: "aging_interval",
            optionValue: agingInterval,
            reload: true,
        });
    }
}

AccountReport.registerCustomComponent(AgedPartnerBalanceFilters);
