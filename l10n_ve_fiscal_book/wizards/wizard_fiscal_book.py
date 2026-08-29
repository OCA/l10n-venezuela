# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class WizardFiscalBook(models.TransientModel):
    _name = "wizard.fiscal.book"
    _description = "Fiscal Book Generator Wizard"

    type = fields.Selection([("purchase", "Purchase Book"), ("sale", "Sale Book")], string="Book Type", required=True, default="purchase")
    date_start = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    date_end = fields.Date(string="End Date", required=True, default=fields.Date.context_today)

    def action_create_book(self):
        self.ensure_one()
        book_title = f"{'Libro de Compras' if self.type == 'purchase' else 'Libro de Ventas'} - {self.date_start.strftime('%m/%Y')}"
        book = self.env["fiscal.book"].create({
            "name": book_title,
            "type": self.type,
            "date_start": self.date_start,
            "date_end": self.date_end,
        })
        book.action_update_book()
        return {
            "type": "ir.actions.act_window",
            "res_model": "fiscal.book",
            "res_id": book.id,
            "view_mode": "form",
            "target": "current",
        }
