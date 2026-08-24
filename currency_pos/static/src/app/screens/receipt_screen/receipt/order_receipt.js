import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { formatFloat } from "@web/core/utils/numbers";

patch(OrderReceipt.prototype, {
    formatReceiptPaymentForeignAmount(line) {
        if (!line?.is_foreign_currency_payment) {
            return "";
        }
        const decimalPlaces = line.payment_currency_decimal_places ?? 2;
        const formattedAmount = formatFloat(line.payment_currency_amount, {
            digits: [true, decimalPlaces],
        });
        const symbol = line.payment_currency_symbol || line.payment_currency_name || "";
        return `${formattedAmount} ${symbol}`.trim();
    },
});
