# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    wh_iva_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Default VAT Withholding Journal",
        help="Journal used to generate VAT withholding entries",
    )
    wh_iva_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default VAT Withholding Account",
        help="Account used for VAT Withholding retention credits/debits",
    )
