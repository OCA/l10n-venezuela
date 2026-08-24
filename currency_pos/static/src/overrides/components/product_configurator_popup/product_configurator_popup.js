import { ProductConfiguratorPopup } from "@point_of_sale/app/store/product_configurator_popup/product_configurator_popup";
import { patch } from "@web/core/utils/patch";

patch(ProductConfiguratorPopup.prototype, {
    get unitPrice() {
        const product = this.state?.product || this.props.product;
        if (!product) {
            return this.env.utils.formatCurrency(0);
        }
        return this.env.utils.formatCurrency(this.pos.getProductPrice(product));
    },
});
