/** @odoo-module **/

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class L10nVeGlobalDiscountDetailsPopover extends Component {
    static template = "l10n_ve_loyalty.GlobalDiscountDetailsPopover";
    static props = {
        lines: { type: Array },
        currencyId: { type: Number, optional: true },
        onRemove: { type: Function },
        onRemoveAll: { type: Function },
        close: { type: Function, optional: true },
    };

    get showRemoveAll() {
        return this.props.lines.length > 1;
    }

    formatAmount(amount) {
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }

    formatLineDetail(line) {
        if (line.discount_type === "percentage" && line.discount_percentage) {
            return `${(line.discount_percentage * 100).toFixed(2)}% (${this.formatAmount(line.amount)})`;
        }
        return this.formatAmount(line.amount);
    }

    async onRemoveClick(discountId) {
        await this.props.onRemove(discountId);
        this.props.close?.();
    }

    async onRemoveAllClick() {
        await this.props.onRemoveAll();
        this.props.close?.();
    }
}

const l10nVeGlobalDiscountTaxTotalsPatch = {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.discountPopover = usePopover(L10nVeGlobalDiscountDetailsPopover, {
            position: "left",
        });
    },

    get l10nVeDiscountTotals() {
        return this.totals || this.taxTotals || {};
    },

    get showGlobalDiscount() {
        return Boolean(this.l10nVeDiscountTotals.l10n_ve_show_global_discount);
    },

    get discountLines() {
        return this.l10nVeDiscountTotals.l10n_ve_global_discount_lines || [];
    },

    get globalDiscountPercentageLabel() {
        const percentage = this.l10nVeDiscountTotals.l10n_ve_global_discount_percentage;
        if (typeof percentage !== "number" || !percentage) {
            return "";
        }
        return ` (${(percentage * 100).toFixed(2)}%)`;
    },

    get displayInCompanyCurrency() {
        return Boolean(this.l10nVeDiscountTotals.display_in_company_currency);
    },

    formatGlobalDiscountAmount(amount, useCompanyCurrency = false) {
        if (typeof amount !== "number") {
            return "";
        }
        if (
            !useCompanyCurrency &&
            typeof this.formatMonetaryForeign === "function"
        ) {
            return this.formatMonetaryForeign(amount);
        }
        if (typeof this.formatAmount === "function") {
            return this.formatAmount(amount, useCompanyCurrency);
        }
        const totals = this.l10nVeDiscountTotals;
        const currencyId = useCompanyCurrency
            ? totals.company_currency_id
            : totals.currency_id;
        return formatMonetary(amount, { currencyId });
    },

    async removeGlobalDiscount(discountId) {
        await this.orm.call(
            this.props.record.resModel,
            "action_l10n_ve_remove_global_discount",
            [[this.props.record.resId], discountId]
        );
        await this.props.record.load();
    },

    async removeAllGlobalDiscounts() {
        await this.orm.call(
            this.props.record.resModel,
            "action_l10n_ve_remove_all_global_discounts",
            [[this.props.record.resId]]
        );
        await this.props.record.load();
    },

    onGlobalDiscountInfoClick(ev) {
        if (!this.discountLines.length) {
            return;
        }
        this.discountPopover.open(ev.currentTarget, {
            lines: this.discountLines,
            currencyId: this.l10nVeDiscountTotals.currency_id,
            onRemove: this.removeGlobalDiscount.bind(this),
            onRemoveAll: this.removeAllGlobalDiscounts.bind(this),
        });
    },
};

patch(TaxTotalsComponent.prototype, l10nVeGlobalDiscountTaxTotalsPatch);

const PATCHED_COMPANY_CURRENCY = new WeakSet();

function patchCompanyCurrencyTaxTotalsWidget() {
    const companyCurrencyField = registry
        .category("fields")
        .get("tax_totals_company_currency_widget", null);
    const component = companyCurrencyField?.component;
    if (!component || PATCHED_COMPANY_CURRENCY.has(component)) {
        return Boolean(component);
    }
    patch(component.prototype, l10nVeGlobalDiscountTaxTotalsPatch);
    PATCHED_COMPANY_CURRENCY.add(component);
    return true;
}

if (!patchCompanyCurrencyTaxTotalsWidget()) {
    const fieldsRegistry = registry.category("fields");
    const originalAdd = fieldsRegistry.add.bind(fieldsRegistry);
    fieldsRegistry.add = (key, value, ...args) => {
        const result = originalAdd(key, value, ...args);
        if (key === "tax_totals_company_currency_widget") {
            patchCompanyCurrencyTaxTotalsWidget();
        }
        return result;
    };
}
