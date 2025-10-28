/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillRender, toRaw} from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { formatMonetary } from "@web/views/fields/formatters";


export class TotalCurrenciesWidget extends Component {
    static props = {...standardFieldProps,};
    static template = 'currency_account.TotalCurrenciesWidget';

    setup() {
        super.setup();
        this.totals = [];
        this.formatData(this.props);
        onWillRender(() => this.formatData(this.props));
    }

    formatData(props) {
        let totals = JSON.parse(props.record.data[this.props.name]);
        if (!totals) {
            return;
        }
        this.totals = Object.values(totals);
    }

    parseJson(value) {
        try {
            return JSON.parse(value);
        } catch (e) {
            console.error("Error al parsear JSON para total_currencies:", e);
            return {};
        }
    }

    formatAmount(total, key) {
        return formatMonetary(total[key], {currencyId: total["currency_id"]});
    }

}

registry.category("fields").add("total_currencies_widget",{component: TotalCurrenciesWidget} );
