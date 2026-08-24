/**
 * Currency conversion utilities for POS multi-currency payments.
 */
import { formatFloat } from "@web/core/utils/numbers";

export function getCurrencyRecord(models, currencyLike) {
    if (!currencyLike || !models) {
        return null;
    }
    if (typeof currencyLike === "object") {
        if (Array.isArray(currencyLike)) {
            currencyLike = currencyLike[0];
        } else if (currencyLike.id) {
            return currencyLike;
        } else {
            return null;
        }
    }
    const currencyModel = models["res.currency"];
    if (!currencyModel) {
        return null;
    }
    if (currencyModel.get) {
        const byGet = currencyModel.get(currencyLike);
        if (byGet) {
            return byGet;
        }
    }
    return currencyModel.find?.((currency) => currency.id === currencyLike) || null;
}

/**
 * Resolve the currency of a POS payment method (relation, raw id, or fallback).
 */
export function getPaymentMethodCurrency(paymentMethod, models, fallbackCurrency = null) {
    if (!paymentMethod) {
        return fallbackCurrency;
    }
    const modelStore = models || paymentMethod.models;
    const candidates = [
        paymentMethod.payment_currency_id,
        paymentMethod.raw?.payment_currency_id,
    ];
    for (const currencyLike of candidates) {
        const currency = getCurrencyRecord(modelStore, currencyLike);
        if (currency) {
            return currency;
        }
    }
    return fallbackCurrency;
}

function getCompanyCurrency(models) {
    const company = models["res.company"]?.getFirst?.();
    return getCurrencyRecord(models, company?.currency_id);
}

function getLatestRate(models, currencyId) {
    const currencyRates = models["res.currency.rate"]?.readAll?.() || [];
    return currencyRates.find((rate) => {
        const rateCurrencyId = Array.isArray(rate.currency_id)
            ? rate.currency_id[0]
            : rate.currency_id?.id || rate.currency_id;
        return rateCurrencyId === currencyId;
    });
}

function getRateToCompanyCurrency(currencyRecord, models) {
    const companyCurrency = getCompanyCurrency(models);
    if (!currencyRecord || !companyCurrency || currencyRecord.id === companyCurrency.id) {
        return 1;
    }
    if (currencyRecord.inverse_rate) {
        return currencyRecord.inverse_rate;
    }
    if (currencyRecord.rate) {
        return 1 / currencyRecord.rate;
    }
    const rateRecord = getLatestRate(models, currencyRecord.id);
    if (rateRecord?.rate) {
        return 1 / rateRecord.rate;
    }
    return 1;
}

function getRateFromCompanyCurrency(currencyRecord, models) {
    const companyCurrency = getCompanyCurrency(models);
    if (!currencyRecord || !companyCurrency || currencyRecord.id === companyCurrency.id) {
        return 1;
    }
    if (currencyRecord.rate) {
        return currencyRecord.rate;
    }
    if (currencyRecord.inverse_rate) {
        return 1 / currencyRecord.inverse_rate;
    }
    const rateRecord = getLatestRate(models, currencyRecord.id);
    if (rateRecord?.rate) {
        return rateRecord.rate;
    }
    return 1;
}

export function getExchangeRate(fromCurrency, toCurrency, models) {
    const from = getCurrencyRecord(models, fromCurrency);
    const to = getCurrencyRecord(models, toCurrency);
    if (!from || !to || from.id === to.id) {
        return 1;
    }

    const companyCurrency = getCompanyCurrency(models);
    if (!companyCurrency) {
        return 1;
    }

    if (from.id === companyCurrency.id) {
        return getRateFromCompanyCurrency(to, models);
    }
    if (to.id === companyCurrency.id) {
        return getRateToCompanyCurrency(from, models);
    }
    return getRateToCompanyCurrency(from, models) * getRateFromCompanyCurrency(to, models);
}

