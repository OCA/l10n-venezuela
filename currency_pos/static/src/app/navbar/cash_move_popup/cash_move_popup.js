import { CashMovePopup } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_popup";
import { CashMoveReceipt } from "@point_of_sale/app/navbar/cash_move_popup/cash_move_receipt/cash_move_receipt";
import { patch } from "@web/core/utils/patch";
import { formatFloat } from "@web/core/utils/numbers";
import { parseFloat } from "@web/views/fields/parsers";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";
import { getPaymentMethodCurrency } from "@currency_pos/app/utils/payment_currency_utils";

const { DateTime } = luxon;

patch(CashMovePopup.prototype, {
    setup() {
        super.setup();
        const cashMethods = this.getCashPaymentMethods();
        this.state.paymentMethodId = cashMethods[0]?.id || false;
    },

    getCashPaymentMethods() {
        return this.pos.config.payment_method_ids.filter(
            (pm) => pm.is_cash_count || pm.type === "cash"
        );
    },

    getSelectedCashPaymentMethod() {
        const cashMethods = this.getCashPaymentMethods();
        return (
            cashMethods.find((pm) => pm.id === this.state.paymentMethodId) ||
            cashMethods[0] ||
            null
        );
    },

    _getCashMethodCurrency(paymentMethod) {
        return getPaymentMethodCurrency(paymentMethod, this.pos.models, this.pos.currency);
    },

    get selectedCashCurrency() {
        return this._getCashMethodCurrency(this.getSelectedCashPaymentMethod());
    },

    get showCashMethodSelector() {
        return this.getCashPaymentMethods().length > 1;
    },

    format(value) {
        if (!this.env.utils.isValidFloat(value)) {
            return "";
        }
        const amount = parseFloat(value);
        const currency = this.selectedCashCurrency;
        if (currency && currency.id !== this.pos.currency.id) {
            const formatted = formatFloat(amount, {
                digits: [true, currency.decimal_places ?? 2],
            });
            return `${formatted} ${currency.symbol || currency.name || ""}`.trim();
        }
        return this.env.utils.formatCurrency(amount);
    },

    async confirm() {
        const amount = parseFloat(this.state.amount);
        const formattedAmount = this.format(this.state.amount);
        if (!amount) {
            this.notification.add(_t("Cash in/out of %s is ignored.", formattedAmount));
            return this.props.close();
        }

        const type = this.state.type;
        const translatedType = _t(type);
        const paymentMethod = this.getSelectedCashPaymentMethod();
        const extras = {
            formattedAmount,
            translatedType,
            payment_method_id: paymentMethod?.id,
        };
        const reason = this.state.reason.trim();

        await this.pos.data.call(
            "pos.session",
            "try_cash_in_out",
            this._prepare_try_cash_in_out_payload(type, amount, reason, extras),
            {},
            true
        );
        await this.pos.logEmployeeMessage(
            `${_t("Cash")} ${translatedType} - ${_t("Amount")}: ${formattedAmount}`,
            "CASH_DRAWER_ACTION"
        );
        await this.printer.print(CashMoveReceipt, {
            reason,
            translatedType,
            formattedAmount,
            headerData: this.pos.getReceiptHeaderData(),
            date: formatDateTime(DateTime.now()),
        });

        this.props.close();
        this.notification.add(
            _t("Successfully made a cash %s of %s.", type, formattedAmount),
            3000
        );
    },
});
