# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVeAccountMoveDiscount(models.Model):
    _inherit = "l10n.ve.account.move.discount"

    l10n_ve_sale_discount_id = fields.Many2one(
        comodel_name="l10n.ve.sale.order.discount",
        string="Sale discount",
        ondelete="set null",
        index=True,
    )
