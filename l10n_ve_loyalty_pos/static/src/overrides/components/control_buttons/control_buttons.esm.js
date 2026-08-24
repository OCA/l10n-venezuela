/* eslint-disable complexity */
import {AlertDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {ControlButtons} from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import {NumberPopup} from "@point_of_sale/app/utils/input_popups/number_popup";
import {SelectionPopup} from "@point_of_sale/app/utils/input_popups/selection_popup";
import {_t} from "@web/core/l10n/translation";
import {makeAwaitable} from "@point_of_sale/app/store/make_awaitable_dialog";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(ControlButtons.prototype, {
    _l10nVeCompanyIsVenezuela() {
        return isVenezuelaCompany(this.pos);
    },

    async onClickL10nVeGlobalDiscount() {
        const order = this.pos.get_order();
        if (!order || !this._l10nVeCompanyIsVenezuela()) {
            return;
        }

        const action = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Global discount"),
            list: [
                {
                    id: "add_fixed",
                    item: {action: "add", discountType: "fixed"},
                    label: _t("Add fixed amount"),
                },
                {
                    id: "add_percent",
                    item: {action: "add", discountType: "percentage"},
                    label: _t("Add percentage"),
                },
                {
                    id: "remove",
                    item: {action: "remove"},
                    label: _t("Remove a discount"),
                },
            ],
        });
        if (!action) {
            return;
        }

        if (action.action === "remove") {
            await this._l10nVeRemoveGlobalDiscount(order);
            return;
        }
        await this._l10nVeAddGlobalDiscount(order, action.discountType);
    },

    _l10nVeGetDiscountReasons() {
        const model = this.pos.models["l10n.ve.discount.reason"];
        const reasons = model?.getAll ? model.getAll() : [];
        const seen = new Set();
        return reasons
            .filter((reason) => reason.active !== false)
            .sort((a, b) => (a.sequence || 0) - (b.sequence || 0) || a.id - b.id)
            .filter((reason) => {
                const key = (reason.name || "").trim().toLowerCase();
                if (!key || seen.has(key)) {
                    return false;
                }
                seen.add(key);
                return true;
            });
    },

    _l10nVeGetFixedDiscountCurrencies(order) {
        const resolve = (currency) => order._l10nVeResolveCurrency(currency);
        const currencies = [];
        const seen = new Set();
        const pushCurrency = (currency) => {
            const resolved = resolve(currency);
            if (!resolved || seen.has(resolved.id)) {
                return;
            }
            seen.add(resolved.id);
            currencies.push(resolved);
        };

        pushCurrency(order._l10nVeGetOrderCurrency());
        pushCurrency(this.pos.company?.currency_id);
        pushCurrency(this.pos.config?.currency_id);

        const currencyModel = this.pos.models["res.currency"];
        const allCurrencies = currencyModel?.getAll ? currencyModel.getAll() : [];
        for (const currency of allCurrencies) {
            if (currency.name === "USD" || currency.symbol === "$") {
                pushCurrency(currency);
            }
        }
        for (const method of this.pos.config?.payment_method_ids || []) {
            pushCurrency(method.payment_currency_id);
        }
        return currencies;
    },

    async _l10nVeSelectFixedDiscountCurrency(order) {
        const currencies = this._l10nVeGetFixedDiscountCurrencies(order);
        if (!currencies.length) {
            return order._l10nVeGetOrderCurrency();
        }
        if (currencies.length === 1) {
            return currencies[0];
        }
        return await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Discount currency"),
            list: currencies.map((currency) => ({
                id: currency.id,
                item: currency,
                label: `${currency.name} (${currency.symbol})`,
            })),
        });
    },

    async _l10nVeAddGlobalDiscount(order, discountType) {
        const reasons = this._l10nVeGetDiscountReasons();
        let reasonName = _t("Global discount");
        let reasonId = false;
        if (reasons.length) {
            const reason = await makeAwaitable(this.dialog, SelectionPopup, {
                title: _t("Discount reason"),
                list: reasons.map((discountReason) => ({
                    id: discountReason.id,
                    item: discountReason,
                    label: discountReason.name,
                })),
            });
            if (!reason) {
                return;
            }
            reasonName = reason.name;
            reasonId = reason.id;
        }

        const isPercentage = discountType === "percentage";
        let amountCurrency = order._l10nVeGetOrderCurrency();
        let amountBase = "untaxed";
        if (!isPercentage) {
            amountCurrency = await this._l10nVeSelectFixedDiscountCurrency(order);
            if (!amountCurrency) {
                return;
            }
            const baseChoice = await makeAwaitable(this.dialog, SelectionPopup, {
                title: _t("Discount amount base"),
                list: [
                    {
                        id: "untaxed",
                        item: "untaxed",
                        label: _t("Subtotal"),
                    },
                    {
                        id: "total",
                        item: "total",
                        label: _t("Total"),
                    },
                ],
            });
            if (!baseChoice) {
                return;
            }
            amountBase = baseChoice;
        }

        const amountTitle = amountCurrency?.symbol
            ? _t("Discount amount (%s)", amountCurrency.symbol)
            : _t("Discount amount");
        const input = await makeAwaitable(this.dialog, NumberPopup, {
            title: isPercentage ? _t("Discount percentage") : amountTitle,
            startingValue: isPercentage ? 10 : 0,
        });
        if (input === undefined || input === null || input === "") {
            return;
        }
        const value = Math.abs(parseFloat(String(input).replace(",", ".")));
        if (Number.isNaN(value) || value <= 0) {
            this.dialog.add(AlertDialog, {
                title: _t("Invalid discount"),
                body: _t("Enter a value greater than zero."),
            });
            return;
        }

        let amountInOrderCurrency = value;
        if (!isPercentage) {
            const orderCurrency = order._l10nVeGetOrderCurrency();
            amountInOrderCurrency = order._l10nVeRoundInCurrency(
                order._l10nVeConvertAmount(value, amountCurrency, orderCurrency),
                orderCurrency
            );
        }

        const result = order._l10nVeApplyManualGlobalDiscount({
            amount: isPercentage ? 0 : amountInOrderCurrency,
            discountType: isPercentage ? "percentage" : "fixed",
            percentage: isPercentage ? value / 100 : 0,
            name: reasonName,
            reasonId,
            amountBase,
        });
        if (result !== true) {
            this.dialog.add(AlertDialog, {
                title: _t("Global discount"),
                body: result,
            });
        }
    },

    async _l10nVeRemoveGlobalDiscount(order) {
        const groups = order.taxTotals?.l10n_ve_global_discount_lines || [];
        if (!groups.length) {
            this.dialog.add(AlertDialog, {
                title: _t("Global discount"),
                body: _t("There are no global discounts to remove."),
            });
            return;
        }
        const selected = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Remove discount"),
            list: groups.map((group) => ({
                id: group.id,
                item: group,
                label: `${group.name}: ${this.env.utils.formatCurrency(group.amount)}`,
            })),
        });

        if (!selected) {
            return;
        }
        order._l10nVeRemoveGlobalDiscountGroup(selected.id);
    },
});
