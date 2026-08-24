# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

from odoo.addons.l10n_ve_loyalty.models import (
    l10n_ve_global_discount as l10n_ve_discount_logic,
)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l10n_ve_global_discount_ids = fields.One2many(
        comodel_name="l10n.ve.sale.order.discount",
        inverse_name="sale_order_id",
        string="Global discounts",
        copy=False,
    )

    def action_l10n_ve_remove_global_discount(self, discount_id):
        self.ensure_one()
        discount = self.env["l10n.ve.sale.order.discount"].browse(discount_id)
        if discount.exists():
            if discount.sale_order_id != self:
                raise UserError(_("El descuento no pertenece a este pedido."))
            discount.unlink()
            return True
        return super().action_l10n_ve_remove_global_discount(discount_id)

    def action_l10n_ve_remove_all_global_discounts(self):
        self.ensure_one()
        if self.l10n_ve_global_discount_ids:
            if len(self.l10n_ve_global_discount_ids) <= 1:
                return True
            self.l10n_ve_global_discount_ids.unlink()
            return True
        return super().action_l10n_ve_remove_all_global_discounts()

    def _l10n_ve_check_single_percentage_global_discount(self, discounts):
        return l10n_ve_discount_logic.l10n_ve_check_single_percentage_global_discount(
            discounts
        )

    def _l10n_ve_sequential_global_discount_amounts(self, subtotal_by_taxes):
        self.ensure_one()
        return l10n_ve_discount_logic.l10n_ve_sequential_global_discount_amounts(
            self, subtotal_by_taxes
        )

    def _l10n_ve_get_global_discount_lines_data(self, subtotal_by_taxes):
        self.ensure_one()
        return l10n_ve_discount_logic.l10n_ve_get_global_discount_lines_data(
            self, subtotal_by_taxes
        )

    def _l10n_ve_validate_global_discount_total(self):
        for order in self:
            l10n_ve_discount_logic.l10n_ve_validate_global_discount_total(order)

    def _l10n_ve_refresh_percentage_global_discount_amounts(self):
        for order in self:
            l10n_ve_discount_logic.l10n_ve_refresh_percentage_global_discount_amounts(
                order
            )

    def _l10n_ve_refresh_global_discounts_from_lines(self):
        orders = self.filtered(
            lambda order: order.state not in ("cancel",)
            and order.l10n_ve_global_discount_ids
        )
        if not orders or self.env.context.get("l10n_ve_skip_discount_refresh"):
            return
        orders._l10n_ve_refresh_percentage_global_discount_amounts()
        orders._l10n_ve_validate_global_discount_total()

    def _l10n_ve_global_discount_applies(self):
        self.ensure_one()
        return self.country_code == "VE" and bool(self.l10n_ve_global_discount_ids)

    def _l10n_ve_build_global_discount_base_lines(self, base_lines):
        self.ensure_one()
        if not self.l10n_ve_global_discount_ids:
            return []

        subtotal_by_taxes = self._l10n_ve_subtotal_by_taxes_from_base_lines(base_lines)
        if not subtotal_by_taxes:
            return []

        line_currency = base_lines[0]["currency_id"] if base_lines else self.currency_id
        rate = self.currency_rate or 1.0

        AccountTax = self.env["account.tax"]
        discount_base_lines = []
        sequence = 0
        running = dict(subtotal_by_taxes)
        for (
            discount,
            discount_amount,
        ) in self._l10n_ve_sequential_global_discount_amounts(subtotal_by_taxes):
            tax_groups = list(running.keys())
            weights = [running[taxes] for taxes in tax_groups]
            parts = self._l10n_ve_split_amount_by_weights(discount_amount, weights)
            for taxes, part in zip(tax_groups, parts, strict=False):
                if float_is_zero(part, precision_rounding=line_currency.rounding):
                    continue
                sequence += 1
                discount_base_lines.append(
                    AccountTax._prepare_base_line_for_taxes_computation(
                        {
                            "id": f"l10n_ve_global_discount_{discount.id}_{sequence}",
                            "tax_ids": taxes,
                            "price_unit": -part,
                            "quantity": 1.0,
                            "currency_id": line_currency,
                            "name": discount.name,
                        },
                        special_type="global_discount",
                        special_mode="total_excluded",
                        sign=1,
                        rate=rate,
                    )
                )
                running[taxes] = max(0.0, running[taxes] - part)
        return discount_base_lines

    def _l10n_ve_apply_global_discount_to_base_lines(self, base_lines):
        self.ensure_one()
        if not self._l10n_ve_global_discount_applies():
            return base_lines

        AccountTax = self.env["account.tax"]
        product_lines = self._l10n_ve_product_base_lines_for_discount(base_lines)
        special_lines = self._l10n_ve_non_product_base_lines(base_lines)
        AccountTax._add_tax_details_in_base_lines(product_lines, self.company_id)
        discount_lines = self._l10n_ve_build_global_discount_base_lines(product_lines)
        if not discount_lines:
            all_lines = product_lines + special_lines
            if special_lines:
                AccountTax._add_tax_details_in_base_lines(
                    special_lines, self.company_id
                )
            AccountTax._round_base_lines_tax_details(all_lines, self.company_id)
            return all_lines

        working_lines = product_lines + discount_lines
        AccountTax._add_tax_details_in_base_lines(discount_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(working_lines, self.company_id)
        working_lines = AccountTax._dispatch_global_discount_lines(
            working_lines, self.company_id
        )
        AccountTax._squash_global_discount_lines(working_lines, self.company_id)
        AccountTax._add_and_round_raw_gross_total_excluded_and_discount(
            working_lines,
            self.company_id,
            account_discount_base_lines=True,
        )
        AccountTax._add_and_round_raw_gross_total_excluded_and_discount(
            working_lines,
            self.company_id,
            in_foreign_currency=False,
            account_discount_base_lines=True,
        )
        if special_lines:
            AccountTax._add_tax_details_in_base_lines(special_lines, self.company_id)
        all_lines = working_lines + special_lines
        AccountTax._round_base_lines_tax_details(all_lines, self.company_id)
        return all_lines

    def _l10n_ve_get_computation_base_lines(self):
        self.ensure_one()
        order_lines = self._get_priced_lines()
        base_lines = [
            line._prepare_base_line_for_taxes_computation() for line in order_lines
        ]
        base_lines += self._add_base_lines_for_early_payment_discount()
        return self._l10n_ve_apply_global_discount_to_base_lines(base_lines)

    def _l10n_ve_global_discount_subtotal_by_taxes(self):
        self.ensure_one()
        order_lines = self._get_priced_lines()
        base_lines = [
            line._prepare_base_line_for_taxes_computation() for line in order_lines
        ]
        base_lines += self._add_base_lines_for_early_payment_discount()
        return self._l10n_ve_subtotal_by_taxes_from_base_lines(
            self._l10n_ve_product_base_lines_for_discount(base_lines)
        )

    def _l10n_ve_discount_amounts_for_invoiceable(self, invoiceable_lines):
        self.ensure_one()
        product_lines = self._l10n_ve_product_order_lines(invoiceable_lines)
        uninvoiced_subtotal = self._l10n_ve_product_subtotal(
            self._l10n_ve_product_order_lines(self.order_line),
            qty_field="qty_to_invoice",
        )
        invoiceable_subtotal = self._l10n_ve_product_subtotal(
            product_lines,
            qty_field="qty_to_invoice",
        )
        if float_is_zero(
            uninvoiced_subtotal, precision_rounding=self.currency_id.rounding
        ):
            return {}
        ratio = invoiceable_subtotal / uninvoiced_subtotal
        amounts = {}
        for discount in self.l10n_ve_global_discount_ids:
            remaining = discount.amount - discount.amount_invoiced
            if float_is_zero(remaining, precision_rounding=self.currency_id.rounding):
                continue
            amount = self.currency_id.round(remaining * ratio)
            if amount:
                amounts[discount.id] = amount
        return amounts

    def _l10n_ve_create_move_global_discounts(self, moves, discount_alloc):
        Discount = self.env["l10n.ve.account.move.discount"]
        for move in moves:
            for discount_id, amount in discount_alloc.items():
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                sale_discount = self.env["l10n.ve.sale.order.discount"].browse(
                    discount_id
                )
                Discount.create(
                    {
                        "move_id": move.id,
                        "reason_id": sale_discount.reason_id.id,
                        "amount": amount,
                        "discount_type": sale_discount.discount_type,
                        "discount_percentage": sale_discount.discount_percentage,
                        "amount_base": sale_discount.amount_base or "untaxed",
                        "l10n_ve_sale_discount_id": sale_discount.id,
                    }
                )

    def _l10n_ve_global_discount_lines(self, invoiceable_lines):
        self.ensure_one()
        if self.l10n_ve_global_discount_ids:
            return self.env["sale.order.line"]
        return super()._l10n_ve_global_discount_lines(invoiceable_lines)

    def _l10n_ve_invoiceable_line_chunks(self, final):
        self.ensure_one()
        if not self.l10n_ve_global_discount_ids:
            return super()._l10n_ve_invoiceable_line_chunks(final)

        invoiceable_lines = super()._get_invoiceable_lines(final)
        disc_lines = self._l10n_ve_global_discount_lines(invoiceable_lines)
        lines_wo_disc = invoiceable_lines - disc_lines
        max_lines = self._l10n_ve_get_max_invoice_lines_from_book()
        product_line_count = self._l10n_ve_product_line_count_invoiceable(lines_wo_disc)
        if max_lines <= 0 or product_line_count <= max_lines:
            discount_amounts = self._l10n_ve_discount_amounts_for_invoiceable(
                lines_wo_disc
            )
            return [(lines_wo_disc, discount_amounts)]
        core_chunks = self._l10n_ve_split_invoiceable_lines(lines_wo_disc, max_lines)
        run_discount_amounts = self._l10n_ve_discount_amounts_for_invoiceable(
            lines_wo_disc
        )
        if not run_discount_amounts:
            return [(chunk, {}) for chunk in core_chunks]
        weights = [self._l10n_ve_chunk_product_subtotal(chunk) for chunk in core_chunks]
        out = []
        for i, chunk in enumerate(core_chunks):
            alloc = {}
            for discount_id, total_amount in run_discount_amounts.items():
                parts = self._l10n_ve_split_amount_by_weights(total_amount, weights)
                part = parts[i]
                if not float_is_zero(
                    part, precision_rounding=10 ** (-self.currency_id.decimal_places)
                ):
                    alloc[discount_id] = part
            out.append((chunk, alloc))
        return out

    def _l10n_ve_on_before_create_invoices(self):
        self._l10n_ve_refresh_global_discounts_from_lines()

    def _l10n_ve_should_use_discount_line_allocation(self, discount_alloc):
        return bool(discount_alloc) and not self.l10n_ve_global_discount_ids

    def _l10n_ve_after_invoice_chunk(self, moves, discount_alloc):
        if discount_alloc and self.l10n_ve_global_discount_ids:
            self._l10n_ve_create_move_global_discounts(moves, discount_alloc)

    def action_open_discount_wizard(self):
        self.ensure_one()
        if self.country_code == "VE":
            return {
                "name": _("Descuento global"),
                "type": "ir.actions.act_window",
                "res_model": "sale.order.discount",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_sale_order_id": self.id,
                    "default_l10n_ve_discount_mode": "percentage",
                    **(
                        {"default_l10n_ve_discount_reason_id": default_reason.id}
                        if (
                            default_reason := self.env[
                                "l10n.ve.discount.reason"
                            ]._l10n_ve_get_default()
                        )
                        else {}
                    ),
                },
                "views": [
                    (
                        self.env.ref(
                            "l10n_ve_sale_loyalty."
                            "l10n_ve_sale_order_discount_wizard_view_form"
                        ).id,
                        "form",
                    )
                ],
            }
        return super().action_open_discount_wizard()

    @api.depends(
        "order_line.price_subtotal",
        "currency_id",
        "company_id",
        "payment_term_id",
        "l10n_ve_global_discount_ids",
        "l10n_ve_global_discount_ids.amount",
    )
    def _compute_amounts(self):
        ve_with_discount = self.filtered(
            lambda order: order.country_code == "VE"
            and order.l10n_ve_global_discount_ids
        )
        res = super(SaleOrder, self - ve_with_discount)._compute_amounts()
        AccountTax = self.env["account.tax"]
        for order in ve_with_discount:
            base_lines = order._l10n_ve_get_computation_base_lines()
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )
            order.amount_untaxed = tax_totals["base_amount_currency"]
            order.amount_tax = tax_totals["tax_amount_currency"]
            order.amount_total = tax_totals["total_amount_currency"]
        return res

    @api.depends_context("lang")
    @api.depends(
        "order_line.price_subtotal",
        "order_line.product_id",
        "currency_id",
        "company_id",
        "payment_term_id",
        "l10n_ve_global_discount_ids",
        "l10n_ve_global_discount_ids.amount",
    )
    def _compute_tax_totals(self):
        AccountTax = self.env["account.tax"]
        ve_with_discount = self.filtered(
            lambda order: order.country_code == "VE"
            and order.l10n_ve_global_discount_ids
        )
        res = super(SaleOrder, self - ve_with_discount)._compute_tax_totals()
        for order in ve_with_discount:
            base_lines = order._l10n_ve_get_computation_base_lines()
            order.tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )
        for order in self:
            if (
                order.company_id.account_fiscal_country_id.code != "VE"
                or not order.tax_totals
            ):
                continue
            totals = AccountTax._l10n_ve_apply_global_discount_to_tax_totals(
                order,
                order.tax_totals,
            )
            totals["same_tax_base"] = False
            for subtotal in totals.get("subtotals", []):
                for tax_group in subtotal.get("tax_groups", []):
                    if tax_group.get("display_base_amount_currency") is False:
                        tax_group["display_base_amount_currency"] = tax_group.get(
                            "base_amount_currency", 0.0
                        )
                    if tax_group.get("display_base_amount") in (False, None):
                        tax_group["display_base_amount"] = tax_group.get(
                            "base_amount", 0.0
                        )
            order.tax_totals = totals
        return res
