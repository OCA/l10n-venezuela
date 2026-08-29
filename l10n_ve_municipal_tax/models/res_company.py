# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_municipal_name = fields.Char(
        string="Municipality",
        help="Municipality where the company pays the economic activities tax.",
    )
    l10n_ve_municipal_rate = fields.Float(
        string="Municipal tax rate (%)",
        help="Rate on gross income established by the applicable municipal ordinance.",
    )
    l10n_ve_municipal_minimum = fields.Monetary(
        string="Fixed monthly minimum",
        currency_field="currency_id",
        help="Fixed monthly minimum in the company currency.",
    )
    l10n_ve_municipal_minimum_mmv = fields.Float(
        string="Minimum (MMV units)",
        help="Monthly minimum expressed as a multiple of the highest-value "
        "currency rate.",
    )
    l10n_ve_municipal_tcmmv = fields.Float(
        string="TCMMV (VES)",
        help="Highest-value currency exchange rate published by the Venezuelan "
        "Central Bank, expressed in VES.",
    )
    l10n_ve_municipal_taxable_account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="l10n_ve_municipal_taxable_account_rel",
        column1="company_id",
        column2="account_id",
        string="Taxable income accounts",
        check_company=True,
        domain=[("internal_group", "=", "income")],
        help="Income accounts included in the municipal gross-income tax base.",
    )
    l10n_ve_municipal_expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Municipal tax expense account",
        check_company=True,
        domain=[("internal_group", "=", "expense")],
    )
    l10n_ve_municipal_payable_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Municipal tax payable account",
        check_company=True,
        domain=[("internal_group", "=", "liability")],
    )
    l10n_ve_municipal_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Municipal tax journal",
        check_company=True,
        domain=[("type", "=", "general")],
    )

    @api.constrains(
        "l10n_ve_municipal_rate",
        "l10n_ve_municipal_minimum",
        "l10n_ve_municipal_minimum_mmv",
        "l10n_ve_municipal_tcmmv",
    )
    def _check_l10n_ve_municipal_amounts(self):
        for company in self:
            if company.l10n_ve_municipal_rate < 0:
                raise ValidationError(
                    self.env._("The municipal tax rate cannot be negative.")
                )
            if company.l10n_ve_municipal_minimum < 0:
                raise ValidationError(
                    self.env._("The fixed monthly minimum cannot be negative.")
                )
            if company.l10n_ve_municipal_minimum_mmv < 0:
                raise ValidationError(self.env._("The MMV minimum cannot be negative."))
            if company.l10n_ve_municipal_tcmmv < 0:
                raise ValidationError(self.env._("The TCMMV cannot be negative."))

    @api.constrains(
        "l10n_ve_municipal_taxable_account_ids",
        "l10n_ve_municipal_expense_account_id",
        "l10n_ve_municipal_payable_account_id",
        "l10n_ve_municipal_journal_id",
    )
    def _check_l10n_ve_municipal_accounts(self):
        for company in self:
            invalid_accounts = company.l10n_ve_municipal_taxable_account_ids.filtered(
                lambda account: account.internal_group != "income"
            )
            if invalid_accounts:
                raise ValidationError(
                    self.env._("Municipal taxable accounts must be income accounts.")
                )
            if (
                company.l10n_ve_municipal_expense_account_id
                and company.l10n_ve_municipal_expense_account_id.internal_group
                != "expense"
            ):
                raise ValidationError(
                    self.env._(
                        "The municipal tax expense account must be an expense account."
                    )
                )
            if (
                company.l10n_ve_municipal_payable_account_id
                and company.l10n_ve_municipal_payable_account_id.internal_group
                != "liability"
            ):
                raise ValidationError(
                    self.env._(
                        "The municipal tax payable account must be a liability account."
                    )
                )
            configured_accounts = (
                company.l10n_ve_municipal_taxable_account_ids
                | company.l10n_ve_municipal_expense_account_id
                | company.l10n_ve_municipal_payable_account_id
            )
            compatible_accounts = configured_accounts.filtered_domain(
                configured_accounts._check_company_domain(company)
            )
            if configured_accounts != compatible_accounts:
                raise ValidationError(
                    self.env._("Municipal tax accounts must belong to the company.")
                )
            entry_accounts = (
                company.l10n_ve_municipal_expense_account_id
                | company.l10n_ve_municipal_payable_account_id
            )
            if any(
                account.currency_id and account.currency_id != company.currency_id
                for account in entry_accounts
            ):
                raise ValidationError(
                    self.env._(
                        "Municipal tax entry accounts cannot force another currency."
                    )
                )
            journal = company.l10n_ve_municipal_journal_id
            compatible_journal = journal.filtered_domain(
                journal._check_company_domain(company)
            )
            if journal and (journal.type != "general" or not compatible_journal):
                raise ValidationError(
                    self.env._(
                        "The municipal tax journal must be a compatible miscellaneous "
                        "journal."
                    )
                )
