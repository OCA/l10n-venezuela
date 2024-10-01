import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    automatic_withholdings = fields.Boolean(
        related="company_id.automatic_withholdings",
        readonly=False,
    )
