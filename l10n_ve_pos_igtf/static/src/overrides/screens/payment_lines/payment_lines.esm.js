import {PaymentScreenPaymentLines} from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import {_t} from "@web/core/l10n/translation";
import {formatCurrency as formatCurrencyById} from "@web/core/currency";
import {patch} from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
    l10nVePosIgtfLineLabel(line) {
        const percent = line.pos_order_id?.company?.l10n_ve_igtf_percent ?? 0;
        return `${_t("IGTF")} (${percent}%)`;
    },

    l10nVePosFormatIgtfLine(line) {
        const orderCur = line.pos_order_id?.currency;
        const payCur =
            typeof line.getPaymentCurrency === "function"
                ? line.getPaymentCurrency()
                : orderCur;
        const igtfOrder = this.env.utils.formatCurrency(line.igtf_amount ?? 0);
        if (payCur && orderCur && payCur.id !== orderCur.id) {
            const foreign = line.foreign_igtf_amount ?? 0;
            const igtfForeign = formatCurrencyById(foreign, payCur.id, {});
            return `${igtfOrder} / ${igtfForeign}`;
        }
        return igtfOrder;
    },
});
