# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class LoyaltyReward(models.Model):
    _inherit = "loyalty.reward"

    def _get_discount_product_values(self):
        # pos_loyalty forces taxes_id=False after l10n_ve_loyalty; re-apply VE taxes.
        return self._l10n_ve_prepare_discount_product_values(
            super()._get_discount_product_values()
        )
