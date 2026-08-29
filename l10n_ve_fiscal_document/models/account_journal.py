# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models

EMISSION_MEDIUM_SELECTION = [
    ("free", "Free form"),
    ("contingency", "Contingency"),
    ("fiscal_machine", "Fiscal machine"),
    ("digital", "Digital billing"),
]


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_emission_medium = fields.Selection(
        selection=EMISSION_MEDIUM_SELECTION,
        string="Emission Medium",
        copy=False,
        help="Medium used to issue Venezuelan customer fiscal documents.",
    )
