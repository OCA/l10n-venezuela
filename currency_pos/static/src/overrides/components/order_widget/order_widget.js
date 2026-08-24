import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";
import { useState, onMounted, onWillUnmount } from "@odoo/owl";

patch(OrderWidget.prototype, {
    setup() {
        super.setup();
        this.pos = this.env.services.pos;
        this.currencyState = useState({
            exchangeCurrencyId: this.pos.getExchangeCurrencyForDisplay()?.id || null,
            updateKey: 0,
        });

        onMounted(() => {
            this.currencyState.exchangeCurrencyId =
                this.pos.getExchangeCurrencyForDisplay()?.id || null;
            this.currencyEventListener = () => {
                const currentExchangeCurrencyId = this.pos.getExchangeCurrencyForDisplay()?.id;
                if (this.currencyState.exchangeCurrencyId !== currentExchangeCurrencyId) {
                    this.currencyState.exchangeCurrencyId = currentExchangeCurrencyId;
                    this.currencyState.updateKey++;
                }
            };
            this.pos.currencyEventBus?.addEventListener(
                "change:exchange_currency_id",
                this.currencyEventListener
            );
        });

        onWillUnmount(() => {
            if (this.currencyEventListener) {
                this.pos.currencyEventBus?.removeEventListener(
                    "change:exchange_currency_id",
                    this.currencyEventListener
                );
            }
        });
    },

    getConvertedTotal() {
        void this.currencyState.updateKey;
        const exchangeCurrency = this.pos.getExchangeCurrencyForDisplay();
        if (!exchangeCurrency || !this.props.taxTotals) {
            return null;
        }

        const total = this.props.taxTotals.order_sign * this.props.taxTotals.order_total;
        const companyCurrency = this.pos.company.currency_id;
        if (!companyCurrency || exchangeCurrency.id === companyCurrency.id) {
            return null;
        }

        const products = this.pos.models["product.product"]?.readAll() || [];
        const sampleProduct = products.length > 0 ? products[0] : null;
        if (!sampleProduct?.convertCurrency) {
            return null;
        }

        const convertedTotal = sampleProduct.convertCurrency(
            total,
            companyCurrency,
            exchangeCurrency
        );
        const formattedTotal = convertedTotal.toFixed(2);
        const currencySymbol = exchangeCurrency.symbol || exchangeCurrency.name || "USD";
        return `${currencySymbol}${formattedTotal}`;
    },

    shouldShowTotalConversion() {
        void this.currencyState.updateKey;
        const exchangeCurrency = this.pos.getExchangeCurrencyForDisplay();
        const companyCurrency = this.pos.company.currency_id;
        return Boolean(
            exchangeCurrency &&
                companyCurrency &&
                exchangeCurrency.id !== companyCurrency.id &&
                this.props.taxTotals
        );
    },

    getAlternatePricelistTotals() {
        if (this.pos.mainScreen?.component?.name !== "ProductScreen") {
            return [];
        }
        const order = this.pos.get_order();
        if (!order || !this.props.taxTotals) {
            return [];
        }
        return order.getAlternatePricelistTotals?.() || [];
    },
});

