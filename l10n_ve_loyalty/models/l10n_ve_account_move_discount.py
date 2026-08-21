# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, float_round, frozendict

from . import l10n_ve_global_discount as l10n_ve_discount_logic


class L10nVeAccountMoveDiscount(models.Model):
    _name = "l10n.ve.account.move.discount"
    _inherit = ["l10n.ve.global.discount.mixin"]
    _description = "Venezuela invoice global discount"
    _order = "id"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
        index=True,
    )
    reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Reason",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env["l10n.ve.discount.reason"]._l10n_ve_get_default(),
    )
    name = fields.Char(related="reason_id.name", readonly=True)
    amount = fields.Monetary(
        string="Amount",
        required=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="move_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="move_id.company_id",
        store=True,
        readonly=True,
    )

    @api.constrains("amount")
    def _check_amount_positive(self):
        for discount in self:
            if float_compare(
                discount.amount, 0.0, precision_digits=discount.currency_id.decimal_places
            ) <= 0:
                raise ValidationError(_("El monto del descuento debe ser mayor que cero."))

    @api.constrains("discount_type", "move_id")
    def _check_single_percentage_discount(self):
        for discount in self.filtered(lambda record: record.discount_type == "percentage"):
            others = discount.move_id.l10n_ve_global_discount_ids.filtered(
                lambda record: record.discount_type == "percentage" and record.id != discount.id
            )
            if others:
                raise ValidationError(_("Solo puede existir un descuento global por porcentaje."))

    def _l10n_ve_sync_global_discount_accounting(self):
        moves = self.mapped("move_id").filtered(
            lambda move: move.state == "draft" and move.is_invoice(include_receipts=True)
        )
        if not moves:
            return
        self.env["l10n.ve.account.move.discount"]._l10n_ve_sync_global_discount_accounting_for_moves(
            moves
        )

    @api.model
    def _l10n_ve_sync_global_discount_accounting_for_moves(self, moves):
        if not moves:
            return
        moves = moves.filtered(
            lambda move: move.state == "draft" and move.is_invoice(include_receipts=True)
        )
        if not moves:
            return
        moves = moves.with_context(l10n_ve_skip_discount_refresh=True)
        container = {"records": moves}
        with moves._check_balanced(container):
            moves.filtered(
                lambda move: not move._l10n_ve_uses_global_discount_journal_lines()
            )._l10n_ve_remove_ve_discount_journal_lines()
            with moves._sync_dynamic_lines(container):
                pass
            moves._l10n_ve_apply_global_discount_sync()
            moves.filtered(
                lambda move: move._l10n_ve_uses_global_discount_journal_lines()
            )._l10n_ve_cleanup_line_discount_journal_lines()
            moves.filtered(
                lambda move: move._l10n_ve_global_discount_applies()
            )._l10n_ve_sync_global_discount_journal_lines()
            moves._l10n_ve_rebalance_payment_term_from_lines()

    @api.model
    def _l10n_ve_check_global_discount_user_access(self):
        if self.env.context.get("l10n_ve_skip_global_discount_access_check"):
            return
        if not self.env.user.has_group("l10n_ve_loyalty.group_l10n_ve_global_discount"):
            raise UserError(
                _("You do not have permission to manage global discounts.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._l10n_ve_check_global_discount_user_access()
        records = super().create(vals_list)
        if not self.env.context.get("l10n_ve_skip_discount_refresh"):
            records._l10n_ve_check_move_editable()
            records.move_id._l10n_ve_check_single_percentage_global_discount(
                records.move_id.l10n_ve_global_discount_ids
            )
            records.move_id._l10n_ve_refresh_percentage_global_discount_amounts()
            records.move_id._l10n_ve_validate_global_discount_total()
            records._l10n_ve_sync_global_discount_accounting()
        return records

    def write(self, vals):
        if {"reason_id", "amount", "discount_type", "discount_percentage"} & set(vals):
            self._l10n_ve_check_global_discount_user_access()
        res = super().write(vals)
        if self.env.context.get("l10n_ve_skip_discount_refresh"):
            return res
        if {"reason_id", "amount", "discount_type", "discount_percentage"} & set(vals):
            self._l10n_ve_check_move_editable()
            self.move_id._l10n_ve_check_single_percentage_global_discount(
                self.move_id.l10n_ve_global_discount_ids
            )
            self.move_id._l10n_ve_refresh_percentage_global_discount_amounts()
            self.move_id._l10n_ve_validate_global_discount_total()
            self._l10n_ve_sync_global_discount_accounting()
        return res

    def unlink(self):
        moves = self.move_id
        self._l10n_ve_check_move_editable()
        res = super().unlink()
        self.env["l10n.ve.account.move.discount"]._l10n_ve_sync_global_discount_accounting_for_moves(
            moves
        )
        return res

    def _l10n_ve_check_move_editable(self):
        self._l10n_ve_check_global_discount_user_access()
        for discount in self:
            move = discount.move_id
            if move.state != "draft":
                raise UserError(
                    _("Solo puede modificar descuentos globales en facturas en borrador.")
                )
            if move.country_code != "VE":
                raise UserError(
                    _("Los descuentos globales venezolanos solo aplican a facturas VE.")
                )
            if not move.is_invoice(include_receipts=True):
                raise UserError(
                    _("Los descuentos globales solo aplican a documentos de factura.")
                )


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_global_discount_ids = fields.One2many(
        comodel_name="l10n.ve.account.move.discount",
        inverse_name="move_id",
        string="Global discounts",
        copy=False,
    )
    l10n_ve_discount_reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Motivo de descuento",
        copy=False,
        ondelete="restrict",
    )
    l10n_ve_show_post_discount_action = fields.Boolean(
        compute="_compute_l10n_ve_show_post_discount_action",
    )
    l10n_ve_show_global_discount_action = fields.Boolean(
        compute="_compute_l10n_ve_show_global_discount_action",
    )

    @api.depends(
        "state",
        "move_type",
        "country_code",
    )
    def _compute_l10n_ve_show_global_discount_action(self):
        for move in self:
            move.l10n_ve_show_global_discount_action = (
                move.country_code == "VE"
                and move.state == "draft"
                and move.is_invoice(include_receipts=True)
                and move._l10n_ve_user_can_apply_global_discount()
            )

    def _l10n_ve_user_can_apply_global_discount(self):
        return self.env.user.has_group("l10n_ve_loyalty.group_l10n_ve_global_discount")

    def _l10n_ve_check_global_discount_user_access(self):
        if not self._l10n_ve_user_can_apply_global_discount():
            raise UserError(
                _("You do not have permission to manage global discounts.")
            )

    @api.depends(
        "state",
        "move_type",
        "country_code",
        "amount_untaxed",
        "currency_id",
        "reversal_move_ids.state",
        "reversal_move_ids.move_type",
        "reversal_move_ids.amount_untaxed",
    )
    def _compute_l10n_ve_show_post_discount_action(self):
        for move in self:
            move.l10n_ve_show_post_discount_action = (
                move._l10n_ve_allows_post_discount_action()
            )

    def copy(self, default=None):
        return super(
            AccountMove,
            self.with_context(l10n_ve_skip_global_discount_access_check=True),
        ).copy(default=default)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for move, vals in zip(self, vals_list):
            if not move.is_invoice(include_receipts=True):
                continue
            line_commands = vals.get("line_ids")
            if line_commands:
                excluded_types = {"global_discount"}
                if move.l10n_ve_global_discount_ids:
                    excluded_types.add("discount")
                vals["line_ids"] = [
                    (command, line_id, line_vals)
                    for command, line_id, line_vals in line_commands
                    if line_vals.get("display_type") not in excluded_types
                ]
            if move.l10n_ve_global_discount_ids:
                vals["l10n_ve_global_discount_ids"] = [
                    Command.create(
                        {
                            "reason_id": discount.reason_id.id,
                            "amount": discount.amount,
                            "discount_type": discount.discount_type,
                            "discount_percentage": discount.discount_percentage,
                            "amount_base": discount.amount_base,
                        }
                    )
                    for discount in move.l10n_ve_global_discount_ids
                ]
        return vals_list

    def copy(self, default=None):
        new_moves = super(
            AccountMove, self.with_context(l10n_ve_skip_discount_refresh=True)
        ).copy(default)
        moves_to_sync = new_moves.filtered(
            lambda move: move.is_invoice(include_receipts=True)
            and move.l10n_ve_global_discount_ids
        )
        if moves_to_sync:
            moves_to_sync._l10n_ve_refresh_percentage_global_discount_amounts()
            moves_to_sync._l10n_ve_validate_global_discount_total()
            self.env[
                "l10n.ve.account.move.discount"
            ]._l10n_ve_sync_global_discount_accounting_for_moves(moves_to_sync)
        return new_moves

    def _l10n_ve_snapshot_global_discount_amounts_for_currency(self):
        pending = []
        for move in self:
            if (
                move.move_type not in ("out_refund", "in_refund")
                or not move.l10n_ve_global_discount_ids
                or move.currency_id == move.company_currency_id
            ):
                continue
            if move._l10n_ve_is_post_discount_credit_note():
                continue
            pending.append(
                (
                    move,
                    move.currency_id,
                    {
                        discount.id: (discount.amount, discount.discount_type)
                        for discount in move.l10n_ve_global_discount_ids
                    },
                )
            )
        return pending

    def _l10n_ve_apply_global_discount_amounts_after_currency(self, pending):
        if not pending:
            return
        Discount = self.env["l10n.ve.account.move.discount"]
        to_sync = self.env["account.move"]
        for move, old_currency, amounts in pending:
            if not move.exists() or move.currency_id == old_currency:
                continue
            origin = move.reversed_entry_id
            converter = origin if origin else move
            for discount in move.l10n_ve_global_discount_ids:
                old_amount, discount_type = amounts.get(
                    discount.id, (discount.amount, discount.discount_type)
                )
                if discount_type == "percentage":
                    continue
                discount.amount = converter._l10n_ve_post_discount_amount_in_currency(
                    old_amount, move.currency_id
                )
            to_sync |= move
        if to_sync:
            to_sync._l10n_ve_refresh_percentage_global_discount_amounts()
            Discount._l10n_ve_sync_global_discount_accounting_for_moves(to_sync)

    def _l10n_ve_get_product_discount_lines(self):
        self.ensure_one()
        disc = getattr(self.company_id, "sale_discount_product_id", False)
        if not disc:
            return self.env["account.move.line"]
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.product_id == disc
        )

    def action_l10n_ve_remove_global_discount(self, discount_id):
        self.ensure_one()
        discount = self.env["l10n.ve.account.move.discount"].browse(discount_id)
        if discount.exists():
            if discount.move_id != self:
                raise UserError(_("El descuento no pertenece a esta factura."))
            discount.unlink()
            return True
        line = self.env["account.move.line"].browse(discount_id)
        if line.exists() and line in self._l10n_ve_get_product_discount_lines():
            self._l10n_ve_check_global_discount_allowed()
            line.unlink()
            return True
        raise UserError(_("El descuento no pertenece a esta factura."))

    def action_l10n_ve_remove_all_global_discounts(self):
        self.ensure_one()
        product_lines = self._l10n_ve_get_product_discount_lines()
        if self.l10n_ve_global_discount_ids:
            if len(self.l10n_ve_global_discount_ids) <= 1:
                return True
            self._l10n_ve_check_global_discount_allowed()
            self.l10n_ve_global_discount_ids.unlink()
            return True
        if len(product_lines) <= 1:
            return True
        self._l10n_ve_check_global_discount_allowed()
        product_lines.unlink()
        return True

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
        for move in self:
            l10n_ve_discount_logic.l10n_ve_validate_global_discount_total(move)

    def _l10n_ve_refresh_percentage_global_discount_amounts(self):
        for move in self:
            l10n_ve_discount_logic.l10n_ve_refresh_percentage_global_discount_amounts(move)

    def _l10n_ve_total_sequential_global_discount(self, subtotal_by_taxes):
        self.ensure_one()
        return l10n_ve_discount_logic.l10n_ve_total_sequential_global_discount(
            self, subtotal_by_taxes
        )

    def _l10n_ve_refresh_global_discounts_from_lines(self):
        moves = self.filtered(
            lambda move: move.state == "draft"
            and move.is_invoice(include_receipts=True)
            and move.l10n_ve_global_discount_ids
        )
        if not moves or self.env.context.get("l10n_ve_skip_discount_refresh"):
            return
        moves._l10n_ve_refresh_percentage_global_discount_amounts()
        moves._l10n_ve_validate_global_discount_total()
        self.env["l10n.ve.account.move.discount"]._l10n_ve_sync_global_discount_accounting_for_moves(
            moves
        )

    def action_l10n_ve_open_discount_wizard(self):
        self.ensure_one()
        if self.state == "posted":
            self._l10n_ve_check_post_discount_allowed()
        else:
            self._l10n_ve_check_global_discount_allowed()
        return {
            "name": _("Descuento"),
            "type": "ir.actions.act_window",
            "res_model": "l10n.ve.account.move.discount.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_discount_currency_id": self.currency_id.id,
                **(
                    {"default_reason_id": default_reason.id}
                    if (default_reason := self.env["l10n.ve.discount.reason"]._l10n_ve_get_default())
                    else {}
                ),
            },
        }

    def action_l10n_ve_open_global_discount_wizard(self):
        return self.action_l10n_ve_open_discount_wizard()

    def _l10n_ve_check_global_discount_allowed(self):
        self.ensure_one()
        self._l10n_ve_check_global_discount_user_access()
        if self.country_code != "VE":
            raise UserError(_("Esta acción solo aplica a facturas venezolanas."))
        if self.state != "draft":
            raise UserError(_("Solo puede agregar descuentos en facturas en borrador."))
        if not self.is_invoice(include_receipts=True):
            raise UserError(_("Los descuentos globales solo aplican a facturas."))

    def _l10n_ve_allows_post_discount_action(self):
        self.ensure_one()
        if not self._l10n_ve_user_can_apply_global_discount():
            return False
        if self.country_code != "VE" or self.move_type != "out_invoice":
            return False
        if self.state != "posted":
            return False
        if "l10n_ve_show_credit_note_action" in self._fields:
            if not self.l10n_ve_show_credit_note_action:
                return False
        available = self._l10n_ve_post_discount_available_untaxed()
        return float_compare(
            available, 0.0, precision_digits=self.currency_id.decimal_places
        ) > 0

    def _l10n_ve_check_post_discount_allowed(self):
        self.ensure_one()
        self._l10n_ve_check_global_discount_user_access()
        if self.country_code != "VE":
            raise UserError(_("Esta acción solo aplica a facturas venezolanas."))
        if self.move_type != "out_invoice":
            raise UserError(
                _("El descuento post-factura solo aplica a facturas de cliente.")
            )
        if self.state != "posted":
            raise UserError(
                _("El descuento post-factura solo aplica a facturas confirmadas.")
            )
        self._l10n_ve_check_credit_note_creation_allowed()
        available = self._l10n_ve_post_discount_available_untaxed()
        if float_compare(
            available, 0.0, precision_digits=self.currency_id.decimal_places
        ) <= 0:
            raise UserError(
                _("No queda subtotal disponible para aplicar un descuento post-factura.")
            )

    def _l10n_ve_post_discount_credit_notes(self):
        self.ensure_one()

        def _is_post_discount_refund(move):
            if move.move_type != "out_refund" or move.state == "cancel":
                return False
            if "l10n_ve_debit_note_reversed_ids" in move._fields:
                return not move.l10n_ve_debit_note_reversed_ids
            return True

        return self.reversal_move_ids.filtered(_is_post_discount_refund)

    def _l10n_ve_discount_remaining_subtotal_by_taxes(self):
        self.ensure_one()
        remaining = l10n_ve_discount_logic.l10n_ve_remaining_subtotal_by_taxes(self)
        if self.state != "posted":
            return remaining
        used = self._l10n_ve_post_discount_used_untaxed()
        if self.currency_id.is_zero(used):
            return remaining
        tax_groups = list(remaining.keys())
        weights = [remaining[taxes] for taxes in tax_groups]
        parts = self._l10n_ve_split_amount_by_weights(used, weights)
        result = {}
        for taxes, part in zip(tax_groups, parts):
            result[taxes] = max(0.0, remaining[taxes] - part)
        return result

    def _l10n_ve_discount_available_total(self, remaining=None):
        self.ensure_one()
        return self.currency_id.round(
            self.amount_total - self._l10n_ve_post_discount_used_total()
        )

    def _l10n_ve_discount_available_in_currency(self, amount_base, currency):
        self.ensure_one()
        currency = currency or self.currency_id
        if amount_base == "total":
            if currency == self.company_currency_id:
                return currency.round(
                    abs(self.amount_total_signed)
                    - self._l10n_ve_post_discount_used_total_company()
                )
            available = self.amount_total - self._l10n_ve_post_discount_used_total()
            return self._l10n_ve_post_discount_amount_in_currency(
                available, currency, amount_base="total"
            )
        if currency == self.company_currency_id:
            return currency.round(
                abs(self.amount_untaxed_signed)
                - self._l10n_ve_post_discount_used_untaxed_company()
            )
        remaining = self._l10n_ve_discount_remaining_subtotal_by_taxes()
        return self._l10n_ve_post_discount_amount_in_currency(
            sum(remaining.values()), currency, amount_base="untaxed"
        )

    def _l10n_ve_invoice_company_rate(self, amount_base="untaxed"):
        self.ensure_one()
        if self.currency_id == self.company_currency_id:
            return 1.0
        if amount_base == "total":
            if self.currency_id.is_zero(self.amount_total):
                return 0.0
            return abs(self.amount_total_signed) / abs(self.amount_total)
        return self._l10n_ve_invoice_untaxed_company_rate()

    def _l10n_ve_invoice_untaxed_company_rate(self):
        self.ensure_one()
        if self.currency_id == self.company_currency_id:
            return 1.0
        if self.currency_id.is_zero(self.amount_untaxed):
            return 0.0
        return abs(self.amount_untaxed_signed) / abs(self.amount_untaxed)

    def _l10n_ve_post_discount_amount_in_currency(
        self, amount_invoice_currency, currency, amount_base="untaxed"
    ):
        self.ensure_one()
        if currency == self.currency_id:
            return currency.round(amount_invoice_currency)
        rate = self._l10n_ve_invoice_company_rate(amount_base)
        if currency == self.company_currency_id:
            return currency.round(amount_invoice_currency * rate)
        date = self.invoice_date or fields.Date.context_today(self)
        return self.currency_id._convert(
            amount_invoice_currency, currency, self.company_id, date
        )

    def _l10n_ve_post_discount_amount_from_currency(
        self, amount, currency, amount_base="untaxed"
    ):
        self.ensure_one()
        if currency == self.currency_id:
            return self.currency_id.round(amount)
        rate = self._l10n_ve_invoice_company_rate(amount_base)
        if currency == self.company_currency_id and rate:
            return self.currency_id.round(amount / rate)
        date = self.invoice_date or fields.Date.context_today(self)
        return currency._convert(
            amount, self.currency_id, self.company_id, date
        )

    def _l10n_ve_post_discount_credit_note_currency(self):
        self.ensure_one()
        if (
            hasattr(self, "_l10n_ve_requires_refund_company_currency")
            and self._l10n_ve_requires_refund_company_currency()
        ):
            return self.company_currency_id
        return self.currency_id

    def _l10n_ve_credit_untaxed_in_invoice_currency(self, credit):
        self.ensure_one()
        if credit.currency_id == self.currency_id:
            return credit.amount_untaxed
        credit_bs = abs(
            sum(
                credit.line_ids.filtered(
                    lambda line: line.display_type == "product"
                ).mapped("balance")
            )
        )
        if self.currency_id == self.company_currency_id:
            return self.currency_id.round(credit_bs)
        rate = self._l10n_ve_invoice_untaxed_company_rate()
        if not rate:
            return 0.0
        return self.currency_id.round(credit_bs / rate)

    def _l10n_ve_post_discount_used_untaxed(self):
        self.ensure_one()
        return self.currency_id.round(
            sum(
                self._l10n_ve_credit_untaxed_in_invoice_currency(credit)
                for credit in self._l10n_ve_post_discount_credit_notes()
            )
        )

    def _l10n_ve_credit_total_in_invoice_currency(self, credit):
        self.ensure_one()
        if credit.currency_id == self.currency_id:
            return credit.amount_total
        credit_bs = abs(credit.amount_total_signed)
        if self.currency_id == self.company_currency_id:
            return self.currency_id.round(credit_bs)
        rate = self._l10n_ve_invoice_company_rate("total")
        if not rate:
            return 0.0
        return self.currency_id.round(credit_bs / rate)

    def _l10n_ve_post_discount_used_total(self):
        self.ensure_one()
        return self.currency_id.round(
            sum(
                self._l10n_ve_credit_total_in_invoice_currency(credit)
                for credit in self._l10n_ve_post_discount_credit_notes()
            )
        )

    def _l10n_ve_post_discount_used_total_company(self):
        self.ensure_one()
        return self.company_currency_id.round(
            sum(
                abs(credit.amount_total_signed)
                for credit in self._l10n_ve_post_discount_credit_notes()
            )
        )

    def _l10n_ve_post_discount_used_untaxed_company(self):
        self.ensure_one()
        return self.company_currency_id.round(
            sum(
                abs(
                    sum(
                        credit.line_ids.filtered(
                            lambda line: line.display_type == "product"
                        ).mapped("balance")
                    )
                )
                for credit in self._l10n_ve_post_discount_credit_notes()
            )
        )

    def _l10n_ve_post_discount_available_untaxed(self):
        self.ensure_one()
        return self.currency_id.round(
            self.amount_untaxed - self._l10n_ve_post_discount_used_untaxed()
        )

    def _l10n_ve_post_discount_subtotal_by_taxes(self):
        self.ensure_one()
        totals = defaultdict(float)
        for line in self.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.display_type == "product"
        ):
            taxes = line.tax_ids.filtered(lambda tax: tax.amount_type != "fixed")
            if float_is_zero(line.price_subtotal, precision_rounding=self.currency_id.rounding):
                continue
            totals[taxes] += line.price_subtotal
        return totals

    def _l10n_ve_post_discount_account_for_taxes(self, taxes):
        self.ensure_one()
        discount_account = self._get_discount_allocation_account()
        if discount_account:
            return discount_account
        lines = self.invoice_line_ids.filtered(
            lambda line: (
                line.display_type == "product"
                and line.account_id
                and set(line.tax_ids.filtered(lambda tax: tax.amount_type != "fixed").ids)
                == set(taxes.ids)
            )
        )
        if lines:
            return lines[0].account_id
        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.account_id
        )
        if product_lines:
            return product_lines[0].account_id
        return self.journal_id.default_account_id

    def _l10n_ve_post_discount_sample_line_for_taxes(self, taxes):
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(
            lambda line: (
                line.display_type == "product"
                and set(
                    line.tax_ids.filtered(lambda tax: tax.amount_type != "fixed").ids
                )
                == set(taxes.ids)
            )
        )
        return lines[:1]

    def _l10n_ve_prepare_post_discount_credit_note_lines(
        self, amount, reason, currency=None
    ):
        self.ensure_one()
        currency = currency or self.currency_id
        subtotal_by_taxes = self._l10n_ve_post_discount_subtotal_by_taxes()
        if not subtotal_by_taxes:
            raise UserError(
                _("La factura no tiene líneas de producto para prorratear el descuento.")
            )
        tax_groups = list(subtotal_by_taxes.keys())
        weights = [subtotal_by_taxes[taxes] for taxes in tax_groups]
        parts = self._l10n_ve_split_amount_by_weights(
            amount, weights, currency=currency
        )
        line_name = _("Descuento: %(reason)s", reason=reason.name)
        line_vals = []
        for taxes, part in zip(tax_groups, parts):
            if float_is_zero(part, precision_rounding=currency.rounding):
                continue
            sample = self._l10n_ve_post_discount_sample_line_for_taxes(taxes)
            account = self._l10n_ve_post_discount_account_for_taxes(taxes)
            if not account:
                raise UserError(
                    _("No se encontró una cuenta contable para la nota de crédito.")
                )
            vals = {
                "name": line_name,
                "quantity": 1.0,
                "price_unit": part,
                "account_id": account.id,
                "tax_ids": [Command.set(taxes.ids)],
            }
            if sample.product_id:
                vals["product_id"] = sample.product_id.id
            line_vals.append(Command.create(vals))
        if not line_vals:
            raise UserError(_("No se pudo construir líneas para la nota de crédito."))
        return line_vals

    def _l10n_ve_adjust_post_discount_to_untaxed_amount(self, target_untaxed):
        self.ensure_one()
        current = self.amount_untaxed
        if float_is_zero(current, precision_rounding=self.currency_id.rounding):
            return
        if (
            float_compare(
                current,
                target_untaxed,
                precision_digits=self.currency_id.decimal_places,
            )
            == 0
        ):
            return
        factor = target_untaxed / current
        lines = self.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.display_type == "product"
        )
        for line in lines:
            line.with_context(l10n_ve_skip_exempt_tax_line=True).write(
                {"price_unit": self.currency_id.round(line.price_unit * factor)}
            )

    def _l10n_ve_create_post_discount_credit_note(
        self, amount, reason, amount_cn=None
    ):
        self.ensure_one()
        target_currency = self._l10n_ve_post_discount_credit_note_currency()
        if amount_cn is not None:
            line_amount = target_currency.round(amount_cn)
        else:
            line_amount = self._l10n_ve_post_discount_amount_in_currency(
                amount, target_currency
            )
        line_vals = self._l10n_ve_prepare_post_discount_credit_note_lines(
            line_amount, reason, currency=target_currency
        )
        credit_note = (
            self.env["account.move"]
            .with_context(l10n_ve_skip_exempt_tax_line=True)
            .create(
                {
                    "move_type": "out_refund",
                    "reversed_entry_id": self.id,
                    "partner_id": self.partner_id.id,
                    "journal_id": self.journal_id.id,
                    "invoice_date": fields.Date.context_today(self),
                    "currency_id": target_currency.id,
                    "l10n_ve_discount_reason_id": reason.id,
                    "ref": _(
                        "Descuento post-factura %(invoice)s: %(reason)s",
                        invoice=self.name,
                        reason=reason.name,
                    ),
                    "invoice_line_ids": line_vals,
                }
            )
        )
        if credit_note.currency_id != target_currency:
            credit_note._l10n_ve_force_refund_to_company_currency()
        credit_note.with_context(
            l10n_ve_skip_exempt_tax_line=True
        )._l10n_ve_adjust_post_discount_to_untaxed_amount(line_amount)
        return credit_note

    def action_l10n_ve_open_post_discount_wizard(self):
        return self.action_l10n_ve_open_discount_wizard()

    def _l10n_ve_global_discount_applies(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.is_invoice(include_receipts=True)
            and bool(self.l10n_ve_global_discount_ids)
        )

    def _l10n_ve_uses_global_discount_journal_lines(self):
        self.ensure_one()
        return (
            self._l10n_ve_global_discount_applies()
            and bool(self._get_discount_allocation_account())
        )

    def _get_rounded_base_and_tax_lines(self, round_from_tax_lines=True):
        if self.env.context.get("l10n_ve_skip_global_discount_base_lines"):
            return super()._get_rounded_base_and_tax_lines(
                round_from_tax_lines=round_from_tax_lines
            )
        base_lines, tax_lines = super()._get_rounded_base_and_tax_lines(
            round_from_tax_lines=round_from_tax_lines
        )
        return self._l10n_ve_apply_global_discount_to_base_lines(
            base_lines,
            tax_lines,
            round_from_tax_lines,
            foreign=False,
        )

    def _get_rounded_foreign_base_and_tax_lines(self, round_from_tax_lines=True):
        parent_method = getattr(
            super(), "_get_rounded_foreign_base_and_tax_lines", None
        )
        if not parent_method:
            return [], []
        if self.env.context.get("l10n_ve_skip_global_discount_base_lines"):
            return parent_method(round_from_tax_lines=round_from_tax_lines)
        base_lines, tax_lines = parent_method(
            round_from_tax_lines=round_from_tax_lines
        )
        return self._l10n_ve_apply_global_discount_to_base_lines(
            base_lines,
            tax_lines,
            round_from_tax_lines,
            foreign=True,
        )

    def _l10n_ve_global_discount_subtotal_by_taxes(self):
        self.ensure_one()
        base_lines, _tax_lines = super(
            AccountMove,
            self.with_context(l10n_ve_skip_global_discount_base_lines=True),
        )._get_rounded_base_and_tax_lines()
        return self._l10n_ve_subtotal_by_taxes_from_base_lines(base_lines)

    def _l10n_ve_subtotal_by_taxes_from_base_lines(self, base_lines):
        AccountTax = self.env["account.tax"]
        product_lines = self._l10n_ve_product_base_lines_for_discount(base_lines)
        lines_needing_details = [
            base_line for base_line in product_lines if not base_line.get("tax_details")
        ]
        if lines_needing_details:
            AccountTax._add_tax_details_in_base_lines(lines_needing_details, self.company_id)
        totals = defaultdict(float)
        for base_line in product_lines:
            taxes = base_line["tax_ids"].filtered(
                lambda tax: tax.amount_type != "fixed"
            )
            quantity = base_line.get("quantity") or 0.0
            if float_is_zero(quantity, precision_rounding=1e-9):
                continue
            tax_details = base_line.get("tax_details") or {}
            if "total_excluded_currency" in tax_details:
                line_subtotal = tax_details["total_excluded_currency"]
            elif "raw_total_excluded_currency" in tax_details:
                line_subtotal = tax_details["raw_total_excluded_currency"]
            else:
                price_unit = base_line.get("price_unit") or 0.0
                discount = base_line.get("discount") or 0.0
                price_reduce = price_unit * (1 - discount / 100.0)
                line_subtotal = price_reduce * quantity
            totals[taxes] += line_subtotal
        return totals

    def _l10n_ve_product_base_lines_for_discount(self, base_lines):
        return [
            base_line
            for base_line in base_lines
            if not base_line.get("special_type")
        ]

    def _l10n_ve_split_amount_by_weights(self, amount, weights, currency=None):
        self.ensure_one()
        if not weights:
            return []
        if len(weights) == 1:
            return [amount]
        total_weight = sum(weights)
        if float_is_zero(total_weight, precision_rounding=1e-9):
            return [0.0] * len(weights)
        currency = currency or self.currency_id
        prec = currency.decimal_places
        parts = []
        accumulated = 0.0
        for weight in weights[:-1]:
            part = float_round(amount * weight / total_weight, precision_digits=prec)
            parts.append(part)
            accumulated += part
        parts.append(float_round(amount - accumulated, precision_digits=prec))
        return parts

    def _l10n_ve_discount_amount_in_line_currency(self, amount, line_currency):
        self.ensure_one()
        if line_currency == self.currency_id:
            return amount
        conversion_date = self.invoice_date or fields.Date.context_today(self)
        return self.currency_id._convert(
            amount,
            line_currency,
            self.company_id,
            conversion_date,
        )

    def _l10n_ve_build_global_discount_base_lines(self, base_lines, foreign=False):
        self.ensure_one()
        if not self.l10n_ve_global_discount_ids:
            return []

        subtotal_by_taxes = self._l10n_ve_subtotal_by_taxes_from_base_lines(base_lines)
        if not subtotal_by_taxes:
            return []

        line_currency = base_lines[0]["currency_id"] if base_lines else self.currency_id
        rate = self.foreign_rate if foreign and hasattr(self, "foreign_rate") else self.invoice_currency_rate
        if not rate:
            rate = 1.0

        AccountTax = self.env["account.tax"]
        discount_base_lines = []
        sequence = 0
        running = dict(subtotal_by_taxes)
        for discount, discount_amount in self._l10n_ve_sequential_global_discount_amounts(
            subtotal_by_taxes
        ):
            amount = self._l10n_ve_discount_amount_in_line_currency(
                discount_amount, line_currency
            )
            tax_groups = list(running.keys())
            weights = [running[taxes] for taxes in tax_groups]
            parts = self._l10n_ve_split_amount_by_weights(amount, weights)
            for taxes, part in zip(tax_groups, parts):
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
                        sign=self.direction_sign,
                        rate=rate,
                    )
                )
                running[taxes] = max(0.0, running[taxes] - part)
        return discount_base_lines

    def _l10n_ve_non_product_base_lines(self, base_lines):
        return [
            base_line
            for base_line in base_lines
            if base_line.get("special_type") in ("early_payment", "cash_rounding")
        ]

    def _l10n_ve_apply_global_discount_to_base_lines(
        self, base_lines, tax_lines, round_from_tax_lines, foreign=False
    ):
        self.ensure_one()
        if not self._l10n_ve_global_discount_applies():
            return base_lines, tax_lines

        AccountTax = self.env["account.tax"]
        product_lines = self._l10n_ve_product_base_lines_for_discount(base_lines)
        special_lines = self._l10n_ve_non_product_base_lines(base_lines)
        AccountTax._add_tax_details_in_base_lines(product_lines, self.company_id)
        discount_lines = self._l10n_ve_build_global_discount_base_lines(
            product_lines, foreign=foreign
        )
        if not discount_lines:
            return base_lines, tax_lines

        working_lines = product_lines + discount_lines
        AccountTax._add_tax_details_in_base_lines(discount_lines, self.company_id)
        if self.id and round_from_tax_lines is not False:
            AccountTax._round_base_lines_tax_details(
                working_lines,
                self.company_id,
                tax_lines=tax_lines if round_from_tax_lines else [],
            )
        else:
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

        all_lines = working_lines + special_lines
        if self.id and round_from_tax_lines is not False:
            AccountTax._round_base_lines_tax_details(
                all_lines,
                self.company_id,
                tax_lines=tax_lines if round_from_tax_lines else [],
            )
        else:
            AccountTax._round_base_lines_tax_details(all_lines, self.company_id)
        return all_lines, tax_lines

    def _l10n_ve_get_global_discount_allocation_by_taxes(self):
        self.ensure_one()
        if not self._l10n_ve_global_discount_applies():
            return {}

        AccountTax = self.env["account.tax"]
        base_lines, _tax_lines = super(
            AccountMove,
            self.with_context(l10n_ve_skip_global_discount_base_lines=True),
        )._get_rounded_base_and_tax_lines(round_from_tax_lines=False)
        product_lines = self._l10n_ve_product_base_lines_for_discount(base_lines)
        if not product_lines:
            return {}

        AccountTax._add_tax_details_in_base_lines(product_lines, self.company_id)
        discount_lines = self._l10n_ve_build_global_discount_base_lines(
            product_lines, foreign=False
        )
        if not discount_lines:
            return {}

        AccountTax._add_tax_details_in_base_lines(discount_lines, self.company_id)
        AccountTax._round_base_lines_tax_details(discount_lines, self.company_id)

        discount_account = self._get_discount_allocation_account()
        tax_account_weights = defaultdict(lambda: defaultdict(float))
        for base_line in product_lines:
            taxes = base_line["tax_ids"].filtered(
                lambda tax: tax.amount_type != "fixed"
            )
            record = base_line.get("record")
            if not record or record.display_type != "product":
                continue
            account_id = record.account_id.id
            if discount_account and account_id == discount_account.id:
                continue
            tax_details = base_line.get("tax_details") or {}
            if "total_excluded_currency" in tax_details:
                line_subtotal = tax_details["total_excluded_currency"]
            elif "raw_total_excluded_currency" in tax_details:
                line_subtotal = tax_details["raw_total_excluded_currency"]
            else:
                price_unit = base_line.get("price_unit") or 0.0
                discount = base_line.get("discount") or 0.0
                quantity = base_line.get("quantity") or 0.0
                line_subtotal = price_unit * (1 - discount / 100.0) * quantity
            if float_is_zero(line_subtotal, precision_rounding=self.currency_id.rounding):
                continue
            tax_account_weights[taxes][account_id] += line_subtotal

        allocations = defaultdict(lambda: defaultdict(float))
        for discount_bl in discount_lines:
            taxes = discount_bl["tax_ids"].filtered(
                lambda tax: tax.amount_type != "fixed"
            )
            tax_details = discount_bl["tax_details"]
            discount_amount = abs(
                tax_details["total_excluded_currency"]
                + tax_details.get("delta_total_excluded_currency", 0.0)
            )
            if float_is_zero(discount_amount, precision_rounding=self.currency_id.rounding):
                continue
            account_amounts = tax_account_weights.get(taxes)
            if not account_amounts:
                continue
            account_ids = list(account_amounts.keys())
            weights = [account_amounts[account_id] for account_id in account_ids]
            parts = self._l10n_ve_split_amount_by_weights(discount_amount, weights)
            for account_id, part in zip(account_ids, parts):
                if float_is_zero(part, precision_rounding=self.currency_id.rounding):
                    continue
                allocations[taxes][account_id] += part
        return allocations

    def _l10n_ve_global_discount_allocation_line_name(self, taxes):
        self.ensure_one()
        if taxes:
            return _("%(discount)s (%(taxes)s)", discount=_("Descuento global"), taxes=taxes.name)
        return _("Descuento global")

    def _l10n_ve_remove_ve_discount_journal_lines(self):
        MoveLine = self.env["account.move.line"].with_context(
            skip_invoice_sync=True,
            l10n_ve_skip_discount_refresh=True,
            dynamic_unlink=True,
        )
        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue
            lines = move.line_ids.filtered(
                lambda line: line.l10n_ve_global_discount_line
                or line.l10n_ve_line_discount_line
                or line.display_type == "global_discount"
            )
            if lines:
                MoveLine.browse(lines.ids).unlink()

    def _l10n_ve_cleanup_line_discount_journal_lines(self):
        MoveLine = self.env["account.move.line"].with_context(
            skip_invoice_sync=True,
            l10n_ve_skip_discount_refresh=True,
            dynamic_unlink=True,
        )
        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue
            if not move._l10n_ve_uses_global_discount_journal_lines():
                continue
            lines = move.line_ids.filtered(
                lambda line: line.l10n_ve_line_discount_line
                or (
                    line.display_type == "discount"
                    and not line.l10n_ve_global_discount_line
                )
            )
            if lines:
                MoveLine.browse(lines.ids).unlink()

    def _l10n_ve_sync_global_discount_journal_lines(self):
        MoveLine = self.env["account.move.line"].with_context(
            skip_invoice_sync=True,
            l10n_ve_skip_discount_refresh=True,
        )

        def is_write_needed(line, values):
            if not line.exists():
                return False
            for fname, value in values.items():
                if fname == "l10n_ve_global_discount_tax_ids":
                    if set(line.l10n_ve_global_discount_tax_ids.ids) != set(
                        value[0][2]
                    ):
                        return True
                    continue
                if (
                    MoveLine._fields[fname].convert_to_write(line[fname], line)
                    != value
                ):
                    return True
            return False

        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue

            existing_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
            if not move._l10n_ve_global_discount_applies():
                if existing_lines:
                    existing_lines.with_context(dynamic_unlink=True).unlink()
                continue

            discount_account = move._get_discount_allocation_account()
            if not discount_account:
                if existing_lines:
                    existing_lines.with_context(dynamic_unlink=True).unlink()
                continue

            allocations = move._l10n_ve_get_global_discount_allocation_by_taxes()
            needed = {}
            rate = move.invoice_currency_rate or 1.0
            sign = move.direction_sign
            line_name_by_taxes = {}

            for taxes, account_amounts in allocations.items():
                line_name_by_taxes[taxes] = move._l10n_ve_global_discount_allocation_line_name(
                    taxes
                )
                total_for_taxes = sum(account_amounts.values())
                key_discount = frozendict(
                    {
                        "move_id": move.id,
                        "account_id": discount_account.id,
                        "currency_rate": rate,
                        "tax_ids": tuple(sorted(taxes.ids)),
                    }
                )
                needed[key_discount] = {
                    "display_type": "global_discount",
                    "name": line_name_by_taxes[taxes],
                    "account_id": discount_account.id,
                    "tax_ids": [Command.clear()],
                    "amount_currency": move.currency_id.round(-sign * total_for_taxes),
                    "balance": move.company_id.currency_id.round(
                        -sign * total_for_taxes / rate
                    ),
                    "l10n_ve_global_discount_line": True,
                    "l10n_ve_global_discount_tax_ids": [Command.set(taxes.ids)],
                }

            existing_map = {
                line.l10n_ve_global_discount_allocation_key: line
                for line in existing_lines
                if line.l10n_ve_global_discount_allocation_key
            }
            to_delete = [
                line.id
                for key, line in existing_map.items()
                if key not in needed
            ]
            to_create = [
                {**values, "move_id": move.id}
                for key, values in needed.items()
                if key not in existing_map
            ]
            to_write = [
                (existing_map[key], values)
                for key, values in needed.items()
                if key in existing_map
                and is_write_needed(existing_map[key], values)
            ]

            if to_delete:
                MoveLine.browse(to_delete).exists().with_context(
                    dynamic_unlink=True
                ).unlink()
            if to_create:
                MoveLine.create(to_create)
            for line, values in to_write:
                if line.exists():
                    line.write(values)

    def _l10n_ve_rebalance_payment_term_from_lines(self):
        MoveLine = self.env["account.move.line"].with_context(
            skip_invoice_sync=True,
            l10n_ve_skip_discount_refresh=True,
        )
        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue
            payment_lines = move.line_ids.filtered(
                lambda line: line.display_type == "payment_term"
            )
            if not payment_lines:
                continue
            other_lines = move.line_ids - payment_lines
            balance = sum(other_lines.mapped("balance"))
            amount_currency = sum(other_lines.mapped("amount_currency"))
            values = {
                "balance": move.company_id.currency_id.round(-balance),
                "amount_currency": move.currency_id.round(-amount_currency),
            }
            for line in payment_lines:
                if any(
                    MoveLine._fields[fname].convert_to_write(line[fname], line)
                    != values[fname]
                    for fname in values
                ):
                    line.write(values)
            move.invalidate_recordset(
                [
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                    "amount_total_signed",
                    "amount_untaxed_signed",
                    "amount_tax_signed",
                    "amount_total_in_currency_signed",
                    "amount_untaxed_in_currency_signed",
                    "needed_terms",
                ]
            )

    def _l10n_ve_sync_payment_term_after_global_discount_lines(self):
        return self._l10n_ve_rebalance_payment_term_from_lines()

    def _l10n_ve_apply_global_discount_sync(self):
        AccountTax = self.env["account.tax"]
        MoveLine = self.env["account.move.line"].with_context(
            skip_invoice_sync=True,
            l10n_ve_skip_discount_refresh=True,
        )

        def is_write_needed(line, values):
            if not line.exists():
                return False
            return any(
                MoveLine._fields[fname].convert_to_write(line[fname], line) != values[fname]
                for fname in values
            )

        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue

            base_lines_values, tax_lines_values = move._get_rounded_base_and_tax_lines(
                round_from_tax_lines=False
            )
            AccountTax._add_accounting_data_in_base_lines_tax_details(
                base_lines_values,
                move.company_id,
                include_caba_tags=move.always_tax_exigible,
            )
            tax_results = AccountTax._prepare_tax_lines(
                base_lines_values,
                move.company_id,
                tax_lines=tax_lines_values,
            )

            grouped_update = defaultdict(set)
            to_delete = []
            to_create = []

            use_pre_global_product_lines = move._l10n_ve_uses_global_discount_journal_lines()

            for base_line, to_update in tax_results["base_lines_to_update"]:
                line = base_line["record"]
                if not isinstance(line, models.BaseModel) or not line.exists():
                    continue
                if use_pre_global_product_lines:
                    record = base_line.get("record")
                    if (
                        record
                        and record.display_type == "product"
                        and not base_line.get("special_type")
                    ):
                        tax_details = base_line.get("tax_details") or {}
                        sign = base_line["sign"]
                        to_update = dict(to_update)
                        if float_is_zero(
                            base_line.get("discount") or 0.0, precision_rounding=1e-9
                        ):
                            pre_global_currency = tax_details.get(
                                "raw_gross_total_excluded_currency"
                            )
                            pre_global_balance = tax_details.get(
                                "raw_gross_total_excluded"
                            )
                        else:
                            line_currency = base_line["currency_id"]
                            discount_factor = 1 - (base_line.get("discount") or 0.0) / 100.0
                            pre_global_currency = line_currency.round(
                                base_line["price_unit"]
                                * base_line["quantity"]
                                * discount_factor
                            )
                            rate = base_line.get("rate") or 1.0
                            pre_global_balance = move.company_id.currency_id.round(
                                pre_global_currency / rate
                                if rate
                                else pre_global_currency
                            )
                        if (
                            pre_global_currency is not None
                            and pre_global_balance is not None
                        ):
                            to_update["amount_currency"] = sign * (
                                pre_global_currency
                                + tax_details.get("delta_total_excluded_currency", 0.0)
                            )
                            to_update["balance"] = sign * (
                                pre_global_balance
                                + tax_details.get("delta_total_excluded", 0.0)
                            )
                if is_write_needed(line, to_update):
                    grouped_update[line.currency_id.id, frozendict(to_update)].add(line.id)

            for tax_line_vals in tax_results["tax_lines_to_delete"]:
                line = tax_line_vals["record"]
                if line.exists():
                    to_delete.append(line.id)

            for tax_line_vals in tax_results["tax_lines_to_add"]:
                to_create.append(
                    {
                        **tax_line_vals,
                        "display_type": "tax",
                        "move_id": move.id,
                    }
                )

            for tax_line_vals, _grouping_key, to_update in tax_results[
                "tax_lines_to_update"
            ]:
                line = tax_line_vals["record"]
                if not line.exists():
                    continue
                if is_write_needed(line, to_update):
                    grouped_update[line.currency_id.id, frozendict(to_update)].add(line.id)

            if grouped_update:
                for (_currency_id, values), lines in grouped_update.items():
                    lines_to_update = MoveLine.browse(lines).exists()
                    if lines_to_update:
                        lines_to_update.write(dict(values))
            if to_delete:
                MoveLine.browse(to_delete).exists().with_context(
                    dynamic_unlink=True,
                ).unlink()
            if to_create:
                MoveLine.create(to_create)

            move.invalidate_recordset(
                [
                    "amount_untaxed",
                    "amount_tax",
                    "amount_total",
                    "amount_total_signed",
                    "amount_untaxed_signed",
                    "amount_tax_signed",
                    "amount_total_in_currency_signed",
                    "amount_untaxed_in_currency_signed",
                    "tax_totals",
                    "needed_terms",
                ]
            )

    @api.depends(
        "line_ids.matched_debit_ids.debit_move_id.payment_id.is_matched",
        "line_ids.matched_credit_ids.credit_move_id.payment_id.is_matched",
        "line_ids.full_reconcile_id",
        "state",
        "line_ids.l10n_ve_global_discount_line",
        "line_ids.l10n_ve_line_discount_line",
    )
    def _compute_amount(self):
        super()._compute_amount()
        for move in self.filtered(
            lambda m: m.is_invoice(include_receipts=True)
            and m._l10n_ve_uses_global_discount_journal_lines()
        ):
            global_discount_lines = move.line_ids.filtered(
                lambda line: line.l10n_ve_global_discount_line
                and line.display_type == "global_discount"
            )
            line_discount_lines = move.line_ids.filtered(
                lambda line: line.l10n_ve_line_discount_line
                and line.display_type == "discount"
            )
            discount_lines = global_discount_lines | line_discount_lines
            if not discount_lines:
                continue
            sign = move.direction_sign
            product_lines = move.line_ids.filtered(
                lambda line: line.display_type == "product"
            )
            tax_lines = move.line_ids.filtered(
                lambda line: line.display_type == "tax"
                or (
                    line.display_type == "rounding"
                    and line.tax_repartition_line_id
                )
            )
            total_untaxed_currency = sum(product_lines.mapped("amount_currency")) + sum(
                discount_lines.mapped("amount_currency")
            )
            total_untaxed = sum(product_lines.mapped("balance")) + sum(
                discount_lines.mapped("balance")
            )
            total_tax_currency = sum(tax_lines.mapped("amount_currency"))
            total_tax = sum(tax_lines.mapped("balance"))
            total_currency = total_untaxed_currency + total_tax_currency
            total = total_untaxed + total_tax
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency
            move.amount_untaxed_signed = -total_untaxed
            move.amount_untaxed_in_currency_signed = -total_untaxed_currency
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = (
                abs(total) if move.move_type == "entry" else -total
            )
            move.amount_total_in_currency_signed = (
                abs(move.amount_total)
                if move.move_type == "entry"
                else -(sign * move.amount_total)
            )
