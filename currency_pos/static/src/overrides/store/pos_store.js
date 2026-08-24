import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { EventBus } from "@odoo/owl";

import { getPaymentMethodCurrency } from "@currency_pos/app/utils/payment_currency_utils";

patch(PosStore.prototype, {
    async setup(...args) {
        await super.setup(...args);
        this.currencyEventBus = new EventBus();
        this.exchange_currency_id = this._getDefaultPricelistCurrency();
        await this.currencyPosRefreshForeignProductPrices();
    },

    _getCurrencyRecord(currencyLike) {
        if (!currencyLike) {
            return null;
        }
        if (typeof currencyLike === "object") {
            return currencyLike;
        }
        return this.models["res.currency"]?.find((currency) => currency.id === currencyLike) || null;
    },

    _getDefaultPricelistCurrency() {
        const pricelist = this.config?.pricelist_id;
        return this._getCurrencyRecord(pricelist?.currency_id) || this.company?.currency_id || null;
    },

    setExchangeCurrency(currency) {
        const oldCurrency = this.exchange_currency_id;
        this.exchange_currency_id = currency;
        if (oldCurrency !== currency) {
            this.currencyEventBus.trigger("change:exchange_currency_id", currency);
        }
    },

    getExchangeCurrency() {
        return (
            this.exchange_currency_id ||
            this._getDefaultPricelistCurrency() ||
            this.company?.currency_id
        );
    },

    getExchangeCurrencyForDisplay() {
        return this.exchange_currency_id || this._getDefaultPricelistCurrency();
    },

    getPaymentMethodDisplayText(pm, order) {
        const baseText = super.getPaymentMethodDisplayText(pm, order);
        const currency =
            getPaymentMethodCurrency(pm, this.models, null) ||
            this.company?.currency_id ||
            this.currency;
        if (!currency?.name) {
            return baseText;
        }
        return `${baseText} - ${currency.name}`;
    },

    _currencyPosIsForeignProduct(product) {
        const posCurrencyId = this.currency?.id;
        if (!product || !posCurrencyId) {
            return false;
        }
        const productCurrencyId = product.currency_id?.id || product.currency_id;
        return Boolean(productCurrencyId && productCurrencyId !== posCurrencyId);
    },

    async currencyPosApplyProductPrices(products) {
        const productList = (products || []).filter((product) => product?.id);
        if (!productList.length || !this.config?.id) {
            return productList;
        }
        const prices = await this.data.call(
            "product.product",
            "currency_pos_get_product_prices",
            [productList.map((product) => product.id), this.config.id]
        );
        const posCurrencyId = this.currency?.id;
        for (const product of productList) {
            const converted = prices[product.id];
            if (!converted) {
                continue;
            }
            product.update({
                lst_price: converted.lst_price,
                standard_price: converted.standard_price,
            });
            product.currency_pos_lst_price = converted.currency_pos_lst_price;
            product.currency_pos_standard_price = converted.currency_pos_standard_price;
            product._currencyPosPriceCurrencyId =
                converted._currency_pos_price_currency_id || posCurrencyId;
            if (product.raw) {
                product.raw.currency_pos_lst_price = converted.currency_pos_lst_price;
                product.raw.currency_pos_standard_price =
                    converted.currency_pos_standard_price;
                product.raw._currency_pos_price_currency_id =
                    converted._currency_pos_price_currency_id || posCurrencyId;
            }
        }
        return productList;
    },

    async currencyPosRefreshForeignProductPrices() {
        const products = this.models["product.product"]
            .getAll()
            .filter((product) => this._currencyPosIsForeignProduct(product));
        for (let index = 0; index < products.length; index += 50) {
            await this.currencyPosApplyProductPrices(products.slice(index, index + 50));
        }
    },

    async processProductAttributesByProducts(products) {
        const idsBefore = new Set(
            this.models["product.product"].getAll().map((product) => product.id)
        );
        await super.processProductAttributesByProducts(...arguments);
        const newProducts = this.models["product.product"]
            .getAll()
            .filter((product) => !idsBefore.has(product.id));
        if (newProducts.length) {
            await this.currencyPosApplyProductPrices(newProducts);
        }
    },

    async editProduct(product) {
        const originalDoAction = this.action.doAction.bind(this.action);
        this.action.doAction = (actionRequest, options = {}) => {
            if (options?.props?.onSave) {
                const originalOnSave = options.props.onSave;
                options.props.onSave = async (record) => {
                    await originalOnSave(record);
                    const productRecord = this.models["product.product"].get(
                        record.evalContext.id
                    );
                    if (productRecord) {
                        await this.currencyPosApplyProductPrices([productRecord]);
                    }
                };
            }
            return originalDoAction(actionRequest, options);
        };
        try {
            return await super.editProduct(...arguments);
        } finally {
            this.action.doAction = originalDoAction;
        }
    },

    _currencyPosAvailablePricelists() {
        if (this.config?.use_pricelist) {
            return this.config.available_pricelist_ids || [];
        }
        return this.config?.pricelist_id ? [this.config.pricelist_id] : [];
    },

    _currencyPosFixProductInfoPricelists(product, quantity, priceExtra, productInfo) {
        if (!product || !productInfo?.pricelists?.length) {
            return;
        }
        const posCurrency = this.currency;
        const available = this._currencyPosAvailablePricelists();
        const byId = Object.fromEntries(available.map((pricelist) => [pricelist.id, pricelist]));
        for (const row of productInfo.pricelists) {
            const pricelist = byId[row.id] || this.models["product.pricelist"]?.get?.(row.id);
            if (!pricelist) {
                continue;
            }
            const pricePos = product.get_price(pricelist, quantity, priceExtra);
            row.price = pricePos;
            row.price_pos_currency = pricePos;
            row.currency_id = posCurrency?.id;
            const pricelistCurrency = pricelist.currency_id;
            row.pricelist_currency_id = pricelistCurrency?.id;
            row.pricelist_currency_name = pricelistCurrency?.name;
            row.pricelist_currency_symbol =
                pricelistCurrency?.symbol || pricelistCurrency?.name;
            if (row.price_pricelist_currency == null) {
                if (
                    pricelistCurrency &&
                    posCurrency &&
                    pricelistCurrency.id !== posCurrency.id &&
                    typeof product.convertCurrency === "function"
                ) {
                    row.price_pricelist_currency = product.convertCurrency(
                        pricePos,
                        posCurrency,
                        pricelistCurrency
                    );
                } else {
                    row.price_pricelist_currency = pricePos;
                }
            }
        }
    },

    async getProductInfo(product, quantity, priceExtra = 0) {
        const order = this.get_order();
        const pricelist = order?.pricelist_id || this.config.pricelist_id;
        if (product) {
            await this.currencyPosApplyProductPrices([product]);
        }
        const originalCall = this.data.call.bind(this.data);
        this.data.call = async (model, method, args = [], ...rest) => {
            if (model === "product.product" && method === "get_product_info_pos") {
                const price = product.get_price(pricelist, quantity, priceExtra);
                args = [
                    [product.id],
                    price,
                    quantity,
                    this.config.id,
                    pricelist?.id || false,
                ];
            }
            return originalCall(model, method, args, ...rest);
        };
        try {
            const result = await super.getProductInfo(product, quantity, priceExtra);
            this._currencyPosFixProductInfoPricelists(
                product,
                quantity,
                priceExtra,
                result?.productInfo
            );
            if (product && result?.productInfo?.all_prices) {
                const standardPrice =
                    typeof product._currencyPosResolveStandardPrice === "function"
                        ? product._currencyPosResolveStandardPrice()
                        : product.standard_price;
                const priceWithoutTax = result.productInfo.all_prices.price_without_tax;
                const margin = priceWithoutTax - standardPrice;
                result.costCurrency = this.env.utils.formatCurrency(standardPrice);
                result.marginCurrency = this.env.utils.formatCurrency(margin);
                result.marginPercent = priceWithoutTax
                    ? Math.round((margin / priceWithoutTax) * 10000) / 100
                    : 0;
            }
            return result;
        } finally {
            this.data.call = originalCall;
        }
    },
});


