# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class L10nVeGlobalDiscountMixin(models.AbstractModel):
    _name = "l10n.ve.global.discount.mixin"
    _description = "Shared Venezuela global discount fields"

    discount_type = fields.Selection(
        selection=[
            ("percentage", "Porcentaje"),
            ("fixed", "Monto fijo"),
        ],
        string="Discount type",
        default="fixed",
        required=True,
    )
    discount_percentage = fields.Float(string="Discount percentage", digits="Discount")
    amount_base = fields.Selection(
        selection=[
            ("untaxed", "Subtotal"),
            ("total", "Total"),
        ],
        string="Base del monto",
        default="untaxed",
        required=True,
        help="Para monto fijo: si el importe ingresado aplica sobre el subtotal "
        "o sobre el total con impuestos.",
    )


def l10n_ve_ordered_global_discounts(discounts):
    percentage = discounts.filtered(lambda discount: discount.discount_type == "percentage")
    fixed = discounts.filtered(lambda discount: discount.discount_type != "percentage").sorted(
        "id"
    )
    return percentage + fixed


def l10n_ve_taxes_total_factor(taxes):
    factor = 1.0
    for tax in taxes.flatten_taxes_hierarchy():
        if tax.amount_type == "percent":
            factor += tax.amount / 100.0
    return factor


def l10n_ve_remaining_subtotal_by_taxes(document, subtotal_by_taxes=None):
    if subtotal_by_taxes is None:
        subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
    running = dict(subtotal_by_taxes)
    for _discount, amount in l10n_ve_sequential_global_discount_amounts(
        document, subtotal_by_taxes
    ):
        tax_groups = list(running.keys())
        weights = [running[taxes] for taxes in tax_groups]
        parts = document._l10n_ve_split_amount_by_weights(amount, weights)
        for taxes, part in zip(tax_groups, parts):
            running[taxes] = max(0.0, running[taxes] - part)
    return running


def l10n_ve_fixed_discount_to_untaxed(
    document, amount, amount_base, subtotal_by_taxes=None, currency=None
):
    currency = currency or document.currency_id
    if subtotal_by_taxes is None:
        subtotal_by_taxes = l10n_ve_remaining_subtotal_by_taxes(document)
    if amount_base != "total":
        return currency.round(amount)

    tax_groups = list(subtotal_by_taxes.keys())
    if not tax_groups:
        return currency.round(amount)

    weights = []
    factors = []
    for taxes in tax_groups:
        untaxed = subtotal_by_taxes[taxes]
        factor = l10n_ve_taxes_total_factor(taxes) or 1.0
        factors.append(factor)
        weights.append(untaxed * factor)

    available_total = sum(weights)
    if float_is_zero(available_total, precision_rounding=currency.rounding):
        return 0.0

    capped = amount
    if currency == document.currency_id:
        capped = min(amount, available_total)
    parts = document._l10n_ve_split_amount_by_weights(
        capped, weights, currency=currency
    )
    untaxed_sum = 0.0
    for part, factor in zip(parts, factors):
        untaxed_sum += part / factor
    return currency.round(untaxed_sum)


def l10n_ve_available_total_for_discount(document, subtotal_by_taxes=None):
    remaining = l10n_ve_remaining_subtotal_by_taxes(document, subtotal_by_taxes)
    return sum(
        untaxed * (l10n_ve_taxes_total_factor(taxes) or 1.0)
        for taxes, untaxed in remaining.items()
    )


def l10n_ve_sequential_global_discount_amounts(document, subtotal_by_taxes):
    currency = document.currency_id
    running = dict(subtotal_by_taxes)
    results = []
    for discount in l10n_ve_ordered_global_discounts(document.l10n_ve_global_discount_ids):
        total_running = sum(running.values())
        if float_is_zero(total_running, precision_rounding=currency.rounding):
            break
        if discount.discount_type == "percentage":
            amount = currency.round(total_running * discount.discount_percentage)
        else:
            amount = currency.round(min(discount.amount, total_running))
        if float_is_zero(amount, precision_rounding=currency.rounding):
            continue
        results.append((discount, amount))
        tax_groups = list(running.keys())
        weights = [running[taxes] for taxes in tax_groups]
        parts = document._l10n_ve_split_amount_by_weights(amount, weights)
        for taxes, part in zip(tax_groups, parts):
            running[taxes] = max(0.0, running[taxes] - part)
    return results


def l10n_ve_total_sequential_global_discount(document, subtotal_by_taxes):
    return sum(
        amount
        for _discount, amount in l10n_ve_sequential_global_discount_amounts(
            document, subtotal_by_taxes
        )
    )


def l10n_ve_get_global_discount_lines_data(document, subtotal_by_taxes):
    lines = []
    for discount, amount in l10n_ve_sequential_global_discount_amounts(
        document, subtotal_by_taxes
    ):
        lines.append(
            {
                "id": discount.id,
                "name": discount.name,
                "amount": amount,
                "discount_type": discount.discount_type,
                "discount_percentage": discount.discount_percentage
                if discount.discount_type == "percentage"
                else False,
            }
        )
    return lines


def l10n_ve_validate_global_discount_total(document):
    if not document.l10n_ve_global_discount_ids:
        return
    subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
    currency = document.currency_id
    running_total = sum(subtotal_by_taxes.values())
    for discount in l10n_ve_ordered_global_discounts(document.l10n_ve_global_discount_ids):
        if float_is_zero(running_total, precision_rounding=currency.rounding):
            break
        if discount.discount_type == "percentage":
            amount = currency.round(running_total * discount.discount_percentage)
        else:
            amount = discount.amount
            if float_compare(
                amount,
                running_total,
                precision_digits=currency.decimal_places,
            ) > 0:
                raise UserError(
                    _(
                        "El descuento (%(discount)s) supera el subtotal disponible "
                        "(%(subtotal)s)."
                    )
                    % {"discount": amount, "subtotal": running_total}
                )
        running_total = max(0.0, running_total - amount)
    total_subtotal = sum(subtotal_by_taxes.values())
    total_discount = l10n_ve_total_sequential_global_discount(document, subtotal_by_taxes)
    if float_compare(
        total_discount,
        total_subtotal,
        precision_digits=document.currency_id.decimal_places,
    ) > 0:
        raise UserError(
            _(
                "La suma de los descuentos globales (%(discount)s) supera el "
                "subtotal facturable (%(subtotal)s)."
            )
            % {"discount": total_discount, "subtotal": total_subtotal}
        )


def l10n_ve_check_single_percentage_global_discount(discounts):
    percentage_discounts = discounts.filtered(
        lambda discount: discount.discount_type == "percentage"
    )
    if len(percentage_discounts) > 1:
        raise ValidationError(_("Solo puede existir un descuento global por porcentaje."))


def l10n_ve_refresh_percentage_global_discount_amounts(document):
    if not document.l10n_ve_global_discount_ids:
        return
    percentage_discounts = document.l10n_ve_global_discount_ids.filtered(
        lambda discount: discount.discount_type == "percentage"
    )
    if not percentage_discounts:
        return
    subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
    sequential = {
        discount.id: amount
        for discount, amount in l10n_ve_sequential_global_discount_amounts(
            document, subtotal_by_taxes
        )
    }
    for discount in percentage_discounts:
        new_amount = sequential.get(discount.id, 0.0)
        if (
            float_compare(
                discount.amount,
                new_amount,
                precision_digits=document.currency_id.decimal_places,
            )
            != 0
        ):
            discount.with_context(l10n_ve_skip_discount_refresh=True).write(
                {"amount": new_amount}
            )
