/**
 * Currency conversion utilities for POS
 * Provides functions to convert amounts between currencies using exchange rates
 */

/**
 * Convert an amount from one currency to another using the available currency rates
 * @param {number} amount - The amount to convert
 * @param {Object} fromCurrency - The source currency object
 * @param {Object} toCurrency - The target currency object
 * @param {Object} models - The POS models object containing currency rates
 * @returns {number} - The converted amount
 */
export function convertCurrency(amount, fromCurrency, toCurrency, models) {
    if (!fromCurrency || !toCurrency || fromCurrency.id === toCurrency.id) {
        return amount;
    }

    // Get currency rates from the models
    const currencyRates = models["res.currency.rate"]?.readAll() || [];

    // Get company currency (base currency)
    const company = models['res.company']?.getFirst();
    const companyCurrency = company?.currency_id;

    // If converting to company currency, use inverse of from rate
    if (toCurrency.id === companyCurrency?.id) {
        const fromRate = currencyRates.find(rate => {
            const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
            return currencyId === fromCurrency.id;
        });

        if (fromRate) {
            const rateValue = fromRate.inverse_rate || (1 / fromRate.rate) || 1;
            return amount * rateValue;
        }
    }

    // If converting from company currency, use direct rate
    if (fromCurrency.id === companyCurrency?.id) {
        const toRate = currencyRates.find(rate => {
            const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
            return currencyId === toCurrency.id;
        });

        if (toRate) {
            const rateValue = toRate.inverse_rate || (1 / toRate.rate) || 1;
            return amount / rateValue;
        }
    }

    // For cross-currency conversion: from -> company -> to

    // First convert from source to company currency
    const fromRate = currencyRates.find(rate => {
        const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
        return currencyId === fromCurrency.id;
    });

    // Then convert from company to target currency
    const toRate = currencyRates.find(rate => {
        const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
        return currencyId === toCurrency.id;
    });


    if (fromRate && toRate) {
        const fromRateValue = fromRate.inverse_rate || (1 / fromRate.rate) || 1;
        const toRateValue = toRate.inverse_rate || (1 / toRate.rate) || 1;

        // Convert: amount -> company currency -> target currency
        const amountInCompany = amount * fromRateValue;
        const finalAmount = amountInCompany / toRateValue;

        return finalAmount;
    }

    return amount; // If no rates found, return original amount
}

/**
 * Format a currency amount with the appropriate symbol
 * @param {number} amount - The amount to format
 * @param {Object} currency - The currency object
 * @returns {string} - The formatted currency string
 */
export function formatCurrencyAmount(amount, currency) {
    if (!currency) return amount.toString();

    // Simple formatting - in a real implementation you might want to use the proper currency formatter
    return `${currency.symbol || currency.name || ''}${amount.toFixed(2)}`;
}

/**
 * Get the exchange rate between two currencies
 * @param {Object} fromCurrency - The source currency
 * @param {Object} toCurrency - The target currency
 * @param {Object} models - The POS models
 * @returns {number} - The exchange rate (from -> to)
 */
export function getExchangeRate(fromCurrency, toCurrency, models) {
    if (!fromCurrency || !toCurrency || fromCurrency.id === toCurrency.id) {
        return 1;
    }

    // Get currency rates from the models
    const currencyRates = models["res.currency.rate"]?.readAll() || [];

    // Get company currency (base currency)
    const company = models['res.company']?.getFirst();
    const companyCurrency = company?.currency_id;

    // If converting from company currency, use direct rate
    if (fromCurrency.id === companyCurrency?.id) {
        const toRate = currencyRates.find(rate => {
            const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
            return currencyId === toCurrency.id;
        });

        if (toRate) {
            return toRate.inverse_rate || (1 / toRate.rate) || 1;
        }
    }

    // For other conversions, calculate the cross rate
    // First convert from source to company currency
    const fromRate = currencyRates.find(rate => {
        const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
        return currencyId === fromCurrency.id;
    });

    // Then convert from company to target currency
    const toRate = currencyRates.find(rate => {
        const currencyId = Array.isArray(rate.currency_id) ? rate.currency_id[0] : (rate.currency_id?.id || rate.currency_id);
        return currencyId === toCurrency.id;
    });

    if (fromRate && toRate) {
        const fromRateValue = fromRate.inverse_rate || (1 / fromRate.rate) || 1;
        const toRateValue = toRate.inverse_rate || (1 / toRate.rate) || 1;
        return toRateValue / fromRateValue;
    }

    return 1; // Default rate if not found
}
