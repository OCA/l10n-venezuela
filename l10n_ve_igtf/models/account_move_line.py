# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_ve_igtf_line = fields.Boolean(
        string="IGTF Line",
        copy=False,
    )
