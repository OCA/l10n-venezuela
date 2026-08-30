# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    wh_state = fields.Selection(
        selection=[
            ("no_withheld", "Not Withheld"),
            ("partially_withheld", "Partially Withheld"),
            ("withheld", "Withheld"),
        ],
        string="Withholding State",
        default="no_withheld",
        copy=False,
        help="State of withholdings applied to this invoice",
    )
