# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ve_bridge_url = fields.Char(
        string="Fiscal Printer Bridge URL",
        help=(
            "Local bridge on the point of sale computer, for example "
            "http://localhost:5001. Leave empty to disable fiscal printing."
        ),
    )
    l10n_ve_bridge_token = fields.Char(
        string="Fiscal Printer Bridge Token",
        copy=False,
        help="Shared token expected by the local fiscal printer bridge.",
    )
    l10n_ve_machine_serial = fields.Char(
        string="Fiscal Machine Serial",
        copy=False,
        help="Serial number of the fiscal machine connected to this point of sale.",
    )
    l10n_ve_default_payment_code = fields.Char(
        string="Default Fiscal Payment Code",
        default="01",
        help=(
            "Fiscal machine payment slot used for backend invoices, where no "
            "point of sale payment lines are available."
        ),
    )

    def l10n_ve_get_ves_rate(self):
        """Return VES per company-currency unit at today's rate."""
        self.ensure_one()
        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not ves:
            return 0.0
        company = self.company_id
        today = fields.Date.context_today(self)
        if ves != company.currency_id and not self.env[
            "res.currency.rate"
        ].search_count(
            [
                ("currency_id", "=", ves.id),
                ("company_id", "in", (False, company.id)),
                ("name", "<=", today),
            ],
            limit=1,
        ):
            # Odoo otherwise falls back to an implicit 1.0 exchange rate.
            return 0.0
        return company.currency_id._convert(1.0, ves, company, today, round=False)
