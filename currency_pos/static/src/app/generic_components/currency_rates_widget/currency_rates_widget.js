import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { formatMajorExchangeRateLabel } from "@currency_pos/app/utils/payment_currency_utils";

export class CurrencyRatesWidget extends Component {
    static template = "currency_pos.CurrencyRatesWidget";
    static props = {};

    setup() {
        super.setup();
        this.pos = usePos();
    }

    get rates() {
        const rates = [];
        if (!this.pos?.models) {
            return rates;
        }

        const currencyModel = this.pos.models["res.currency"];
        const companyCurrency = this.companyCurrency;
        if (!currencyModel || !companyCurrency) {
            return rates;
        }

        currencyModel.forEach((currency) => {
            if (currency.id === companyCurrency.id) {
                return;
            }
            const label = formatMajorExchangeRateLabel(
                companyCurrency,
                currency,
                this.pos.models
            );
            if (!label) {
                return;
            }
            rates.push({
                currency,
                label,
            });
        });

        return rates;
    }

    get companyCurrency() {
        return this.pos?.company?.currency_id;
    }
}
