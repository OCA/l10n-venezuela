# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    appl_type = fields.Selection(
        selection=[
            ("exento", "Exempt"),
            ("sdcf", "Not entitled to tax credit (SDCF)"),
            ("general", "General Aliquot"),
            ("reducido", "Reduced Aliquot"),
            ("adicional", "General + Additional Aliquot"),
        ],
        string="Aliquot Type",
        help="Specify the aliquot type according to Venezuelan law for Fiscal Books",
    )
