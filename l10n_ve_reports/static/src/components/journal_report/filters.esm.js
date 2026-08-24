import {AccountReportFilters} from "@l10n_ve_reports/components/account_report/filters/filters";
import {patch} from "@web/core/utils/patch";

patch(AccountReportFilters.prototype, {
    get hasExtraOptionsFilter() {
        return (
            super.hasExtraOptionsFilter ||
            "show_payment_lines" in this.controller.options
        );
    },
});
