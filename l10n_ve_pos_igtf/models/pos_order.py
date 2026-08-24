from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float(string="IGTF")
    bi_igtf = fields.Float(string="Base IGTF")
