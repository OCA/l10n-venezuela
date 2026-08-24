import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    async loadProductFromDB() {
        const products = await super.loadProductFromDB(...arguments);
        if (!products?.length) {
            return products;
        }
        await this.pos.currencyPosApplyProductPrices(products);
        return products;
    },
});
