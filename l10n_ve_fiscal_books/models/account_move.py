# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_paper_number = fields.Char(
        string="Paper Invoice Number",
        copy=False,
        tracking=True,
        index="btree_not_null",
        help="Preprinted invoice number from the authorized contingency booklet. "
        "The sales book uses it instead of the internal sequence.",
    )
