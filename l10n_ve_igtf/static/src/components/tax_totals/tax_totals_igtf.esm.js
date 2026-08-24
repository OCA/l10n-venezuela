import {TaxTotalsComponent} from "@account/components/tax_totals/tax_totals";
import {formatMonetary} from "@web/views/fields/formatters";
import {patch} from "@web/core/utils/patch";

patch(TaxTotalsComponent.prototype, {
    formatMonetaryCompany(value) {
        if (value === undefined || value === null) {
            return "";
        }
        return formatMonetary(value, {currencyId: this.totals?.company_currency_id});
    },
});
