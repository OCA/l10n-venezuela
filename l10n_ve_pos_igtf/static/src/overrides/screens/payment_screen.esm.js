import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {_t} from "@web/core/l10n/translation";
import {floatIsZero} from "@web/core/utils/numbers";
import {patch} from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    get l10nVePosShowIgtf() {
        const order = this.currentOrder;
        if (!order?.company?.l10n_ve_igtf_feature_active || !order.is_to_invoice?.()) {
            return false;
        }
        return !floatIsZero(order.igtf_amount || 0, order.currency.decimal_places);
    },

    get l10nVePosIgtfPercent() {
        return this.currentOrder?.company?.l10n_ve_igtf_percent ?? 0;
    },

    get l10nVePosIgtfAmountText() {
        return this.env.utils.formatCurrency(this.currentOrder?.igtf_amount || 0);
    },

    get l10nVePosTotalWithoutIgtfText() {
        const order = this.currentOrder;
        const total = (order?.getTotalDue?.() || 0) - (order?.igtf_amount || 0);
        return this.env.utils.formatCurrency(total);
    },

    get l10nVePosIgtfLabel() {
        return `${_t("IGTF")} (${this.l10nVePosIgtfPercent}%)`;
    },

    get l10nVePosTotalLabel() {
        return _t("Total");
    },

    async addNewPaymentLine(...args) {
        const result = await super.addNewPaymentLine(...args);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
        return result;
    },

    updateSelectedPaymentline(...args) {
        super.updateSelectedPaymentline(...args);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
    },

    toggleIsToInvoice(...args) {
        super.toggleIsToInvoice(...args);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
    },
});
