# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class FiscalBookLine(models.Model):
    _name = "fiscal.book.line"
    _description = "Fiscal Book Line"
    _order = "rank asc"

    fb_id = fields.Many2one(
        comodel_name="fiscal.book",
        string="Fiscal Book",
        ondelete="cascade",
        required=True,
    )
    rank = fields.Integer(string="Operation N°", default=1)
    move_id = fields.Many2one(comodel_name="account.move", string="Invoice / Move", required=True)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
    partner_vat = fields.Char(string="RIF / CI")
    doc_date = fields.Date(string="Doc Date")
    invoice_number = fields.Char(string="Invoice Number")
    nro_ctrl = fields.Char(string="Control Number")
    doc_type = fields.Selection([("01", "Invoice"), ("02", "Debit Note"), ("03", "Credit Note")], string="Doc Type", default="01")
    
    total_amount = fields.Float(string="Total Amount")
    exempt_amount = fields.Float(string="Exempt Amount")
    base_general = fields.Float(string="Base General")
    tax_general = fields.Float(string="Tax General")
    base_reduced = fields.Float(string="Base Reduced")
    tax_reduced = fields.Float(string="Tax Reduced")
    base_additional = fields.Float(string="Base Additional")
    tax_additional = fields.Float(string="Tax Additional")
    vat_withheld = fields.Float(string="VAT Withheld")
    voucher_number = fields.Char(string="Withholding Voucher")
