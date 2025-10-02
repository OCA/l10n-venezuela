from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )

    def button_draft(self):
        if self.country_code != self.env.ref("base.ve").code:
            return super().button_draft()

        if self.move_type == "entry":
            return super().button_draft()

        raise ValidationError(
            """You cannot reset to draft an invoice in the Venezuelan localization.
Please create a credit note instead.
        """
        )
