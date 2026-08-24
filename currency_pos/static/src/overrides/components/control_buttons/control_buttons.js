import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(ControlButtons.prototype, {
    get exchangeCurrency() {
        return this.pos.getExchangeCurrencyForDisplay();
    },

    getExchangeCurrencyList() {
        const currencyList = [];
        const currentExchangeCurrency =
            this.exchangeCurrency || this.pos._getDefaultPricelistCurrency();
        const companyCurrency = this.pos.company.currency_id;
        if (companyCurrency) {
            currencyList.push({
                id: companyCurrency.id,
                label: `${companyCurrency.name} (${companyCurrency.symbol})`,
                isSelected: currentExchangeCurrency?.id === companyCurrency.id,
                item: companyCurrency,
            });
        }
        const currencyModel = this.pos.models["res.currency"];
        if (currencyModel) {
            currencyModel.forEach((currency) => {
                if (currency.id !== companyCurrency?.id) {
                    currencyList.push({
                        id: currency.id,
                        label: `${currency.name} (${currency.symbol})`,
                        isSelected: currentExchangeCurrency?.id === currency.id,
                        item: currency,
                    });
                }
            });
        }
        return currencyList;
    },

    async clickExchangeCurrency() {
        const selectionList = this.getExchangeCurrencyList();
        const selectedCurrency = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Seleccionar moneda de cambio"),
            list: selectionList,
        });

        if (selectedCurrency) {
            this.pos.setExchangeCurrency(selectedCurrency);
            this.props.close?.();
        }
    },
});
