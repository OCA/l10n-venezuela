import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { CurrencyRatesWidget } from "@currency_pos/app/generic_components/currency_rates_widget/currency_rates_widget";
import { patch } from "@web/core/utils/patch";

if (!OrderSummary.components) {
    OrderSummary.components = {};
}

OrderSummary.components.CurrencyRatesWidget = CurrencyRatesWidget;

patch(OrderSummary, {
    static: {
        components: {
            ...OrderSummary.components,
            CurrencyRatesWidget,
        },
    },
});
