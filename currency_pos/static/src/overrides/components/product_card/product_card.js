import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { patch } from "@web/core/utils/patch";

patch(ProductCard.prototype, {
    get productPrice() {
        if (!this.props.product) {
            return "";
        }

        try {
            const pos = this.env.services.pos;
            const price = pos.getProductPrice(this.props.product);
            return this.env.utils.formatCurrency(price);
        } catch (error) {
            console.warn("Error calculating product price:", error);
            return "";
        }
    },

    get productPricesInOtherCurrencies() {
        if (!this.props.product) {
            return [];
        }

        try {
            const prices = [];
            const pos = this.env.services.pos;
            const posCurrency = pos.currency;
            const price = pos.getProductPrice(this.props.product);
            const currencies = pos.models["res.currency"]
                .readAll()
                .filter((currency) => currency.id !== posCurrency.id);

            for (const currency of currencies) {
                try {
                    const convertedPrice = this.props.product.convertCurrency(
                        price,
                        posCurrency,
                        currency
                    );
                    const formattedPrice = `${currency.symbol || currency.name} ${convertedPrice.toLocaleString(
                        "es-ES",
                        { minimumFractionDigits: 2, maximumFractionDigits: 2 }
                    )}`;
                    prices.push({
                        currency: currency,
                        price: formattedPrice,
                    });
                } catch (error) {
                    console.warn(
                        "Error calculating price for currency " + currency.name + ":",
                        error
                    );
                }
            }

            return prices;
        } catch (error) {
            console.warn("Error calculating prices in other currencies:", error);
            return [];
        }
    },
});
