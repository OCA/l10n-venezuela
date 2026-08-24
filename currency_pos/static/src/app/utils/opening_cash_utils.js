/**
 * Resolve suggested opening amount for a cash payment method.
 * POS session extras must use a "_" prefix (see Base.setup in related_models).
 */
export function resolvePreviousOpeningAmount({
    paymentMethodId,
    openings = {},
    isPrimary = false,
    cashRegisterBalanceStart = 0,
}) {
    const key = paymentMethodId;
    let previousAmount = openings[key];
    if (previousAmount === undefined || previousAmount === null) {
        previousAmount = openings[String(key)];
    }
    if (previousAmount === undefined || previousAmount === null) {
        previousAmount = isPrimary ? cashRegisterBalanceStart || 0 : 0;
    }
    return previousAmount;
}

export function buildOpeningCashByMethod({
    cashPaymentMethods,
    openings = {},
    primaryPaymentMethod,
    cashRegisterBalanceStart = 0,
    getCurrency,
    companyCurrency,
    formatCurrency,
    formatFloat,
}) {
    const openingCashByMethod = {};
    for (const paymentMethod of cashPaymentMethods) {
        const currency = getCurrency(paymentMethod);
        const isForeign = currency && companyCurrency && currency.id !== companyCurrency.id;
        const previousAmount = resolvePreviousOpeningAmount({
            paymentMethodId: paymentMethod.id,
            openings,
            isPrimary: paymentMethod === primaryPaymentMethod,
            cashRegisterBalanceStart,
        });
        openingCashByMethod[paymentMethod.id] = isForeign
            ? formatFloat(previousAmount, {
                  digits: [true, currency.decimal_places ?? 2],
              })
            : formatCurrency(previousAmount, false);
    }
    return openingCashByMethod;
}
