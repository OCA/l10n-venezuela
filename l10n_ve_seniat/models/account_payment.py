from odoo.tools.float_utils import float_round
from odoo import api, fields, models, Command


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        copy=False,
    )
