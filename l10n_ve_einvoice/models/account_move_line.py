# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_ve_edoc_is_exempt(self):
        """Return whether the invoice line has no tax with a nonzero rate."""
        self.ensure_one()
        return self.display_type == "product" and not any(
            tax.amount for tax in self.tax_ids
        )
