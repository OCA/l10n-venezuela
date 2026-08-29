# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class FiscalBookTaxes(models.Model):
    _name = "fiscal.book.taxes"
    _description = "Fiscal Book Tax Summary"

    fb_id = fields.Many2one(comodel_name="fiscal.book", string="Fiscal Book", ondelete="cascade")
    base_amount = fields.Float(string="Base Amount")
    tax_amount = fields.Float(string="Tax Amount")
    appl_type = fields.Selection([
        ("exento", "Exempt"),
        ("general", "General"),
        ("reducido", "Reduced"),
        ("adicional", "Additional"),
    ], string="Type")
