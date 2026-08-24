import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { convertCurrency } from "@currency_pos/app/utils/payment_currency_utils";
import { roundPrecision } from "@web/core/utils/numbers";
import { patch } from "@web/core/utils/patch";

function resolveCurrencyId(currencyLike) {
    if (!currencyLike) {
        return null;
    }
    if (Array.isArray(currencyLike)) {
        return currencyLike[0];
    }
    if (currencyLike.id) {
        return currencyLike.id;
    }
    return currencyLike;
}

patch(ProductProduct.prototype, {
    convertCurrency(amount, fromCurrency, toCurrency) {
        if (amount === null || amount === undefined || isNaN(amount)) {
            return amount || 0;
        }
        if (!fromCurrency || !toCurrency) {
            return amount;
        }
        return convertCurrency(amount, fromCurrency, toCurrency, this.models);
    },

    _currencyPosGetCurrency(currencyLike) {
        const currencyId = resolveCurrencyId(currencyLike);
        if (!currencyId) {
            return null;
        }
        return (
            this.models["res.currency"]?.get?.(currencyId) ||
            this.models["res.currency"]?.find?.((currency) => currency.id === currencyId) ||
            null
        );
    },

    _currencyPosGetPosCurrency() {
        const posConfig = this.models["pos.config"]?.getFirst?.();
        return this._currencyPosGetCurrency(posConfig?.currency_id);
    },

    _currencyPosGetPriceCurrencyId() {
        return (
            this._currencyPosPriceCurrencyId ||
            this.raw?._currency_pos_price_currency_id ||
            null
        );
    },

    _currencyPosGetRawListPrice() {
        const raw = this.currency_pos_lst_price ?? this.raw?.currency_pos_lst_price;
        return raw === undefined ? null : raw;
    },

    _currencyPosGetRawStandardPrice() {
        const raw =
            this.currency_pos_standard_price ?? this.raw?.currency_pos_standard_price;
        return raw === undefined ? null : raw;
    },

    _currencyPosResolveListPrice(list_price) {
        if (list_price !== false && list_price !== undefined && list_price !== null) {
            return list_price;
        }
        const posCurrency = this._currencyPosGetPosCurrency();
        const productCurrency = this._currencyPosGetCurrency(this.currency_id);
        if (!posCurrency || !productCurrency || productCurrency.id === posCurrency.id) {
            return list_price;
        }
        const raw = this._currencyPosGetRawListPrice();
        if (raw !== null) {
            return this.convertCurrency(raw, productCurrency, posCurrency);
        }
        if (this._currencyPosGetPriceCurrencyId() === posCurrency.id) {
            return list_price;
        }
        return this.convertCurrency(this.lst_price || 0, productCurrency, posCurrency);
    },

    _currencyPosResolveStandardPrice() {
        const posCurrency = this._currencyPosGetPosCurrency();
        const costCurrency =
            this._currencyPosGetCurrency(this.cost_currency_id) ||
            this._currencyPosGetCurrency(this.currency_id);
        if (!posCurrency || !costCurrency || costCurrency.id === posCurrency.id) {
            return this.standard_price;
        }
        const raw = this._currencyPosGetRawStandardPrice();
        if (raw !== null) {
            return this.convertCurrency(raw, costCurrency, posCurrency);
        }
        if (this._currencyPosGetPriceCurrencyId() === posCurrency.id) {
            return this.standard_price;
        }
        return this.convertCurrency(this.standard_price || 0, costCurrency, posCurrency);
    },

    _currencyPosConvertRuleAmount(amount, ruleCurrency, posCurrency) {
        if (!amount) {
            return 0;
        }
        if (!ruleCurrency || !posCurrency || ruleCurrency.id === posCurrency.id) {
            return amount;
        }
        return this.convertCurrency(amount, ruleCurrency, posCurrency);
    },

    get_price(
        pricelist,
        quantity,
        price_extra = 0,
        recurring = false,
        list_price = false,
        original_line = false,
        related_lines = []
    ) {
        const resolvedListPrice = this._currencyPosResolveListPrice(list_price);
        const result = super.get_price(
            pricelist,
            quantity,
            price_extra,
            recurring,
            resolvedListPrice,
            original_line,
            related_lines
        );
        const rule = this.getPricelistRule(pricelist, quantity);
        if (!rule) {
            return result;
        }

        const posCurrency = this._currencyPosGetPosCurrency();
        const ruleCurrency = this._currencyPosGetCurrency(rule.currency_id);
        if (!posCurrency || !ruleCurrency || ruleCurrency.id === posCurrency.id) {
            return result;
        }

        if (rule.compute_price === "fixed") {
            return this.convertCurrency(rule.fixed_price, ruleCurrency, posCurrency);
        }

        if (rule.compute_price !== "formula") {
            return result;
        }

        let price =
            (resolvedListPrice === false || resolvedListPrice === undefined
                ? this.lst_price
                : resolvedListPrice) + (price_extra || 0);
        if (rule.base === "pricelist") {
            if (rule.base_pricelist_id) {
                price = this.get_price(rule.base_pricelist_id, quantity, 0, true, list_price);
            }
        } else if (rule.base === "standard_price") {
            price = this._currencyPosResolveStandardPrice();
        }

        const priceLimit = price;
        price -= price * (rule.price_discount / 100);
        if (rule.price_round) {
            price = roundPrecision(price, rule.price_round);
        }
        if (rule.price_surcharge) {
            price += this._currencyPosConvertRuleAmount(
                rule.price_surcharge,
                ruleCurrency,
                posCurrency
            );
        }
        if (rule.price_min_margin) {
            price = Math.max(
                price,
                priceLimit +
                    this._currencyPosConvertRuleAmount(
                        rule.price_min_margin,
                        ruleCurrency,
                        posCurrency
                    )
            );
        }
        if (rule.price_max_margin) {
            price = Math.min(
                price,
                priceLimit +
                    this._currencyPosConvertRuleAmount(
                        rule.price_max_margin,
                        ruleCurrency,
                        posCurrency
                    )
            );
        }
        return price;
    },
});
