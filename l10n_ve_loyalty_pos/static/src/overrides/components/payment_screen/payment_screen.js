/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

function isPayLaterNoJournal(paymentMethod) {
    return Boolean(paymentMethod) && paymentMethod.type === "pay_later";
}

patch(PaymentScreen.prototype, {
    _l10nVeGetRefundedOriginalOrders(order) {
        const refundedLines = (order?.lines || []).filter(
            (line) => line.refunded_orderline_id
        );
        return [
            ...new Set(
                refundedLines
                    .map((line) => line.refunded_orderline_id.order_id)
                    .filter(Boolean)
            ),
        ];
    },

    _l10nVeGetOriginalNonCreditPaidAmount(order) {
        const originalOrders = this._l10nVeGetRefundedOriginalOrders(order);
        if (!originalOrders.length) {
            return null;
        }
        return originalOrders.reduce((total, original) => {
            const payments = (original.payment_ids || []).filter(
                (payment) => Number(payment.amount || 0) > 0
            );
            const nonCredit = payments.reduce((sum, payment) => {
                if (isPayLaterNoJournal(payment.payment_method_id)) {
                    return sum;
                }
                return sum + Number(payment.amount || 0);
            }, 0);
            return total + nonCredit;
        }, 0);
    },

    _l10nVeRefundedOrderPaidOnCredit(order) {
        const maxNonCredit = this._l10nVeGetOriginalNonCreditPaidAmount(order);
        return maxNonCredit !== null && maxNonCredit <= 0;
    },

    _l10nVeOrderHasPayLaterRefundCredit(order) {
        if (!order || order.get_total_with_tax() >= 0) {
            return false;
        }
        if (this._l10nVeRefundedOrderPaidOnCredit(order)) {
            return false;
        }
        return (order.payment_ids || []).some((payment) =>
            isPayLaterNoJournal(payment.payment_method_id)
        );
    },

    async addNewPaymentLine(paymentMethod) {
        const order = this.currentOrder;
        if (
            isVenezuelaCompany(this.pos) &&
            order &&
            isPayLaterNoJournal(paymentMethod) &&
            order.get_total_with_tax() < 0 &&
            !this._l10nVeRefundedOrderPaidOnCredit(order)
        ) {
            if (!order.get_partner()) {
                this.notification.add(
                    _t("Select a customer to credit the eWallet on refund."),
                    { type: "warning" }
                );
                const partner = await this.pos.selectPartner();
                if (!partner) {
                    return false;
                }
            }
            this.notification.add(
                _t("This credit payment will be added to the customer eWallet."),
                { type: "info" }
            );
        }
        return await super.addNewPaymentLine(...arguments);
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const partner = order?.get_partner?.();
        const shouldRefreshEwallet =
            isVenezuelaCompany(this.pos) &&
            this._l10nVeOrderHasPayLaterRefundCredit(order) &&
            partner;

        await super.validateOrder(...arguments);

        if (shouldRefreshEwallet && typeof this.pos._l10nVeRefreshPartnerEwalletCards === "function") {
            await this.pos._l10nVeRefreshPartnerEwalletCards(partner.id);
            if (typeof this.pos.updateRewards === "function") {
                this.pos.updateRewards();
            }
        }
    },
});
