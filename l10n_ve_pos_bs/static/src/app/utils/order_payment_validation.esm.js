// Copyright 2026 BWEALTHICS LLC
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {NumberPopup} from "@point_of_sale/app/components/popups/number_popup/number_popup";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import {TextInputPopup} from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import {_t} from "@web/core/l10n/translation";
import {makeAwaitable} from "@point_of_sale/app/utils/make_awaitable_dialog";
import {patch} from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        if ((await super.askBeforeValidation(...arguments)) === false) {
            return false;
        }
        return this._l10nVeCaptureVesPayments();
    },

    async _l10nVeCaptureVesPayments() {
        const payments = this.order.payment_ids.filter(
            (payment) => payment.payment_method_id?.l10n_ve_ves_tender && payment.amount
        );
        if (!payments.length) {
            return true;
        }

        const ves = this.pos.models["res.currency"]
            .getAll()
            .find((currency) => currency.name === "VES");
        const posCurrency = this.pos.currency;
        const rate = ves?.rate && posCurrency.rate ? ves.rate / posCurrency.rate : 0;
        if (!ves || rate <= 0) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("VES exchange rate unavailable"),
                body: _t(
                    "Activate VES and configure its exchange rate before taking this payment."
                ),
            });
            return false;
        }

        for (const payment of payments) {
            if (!(await this._l10nVeCaptureVesPayment(payment, ves, rate))) {
                return false;
            }
        }
        return true;
    },

    _l10nVeVesPaymentIsCaptured(payment) {
        const requireReference = payment.payment_method_id.l10n_ve_require_reference;
        return (
            payment.l10n_ve_amount_ves &&
            payment.l10n_ve_ves_rate > 0 &&
            this.pos.currency.equal(payment.l10n_ve_pos_amount, payment.amount) &&
            (!requireReference || (payment.payment_ref_no || "").trim())
        );
    },

    async _l10nVeCaptureVesPayment(payment, ves, rate) {
        if (this._l10nVeVesPaymentIsCaptured(payment)) {
            return true;
        }
        const sign = payment.amount < 0 ? -1 : 1;
        const expectedAmount = ves.round(Math.abs(payment.amount) * rate);
        const amount = await makeAwaitable(this.pos.dialog, NumberPopup, {
            title:
                sign < 0
                    ? _t("%s - VES refunded", payment.payment_method_id.name)
                    : _t("%s - VES received", payment.payment_method_id.name),
            subtitle: _t(
                "Expected at rate %s: VES %s. Enter the exact receipt amount.",
                rate.toFixed(6),
                expectedAmount.toFixed(2)
            ),
            startingValue: (
                Math.abs(payment.l10n_ve_amount_ves || 0) || expectedAmount
            ).toFixed(2),
        });
        if (amount === undefined) {
            return false;
        }
        const amountVes = ves.round(parseFloat(String(amount).replace(",", ".")) || 0);
        if (amountVes <= 0) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Invalid VES amount"),
                body: _t("The exact VES amount must be greater than zero."),
            });
            return false;
        }

        let reference = (payment.payment_ref_no || "").trim();
        if (payment.payment_method_id.l10n_ve_require_reference) {
            reference = await makeAwaitable(this.pos.dialog, TextInputPopup, {
                title: _t("%s - Transaction reference", payment.payment_method_id.name),
                startingValue: reference,
            });
            if (reference === undefined) {
                return false;
            }
            reference = String(reference).trim();
            if (!reference) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Transaction reference required"),
                    body: _t("Enter the reference shown on the payment receipt."),
                });
                return false;
            }
        }

        payment.l10n_ve_amount_ves = sign * amountVes;
        payment.l10n_ve_ves_rate = rate;
        payment.l10n_ve_pos_amount = payment.amount;
        payment.payment_ref_no = reference;
        return true;
    },
});
