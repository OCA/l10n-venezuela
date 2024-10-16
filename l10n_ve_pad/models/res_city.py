from odoo import fields, models


class ResCity(models.Model):
    _inherit = "res.city"

    l10n_ve_code = fields.Char(
        "Code",
        help="This code will help with the identification of each city in Venezuela.",
    )
