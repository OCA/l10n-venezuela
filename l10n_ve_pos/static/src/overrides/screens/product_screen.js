import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

function selectedLineAllowsPriceChange(pos) {
    const line = pos.get_order()?.get_selected_orderline();
    return Boolean(line?.product_id?.l10n_ve_pos_allow_price_change);
}

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!isVenezuelaCompany(this.pos)) {
            return buttons;
        }
        const priceOnly = selectedLineAllowsPriceChange(this.pos);
        return buttons.map((button) => {
            if (button.value === "price") {
                return { ...button, disabled: !priceOnly };
            }
            if (priceOnly && ["quantity", "discount"].includes(button.value)) {
                return { ...button, disabled: true };
            }
            return button;
        });
    },
    onNumpadClick(buttonValue) {
        if (!isVenezuelaCompany(this.pos)) {
            return super.onNumpadClick(...arguments);
        }
        const priceOnly = selectedLineAllowsPriceChange(this.pos);
        if (buttonValue === "price" && !priceOnly) {
            return;
        }
        if (priceOnly && ["quantity", "discount"].includes(buttonValue)) {
            return;
        }
        return super.onNumpadClick(...arguments);
    },
});
