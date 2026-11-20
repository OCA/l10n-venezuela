# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_igtf_enabled = fields.Boolean(
        string="Enable IGTF",
        help="Enable the IGTF option for payments made through this journal. "
        "This setting does not determine whether a specific transaction is taxable.",
    )
