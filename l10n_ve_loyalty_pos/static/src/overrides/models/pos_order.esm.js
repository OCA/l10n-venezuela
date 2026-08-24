import {floatIsZero, roundPrecision} from "@web/core/utils/numbers";
import {lt, uuidv4} from "@point_of_sale/utils";
import {PosOrder} from "@point_of_sale/app/models/pos_order";
import {_t} from "@web/core/l10n/translation";
import {accountTaxHelpers} from "@account/helpers/account_tax";
import {patch} from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.l10n_ve_manual_global_discounts =
            this._l10nVeNormalizeManualGlobalDiscounts(
                this.l10n_ve_manual_global_discounts ??
                    vals?.l10n_ve_manual_global_discounts
            );
    },

    /**
     * POS serialize() JSON.stringifies object values. Json fields must be sent
     * back as real arrays/objects or the backend stores a JSON string and the
     * next sync wipes the discounts in setup().
     */
    serialize() {
        const data = super.serialize(...arguments);
        let discounts = this._l10nVeNormalizeManualGlobalDiscounts(
            data.l10n_ve_manual_global_discounts ?? this.l10n_ve_manual_global_discounts
        );
        if (this._l10nVeCompanyIsVenezuela() && discounts.length) {
            discounts = this._l10nVeGetEffectiveManualGlobalDiscounts();
        }
        data.l10n_ve_manual_global_discounts = discounts;
        return data;
    },

    _l10nVeNormalizeManualGlobalDiscounts(value) {
        let current = value;
        for (let attempt = 0; attempt < 3; attempt++) {
            if (Array.isArray(current)) {
                return current;
            }
            if (typeof current !== "string" || !current) {
                break;
            }
            try {
                current = JSON.parse(current);
            } catch {
                break;
            }
        }
        return [];
    },

    _l10nVeCompanyIsVenezuela() {
        const company = this.company || this.config?.company_id;
        const code =
            company?.account_fiscal_country_id?.code || company?.country_id?.code;
        return code === "VE";
    },

    _l10nVeIsGlobalDiscountReward(reward) {
        if (!reward || reward.reward_type !== "discount") {
            return false;
        }
        return this._l10nVeCompanyIsVenezuela();
    },

    _l10nVeIsWalletLikeProgram(program) {
        return Boolean(
            program && ["ewallet", "gift_card"].includes(program.program_type)
        );
    },

    _l10nVeEwalletPaymentLabel() {
        return _t("Monedero D");
    },

    _l10nVeEwalletFiscalPaymentCode() {
        return "24";
    },

    _l10nVeIsEwalletRewardLine(line) {
        if (!line?.is_reward_line || !line.reward_id) {
            return false;
        }
        return this._l10nVeIsWalletLikeProgram(line.reward_id.program_id);
    },

    _l10nVeGetEwalletSpendLines() {
        return (this.lines || []).filter((line) =>
            this._l10nVeIsEwalletRewardLine(line)
        );
    },

    _l10nVeGetEwalletSpendAmount({withTax = true} = {}) {
        const amount = this._l10nVeGetEwalletSpendLines().reduce((sum, line) => {
            const lineAmount = withTax
                ? Math.abs(
                      Number(
                          line.get_price_with_tax?.() ?? line.price_subtotal_incl ?? 0
                      )
                  )
                : Math.abs(
                      Number(line.get_price_without_tax?.() ?? line.price_subtotal ?? 0)
                  );
            return sum + lineAmount;
        }, 0);
        return this._l10nVeRoundInCurrency(amount, this._l10nVeGetOrderCurrency());
    },

    _l10nVeGetEwalletPaymentLines() {
        const amount = this._l10nVeGetEwalletSpendAmount({withTax: true});
        if (floatIsZero(amount)) {
            return [];
        }
        return [
            {
                name: this._l10nVeEwalletPaymentLabel(),
                amount,
                payment_method: this._l10nVeEwalletFiscalPaymentCode(),
            },
        ];
    },

    _l10nVeResolveCurrency(currency) {
        if (!currency) {
            return null;
        }
        if (typeof currency === "object" && "rate" in currency) {
            return currency;
        }
        const currencyId = typeof currency === "object" ? currency.id : currency;
        return this.models["res.currency"]?.get?.(currencyId) || null;
    },

    _l10nVeGetProgramCurrency(program) {
        return (
            this._l10nVeResolveCurrency(program?.currency_id) ||
            this._l10nVeResolveCurrency(this.currency) ||
            this._l10nVeResolveCurrency(this.config?.currency_id)
        );
    },

    _l10nVeGetOrderCurrency() {
        return (
            this._l10nVeResolveCurrency(this.currency) ||
            this._l10nVeResolveCurrency(this.config?.currency_id)
        );
    },

    _l10nVeConvertAmount(amount, fromCurrency, toCurrency) {
        const from = this._l10nVeResolveCurrency(fromCurrency);
        const to = this._l10nVeResolveCurrency(toCurrency);
        if (!Number.isFinite(amount) || !from || !to || from.id === to.id) {
            return amount;
        }
        const companyCurrency =
            this._l10nVeResolveCurrency(this.company?.currency_id) || from;
        const fromRate = from.rate || 1;
        const toRate = to.rate || 1;
        let amountCompany = amount;
        if (from.id !== companyCurrency.id) {
            amountCompany = from.inverse_rate
                ? amount * from.inverse_rate
                : fromRate
                  ? amount / fromRate
                  : amount;
        }
        if (to.id === companyCurrency.id) {
            return amountCompany;
        }
        return amountCompany * toRate;
    },

    _l10nVeRoundInCurrency(amount, currency) {
        const resolved =
            this._l10nVeResolveCurrency(currency) || this._l10nVeGetOrderCurrency();
        const decimals = resolved?.decimal_places ?? 2;
        return roundPrecision(amount, Math.pow(10, -decimals));
    },

    _l10nVeShouldApplyWalletAsGlobalDiscount(reward) {
        return (
            this._l10nVeIsGlobalDiscountReward(reward) &&
            this._l10nVeIsWalletLikeProgram(reward.program_id)
        );
    },

    _l10nVeIsGlobalDiscountLine(line) {
        if (!line) {
            return false;
        }
        if (line.l10n_ve_global_discount) {
            return true;
        }
        return Boolean(
            this._l10nVeCompanyIsVenezuela() &&
                line.is_reward_line &&
                line.reward_id?.reward_type === "discount"
        );
    },

    _l10nVeGetGlobalDiscountLines() {
        return this.lines.filter((line) => this._l10nVeIsGlobalDiscountLine(line));
    },

    _l10nVeGetManualGlobalDiscounts() {
        return this._l10nVeNormalizeManualGlobalDiscounts(
            this.l10n_ve_manual_global_discounts
        );
    },

    _l10nVeGetProductLinesForDiscount() {
        return this.lines.filter(
            (line) =>
                line.get_quantity() &&
                !line.is_reward_line &&
                !line.l10n_ve_global_discount
        );
    },

    _l10nVeGetDiscountablePerTax() {
        let discountable = 0;
        const discountablePerTax = {};
        for (const line of this._l10nVeGetProductLinesForDiscount()) {
            const taxes = Array.isArray(line.tax_ids) ? line.tax_ids : [];
            const taxKey = taxes
                .filter((tax) => tax && tax.amount_type !== "fixed")
                .map((tax) => tax.id)
                .join(",");
            discountable += line.get_price_with_tax();
            if (!discountablePerTax[taxKey]) {
                discountablePerTax[taxKey] = 0;
            }
            discountablePerTax[taxKey] += line.get_base_price();
        }
        return {discountable, discountablePerTax};
    },

    _l10nVeCloneDiscountablePerTax(discountablePerTax) {
        return Object.fromEntries(
            Object.entries(discountablePerTax).map(([key, value]) => [key, value])
        );
    },

    _l10nVeTaxesTotalFactor(taxIds) {
        let factor = 1.0;
        const ids = taxIds || [];
        for (const taxId of ids) {
            const tax =
                typeof taxId === "object"
                    ? taxId
                    : this.models["account.tax"]?.get?.(taxId);
            if (tax?.amount_type === "percent") {
                factor += (Number(tax.amount) || 0) / 100;
            }
        }
        return factor || 1.0;
    },

    _l10nVeFixedDiscountToUntaxed(amount, amountBase, discountablePerTax) {
        const requested = Math.abs(amount || 0);
        if (floatIsZero(requested) || amountBase !== "total") {
            return requested;
        }
        const entries = Object.entries(discountablePerTax || {});
        if (!entries.length) {
            return requested;
        }
        let availableTotal = 0;
        const weights = [];
        const factors = [];
        for (const [taxKey, untaxed] of entries) {
            const taxIds =
                taxKey === "" ? [] : taxKey.split(",").map((str) => parseInt(str, 10));
            const factor = this._l10nVeTaxesTotalFactor(taxIds);
            factors.push(factor);
            const weight = untaxed * factor;
            weights.push(weight);
            availableTotal += weight;
        }
        if (floatIsZero(availableTotal)) {
            return 0;
        }
        const capped = Math.min(requested, availableTotal);
        let untaxedSum = 0;
        let allocated = 0;
        for (let index = 0; index < weights.length; index++) {
            const isLast = index === weights.length - 1;
            const part = isLast
                ? capped - allocated
                : (capped * weights[index]) / availableTotal;
            allocated += part;
            untaxedSum += part / (factors[index] || 1);
        }
        return untaxedSum;
    },

    _l10nVeBuildSplitsFromBases(discountablePerTax, targetUntaxed) {
        const untaxedAvailable = Object.values(discountablePerTax).reduce(
            (sum, value) => sum + value,
            0
        );
        if (floatIsZero(untaxedAvailable) || floatIsZero(targetUntaxed)) {
            return [];
        }
        const discountFactor = Math.min(1, targetUntaxed / untaxedAvailable);
        const splits = [];
        for (const [taxKey, base] of Object.entries(discountablePerTax)) {
            if (floatIsZero(base)) {
                continue;
            }
            const taxIds =
                taxKey === "" ? [] : taxKey.split(",").map((str) => parseInt(str, 10));
            splits.push({
                tax_ids: taxIds,
                amount: base * discountFactor,
            });
        }
        return splits;
    },

    _l10nVeOrderedManualGlobalDiscounts(manuals) {
        const percentage = manuals.filter((d) => d.discount_type === "percentage");
        const fixed = manuals.filter((d) => d.discount_type !== "percentage");
        return [...percentage, ...fixed];
    },

    /**
     * Recompute manual discounts against the current cart (percentage grows/shrinks;
     * fixed is capped by remaining untaxed base).
     */
    _l10nVeGetEffectiveManualGlobalDiscounts() {
        const {discountablePerTax} = this._l10nVeGetDiscountablePerTax();
        const running = this._l10nVeCloneDiscountablePerTax(discountablePerTax);
        const effective = [];
        for (const discount of this._l10nVeOrderedManualGlobalDiscounts(
            this._l10nVeGetManualGlobalDiscounts()
        )) {
            const untaxedAvailable = Object.values(running).reduce(
                (sum, value) => sum + value,
                0
            );
            let targetUntaxed = 0;
            if (!floatIsZero(untaxedAvailable)) {
                if (discount.discount_type === "percentage") {
                    targetUntaxed = untaxedAvailable * (discount.percentage || 0);
                } else {
                    const requested = Math.abs(
                        discount.requested_amount ?? discount.amount ?? 0
                    );
                    const amountBase = discount.amount_base || "untaxed";
                    targetUntaxed = this._l10nVeFixedDiscountToUntaxed(
                        requested,
                        amountBase,
                        running
                    );
                    targetUntaxed = Math.min(targetUntaxed, untaxedAvailable);
                }
            }
            const splits = floatIsZero(targetUntaxed)
                ? []
                : this._l10nVeBuildSplitsFromBases(running, targetUntaxed);
            for (const split of splits) {
                const taxKey = (split.tax_ids || []).join(",");
                if (running[taxKey] !== undefined) {
                    running[taxKey] = Math.max(0, running[taxKey] - split.amount);
                }
            }
            effective.push({
                ...discount,
                requested_amount:
                    discount.discount_type === "percentage"
                        ? 0
                        : Math.abs(discount.requested_amount ?? discount.amount ?? 0),
                amount: targetUntaxed,
                splits,
            });
        }
        return effective;
    },

    _l10nVeSyncEffectiveManualGlobalDiscounts() {
        // Read-only for UI totals: never mutate the order inside taxTotals.
        // Effective amounts are persisted on serialize() before sync/payment.
        return this._l10nVeGetEffectiveManualGlobalDiscounts();
    },

    pointsForPrograms(programs) {
        const result = super.pointsForPrograms(...arguments);
        if (!this._l10nVeCompanyIsVenezuela()) {
            return result;
        }
        const orderCurrency = this._l10nVeGetOrderCurrency();
        for (const program of programs || []) {
            if (!this._l10nVeIsWalletLikeProgram(program) || !result[program.id]) {
                continue;
            }
            const walletCurrency = this._l10nVeGetProgramCurrency(program);
            if (
                !orderCurrency ||
                !walletCurrency ||
                orderCurrency.id === walletCurrency.id
            ) {
                continue;
            }
            result[program.id] = result[program.id].map((entry) => ({
                ...entry,
                points: this._l10nVeRoundInCurrency(
                    this._l10nVeConvertAmount(
                        entry.points,
                        orderCurrency,
                        walletCurrency
                    ),
                    walletCurrency
                ),
            }));
        }
        return result;
    },

    _l10nVeBuildWalletGlobalDiscountLines(args) {
        const reward = args.reward;
        const coupon_id = args.coupon_id;
        const {discountable: rawDiscountable, discountablePerTax} =
            this._l10nVeGetDiscountablePerTax();
        const discountable = Math.min(this.get_total_with_tax(), rawDiscountable);
        if (floatIsZero(discountable)) {
            return [];
        }

        const orderCurrency = this._l10nVeGetOrderCurrency();
        const walletCurrency = this._l10nVeGetProgramCurrency(reward.program_id);
        let maxDiscount = reward.discount_max_amount || Infinity;
        if (Number.isFinite(maxDiscount)) {
            maxDiscount = this._l10nVeConvertAmount(
                maxDiscount,
                walletCurrency,
                orderCurrency
            );
        }
        const points = this._getRealCouponPoints(coupon_id);
        const pointsInOrderCurrency = this._l10nVeConvertAmount(
            points,
            walletCurrency,
            orderCurrency
        );
        maxDiscount = Math.min(maxDiscount, reward.discount * pointsInOrderCurrency);

        let pointCost = reward.clear_wallet ? points : reward.required_points;
        if (reward.discount_mode === "per_point" && !reward.clear_wallet) {
            const discountInOrderCurrency = Math.min(maxDiscount, discountable);
            const discountInWalletCurrency = this._l10nVeConvertAmount(
                discountInOrderCurrency,
                orderCurrency,
                walletCurrency
            );
            pointCost = discountInWalletCurrency / reward.discount;
        }
        pointCost = this._l10nVeRoundInCurrency(pointCost, walletCurrency);

        const discountProduct = reward.discount_line_product_id;
        const rewardCode = (Math.random() + 1).toString(36).substring(3);
        const discountFactor = discountable
            ? Math.min(1, maxDiscount / discountable)
            : 1;
        const result = Object.entries(discountablePerTax).reduce((lines, entry) => {
            if (!entry[1]) {
                return lines;
            }
            let taxIds =
                entry[0] === ""
                    ? []
                    : entry[0].split(",").map((str) => parseInt(str, 10));
            taxIds = this.models["account.tax"].filter((tax) =>
                taxIds.includes(tax.id)
            );
            lines.push({
                product_id: discountProduct,
                price_unit: -(entry[1] * discountFactor),
                qty: 1,
                reward_id: reward,
                is_reward_line: true,
                coupon_id: coupon_id,
                points_cost: 0,
                reward_identifier_code: rewardCode,
                tax_ids: taxIds,
                l10n_ve_global_discount: true,
            });
            return lines;
        }, []);
        if (result.length) {
            result[0].points_cost = pointCost;
        }
        return result;
    },

    _getRewardLineValuesDiscount(args) {
        const reward = args?.reward;
        if (this._l10nVeShouldApplyWalletAsGlobalDiscount(reward)) {
            return this._l10nVeBuildWalletGlobalDiscountLines(args);
        }
        const lines = super._getRewardLineValuesDiscount(...arguments);
        if (!this._l10nVeIsGlobalDiscountReward(reward) || !Array.isArray(lines)) {
            return lines;
        }
        return lines.map((line) => ({
            ...line,
            l10n_ve_global_discount: true,
        }));
    },

    getSortedOrderlines() {
        const lines = super.getSortedOrderlines(...arguments);
        if (!this._l10nVeCompanyIsVenezuela()) {
            return lines;
        }
        return lines.filter((line) => !this._l10nVeIsGlobalDiscountLine(line));
    },

    _l10nVeBuildManualDiscountBaseLines(documentSign = 1, manuals = null) {
        const currency = this.config.currency_id;
        const baseLines = [];
        const discounts = manuals || this._l10nVeGetEffectiveManualGlobalDiscounts();
        for (const discount of discounts) {
            for (const split of discount.splits || []) {
                const amount = Math.abs(split.amount || 0);
                if (floatIsZero(amount, currency.decimal_places)) {
                    continue;
                }
                const taxIds = this.models["account.tax"].filter((tax) =>
                    (split.tax_ids || []).includes(tax.id)
                );
                baseLines.push(
                    accountTaxHelpers.prepare_base_line_for_taxes_computation(
                        {
                            id: `manual-${discount.id}-${(split.tax_ids || []).join("-")}`,
                        },
                        {
                            quantity: documentSign,
                            price_unit: -amount,
                            discount: 0,
                            tax_ids: taxIds,
                            currency_id: currency,
                            rate: 1,
                        }
                    )
                );
            }
        }
        return baseLines;
    },

    _l10nVeComputeTaxTotalsWithManualDiscounts() {
        const currency = this.config.currency_id;
        const company = this.company;
        const orderLines = this.lines;
        const documentSign =
            this.lines.length === 0 ||
            !this.lines.every((line) =>
                lt(line.qty, 0, {decimals: currency.decimal_places})
            )
                ? 1
                : -1;

        const baseLines = orderLines.map((line) =>
            accountTaxHelpers.prepare_base_line_for_taxes_computation(
                line,
                line.prepareBaseLineForTaxesComputationExtraValues({
                    quantity: documentSign * line.qty,
                })
            )
        );
        const manuals = this._l10nVeSyncEffectiveManualGlobalDiscounts();
        baseLines.push(
            ...this._l10nVeBuildManualDiscountBaseLines(documentSign, manuals)
        );
        accountTaxHelpers.add_tax_details_in_base_lines(baseLines, company);
        accountTaxHelpers.round_base_lines_tax_details(baseLines, company);

        const cashRounding =
            !this.config.only_round_cash_method && this.config.cash_rounding
                ? this.config.rounding_method
                : null;

        const taxTotals = accountTaxHelpers.get_tax_totals_summary(
            baseLines,
            currency,
            company,
            {
                cash_rounding: cashRounding,
            }
        );

        taxTotals.order_sign = documentSign;
        taxTotals.order_total =
            taxTotals.total_amount_currency -
            (taxTotals.cash_rounding_base_amount_currency || 0.0);

        let order_rounding = 0;
        let remaining = taxTotals.order_total;
        const validPayments = this.payment_ids.filter(
            (p) => p.is_done() && !p.is_change
        );
        for (const [payment, isLast] of validPayments.map((p, i) => [
            p,
            i === validPayments.length - 1,
        ])) {
            const paymentAmount = documentSign * payment.get_amount();
            if (isLast) {
                if (this.config.cash_rounding) {
                    const roundedRemaining = this.getRoundedRemaining(
                        this.config.rounding_method,
                        remaining
                    );
                    if (
                        !floatIsZero(
                            paymentAmount - remaining,
                            this.currency.decimal_places
                        )
                    ) {
                        order_rounding = roundedRemaining - remaining;
                    }
                }
            }
            remaining -= paymentAmount;
        }

        taxTotals.order_rounding = order_rounding;
        taxTotals.order_remaining = remaining;
        const remaining_with_rounding = remaining + order_rounding;
        taxTotals.order_has_zero_remaining = floatIsZero(
            remaining_with_rounding,
            currency.decimal_places
        );
        return taxTotals;
    },

    _l10nVeFormatManualDiscountLabel(discount) {
        const baseName = discount.name || _t("Discount");
        if (discount.discount_type === "percentage" && discount.percentage) {
            const pct = discount.percentage * 100;
            const pctLabel = Number.isInteger(pct) ? String(pct) : pct.toFixed(2);
            return `${baseName} (${pctLabel}%)`;
        }
        return baseName;
    },

    _l10nVeEnrichTaxTotalsWithDiscountDisplay(taxTotals, manuals = null) {
        const discountLines = this._l10nVeGetGlobalDiscountLines();
        const effectiveManuals =
            manuals || this._l10nVeGetEffectiveManualGlobalDiscounts();
        if (!discountLines.length && !effectiveManuals.length) {
            taxTotals.l10n_ve_show_global_discount = false;
            taxTotals.l10n_ve_global_discount_amount_currency = 0;
            taxTotals.l10n_ve_subtotal_before_discount = taxTotals.base_amount_currency;
            taxTotals.l10n_ve_global_discount_lines = [];
            return taxTotals;
        }

        const grouped = {};
        for (const line of discountLines) {
            const key =
                line.reward_identifier_code ||
                (line.reward_id && `reward-${line.reward_id.id}`) ||
                `line-${line.uuid || line.id}`;
            if (!grouped[key]) {
                grouped[key] = {
                    id: key,
                    name: this._l10nVeIsEwalletRewardLine(line)
                        ? this._l10nVeEwalletPaymentLabel()
                        : line.full_product_name ||
                          line.reward_id?.description ||
                          line.product_id?.display_name ||
                          _t("Discount"),
                    amount: 0,
                    lines: [],
                    manual: false,
                };
            }
            grouped[key].amount += Math.abs(line.get_base_price());
            grouped[key].lines.push(line);
        }
        for (const discount of effectiveManuals) {
            const amount = Math.abs(discount.amount || 0);
            if (floatIsZero(amount)) {
                continue;
            }
            grouped[discount.id] = {
                id: discount.id,
                name: this._l10nVeFormatManualDiscountLabel(discount),
                amount,
                lines: [],
                manual: true,
            };
        }
        const globalLines = Object.values(grouped);
        const discountUntaxed = globalLines.reduce((sum, row) => sum + row.amount, 0);

        taxTotals.l10n_ve_show_global_discount = discountUntaxed > 0;
        taxTotals.l10n_ve_global_discount_amount_currency = discountUntaxed;
        taxTotals.l10n_ve_subtotal_before_discount =
            taxTotals.base_amount_currency + discountUntaxed;
        taxTotals.l10n_ve_global_discount_lines = globalLines;
        return taxTotals;
    },

    get taxTotals() {
        if (!this._l10nVeCompanyIsVenezuela()) {
            return super.taxTotals;
        }
        const manuals = this._l10nVeGetManualGlobalDiscounts();
        if (!manuals.length) {
            return this._l10nVeEnrichTaxTotalsWithDiscountDisplay(super.taxTotals, []);
        }
        const effective = this._l10nVeSyncEffectiveManualGlobalDiscounts();
        const taxTotals = this._l10nVeComputeTaxTotalsWithManualDiscounts();
        return this._l10nVeEnrichTaxTotalsWithDiscountDisplay(taxTotals, effective);
    },

    _l10nVeApplyManualGlobalDiscount({
        amount,
        discountType,
        percentage,
        name,
        reasonId,
        amountBase = "untaxed",
    }) {
        const effectiveExisting = this._l10nVeGetEffectiveManualGlobalDiscounts();
        const {discountablePerTax} = this._l10nVeGetDiscountablePerTax();
        const running = this._l10nVeCloneDiscountablePerTax(discountablePerTax);
        for (const discount of effectiveExisting) {
            for (const split of discount.splits || []) {
                const taxKey = (split.tax_ids || []).join(",");
                if (running[taxKey] !== undefined) {
                    running[taxKey] = Math.max(0, running[taxKey] - split.amount);
                }
            }
        }
        const untaxedAvailable = Object.values(running).reduce(
            (sum, value) => sum + value,
            0
        );
        if (floatIsZero(untaxedAvailable)) {
            return _t("There is no amount available to discount.");
        }

        let targetUntaxed = amount;
        const resolvedAmountBase =
            discountType === "percentage" ? "untaxed" : amountBase || "untaxed";
        if (discountType === "percentage") {
            targetUntaxed = untaxedAvailable * percentage;
        } else {
            targetUntaxed = this._l10nVeFixedDiscountToUntaxed(
                amount,
                resolvedAmountBase,
                running
            );
        }
        targetUntaxed = Math.min(Math.abs(targetUntaxed), untaxedAvailable);
        if (floatIsZero(targetUntaxed)) {
            return _t("The discount amount must be greater than zero.");
        }

        const splits = this._l10nVeBuildSplitsFromBases(running, targetUntaxed);
        const entry = {
            id: `manual-${uuidv4()}`,
            name: name || _t("Global discount"),
            reason_id: reasonId || false,
            discount_type: discountType,
            percentage: discountType === "percentage" ? percentage : 0,
            requested_amount: discountType === "percentage" ? 0 : Math.abs(amount),
            amount_base: resolvedAmountBase,
            amount: targetUntaxed,
            splits,
        };
        this.update({
            l10n_ve_manual_global_discounts: [
                ...this._l10nVeGetManualGlobalDiscounts(),
                entry,
            ],
        });
        return true;
    },

    _l10nVeGetFiscalGlobalDiscountAmount() {
        let amount = 0;
        for (const line of this.lines || []) {
            if (this._l10nVeIsEwalletRewardLine(line)) {
                continue;
            }
            if (this._l10nVeIsGlobalDiscountLine(line)) {
                amount += Math.abs(
                    Number(line.get_price_without_tax?.() ?? line.price_subtotal ?? 0)
                );
            }
        }
        for (const discount of this._l10nVeGetEffectiveManualGlobalDiscounts()) {
            amount += Math.abs(Number(discount.amount) || 0);
        }
        return this._l10nVeRoundInCurrency(amount, this._l10nVeGetOrderCurrency());
    },

    _l10nVeRemoveGlobalDiscountGroup(groupId) {
        const manuals = this._l10nVeGetManualGlobalDiscounts();
        if (manuals.some((discount) => discount.id === groupId)) {
            this.update({
                l10n_ve_manual_global_discounts: manuals.filter(
                    (discount) => discount.id !== groupId
                ),
            });
            return;
        }
        const lines = this._l10nVeGetGlobalDiscountLines().filter((line) => {
            const key =
                line.reward_identifier_code ||
                (line.reward_id && `reward-${line.reward_id.id}`) ||
                `line-${line.uuid || line.id}`;
            return key === groupId;
        });
        for (const line of lines) {
            line.delete();
        }
        if (typeof this.updateRewards === "function") {
            this.updateRewards();
        }
    },
});
