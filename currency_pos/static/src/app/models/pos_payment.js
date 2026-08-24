import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";
import { convertCurrency, getExchangeRate } from "../utils/payment_currency_utils";

Object.assign(PosPayment, {
    extraFields: {
        ...(PosPayment.extraFields || {}),
        payment_currency_id: {
            name: "payment_currency_id",
            type: "many2one",
            relation: "res.currency",
            model: "pos.payment",
        },
        payment_currency_amount: {
            name: "payment_currency_amount",
            type: "float",
            model: "pos.payment",
        },
        payment_currency_rate: {
            name: "payment_currency_rate",
            type: "float",
            model: "pos.payment",
        },
    },
});

patch(PosPayment.prototype, {
    _getCurrencyRecord(currencyLike) {
        if (!currencyLike) {
            return null;
        }
        if (typeof currencyLike === "object") {
            return currencyLike;
        }
        return this.models["res.currency"].find((currency) => currency.id === currencyLike) || null;
    },

    _getPaymentMethodRecord(paymentMethodLike) {
        if (!paymentMethodLike) {
            return null;
        }
        if (typeof paymentMethodLike === "object") {
            return paymentMethodLike;
        }
        return (
            this.models["pos.payment.method"].find((method) => method.id === paymentMethodLike) ||
            null
        );
    },

    setup(vals) {
        super.setup(...arguments);
        const orderCurrency = this.pos_order_id?.currency;
        const paymentMethod = this._getPaymentMethodRecord(
            vals.payment_method_id || this.payment_method_id
        );
        const methodCurrency = this._getCurrencyRecord(paymentMethod?.payment_currency_id);
        const paymentCurrency = this._getCurrencyRecord(vals.payment_currency_id);
        const resolvedCurrency = paymentCurrency || methodCurrency || orderCurrency;
        this.payment_currency_id = resolvedCurrency || null;
        this.payment_currency_amount = vals.payment_currency_amount ?? this.amount;
        this.payment_currency_rate = vals.payment_currency_rate || 1;
    },

    isForeignCurrencyPayment() {
        const config = this.pos_order_id?.config_id || this.pos_order_id?.config;
        if (!config?.allow_multi_currency_payment) {
            return false;
        }
        const orderCurrency = this.pos_order_id?.currency;
        const paymentCurrency = this.getPaymentCurrency();
        return Boolean(
            paymentCurrency && orderCurrency && paymentCurrency.id !== orderCurrency.id
        );
    },

    getPaymentCurrency() {
        const explicitCurrency = this._getCurrencyRecord(this.payment_currency_id);
        if (explicitCurrency) {
            return explicitCurrency;
        }
        const paymentMethod = this._getPaymentMethodRecord(this.payment_method_id);
        return (
            this._getCurrencyRecord(paymentMethod?.payment_currency_id) ||
            this.pos_order_id?.currency
        );
    },

    getPaymentAmountCurrency() {
        return this.payment_currency_amount ?? this.get_amount();
    },

    getPaymentRate() {
        return this.payment_currency_rate || 1;
    },

    convertAmountToOrderCurrency(amountCurrency) {
        const orderCurrency = this.pos_order_id?.currency;
        const paymentCurrency = this.getPaymentCurrency();
        if (!orderCurrency || !paymentCurrency || amountCurrency === null) {
            return amountCurrency;
        }
        if (paymentCurrency.id === orderCurrency.id) {
            return amountCurrency;
        }
        return convertCurrency(amountCurrency, paymentCurrency, orderCurrency, this.models);
    },

    set_amount_currency_foreign(amountCurrency) {
        this.pos_order_id.assert_editable();
        const paymentCurrency = this.getPaymentCurrency();
        const orderCurrency = this.pos_order_id?.currency;
        if (!paymentCurrency || !orderCurrency) {
            this.set_amount(amountCurrency);
            return;
        }
        const baseAmount = this.convertAmountToOrderCurrency(parseFloat(amountCurrency) || 0);
        this.update({
            amount: baseAmount || 0,
            payment_currency_amount: roundDecimals(
                parseFloat(amountCurrency) || 0,
                paymentCurrency.decimal_places ?? 2
            ),
            payment_currency_rate:
                getExchangeRate(paymentCurrency, orderCurrency, this.models) || 1,
        });
    },

    set_amount(value) {
        if (!this.pos_order_id?.assert_editable || !this.pos_order_id?.currency) {
            this.update({
                amount: parseFloat(value) || 0,
            });
            return;
        }
        if (this.isForeignCurrencyPayment()) {
            this.set_amount_currency_foreign(value);
            return;
        }
        super.set_amount(...arguments);
    },

    serialize(options = {}) {
        const data = super.serialize(...arguments);
        if (!options.orm || !this.isForeignCurrencyPayment?.()) {
            return data;
        }
        const paymentCurrency = this.getPaymentCurrency();
        if (!paymentCurrency) {
            return data;
        }
        return {
            ...data,
            payment_currency_id: paymentCurrency.id,
            payment_currency_amount: this.getPaymentAmountCurrency(),
            payment_currency_rate: this.getPaymentRate(),
        };
    },

    export_for_printing() {
        const data = super.export_for_printing(...arguments);
        const paymentCurrency = this.getPaymentCurrency();
        return {
            ...data,
            payment_currency_name: paymentCurrency?.name || "",
            payment_currency_symbol: paymentCurrency?.symbol || "",
            payment_currency_decimal_places: paymentCurrency?.decimal_places ?? 2,
            payment_currency_amount: this.getPaymentAmountCurrency(),
            payment_currency_rate: this.getPaymentRate(),
            is_foreign_currency_payment: this.isForeignCurrencyPayment(),
        };
    },
});
