# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nVeIvaWhVoucherAdjustment(models.Model):
    """Withholding adjustment issued for a partial vendor credit note.

    Links the credit note added to a voucher with the entry that returns
    its share of the withheld VAT. Users only read these records: they are
    written by the module's own transitions, so the link that decides which
    entry is undone when the credit note is reset cannot be forged over RPC.
    """

    _name = "l10n.ve.iva.wh.voucher.adjustment"
    _description = "Ajuste de Retención de IVA por Nota de Crédito"
    _check_company_auto = True

    voucher_id = fields.Many2one(
        comodel_name="l10n.ve.iva.wh.voucher",
        string="Comprobante",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    company_id = fields.Many2one(
        related="voucher_id.company_id",
        store=True,
        index=True,
    )
    refund_id = fields.Many2one(
        comodel_name="account.move",
        string="Nota de Crédito",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Asiento de Ajuste",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        check_company=True,
    )
    withheld_amount = fields.Monetary(
        string="Impuesto Retenido Revertido",
        currency_field="currency_id",
        readonly=True,
    )
    currency_id = fields.Many2one(related="voucher_id.currency_id")
