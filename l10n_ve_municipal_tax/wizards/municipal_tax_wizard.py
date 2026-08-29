# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

MONTH_SELECTION = [
    ("1", "January"),
    ("2", "February"),
    ("3", "March"),
    ("4", "April"),
    ("5", "May"),
    ("6", "June"),
    ("7", "July"),
    ("8", "August"),
    ("9", "September"),
    ("10", "October"),
    ("11", "November"),
    ("12", "December"),
]


class L10nVeMunicipalTaxWizard(models.TransientModel):
    _name = "l10n.ve.municipal.tax.wizard"
    _description = "Venezuelan Municipal Tax"

    @api.model
    def _default_period_date(self):
        return fields.Date.context_today(self).replace(day=1) - relativedelta(days=1)

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    year = fields.Integer(
        required=True,
        default=lambda self: self._default_period_date().year,
    )
    month = fields.Selection(
        selection=MONTH_SELECTION,
        required=True,
        default=lambda self: str(self._default_period_date().month),
    )
    municipality = fields.Char(related="company_id.l10n_ve_municipal_name")
    rate = fields.Float(related="company_id.l10n_ve_municipal_rate")
    minimum_mmv = fields.Float(related="company_id.l10n_ve_municipal_minimum_mmv")
    tcmmv = fields.Float(related="company_id.l10n_ve_municipal_tcmmv")
    minimum_amount = fields.Monetary(readonly=True)
    base_amount = fields.Monetary(readonly=True)
    computed_tax = fields.Monetary(readonly=True)
    tax_amount = fields.Monetary(readonly=True)
    ves_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_ves_currency",
    )
    amount_bs = fields.Monetary(
        string="Amount in VES",
        currency_field="ves_currency_id",
        readonly=True,
    )
    is_computed = fields.Boolean(readonly=True)

    def _compute_ves_currency(self):
        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        for wizard in self:
            wizard.ves_currency_id = ves

    def _get_period_dates(self):
        self.ensure_one()
        if not 2000 <= self.year <= 2100:
            raise UserError(self.env._("The year %s is not valid.", self.year))
        date_from = date(self.year, int(self.month), 1)
        return date_from, date_from + relativedelta(months=1, days=-1)

    def _get_move_ref(self):
        self.ensure_one()
        return f"MUNI-{self.year:04d}-{int(self.month):02d}"

    def _get_move_line_label(self):
        self.ensure_one()
        municipality = self.company_id.l10n_ve_municipal_name or ""
        period = f"{int(self.month):02d}/{self.year:04d}"
        return f"Municipal tax {period} {municipality}".strip()

    def _validate_company(self):
        self.ensure_one()
        company = self.company_id
        if company.account_fiscal_country_id.code != "VE":
            raise UserError(
                self.env._(
                    "The fiscal country of company %s must be Venezuela.",
                    company.display_name,
                )
            )
        if company.l10n_ve_municipal_rate <= 0:
            raise UserError(
                self.env._(
                    "Configure a positive municipal tax rate for company %s.",
                    company.display_name,
                )
            )
        if not company.l10n_ve_municipal_taxable_account_ids:
            raise UserError(
                self.env._(
                    "Configure at least one municipal taxable income account "
                    "for company %s.",
                    company.display_name,
                )
            )

    def _has_ves_rate(self, date_to):
        self.ensure_one()
        company = self.company_id
        ves = self.ves_currency_id
        if not ves:
            return False
        has_dated_rate = self.env["res.currency.rate"].search_count(
            [
                ("currency_id", "=", ves.id),
                ("company_id", "in", (company.root_id.id, False)),
                ("name", "<=", date_to),
            ],
            limit=1,
        )
        return bool(has_dated_rate) and ves._get_rates(company, date_to)[ves.id] != 1.0

    def _compute_municipal_amounts(self):
        for wizard in self:
            wizard._validate_company()
            company = wizard.company_id
            date_from, date_to = wizard._get_period_dates()
            currency = company.currency_id
            income_lines = self.env["account.move.line"].search(
                [
                    ("company_id", "=", company.id),
                    ("parent_state", "=", "posted"),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                    (
                        "account_id",
                        "in",
                        company.l10n_ve_municipal_taxable_account_ids.ids,
                    ),
                ]
            )
            base = currency.round(
                sum(income_lines.mapped("credit")) - sum(income_lines.mapped("debit"))
            )
            computed = currency.round(base * company.l10n_ve_municipal_rate / 100.0)
            ves = wizard.ves_currency_id
            has_ves_rate = wizard._has_ves_rate(date_to)
            minimum = company.l10n_ve_municipal_minimum
            if company.l10n_ve_municipal_minimum_mmv:
                if not company.l10n_ve_municipal_tcmmv:
                    raise UserError(
                        self.env._(
                            "Configure the TCMMV before using an MMV-based minimum."
                        )
                    )
                minimum_bs = (
                    company.l10n_ve_municipal_minimum_mmv
                    * company.l10n_ve_municipal_tcmmv
                )
                if currency == ves:
                    minimum_mmv = minimum_bs
                elif has_ves_rate:
                    minimum_mmv = ves._convert(minimum_bs, currency, company, date_to)
                else:
                    raise UserError(
                        self.env._(
                            "No actual VES rate is available through %s.", date_to
                        )
                    )
                minimum = max(minimum, currency.round(minimum_mmv))
            amount = max(computed, minimum)
            amount_bs = 0.0
            if currency == ves:
                amount_bs = amount
            elif has_ves_rate:
                amount_bs = currency._convert(amount, ves, company, date_to)
            wizard.write(
                {
                    "base_amount": base,
                    "computed_tax": computed,
                    "minimum_amount": minimum,
                    "tax_amount": amount,
                    "amount_bs": amount_bs,
                    "is_computed": True,
                }
            )

    def _reopen_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Municipal Tax (VE)"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_compute(self):
        self.ensure_one()
        self._compute_municipal_amounts()
        return self._reopen_wizard()

    def action_generate_entry(self):
        self.ensure_one()
        self._compute_municipal_amounts()
        company = self.company_id
        missing = []
        if not company.l10n_ve_municipal_expense_account_id:
            missing.append(self.env._("expense account"))
        if not company.l10n_ve_municipal_payable_account_id:
            missing.append(self.env._("payable account"))
        if not company.l10n_ve_municipal_journal_id:
            missing.append(self.env._("miscellaneous journal"))
        if missing:
            raise UserError(
                self.env._("Configure the municipal tax %s.", ", ".join(missing))
            )
        if company.currency_id.compare_amounts(self.tax_amount, 0.0) <= 0:
            raise UserError(self.env._("The municipal tax amount is zero."))
        date_to = self._get_period_dates()[1]
        ref = self._get_move_ref()
        label = self._get_move_line_label()
        existing = self.env["account.move"].search(
            [
                ("company_id", "=", company.id),
                ("l10n_ve_municipal_tax_period", "=", date_to),
                ("state", "!=", "cancel"),
            ],
            limit=1,
        )
        if existing:
            raise UserError(
                self.env._(
                    "Entry %(move)s already exists for this period with reference "
                    "%(ref)s.",
                    move=existing.display_name,
                    ref=ref,
                )
            )
        move = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": company.l10n_ve_municipal_journal_id.id,
                    "date": date_to,
                    "ref": ref,
                    "narration": label,
                    "l10n_ve_municipal_tax_period": date_to,
                    "line_ids": [
                        Command.create(
                            {
                                "name": label,
                                "account_id": (
                                    company.l10n_ve_municipal_expense_account_id.id
                                ),
                                "debit": self.tax_amount,
                                "credit": 0.0,
                            }
                        ),
                        Command.create(
                            {
                                "name": label,
                                "account_id": (
                                    company.l10n_ve_municipal_payable_account_id.id
                                ),
                                "debit": 0.0,
                                "credit": self.tax_amount,
                            }
                        ),
                    ],
                }
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Municipal Tax"),
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }
