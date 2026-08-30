# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    wh_islr_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default ISLR Withholding Journal",
        help="Journal used to generate ISLR withholding entries",
    )
    wh_islr_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default ISLR Withholding Account",
        help="Account used for ISLR Withholding retention liabilities",
    )
