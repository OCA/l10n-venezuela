# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_ve_edoc_is_exempt(self):
        """A product line with no non-zero tax is exempt, exonerated, or not
        subject to VAT, for the purpose of the digital printing house
        payload. SENIAT PA SNAT/2024/000102 art. 7.8 marks all of these with
        the same "(E)" letter -- there is no separate letter per concept and
        no "G" for taxed lines -- so a single predicate is enough here.
        """
        self.ensure_one()
        return self.display_type == "product" and not any(
            tax.amount for tax in self.tax_ids)
