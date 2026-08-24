import { describe, expect, test } from "@odoo/hoot";
import { convertCurrency } from "../../src/app/utils/payment_currency_utils";

function buildModels({ rates = [], currencies = [] }, companyCurrencyId = 1) {
    return {
        "res.company": {
            getFirst() {
                return { currency_id: { id: companyCurrencyId } };
            },
        },
        "res.currency": {
            get(id) {
                return currencies.find((currency) => currency.id === id);
            },
            find(fn) {
                return currencies.find(fn);
            },
        },
        "res.currency.rate": {
            readAll() {
                return rates;
            },
        },
    };
}

describe("currency_pos product price conversion", () => {
    test("formula surcharge converts from rule currency to pos currency", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 2.0, inverse_rate: 0.5 };
        const models = buildModels({ currencies: [usd, eur] });

        const basePricePos = 50;
        const surchargeEur = 10;
        const surchargePos = convertCurrency(surchargeEur, eur, usd, models);
        expect(surchargePos).toBe(5);
        expect(basePricePos + surchargePos).toBe(55);
    });

    test("fixed price converts from rule currency to pos currency", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 2.0, inverse_rate: 0.5 };
        const models = buildModels({ currencies: [usd, eur] });
        expect(convertCurrency(20, eur, usd, models)).toBe(10);
    });
});
