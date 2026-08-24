import {floatIsZero, roundPrecision} from "@web/core/utils/numbers";
import {PosOrder} from "@point_of_sale/app/models/pos_order";
import {patch} from "@web/core/utils/patch";

const posOrderTaxTotalsDescriptor = Object.getOwnPropertyDescriptor(
    PosOrder.prototype,
    "taxTotals"
);
const rawTaxTotalsGetter = posOrderTaxTotalsDescriptor.get;

function l10nVePosCurrencyIdsSet(order) {
    const jsonIds = order.company?.l10n_ve_igtf_currency_pos_ids_json;
    if (jsonIds) {
        try {
            const ids = JSON.parse(jsonIds);
            if (Array.isArray(ids)) {
                return new Set(ids);
            }
        } catch {
            return new Set();
        }
    }
    const raw = order.company?.l10n_ve_igtf_currency_ids;
    const ids = Array.isArray(raw) ? raw : [];
    return new Set(
        ids.map((item) => {
            if (typeof item === "object" && item !== null) {
                return item.id ?? item;
            }
            return item;
        })
    );
}

function l10nVePosPaymentMethodAppliesIgtf(order, paymentMethod) {
    if (!order.company?.l10n_ve_igtf_feature_active) {
        return false;
    }
    const allowed = l10nVePosCurrencyIdsSet(order);
    if (!allowed.size) {
        return false;
    }
    const cur = paymentMethod?.payment_currency_id;
    const curId = typeof cur === "object" ? cur?.id : cur;
    return Boolean(curId && allowed.has(curId));
}

function l10nVePosClearPaymentIgtf(paymentLine) {
    paymentLine.update({
        include_igtf: false,
        igtf_amount: 0,
        foreign_igtf_amount: 0,
    });
}

function l10nVePosIsChangePaymentLine(isReturn, amountPay) {
    if (isReturn) {
        return amountPay > 0;
    }
    return amountPay < 0;
}

function l10nVePosCappedPayAmount(amountPay, maxTotalWithTax, isReturn) {
    if (isReturn && amountPay < maxTotalWithTax) {
        return maxTotalWithTax;
    }
    if (!isReturn && amountPay > maxTotalWithTax) {
        return maxTotalWithTax;
    }
    return amountPay;
}

function l10nVePosLineIgtfAmounts(paymentLine, amountPay, percent, orderCurrency) {
    const foreignPay =
        typeof paymentLine.getPaymentAmountCurrency === "function"
            ? paymentLine.getPaymentAmountCurrency()
            : amountPay;
    const payCur =
        typeof paymentLine.getPaymentCurrency === "function"
            ? paymentLine.getPaymentCurrency()
            : orderCurrency;
    const igtfLine = roundPrecision(
        amountPay * (percent / 100),
        orderCurrency.rounding
    );
    if (payCur && orderCurrency && payCur.id !== orderCurrency.id) {
        return {
            igtfLine,
            igtfForeign: roundPrecision(
                foreignPay * (percent / 100),
                payCur.decimal_places
            ),
        };
    }
    return {igtfLine, igtfForeign: igtfLine};
}

function l10nVePosResetOrderIgtf(order) {
    for (const paymentLine of order.payment_ids) {
        l10nVePosClearPaymentIgtf(paymentLine);
    }
    order.update({igtf_amount: 0, bi_igtf: 0});
}

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.igtf_amount = vals.igtf_amount ?? 0;
        this.bi_igtf = vals.bi_igtf ?? 0;
    },

    l10n_ve_pos_updateIgtf() {
        const company = this.company;
        if (!company?.l10n_ve_igtf_feature_active || !this.is_to_invoice()) {
            l10nVePosResetOrderIgtf(this);
            return;
        }
        const percent = company.l10n_ve_igtf_percent ?? 0;
        let sumIgtf = 0;
        let sumBi = 0;
        const baseTotals = rawTaxTotalsGetter.call(this);
        const maxTotalWithTax = baseTotals.order_sign * baseTotals.order_total;
        const isReturn = maxTotalWithTax < 0;

        for (const paymentLine of this.payment_ids) {
            l10nVePosClearPaymentIgtf(paymentLine);
            if (!paymentLine.payment_method_id || paymentLine.is_change) {
                continue;
            }
            if (
                !l10nVePosPaymentMethodAppliesIgtf(this, paymentLine.payment_method_id)
            ) {
                continue;
            }
            let amountPay = paymentLine.get_amount();
            if (l10nVePosIsChangePaymentLine(isReturn, amountPay)) {
                continue;
            }
            amountPay = l10nVePosCappedPayAmount(amountPay, maxTotalWithTax, isReturn);
            const {igtfLine, igtfForeign} = l10nVePosLineIgtfAmounts(
                paymentLine,
                amountPay,
                percent,
                this.currency
            );
            paymentLine.update({
                include_igtf: true,
                igtf_amount: igtfLine,
                foreign_igtf_amount: igtfForeign,
            });
            sumIgtf += igtfLine;
            sumBi += amountPay;
        }
        this.update({
            igtf_amount: sumIgtf,
            bi_igtf: sumBi,
        });
    },

    get taxTotals() {
        const base = rawTaxTotalsGetter.call(this);
        const igtfExtra = this.igtf_amount || 0;
        if (
            !this.company?.l10n_ve_igtf_feature_active ||
            !this.is_to_invoice() ||
            floatIsZero(igtfExtra, this.currency.decimal_places)
        ) {
            return base;
        }
        const adjustedOrderTotal = base.order_total + igtfExtra;
        let remaining = adjustedOrderTotal;
        const documentSign = base.order_sign;
        const validPayments = this.payment_ids.filter(
            (paymentLine) => paymentLine.is_done() && !paymentLine.is_change
        );
        let order_rounding = 0;
        for (const [payment, isLast] of validPayments.map((paymentLine, index) => [
            paymentLine,
            index === validPayments.length - 1,
        ])) {
            const paymentAmount = documentSign * payment.get_amount();
            if (isLast && this.config.cash_rounding) {
                const roundedRemaining = this.getRoundedRemaining(
                    this.config.rounding_method,
                    remaining
                );
                if (
                    !floatIsZero(
                        paymentAmount - remaining,
                        this.currency.decimal_places
                    )
                ) {
                    order_rounding = roundedRemaining - remaining;
                }
            }
            remaining -= paymentAmount;
        }
        const remaining_with_rounding = remaining + order_rounding;
        return {
            ...base,
            order_total: adjustedOrderTotal,
            order_remaining: remaining,
            order_rounding,
            order_has_zero_remaining: floatIsZero(
                remaining_with_rounding,
                this.currency.decimal_places
            ),
        };
    },

    add_paymentline(...args) {
        const result = super.add_paymentline(...args);
        if (result) {
            this.l10n_ve_pos_updateIgtf();
        }
        return result;
    },

    remove_paymentline(...args) {
        super.remove_paymentline(...args);
        this.l10n_ve_pos_updateIgtf();
    },

    set_to_invoice(...args) {
        super.set_to_invoice(...args);
        this.l10n_ve_pos_updateIgtf();
    },
});
