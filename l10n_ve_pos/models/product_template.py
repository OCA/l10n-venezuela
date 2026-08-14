# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ve_pos_allow_price_change = fields.Boolean(
        string="Allow price change in POS",
        help="If enabled, cashiers can change this product's unit price "
        "in the Point of Sale (for example eWallet top-up).",
    )
