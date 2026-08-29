# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class VatWriteOff(models.Model):
    _name = "vat.write.off"
    _description = "VAT Write Off"

    name = fields.Char(string="Reference", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    amount = fields.Float(string="Amount to Write Off", required=True)
    reason = fields.Text(string="Reason")
