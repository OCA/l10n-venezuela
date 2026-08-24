import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {OrderSummary} from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(OrderSummary.prototype, {
    _veIsPriceOnlyLine(line) {
        return Boolean(line?.product_id?.l10n_ve_pos_allow_price_change);
    },
    async updateSelectedOrderline({key}) {
        const selectedLine = this.pos.get_order()?.get_selected_orderline();
        if (
            isVenezuelaCompany(this.pos) &&
            selectedLine &&
            this._veIsPriceOnlyLine(selectedLine) &&
            this.pos.numpadMode !== "price"
        ) {
            this.numberBuffer.reset();
            if (key === "Backspace") {
                this._setValue("remove");
            } else {
                this.pos.numpadMode = "price";
            }
            return;
        }
        return await super.updateSelectedOrderline(...arguments);
    },
    _veResolveComboParent(line) {
        return line.combo_parent_id || line;
    },
    _veNumpadDecreaseLineQty(root) {
        const q = root.get_quantity();
        if (this.pos.isProductQtyZero(q)) {
            this.currentOrder.removeOrderline(root);
            this.numberBuffer.reset();
            return;
        }
        const newQ = q > 0 ? q - 1 : q + 1;
        const remove =
            this.pos.isProductQtyZero(newQ) ||
            (q > 0 && newQ < 0) ||
            (q < 0 && newQ > 0);
        if (remove) {
            this.currentOrder.removeOrderline(root);
        } else {
            const result = root.set_quantity(
                newQ,
                Boolean(root.combo_line_ids?.length)
            );
            for (const cl of root.combo_line_ids ?? []) {
                cl.set_quantity(newQ, true);
            }
            if (result !== true) {
                this.dialog.add(AlertDialog, result);
            }
        }
        this.numberBuffer.reset();
    },
    handleOrderLineQuantityChange(selectedLine) {
        if (isVenezuelaCompany(this.pos) && this._veIsPriceOnlyLine(selectedLine)) {
            this.numberBuffer.reset();
            this.pos.numpadMode = "price";
            return;
        }
        return super.handleOrderLineQuantityChange(...arguments);
    },
    async updateQuantityNumber() {
        const selectedLine = this.currentOrder.get_selected_orderline();
        if (isVenezuelaCompany(this.pos) && this._veIsPriceOnlyLine(selectedLine)) {
            this.numberBuffer.reset();
            this.pos.numpadMode = "price";
            return true;
        }
        return await super.updateQuantityNumber(...arguments);
    },
    _setValue(val) {
        const {numpadMode} = this.pos;
        const selectedLine = this.currentOrder.get_selected_orderline();
        if (selectedLine) {
            const root = this._veResolveComboParent(selectedLine);
            const priceOnly = this._veIsPriceOnlyLine(root);
            if (isVenezuelaCompany(this.pos) && priceOnly && val === "remove") {
                this.currentOrder.removeOrderline(root);
                this.numberBuffer.reset();
                this.pos.numpadMode = "quantity";
                return;
            }
            if (
                isVenezuelaCompany(this.pos) &&
                priceOnly &&
                ["quantity", "discount"].includes(numpadMode)
            ) {
                this.numberBuffer.reset();
                this.pos.numpadMode = "price";
                return;
            }
            if (
                numpadMode === "quantity" &&
                isVenezuelaCompany(this.pos) &&
                !root.refunded_orderline_id &&
                (val === "" || val === "remove")
            ) {
                this._veNumpadDecreaseLineQty(root);
                return;
            }
        }
        return super._setValue(...arguments);
    },
    async setLinePrice(line) {
        if (
            isVenezuelaCompany(this.pos) &&
            !line?.product_id?.l10n_ve_pos_allow_price_change
        ) {
            this.pos.notification.add(
                _t("Changing the price from the Point of Sale is not allowed."),
                {type: "warning"}
            );
            return;
        }
        return await super.setLinePrice(...arguments);
    },
});
