import { describe, expect, test } from "@odoo/hoot";
import {
    buildOpeningCashByMethod,
    resolvePreviousOpeningAmount,
} from "../../src/app/utils/opening_cash_utils";
import { Base } from "@point_of_sale/app/models/related_models";

describe("opening cash previous balances", () => {
    test("uses previous box opening when present for every method", () => {
        expect(
            resolvePreviousOpeningAmount({
                paymentMethodId: 10,
                openings: { 10: 5, 20: 100 },
                isPrimary: true,
                cashRegisterBalanceStart: 999,
            })
        ).toBe(5);
        expect(
            resolvePreviousOpeningAmount({
                paymentMethodId: 20,
                openings: { 10: 5, 20: 100 },
                isPrimary: false,
                cashRegisterBalanceStart: 999,
            })
        ).toBe(100);
    });

    test("falls back to session start only for primary cash method", () => {
        expect(
            resolvePreviousOpeningAmount({
                paymentMethodId: 10,
                openings: {},
                isPrimary: true,
                cashRegisterBalanceStart: 12.5,
            })
        ).toBe(12.5);
        expect(
            resolvePreviousOpeningAmount({
                paymentMethodId: 20,
                openings: {},
                isPrimary: false,
                cashRegisterBalanceStart: 12.5,
            })
        ).toBe(0);
    });

    test("reads openings keys as string from JSON maps", () => {
        expect(
            resolvePreviousOpeningAmount({
                paymentMethodId: 20,
                openings: { "20": 88 },
                isPrimary: false,
            })
        ).toBe(88);
    });

    test("builds formatted opening cash values for mixed currencies", () => {
        const usd = { id: 1, decimal_places: 2, symbol: "$" };
        const eur = { id: 2, decimal_places: 2, symbol: "€" };
        const cashUsd = { id: 10, name: "Cash USD" };
        const cashEur = { id: 20, name: "Cash EUR" };
        const values = buildOpeningCashByMethod({
            cashPaymentMethods: [cashUsd, cashEur],
            openings: { 10: 5, 20: 20 },
            primaryPaymentMethod: cashUsd,
            cashRegisterBalanceStart: 0,
            getCurrency: (pm) => (pm.id === 20 ? eur : usd),
            companyCurrency: usd,
            formatCurrency: (amount) => amount.toFixed(2),
            formatFloat: (amount, { digits }) => amount.toFixed(digits[1]),
        });
        expect(values[10]).toBe("5.00");
        expect(values[20]).toBe("20.00");
    });

    test("POS session Base.setup only keeps underscore custom fields", () => {
        const record = Object.create(Base.prototype);
        record.model = { modelFields: {} };
        record.setup({
            id: 1,
            rt_cash_box_openings: { 10: 5, 20: 20 },
            _oca_cash_box_openings: { 10: 5, 20: 20 },
            _base_url: "http://example.test",
        });
        expect(record.rt_cash_box_openings).toBe(undefined);
        expect(record._oca_cash_box_openings).toEqual({ 10: 5, 20: 20 });
        expect(record._base_url).toBe("http://example.test");
    });
});
