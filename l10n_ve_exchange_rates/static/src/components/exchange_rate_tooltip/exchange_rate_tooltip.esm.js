/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class ExchangeRateTooltip extends Component {
    static components = {Dropdown, DropdownItem};
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            rates: [],
            company_currency: null,
            featured: false,
            loading: false,
            showTooltip: false,
        });
        const d = new Date();
        this.currentDate = d.toLocaleString();

        onWillStart(() => this.getRates());
    }

    async getRates() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "res.currency",
                "get_exchange_rates",
                [],
                {}
            );
            this.state.rates = data.rates;
            this.state.company_currency = data.company_currency;
            this.state.featured = data.featured || false;
        } catch {
            this.state.rates = [];
        } finally {
            this.state.loading = false;
        }
    }
}

ExchangeRateTooltip.template = "l10n_ve_exchange_rates.ExchangeRateTooltip";

registry.category("systray").add("ExchangeRateTooltip", {
    Component: ExchangeRateTooltip,
    sequence: 1,
});
