import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import { patch } from "@web/core/utils/patch";

patch(ProductInfoPopup.prototype, {
    getPricelistPriceLabel(pricelist) {
        return this.env.utils.formatCurrency(pricelist.price || 0);
    },

    getPricelistSecondaryPrice(pricelist) {
        const posCurrencyId = this.pos.currency?.id;
        if (
            !pricelist.pricelist_currency_id ||
            !posCurrencyId ||
            pricelist.pricelist_currency_id === posCurrencyId
        ) {
            return null;
        }
        const symbol =
            pricelist.pricelist_currency_symbol || pricelist.pricelist_currency_name || "";
        const amount = Number(pricelist.price_pricelist_currency || 0).toLocaleString("es-ES", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return `${symbol} ${amount}`;
    },
});
