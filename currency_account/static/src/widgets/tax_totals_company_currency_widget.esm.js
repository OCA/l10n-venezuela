/** @odoo-module **/

import {Component, onWillRender, toRaw} from "@odoo/owl";
import {formatMonetary} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class TaxTotalsCompanyCurrencyWidget extends Component {
    static props = {...standardFieldProps};
    static template = "currency_account.TaxTotalsCompanyCurrencyWidget";

    setup() {
        super.setup();
        this.taxTotals = null;
        this.currencyId = null;
        this.companyCurrencyId = null;
        this.formatData(this.props);
        onWillRender(() => this.formatData(this.props));
    }

    formatData(props) {
        const totals = JSON.parse(JSON.stringify(toRaw(props.record.data.tax_totals)));
        if (!totals) {
            this.taxTotals = null;
            return;
        }
        this.taxTotals = totals;

        // Obtener las monedas desde tax_totals
        if (this.taxTotals) {
            this.currencyId = this.taxTotals.currency_id;
            this.companyCurrencyId = this.taxTotals.company_currency_id;
        }
    }

    formatAmount(amount, useCompanyCurrency = false) {
        if (amount === undefined || amount === null) {
            return "";
        }
        const currencyId = useCompanyCurrency
            ? this.companyCurrencyId
            : this.currencyId;
        return formatMonetary(amount, {currencyId});
    }
}

registry.category("fields").add("tax_totals_company_currency_widget", {
    component: TaxTotalsCompanyCurrencyWidget,
});
