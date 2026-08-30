# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class CustomsDeclaration(models.Model):
    _name = "customs.declaration"
    _description = "Customs Declaration (DUA / DVI)"

    name = fields.Char(string="Declaration Number (DUA)", required=True)
    date = fields.Date(
        string="Declaration Date", required=True, default=fields.Date.context_today
    )
    customs_code = fields.Char(string="Customs Office Code")
    move_ids = fields.Many2many(comodel_name="account.move", string="Invoices")
