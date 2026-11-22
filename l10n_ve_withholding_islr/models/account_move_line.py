# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_ve_islr_concept_id = fields.Many2one(
        "l10n.ve.islr.concept",
        string="Concepto ISLR",
        compute="_compute_l10n_ve_islr_concept_id",
        store=True,
        readonly=False,
        precompute=True,
        # Copied so that a credit note created by reversal keeps the concept
        # chosen on the bill line, which drives the netting of its base.
        copy=True,
        help="Concepto del art. 9 del Decreto 1.808 por el que se retiene ISLR "
        "sobre el monto sin IVA de esta línea al contabilizar la factura. Por "
        "defecto viene del producto o, en su defecto, del proveedor. Sin "
        "concepto la línea no se retiene.",
    )

    # The product concept itself is deliberately not a dependency: changing
    # it must not rewrite the concept of lines already posted.
    @api.depends("product_id", "move_id.partner_id", "display_type")
    def _compute_l10n_ve_islr_concept_id(self):
        for line in self:
            move = line.move_id
            if (
                line.display_type != "product"
                or not move.is_purchase_document(include_receipts=True)
                or move.country_code != "VE"
            ):
                line.l10n_ve_islr_concept_id = False
                continue
            line.l10n_ve_islr_concept_id = (
                line.product_id.product_tmpl_id.l10n_ve_islr_concept_id
                or move.commercial_partner_id.l10n_ve_islr_concept_id
            )

    def write(self, vals):
        """Lock the ISLR concept of the lines of posted documents.

        The concept decides the vouchers a bill issued and the netting of
        its credit notes; changing it once posted would desynchronize them.
        Draft documents stay editable.
        """
        if "l10n_ve_islr_concept_id" in vals:
            new_concept = vals["l10n_ve_islr_concept_id"] or False
            if any(
                line.parent_state == "posted"
                and line.l10n_ve_islr_concept_id.id != new_concept
                for line in self
            ):
                raise UserError(
                    self.env._(
                        "El concepto ISLR de una línea de un documento "
                        "contabilizado no puede cambiarse: pase el documento "
                        "a borrador."
                    )
                )
        return super().write(vals)

    def _l10n_ve_islr_reconcile_open(self):
        """Reconcile the open lines when both debits and credits remain."""
        lines = self.filtered(lambda line: not line.reconciled)
        if any(
            line.company_currency_id.compare_amounts(line.amount_residual, 0.0) > 0
            for line in lines
        ) and any(
            line.company_currency_id.compare_amounts(line.amount_residual, 0.0) < 0
            for line in lines
        ):
            lines.reconcile()


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def unlink(self):
        """Keep the entry of an issued voucher reconciled with its bill.

        Un-reconciling an ordinary payment of the same bill is not affected:
        only partials involving the withholding entry are checked. The
        trusted path ``_l10n_ve_unlink_unlocked`` is private, so it cannot
        be reached over RPC.
        """
        (
            self.debit_move_id.move_id | self.credit_move_id.move_id
        )._l10n_ve_islr_check_wh_move_unlocked()
        return super().unlink()

    def _l10n_ve_unlink_unlocked(self):
        return super().unlink()
