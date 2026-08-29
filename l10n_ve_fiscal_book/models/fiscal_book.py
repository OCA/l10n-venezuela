# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FiscalBook(models.Model):
    _name = "fiscal.book"
    _description = "Venezuelan Fiscal Book"
    _order = "date_start desc, type"

    name = fields.Char(string="Description", required=True)
    type = fields.Selection(
        selection=[("purchase", "Purchase Book"), ("sale", "Sale Book")],
        string="Book Type",
        required=True,
        default="purchase",
    )
    state = fields.Selection(
        selection=[("draft", "Draft"), ("confirmed", "Confirmed"), ("done", "Posted"), ("cancel", "Cancelled")],
        string="State",
        default="draft",
    )
    date_start = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    date_end = fields.Date(string="End Date", required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        comodel_name="fiscal.book.line",
        inverse_name="fb_id",
        string="Fiscal Book Lines",
        copy=True,
    )
    
    # Totals
    total_amount = fields.Float(string="Total Operations", compute="_compute_book_totals", store=True)
    total_exempt = fields.Float(string="Total Exempt", compute="_compute_book_totals", store=True)
    total_base_general = fields.Float(string="Base General (16%)", compute="_compute_book_totals", store=True)
    total_tax_general = fields.Float(string="Tax General (16%)", compute="_compute_book_totals", store=True)
    total_base_reduced = fields.Float(string="Base Reduced (8%)", compute="_compute_book_totals", store=True)
    total_tax_reduced = fields.Float(string="Tax Reduced (8%)", compute="_compute_book_totals", store=True)
    total_base_additional = fields.Float(string="Base Additional (31%)", compute="_compute_book_totals", store=True)
    total_tax_additional = fields.Float(string="Tax Additional (31%)", compute="_compute_book_totals", store=True)
    total_vat_withheld = fields.Float(string="Total VAT Withheld", compute="_compute_book_totals", store=True)

    @api.depends("line_ids.total_amount", "line_ids.exempt_amount", "line_ids.base_general", "line_ids.tax_general", "line_ids.vat_withheld")
    def _compute_book_totals(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("total_amount"))
            rec.total_exempt = sum(rec.line_ids.mapped("exempt_amount"))
            rec.total_base_general = sum(rec.line_ids.mapped("base_general"))
            rec.total_tax_general = sum(rec.line_ids.mapped("tax_general"))
            rec.total_base_reduced = sum(rec.line_ids.mapped("base_reduced"))
            rec.total_tax_reduced = sum(rec.line_ids.mapped("tax_reduced"))
            rec.total_base_additional = sum(rec.line_ids.mapped("base_additional"))
            rec.total_tax_additional = sum(rec.line_ids.mapped("tax_additional"))
            rec.total_vat_withheld = sum(rec.line_ids.mapped("vat_withheld"))

    def action_update_book(self):
        self.ensure_one()
        self.line_ids.unlink()
        
        move_types = ["in_invoice", "in_refund"] if self.type == "purchase" else ["out_invoice", "out_refund"]
        moves = self.env["account.move"].search([
            ("date", ">=", self.date_start),
            ("date", "<=", self.date_end),
            ("state", "=", "posted"),
            ("move_type", "in", move_types),
            ("company_id", "=", self.company_id.id),
            ("sin_cred", "=", False),
        ], order="invoice_date asc, name asc")

        rank = 1
        lines = []
        for m in moves:
            sign = -1 if m.move_type in ["in_refund", "out_refund"] else 1
            tot = abs(m.amount_total) * sign
            
            base_gen = 0.0
            tax_gen = 0.0
            base_red = 0.0
            tax_red = 0.0
            base_add = 0.0
            tax_add = 0.0
            exempt = 0.0
            
            for line in m.line_ids.filtered(lambda l: l.tax_line_id):
                t = line.tax_line_id
                t_amt = abs(line.balance) * sign
                t_base = (line.tax_base_amount or 0.0) * sign
                if t.appl_type == "general":
                    base_gen += t_base
                    tax_gen += t_amt
                elif t.appl_type == "reducido":
                    base_red += t_base
                    tax_red += t_amt
                elif t.appl_type == "adicional":
                    base_add += t_base
                    tax_add += t_amt
                elif t.appl_type in ["exento", "sdcf"]:
                    exempt += t_base
            
            # Check lines without taxes (exempt lines)
            untaxed_exempt = sum(m.invoice_line_ids.filtered(lambda l: not l.tax_ids).mapped("price_subtotal")) * sign
            exempt += untaxed_exempt

            wh_amt = 0.0
            wh_num = ""
            if m.wh_iva_id:
                wh_amt = m.wh_iva_id.total_ret_amount
                wh_num = m.wh_iva_id.name

            lines.append((0, 0, {
                "rank": rank,
                "move_id": m.id,
                "partner_id": m.partner_id.id,
                "partner_vat": m.partner_id.vat or "",
                "doc_date": m.invoice_date or m.date,
                "invoice_number": m.supplier_invoice_number or m.name,
                "nro_ctrl": m.nro_ctrl or "",
                "doc_type": "03" if "refund" in m.move_type else "01",
                "total_amount": tot,
                "exempt_amount": exempt,
                "base_general": base_gen,
                "tax_general": tax_gen,
                "base_reduced": base_red,
                "tax_reduced": tax_red,
                "base_additional": base_add,
                "tax_additional": tax_add,
                "vat_withheld": wh_amt,
                "voucher_number": wh_num,
            }))
            rank += 1

        self.write({"line_ids": lines})
        return True

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_done(self):
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})
