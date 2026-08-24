import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import {
    convertCurrency,
    formatPaymentCurrencyAmount,
} from "../../../utils/payment_currency_utils";

patch(PaymentScreenStatus.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    },

    _getSelectedForeignPaymentContext() {
        const order = this.props.order;
        const selectedLine = order.get_selected_paymentline?.();
        if (!this.pos.config.allow_multi_currency_payment || !selectedLine) {
            return null;
        }
        if (!selectedLine.isForeignCurrencyPayment?.()) {
            return null;
        }
        const paymentCurrency = selectedLine.getPaymentCurrency?.();
        if (!paymentCurrency || paymentCurrency.id === order.currency?.id) {
            return null;
        }
        return { order, selectedLine, paymentCurrency };
    },

    getPaymentStatusCurrencyLabel() {
        const context = this._getSelectedForeignPaymentContext();
        if (!context) {
            return "";
        }
        const { paymentCurrency } = context;
        return paymentCurrency.name || paymentCurrency.symbol || "";
    },

    get remainingText() {
        const context = this._getSelectedForeignPaymentContext();
        if (!context) {
            const { order_has_zero_remaining, order_remaining, order_sign } =
                this.props.order.taxTotals;
            if (order_has_zero_remaining) {
                return this.env.utils.formatCurrency(0);
            }
            return this.env.utils.formatCurrency(order_sign * order_remaining);
        }
        const { order, paymentCurrency } = context;
        const due = order.get_due();
        const foreignDue = order.getForeignCurrencyRemaining(paymentCurrency);
        const formattedForeign = formatPaymentCurrencyAmount(foreignDue, paymentCurrency);
        const symbol = paymentCurrency.symbol || paymentCurrency.name || "";
        return `${formattedForeign} ${symbol} (${this.env.utils.formatCurrency(due)})`;
    },

    get changeText() {
        const context = this._getSelectedForeignPaymentContext();
        if (!context) {
            return this.env.utils.formatCurrency(-this.props.order.get_change());
        }
        const { order, paymentCurrency } = context;
        const changeDisplay = -order.get_change();
        const foreignChange = convertCurrency(
            changeDisplay,
            order.currency,
            paymentCurrency,
            this.pos.models
        );
        const formattedForeign = formatPaymentCurrencyAmount(foreignChange, paymentCurrency);
        const symbol = paymentCurrency.symbol || paymentCurrency.name || "";
        return `${formattedForeign} ${symbol} (${this.env.utils.formatCurrency(changeDisplay)})`;
    },
});
