import {PosPayment} from "@point_of_sale/app/models/pos_payment";
import {patch} from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(vals);
        this.include_igtf = vals.include_igtf ?? false;
        this.igtf_amount = vals.igtf_amount ?? 0;
        this.foreign_igtf_amount = vals.foreign_igtf_amount ?? 0;
    },

    getPaymentCurrency() {
        const currency =
            this.payment_currency_id || this.payment_method_id?.payment_currency_id;
        if (!currency) {
            return this.pos_order_id?.currency;
        }
        if (typeof currency === "object") {
            return currency;
        }
        return (
            this.models?.["res.currency"]?.get(currency) || this.pos_order_id?.currency
        );
    },

    getPaymentAmountCurrency() {
        return this.get_amount();
    },
});
