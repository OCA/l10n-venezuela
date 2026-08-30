# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_printer_name = fields.Char(string="Authorized Printer Name")
    l10n_ve_printer_vat = fields.Char(string="Authorized Printer VAT")
    l10n_ve_printer_auth_number = fields.Char(
        string="Authorized Printer Resolution Number",
        help="Number of the SENIAT resolution that authorizes the printer.",
    )
    l10n_ve_printer_auth_date = fields.Date(string="Authorized Printer Resolution Date")
    l10n_ve_control_range_from = fields.Char(string="Control Number Range From")
    l10n_ve_control_range_to = fields.Char(string="Control Number Range To")
    l10n_ve_bs_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Bolivar Reference Currency",
        default=lambda self: self._l10n_ve_default_bs_currency(),
        help="Currency used to show the bolivar equivalent on the invoice. Leave "
        "empty to hide the bolivar totals.",
    )
    l10n_ve_show_line_tax_detail = fields.Boolean(
        string="Show Untaxed and Tax Amounts on Invoice Lines",
        default=True,
        help="Add untaxed and tax amount columns to customer fiscal documents.",
    )

    def _l10n_ve_default_bs_currency(self):
        return (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
