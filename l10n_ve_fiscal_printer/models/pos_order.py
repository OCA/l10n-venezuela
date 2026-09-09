# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_ve_fiscal_number = fields.Char(
        string="Fiscal Document Number", copy=False, readonly=True
    )
    l10n_ve_fiscal_machine_serial = fields.Char(
        string="Fiscal Machine Serial", copy=False, readonly=True
    )
    l10n_ve_fiscal_date = fields.Char(
        string="Fiscal Date and Time", copy=False, readonly=True
    )
    l10n_ve_fiscal_doc_type = fields.Selection(
        [("invoice", "Invoice"), ("credit_note", "Credit Note")],
        string="Fiscal Document Type",
        copy=False,
        readonly=True,
    )
    l10n_ve_fiscal_event = fields.Selection(
        [
            ("adopt_uuid", "Number recovered by UUID"),
            ("adopt_manual", "Number recovered by cashier confirmation"),
            ("reprint", "Reprinted after an uncertain attempt"),
        ],
        string="Fiscal Printing Incident",
        copy=False,
        readonly=True,
    )
    l10n_ve_fiscal_event_note = fields.Text(
        string="Fiscal Printing Incident Log", copy=False, readonly=True
    )

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if len(self) != 1:
            fiscal_orders = self.filtered("l10n_ve_fiscal_number")
            if fiscal_orders:
                raise UserError(
                    self.env._(
                        "Orders %(orders)s already have fiscal machine documents "
                        "and must be invoiced separately.",
                        orders=", ".join(fiscal_orders.mapped("name")),
                    )
                )
            return vals
        if self.l10n_ve_fiscal_number:
            vals.update(
                {
                    "ref": self.env._(
                        "Fiscal machine %(serial)s number %(number)s",
                        serial=self.l10n_ve_fiscal_machine_serial or "",
                        number=self.l10n_ve_fiscal_number,
                    ),
                    "l10n_ve_fiscal_number": self.l10n_ve_fiscal_number,
                    "l10n_ve_fiscal_machine_serial": (
                        self.l10n_ve_fiscal_machine_serial
                    ),
                    "l10n_ve_fiscal_date": self.l10n_ve_fiscal_date,
                    "l10n_ve_fiscal_doc_type": self.l10n_ve_fiscal_doc_type,
                }
            )
        return vals
