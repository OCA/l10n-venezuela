# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError

# Official ISO codes for the bolívar. SENIAT books are in current VES;
# VEF/VED/VEB are obsolete labels, not a BCV pair (BCV never quotes VEF→VES).
_L10N_VE_BOLIVAR = frozenset({"VES", "VEF", "VED", "VEB"})


class L10nUt(models.Model):
    _name = "l10n.ut"
    _description = "Tax Unit (Unidad Tributaria)"
    _order = "date desc"

    name = fields.Char(
        string="Reference number",
        required=True,
        help="Reference number under the law",
    )
    date = fields.Date(
        required=True,
        help="Date on which goes into effect the new Tax Unit",
    )
    amount = fields.Float(
        digits="Account",
        required=True,
        help="Amount of the tax unit in Bs",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        help="User who registered the record",
    )

    @api.model
    def get_amount_ut(self, date=False):
        """Return the value of the tax unit for the specified date or current date."""
        target_date = date or fields.Date.context_today(self)
        ut_record = self.search(
            [("date", "<=", target_date)], order="date desc", limit=1
        )
        return ut_record.amount if ut_record else 0.0

    @api.model
    def compute(self, from_amount, date=False):
        """Return the number of tributary units depending on an amount of money."""
        ut = self.get_amount_ut(date=date)
        return (from_amount / ut) if ut else 0.0

    @api.model
    def compute_ut_to_money(self, amount_ut, date=False):
        """Transforms from tax units into money."""
        ut = self.get_amount_ut(date=date)
        return (amount_ut * ut) if ut else 0.0

    @api.model
    def _l10n_ve_is_bolivar(self, currency):
        return bool(currency) and currency.name in _L10N_VE_BOLIVAR

    @api.model
    def get_ves_currency(self):
        """Return the VES currency or the company currency as fallback."""
        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        return ves or self.env.company.currency_id

    @api.model
    def _l10n_ve_has_rate(self, currency, company, date):
        if not currency or currency == company.currency_id:
            return True
        return bool(
            self.env["res.currency.rate"].search_count(
                [
                    ("currency_id", "=", currency.id),
                    ("name", "<=", date),
                    "|",
                    ("company_id", "=", company.id),
                    ("company_id", "=", False),
                ]
            )
        )

    @api.model
    def amount_to_ves(self, amount, from_currency, date=False, company=False):
        """Convert an amount to bolívares using the rate of the given date."""
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        ves = self.get_ves_currency()
        if (
            not amount
            or not from_currency
            or from_currency == ves
            or self._l10n_ve_is_bolivar(from_currency)
        ):
            return amount
        if not self._l10n_ve_has_rate(
            from_currency, company, date
        ) or not self._l10n_ve_has_rate(ves, company, date):
            raise UserError(
                self.env._(
                    "There is no exchange rate to convert %(currency)s to VES "
                    "on %(date)s. Load the BCV rate before generating fiscal "
                    "documents.",
                    currency=from_currency.name,
                    date=date,
                )
            )
        return from_currency._convert(amount, ves, company, date)
