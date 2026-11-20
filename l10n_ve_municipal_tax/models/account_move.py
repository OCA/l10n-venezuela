# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_municipal_tax_period = fields.Date(
        string="Municipal Tax Period",
        copy=False,
        readonly=True,
        index=True,
        help="End date of the municipal tax period provisioned by this entry.",
    )
