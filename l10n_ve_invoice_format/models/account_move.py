# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_bs_amounts(self):
        """Return document totals in the configured bolivar currency."""
        self.ensure_one()
        if not (
            (self.country_code == "VE" or self.l10n_ve_fiscal_data_locked)
            and self.is_sale_document(include_receipts=True)
        ):
            return {}
        bs_currency = self.company_id.l10n_ve_bs_currency_id
        if not bs_currency or bs_currency == self.currency_id:
            return {}
        conversion_date = (
            self.invoice_date or self.date or fields.Date.context_today(self)
        )
        company = self.company_id
        has_rate = (
            self.env["res.currency.rate"]
            .sudo()
            .search_count(
                [
                    ("currency_id", "=", bs_currency.id),
                    ("company_id", "in", (False, company.root_id.id)),
                ],
                limit=1,
            )
        )
        if not has_rate:
            return {}
        rate = self.currency_id._convert(
            1.0, bs_currency, company, conversion_date, round=False
        )
        if not rate:
            return {}

        def to_bs(amount):
            return self.currency_id._convert(
                amount, bs_currency, company, conversion_date
            )

        total = to_bs(self.amount_total)
        residual = to_bs(self.amount_residual)
        return {
            "currency": bs_currency,
            "rate": rate,
            "date": conversion_date,
            "untaxed": to_bs(self.amount_untaxed),
            "tax": to_bs(self.amount_tax),
            "total": total,
            "residual": residual,
            "show_residual": bool(
                bs_currency.compare_amounts(residual, total)
                and bs_currency.compare_amounts(residual, 0.0)
            ),
        }

    def _l10n_ve_legal_datetime(self):
        """Return the legal document date without inventing an emission time."""
        self.ensure_one()
        if not self.invoice_date:
            return ""
        legal_date = self.invoice_date.strftime("%d-%m-%Y")
        emission_time = self._l10n_ve_emission_time()
        return f"{legal_date} {emission_time}" if emission_time else legal_date

    def _l10n_ve_emission_time(self):
        """Return a known legal emission time, or let connectors override it."""
        self.ensure_one()
        return ""
