from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def write(self, vals):
        res = super().write(vals)
        if "active" in vals:
            _logger.info(vals)
            self._update_currency_fields(vals.get("active"))
        return res

    def _update_currency_fields(self, active):
        AccountMove = self.env["account.move"]
        AccountMove.create_fields(active)
