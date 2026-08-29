# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models

# ISO 4217 codes of the bolivar: VEF (2008), VES (2018) and VED (2021, not
# shipped by Odoo but can be created manually). The ISO code is the unique
# currency name, so it also matches currencies created without an XML ID.
BOLIVAR_CODES = ("VEF", "VES", "VED")


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _l10n_ve_is_bolivar(self):
        return self.name in BOLIVAR_CODES