export function convertCurrency(amount, fromCurrency, toCurrency, models) {
    const from = getCurrencyRecord(models, fromCurrency);
    const to = getCurrencyRecord(models, toCurrency);
    if (!from || !to || from.id === to.id) {
        return amount;
    }
    const rate = getExchangeRate(from, to, models);
    return amount * rate;
}

export function formatPaymentCurrencyAmount(amount, currency) {
    const decimalPlaces = currency?.decimal_places ?? 2;
    return formatFloat(amount ?? 0, {
        digits: [true, decimalPlaces],
    });
}

/**
 * Build a rate label always using the stronger currency as the unit:
 * e.g. "1$ = 732.00 Bs" or "1€ = 900.00 Bs" (never "1 Bs = 0.001 $").
 */
export function formatMajorExchangeRateLabel(currencyA, currencyB, models) {
    const left = getCurrencyRecord(models, currencyA);
    const right = getCurrencyRecord(models, currencyB);
    if (!left || !right || left.id === right.id) {
        return "";
    }
    const rightPerLeft = getExchangeRate(left, right, models);
    if (!rightPerLeft || rightPerLeft <= 0) {
        return "";
    }
    if (rightPerLeft >= 1) {
        const leftSymbol = left.symbol || left.name || "";
        const rightSymbol = right.symbol || right.name || "";
        const formattedRate = formatFloat(rightPerLeft, {
            digits: [true, Math.max(right.decimal_places ?? 2, 2)],
        });
        return `1${leftSymbol} = ${formattedRate} ${rightSymbol}`;
    }
    const leftPerRight = 1 / rightPerLeft;
    const rightSymbol = right.symbol || right.name || "";
    const leftSymbol = left.symbol || left.name || "";
    const formattedRate = formatFloat(leftPerRight, {
        digits: [true, Math.max(left.decimal_places ?? 2, 2)],
    });
    return `1${rightSymbol} = ${formattedRate} ${leftSymbol}`;
}

export function formatOrderCurrencyRateLabel(orderCurrency, foreignCurrency, models) {
    return formatMajorExchangeRateLabel(orderCurrency, foreignCurrency, models);
}

export function getConfiguredPaymentCurrencyRateLabels(
    paymentMethods,
    orderCurrency,
    models,
    config
) {
    if (!config?.allow_multi_currency_payment || !orderCurrency || !paymentMethods?.length) {
        return [];
    }
    const seen = new Set();
    const labels = [];
    for (const paymentMethod of paymentMethods) {
        const paymentCurrency = getCurrencyRecord(models, paymentMethod.payment_currency_id);
        if (!paymentCurrency || paymentCurrency.id === orderCurrency.id) {
            continue;
        }
        if (seen.has(paymentCurrency.id)) {
            continue;
        }
        seen.add(paymentCurrency.id);
        const label = formatOrderCurrencyRateLabel(orderCurrency, paymentCurrency, models);
        if (label) {
            labels.push(label);
        }
    }
    return labels;
}

export function convertOrderRemainingToForeign(order, paymentCurrency, models) {
    const paymentCurrencyRecord = getCurrencyRecord(models, paymentCurrency);
    const orderCurrency = order.currency;
    if (!paymentCurrencyRecord || !orderCurrency || !order.taxTotals) {
        return 0;
    }
    const due =
        order.taxTotals.order_sign * (order.taxTotals.order_remaining || 0);
    if (!due) {
        return 0;
    }
    return convertCurrency(due, orderCurrency, paymentCurrencyRecord, models);
}

export function isForeignPaymentMethod(paymentMethod, orderCurrency, config) {
    if (!config?.allow_multi_currency_payment || !paymentMethod || !orderCurrency) {
        return false;
    }
    const paymentCurrency = getCurrencyRecord(
        paymentMethod.models ? paymentMethod : null,
        paymentMethod.payment_currency_id
    );
    if (!paymentCurrency) {
        return false;
    }
    const orderCurrencyRecord =
        typeof orderCurrency === "object" ? orderCurrency : null;
    if (!orderCurrencyRecord) {
        return false;
    }
    return paymentCurrency.id !== orderCurrencyRecord.id;
}
