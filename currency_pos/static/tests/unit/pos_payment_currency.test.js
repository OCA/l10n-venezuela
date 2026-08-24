import { describe, expect, test } from "@odoo/hoot";
import {
    convertCurrency,
    convertOrderRemainingToForeign,
    formatOrderCurrencyRateLabel,
    formatPaymentCurrencyAmount,
    getConfiguredPaymentCurrencyRateLabels,
    getExchangeRate,
} from "../../src/app/utils/payment_currency_utils";

function buildModels({ rates = [], currencies = [] }, companyCurrencyId = 1) {
    return {
        "res.company": {
            getFirst() {
                return { currency_id: { id: companyCurrencyId } };
            },
        },
        "res.currency": currencies,
        "res.currency.rate": {
            readAll() {
                return rates;
            },
        },
    };
}

describe("currency_pos utils", () => {
    test("same currency keeps amount unchanged", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const models = buildModels({ currencies: [usd] });
        expect(convertCurrency(10, usd, usd, models)).toBe(10);
        expect(getExchangeRate(usd, usd, models)).toBe(1);
    });

    test("converts from company currency to foreign currency", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 2.0, inverse_rate: 0.5 };
        const models = buildModels({ currencies: [usd, eur] });
        expect(getExchangeRate(usd, eur, models)).toBe(2);
        expect(convertCurrency(10, usd, eur, models)).toBe(20);
    });

    test("converts from foreign currency to company currency", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 2.0, inverse_rate: 0.5 };
        const models = buildModels({ currencies: [usd, eur] });
        expect(getExchangeRate(eur, usd, models)).toBe(0.5);
        expect(convertCurrency(20, eur, usd, models)).toBe(10);
    });

    test("converts high-rate foreign currency like bolivars", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const ves = { id: 3, decimal_places: 2, rate: 550, inverse_rate: 1 / 550 };
        const models = buildModels({ currencies: [usd, ves] });
        expect(getExchangeRate(usd, ves, models)).toBe(550);
        expect(convertCurrency(15.5, usd, ves, models)).toBe(8525);
        expect(convertCurrency(8525, ves, usd, models)).toBe(15.5);
    });

    test("falls back to res.currency.rate records when needed", () => {
        const usd = { id: 1, decimal_places: 2 };
        const ves = { id: 3, decimal_places: 2 };
        const models = buildModels(
            {
                currencies: [usd, ves],
                rates: [{ currency_id: 3, rate: 550 }],
            },
            1
        );
        expect(convertCurrency(15.5, usd, ves, models)).toBe(8525);
    });

    test("converts order due to eur for default payment amount", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 1.4, inverse_rate: 1 / 1.4 };
        const models = buildModels({ currencies: [usd, eur] });
        expect(convertCurrency(15.5, usd, eur, models)).toBe(21.7);
    });

    test("small bolivar payments keep precise order remaining", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const ves = { id: 3, decimal_places: 2, rate: 550, inverse_rate: 1 / 550 };
        const models = buildModels({ currencies: [usd, ves] });
        const oneBsInUsd = convertCurrency(1, ves, usd, models);
        expect(oneBsInUsd).toBeCloseTo(1 / 550, 10);
        expect(oneBsInUsd).not.toBe(0);

        const remaining = 15.5 - oneBsInUsd;
        const foreignRemaining = convertOrderRemainingToForeign(
            {
                currency: usd,
                taxTotals: { order_remaining: remaining, order_sign: 1 },
            },
            ves,
            models
        );
        expect(foreignRemaining).toBeCloseTo(8524, 0);
    });

    test("ten bolivars reduce remaining by ten not eleven", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const ves = { id: 3, decimal_places: 2, rate: 550, inverse_rate: 1 / 550 };
        const models = buildModels({ currencies: [usd, ves] });
        const tenBsInUsd = convertCurrency(10, ves, usd, models);
        expect(tenBsInUsd).toBeCloseTo(10 / 550, 10);

        const remaining = 15.5 - tenBsInUsd;
        const foreignRemaining = convertOrderRemainingToForeign(
            {
                currency: usd,
                taxTotals: { order_remaining: remaining, order_sign: 1 },
            },
            ves,
            models
        );
        expect(foreignRemaining).toBeCloseTo(8515, 0);
    });

    test("formats foreign amounts without float artifacts", () => {
        const ves = { id: 3, decimal_places: 2, symbol: "Bs" };
        expect(formatPaymentCurrencyAmount(549.9999999999, ves)).toBe("550.00");
        expect(formatPaymentCurrencyAmount(10.1 + 0.2, ves)).toBe("10.30");
        expect(formatPaymentCurrencyAmount(0, ves)).toBe("0.00");
        expect(formatPaymentCurrencyAmount(-20, ves)).toBe("-20.00");
    });

    test("usd overpay yields negative remaining converted to foreign change", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const eur = { id: 2, decimal_places: 2, rate: 2.0, inverse_rate: 0.5 };
        const models = buildModels({ currencies: [usd, eur] });
        // Order 80 USD, paid 100 USD => remaining -20 USD
        const foreignRemaining = convertOrderRemainingToForeign(
            {
                currency: usd,
                taxTotals: { order_remaining: -20, order_sign: 1 },
            },
            eur,
            models
        );
        expect(foreignRemaining).toBe(-40);
        expect(formatPaymentCurrencyAmount(foreignRemaining, eur)).toBe("-40.00");
        // Default change payment line in EUR is negative (vuelto)
        const changePaymentForeign = convertCurrency(-20, usd, eur, models);
        expect(changePaymentForeign).toBe(-40);
    });

    test("negative order remaining keeps sign for foreign due", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1 };
        const ves = { id: 3, decimal_places: 2, rate: 550, inverse_rate: 1 / 550 };
        const models = buildModels({ currencies: [usd, ves] });
        const foreignRemaining = convertOrderRemainingToForeign(
            {
                currency: usd,
                taxTotals: { order_remaining: -10, order_sign: 1 },
            },
            ves,
            models
        );
        expect(foreignRemaining).toBe(-5500);
    });

    test("formats order currency rate labels for payment methods", () => {
        const usd = { id: 1, decimal_places: 2, rate: 1, inverse_rate: 1, symbol: "$" };
        const eur = { id: 2, decimal_places: 2, rate: 0.96, inverse_rate: 1 / 0.96, symbol: "€" };
        const ves = { id: 3, decimal_places: 2, rate: 500, inverse_rate: 1 / 500, symbol: "VES" };
        const models = buildModels({ currencies: [usd, eur, ves] });
        expect(formatOrderCurrencyRateLabel(usd, ves, models)).toBe("1$ = 500.00 VES");
        expect(formatOrderCurrencyRateLabel(usd, eur, models)).toBe("1€ = 1.04 $");
        expect(formatOrderCurrencyRateLabel(ves, usd, models)).toBe("1$ = 500.00 VES");

        const vesCompanyModels = buildModels({ currencies: [usd, eur, ves] }, 3);
        const usdVsVes = {
            ...usd,
            rate: 1 / 500,
            inverse_rate: 500,
        };
        const eurVsVes = {
            ...eur,
            rate: 1 / 900,
            inverse_rate: 900,
        };
        expect(formatOrderCurrencyRateLabel(ves, usdVsVes, vesCompanyModels)).toBe(
            "1$ = 500.00 VES"
        );
        expect(formatOrderCurrencyRateLabel(ves, eurVsVes, vesCompanyModels)).toBe(
            "1€ = 900.00 VES"
        );

        const labels = getConfiguredPaymentCurrencyRateLabels(
            [
                { id: 1, payment_currency_id: usd },
                { id: 2, payment_currency_id: ves },
                { id: 3, payment_currency_id: eur },
                { id: 4, payment_currency_id: ves },
            ],
            usd,
            models,
            { allow_multi_currency_payment: true }
        );
        expect(labels).toEqual(["1$ = 500.00 VES", "1€ = 1.04 $"]);
    });
});
