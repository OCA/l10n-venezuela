# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    split_parent_id = fields.Many2one(
        comodel_name="account.move",
        string="Split Parent Invoice",
        copy=False,
    )
