# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCurrency(models.Model):
    _name = "res.currency"
    _inherit = ["res.currency", "mail.thread", "mail.activity.mixin"]
