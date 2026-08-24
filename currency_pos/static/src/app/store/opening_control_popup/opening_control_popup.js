import { OpeningControlPopup } from "@point_of_sale/app/store/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { formatFloat } from "@web/core/utils/numbers";
import { MoneyDetailsPopup } from "@point_of_sale/app/utils/money_details_popup/money_details_popup";
import { _t } from "@web/core/l10n/translation";
import { RPCError } from "@web/core/network/rpc";
import { buildOpeningCashByMethod } from "@currency_pos/app/utils/opening_cash_utils";
import { getPaymentMethodCurrency } from "@currency_pos/app/utils/payment_currency_utils";

patch(OpeningControlPopup.prototype, {
    setup() {
        super.setup();
        this.moneyDetailsByMethod = {};
        const openings = this.pos.session._oca_cash_box_openings || {};
        this.state.openingCashByMethod = buildOpeningCashByMethod({
            cashPaymentMethods: this.getCashPaymentMethods(),
            openings,
            primaryPaymentMethod: this.getPrimaryCashPaymentMethod(),
            cashRegisterBalanceStart: this.pos.session.cash_register_balance_start || 0,
            getCurrency: (paymentMethod) => this._getCashMethodCurrency(paymentMethod),
            companyCurrency: this.pos.currency,
            formatCurrency: (amount, withSymbol) =>
                this.env.utils.formatCurrency(amount, withSymbol),
            formatFloat,
        });
    },

    getCashPaymentMethods() {
        return this.pos.config.payment_method_ids.filter((pm) => pm.is_cash_count || pm.type === "cash");
    },

    getPrimaryCashPaymentMethod() {
        return this.getCashPaymentMethods()[0] || null;
    },

    _getCashMethodCurrency(paymentMethod) {
        return getPaymentMethodCurrency(paymentMethod, this.pos.models, this.pos.currency);
    },

    formatOpeningCashLabel(paymentMethod) {
        return paymentMethod.name;
    },

    getCurrencySymbol(paymentMethod) {
        const currency = this._getCashMethodCurrency(paymentMethod);
        return currency?.symbol || currency?.name || "";
    },

    async confirm() {
        const cashboxValues = {};
        for (const paymentMethod of this.getCashPaymentMethods()) {
            const raw = this.state.openingCashByMethod[paymentMethod.id];
            if (!this.env.utils.isValidFloat(raw)) {
                return;
            }
            cashboxValues[paymentMethod.id] = this.env.utils.parseValidFloat(raw);
        }
        try {
            await this.pos.data.call(
                "pos.session",
                "oca_set_opening_control",
                [this.pos.session.id, cashboxValues, this.state.notes],
                {},
                true
            );
        } catch (error) {
            if (
                error instanceof RPCError &&
                error.data.name === "odoo.exceptions.MissingError" &&
                (await this.pos.isSessionDeleted())
            ) {
                return window.location.reload();
            }
            throw error;
        }
        this.pos.session.state = "opened";
        this.props.close();
    },

    async openDetailsPopup(paymentMethod) {
        const method = paymentMethod || this.getPrimaryCashPaymentMethod();
        if (!method) {
            return;
        }
        const action = _t("Cash control - opening");
        this.hardwareProxy.openCashbox(action);
        const currency = this._getCashMethodCurrency(method);
        this.dialog.add(MoneyDetailsPopup, {
            moneyDetails: this.moneyDetailsByMethod[method.id] || null,
            action: action,
            getPayload: (payload) => {
                if (payload) {
                    const { total, moneyDetails, moneyDetailsNotes } = payload;
                    const isForeign = currency && currency.id !== this.pos.currency.id;
                    this.state.openingCashByMethod[method.id] = isForeign
                        ? formatFloat(total, {
                              digits: [true, currency.decimal_places ?? 2],
                          })
                        : this.env.utils.formatCurrency(total, false);
                    if (method === this.getPrimaryCashPaymentMethod()) {
                        this.state.openingCash = this.state.openingCashByMethod[method.id];
                    }
                    if (moneyDetailsNotes) {
                        this.state.notes = moneyDetailsNotes;
                    }
                    this.moneyDetailsByMethod[method.id] = moneyDetails;
                }
            },
            context: "Opening",
        });
    },

    handleMethodInputChange(paymentMethod) {
        if (!this.env.utils.isValidFloat(this.state.openingCashByMethod[paymentMethod.id])) {
            return;
        }
        this.state.notes = "";
    },

    canConfirmOpening() {
        if (!this.cashMethodCount) {
            return true;
        }
        return this.getCashPaymentMethods().every((paymentMethod) =>
            this.env.utils.isValidFloat(this.state.openingCashByMethod[paymentMethod.id])
        );
    },
});
