import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("PosPaymentCurrencyTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Tour MC Product", "1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank EUR"),
            PaymentScreen.clickPaymentMethod("Bank EUR"),
            PaymentScreen.validateButtonIsHighlighted(true),
            PaymentScreen.clickValidate(),
            ProductScreen.isShown(),
        ].flat(),
});
