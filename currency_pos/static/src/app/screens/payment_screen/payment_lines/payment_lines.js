import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";
import { formatPaymentCurrencyAmount } from "../../../utils/payment_currency_utils";

patch(PaymentScreenPaymentLines.prototype, {
    getPaymentLineForeignAmountDisplay(line) {
        if (!line?.isForeignCurrencyPayment?.()) {
            return "";
        }
        const paymentCurrency = line.getPaymentCurrency();
        const amountCurrency = line.getPaymentAmountCurrency();
        const formattedAmount = formatPaymentCurrencyAmount(amountCurrency, paymentCurrency);
        const symbolOrName = paymentCurrency?.symbol || paymentCurrency?.name || "";
        return `${formattedAmount} ${symbolOrName}`.trim();
    },

    getPaymentLineOrderAmountDisplay(line) {
        return this.env.utils.formatCurrency(line.get_amount());
    },
});
