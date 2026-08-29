# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountWhIva(models.Model):
    _name = "account.wh.iva"
    _description = "VAT Withholding Voucher"
    _order = "date desc, name desc"

    name = fields.Char(
        string="Voucher Number",
        required=True,
        copy=False,
        default="/",
        help="Correlative number of VAT Withholding Voucher (YYYYMMXXXXXXXX)",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("done", "Posted"),
            ("cancel", "Cancelled"),
        ],
        string="State",
        default="draft",
        tracking=True,
    )
    type = fields.Selection(
        selection=[
            ("in_invoice", "Vendor Bill"),
            ("out_invoice", "Customer Invoice"),
            ("in_refund", "Vendor Refund"),
            ("out_refund", "Customer Refund"),
        ],
        string="Type",
        default="in_invoice",
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        required=True,
        default=lambda self: self.env.company.wh_iva_journal_id or self.env["account.journal"].search([("type", "=", "general")], limit=1),
    )
    date = fields.Date(
        string="Date of Voucher",
        required=True,
        default=fields.Date.context_today,
    )
    period_date = fields.Date(
        string="Fiscal Period Date",
        default=fields.Date.context_today,
        help="Date used to compute the tax period (month/year)",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Accounting Entry",
        copy=False,
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="account.wh.iva.line",
        inverse_name="wh_iva_id",
        string="Withholding Lines",
        copy=True,
    )
    total_tax_amount = fields.Monetary(
        string="Total Base Tax",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_ret_amount = fields.Monetary(
        string="Total Retained Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )

    @api.depends("line_ids.tax_amount", "line_ids.amount_ret")
    def _compute_totals(self):
        for rec in self:
            rec.total_tax_amount = sum(rec.line_ids.mapped("tax_amount"))
            rec.total_ret_amount = sum(rec.line_ids.mapped("amount_ret"))

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Cannot confirm voucher without lines."))
            if rec.name == "/" or not rec.name:
                date_str = (rec.date or fields.Date.today()).strftime("%Y%m")
                seq = self.env["ir.sequence"].next_by_code("account.wh.iva") or "00000001"
                rec.name = f"{date_str}{seq}"
            rec.write({"state": "confirmed"})

    def action_done(self):
        for rec in self:
            # Generate accounting entry if vendor voucher
            if rec.type in ["in_invoice", "in_refund"] and not rec.move_id:
                partner_acc = rec.partner_id.property_account_payable_id.id
                wh_acc = rec.company_id.wh_iva_account_id.id
                if not wh_acc:
                    raise UserError(_("Please configure default VAT Withholding Account in Company Settings."))
                
                amount = rec.total_ret_amount
                lines = [
                    (0, 0, {
                        "name": _("VAT Retention %s") % rec.name,
                        "partner_id": rec.partner_id.id,
                        "account_id": partner_acc,
                        "debit": amount if rec.type == "in_invoice" else 0.0,
                        "credit": amount if rec.type == "in_refund" else 0.0,
                    }),
                    (0, 0, {
                        "name": _("VAT Retention %s") % rec.name,
                        "partner_id": rec.partner_id.id,
                        "account_id": wh_acc,
                        "debit": amount if rec.type == "in_refund" else 0.0,
                        "credit": amount if rec.type == "in_invoice" else 0.0,
                    }),
                ]
                move = self.env["account.move"].create({
                    "journal_id": rec.journal_id.id,
                    "date": rec.date,
                    "ref": rec.name,
                    "move_type": "entry",
                    "line_ids": lines,
                })
                move.action_post()
                rec.move_id = move.id
            rec.write({"state": "done"})

    def action_cancel(self):
        for rec in self:
            if rec.move_id:
                rec.move_id.button_cancel()
            rec.write({"state": "cancel"})

    def action_draft(self):
        for rec in self:
            rec.write({"state": "draft"})
