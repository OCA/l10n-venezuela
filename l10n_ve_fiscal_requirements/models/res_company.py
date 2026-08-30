# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    jour_id = fields.Many2one(
        comodel_name="account.journal",
        string="Damaged Invoices Journal",
        help="Default journal for damaged/void invoices",
    )
    acc_id = fields.Many2one(
        comodel_name="account.account",
        string="Damaged Invoices Account",
        help="Default account used for damaged/void invoices",
    )
    printer_fiscal = fields.Boolean(
        string="Manages Fiscal Printer",
        help="Indicates that the company operates a fiscal printer",
    )
