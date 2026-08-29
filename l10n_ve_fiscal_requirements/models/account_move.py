# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    nro_ctrl = fields.Char(
        string="Control Number",
        size=32,
        copy=False,
        help="Pre-printed invoice control number required by SENIAT",
    )
    sin_cred = fields.Boolean(
        string="Exclude from Fiscal Book",
        copy=False,
        help="Set to true if invoice is exempt or excluded from Venezuelan fiscal book",
    )
    date_document = fields.Date(
        string="Document Date",
        copy=False,
        help="Administrative date printed on the physical vendor bill for fiscal books",
    )
    invoice_printer = fields.Char(
        string="Fiscal Printer Invoice Number",
        copy=False,
        help="Invoice number emitted by the fiscal printer",
    )
    fiscal_printer = fields.Char(
        string="Fiscal Printer Serial",
        copy=False,
        help="Serial number of the fiscal printer",
    )
    z_report = fields.Char(
        string="Report Z",
        copy=False,
        help="Z Report number emitted by fiscal printer",
    )
    supplier_invoice_number = fields.Char(
        string="Supplier Invoice Number",
        copy=False,
        help="Original invoice number from supplier",
    )

    @api.constrains("nro_ctrl", "partner_id", "move_type")
    def _check_unique_nro_ctrl(self):
        for move in self:
            if move.is_invoice() and move.move_type in ["in_invoice", "in_refund"] and move.nro_ctrl:
                domain = [
                    ("id", "!=", move.id),
                    ("partner_id", "=", move.partner_id.id),
                    ("move_type", "=", move.move_type),
                    ("nro_ctrl", "=", move.nro_ctrl.strip()),
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        _("The Control Number %s has already been registered for partner %s.")
                        % (move.nro_ctrl, move.partner_id.display_name)
                    )

    @api.onchange("invoice_date")
    def _onchange_invoice_date_ve(self):
        if self.invoice_date and not self.date_document:
            self.date_document = self.invoice_date
