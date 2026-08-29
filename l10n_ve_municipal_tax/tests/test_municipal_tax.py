# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestL10nVeMunicipalTax(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Municipal Test VE",
                "currency_id": cls.env.ref("base.USD").id,
                "country_id": cls.env.ref("base.ve").id,
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )

        account_model = cls.env["account.account"].with_company(cls.company)
        cls.income_account = account_model.create(
            {
                "name": "Taxable Sales",
                "code": "410101",
                "account_type": "income",
            }
        )
        cls.unselected_income_account = account_model.create(
            {
                "name": "Untaxed Other Income",
                "code": "430106",
                "account_type": "income_other",
            }
        )
        cls.counterpart_account = account_model.create(
            {
                "name": "Test Bank",
                "code": "101401",
                "account_type": "asset_current",
            }
        )
        cls.expense_account = account_model.create(
            {
                "name": "Municipal Tax Expense",
                "code": "660102",
                "account_type": "expense",
            }
        )
        cls.payable_account = account_model.create(
            {
                "name": "Municipal Tax Payable",
                "code": "210403",
                "account_type": "liability_current",
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Municipal Tax Test",
                "code": "MUNI",
                "type": "general",
                "company_id": cls.company.id,
            }
        )
        cls.company.write(
            {
                "l10n_ve_municipal_name": "Valencia",
                "l10n_ve_municipal_rate": 3.0,
                "l10n_ve_municipal_minimum": 10.0,
                "l10n_ve_municipal_taxable_account_ids": [
                    Command.set(cls.income_account.ids)
                ],
                "l10n_ve_municipal_expense_account_id": cls.expense_account.id,
                "l10n_ve_municipal_payable_account_id": cls.payable_account.id,
                "l10n_ve_municipal_journal_id": cls.journal.id,
            }
        )

        cls._create_move(1000.0, date(2025, 6, 15))
        cls._create_move(500.0, date(2025, 6, 20))
        cls._create_move(-100.0, date(2025, 6, 25))
        cls._create_move(
            300.0,
            date(2025, 6, 10),
            account=cls.unselected_income_account,
        )
        cls._create_move(800.0, date(2025, 6, 12), post=False)
        cls._create_move(900.0, date(2025, 5, 15))

    @classmethod
    def _create_move(cls, amount, move_date, account=None, post=True):
        credit, debit = (amount, 0.0) if amount >= 0 else (0.0, -amount)
        move = (
            cls.env["account.move"]
            .with_company(cls.company)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": cls.journal.id,
                    "date": move_date,
                    "line_ids": [
                        Command.create(
                            {
                                "name": "Test income",
                                "account_id": (account or cls.income_account).id,
                                "credit": credit,
                                "debit": debit,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Counterpart",
                                "account_id": cls.counterpart_account.id,
                                "credit": debit,
                                "debit": credit,
                            }
                        ),
                    ],
                }
            )
        )
        if post:
            move.action_post()
        return move

    def _create_wizard(self, year=2025, month="6"):
        return (
            self.env["l10n.ve.municipal.tax.wizard"]
            .with_company(self.company)
            .create(
                {
                    "company_id": self.company.id,
                    "year": year,
                    "month": month,
                }
            )
        )

    def _set_ves_rate(self, rate=None, rate_date=date(2025, 6, 30)):
        rate_model = self.env["res.currency.rate"].sudo()
        rate_model.search(
            [("currency_id", "in", (self.ves.id, self.company.currency_id.id))]
        ).unlink()
        if rate:
            rate_model.create(
                {
                    "currency_id": self.ves.id,
                    "name": rate_date,
                    "rate": rate,
                    "company_id": self.company.id,
                }
            )

    def test_compute_uses_only_selected_posted_accounts(self):
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.base_amount, 1400.0)
        self.assertEqual(wizard.computed_tax, 42.0)
        self.assertEqual(wizard.tax_amount, 42.0)

    def test_fixed_minimum_applies(self):
        self.company.l10n_ve_municipal_minimum = 100.0
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.tax_amount, 100.0)

    def test_mmv_minimum_applies(self):
        self._set_ves_rate(rate=36.0)
        self.company.write(
            {
                "l10n_ve_municipal_minimum": 0.0,
                "l10n_ve_municipal_minimum_mmv": 30.0,
                "l10n_ve_municipal_tcmmv": 120.0,
            }
        )
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.minimum_amount, 100.0)
        self.assertEqual(wizard.tax_amount, 100.0)

    def test_mmv_minimum_requires_tcmmv_and_ves_rate(self):
        self.company.l10n_ve_municipal_minimum_mmv = 30.0
        with self.assertRaises(UserError):
            self._create_wizard().action_compute()
        self.company.l10n_ve_municipal_tcmmv = 120.0
        self._set_ves_rate()
        with self.assertRaises(UserError):
            self._create_wizard().action_compute()

    def test_zero_sales_month_provisions_minimum(self):
        self.company.l10n_ve_municipal_minimum = 100.0
        action = self._create_wizard(month="7").action_generate_entry()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.line_ids.filtered("debit").debit, 100.0)

    def test_generate_draft_entry(self):
        action = self._create_wizard().action_generate_entry()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.journal_id, self.journal)
        self.assertEqual(move.date, date(2025, 6, 30))
        self.assertEqual(move.ref, "MUNI-2025-06")
        self.assertIn("Valencia", str(move.narration))
        debit_line = move.line_ids.filtered("debit")
        credit_line = move.line_ids.filtered("credit")
        self.assertEqual(debit_line.account_id, self.expense_account)
        self.assertEqual(credit_line.account_id, self.payable_account)
        self.assertEqual(debit_line.debit, 42.0)
        self.assertEqual(credit_line.credit, 42.0)

    def test_duplicate_period_is_blocked_until_entry_is_cancelled(self):
        action = self._create_wizard().action_generate_entry()
        move = self.env["account.move"].browse(action["res_id"])
        self.company.l10n_ve_municipal_name = "Naguanagua"
        move.date = date(2025, 7, 5)
        move.ref = "Edited reference"
        with self.assertRaises(UserError):
            self._create_wizard().action_generate_entry()
        move.button_cancel()
        replacement = self._create_wizard().action_generate_entry()
        self.assertNotEqual(replacement["res_id"], move.id)

    def test_positive_rate_and_taxable_accounts_are_required(self):
        self.company.l10n_ve_municipal_rate = 0.0
        with self.assertRaises(UserError):
            self._create_wizard().action_compute()
        self.company.l10n_ve_municipal_rate = 3.0
        self.company.l10n_ve_municipal_taxable_account_ids = False
        with self.assertRaises(UserError):
            self._create_wizard().action_compute()

    def test_parameters_cannot_be_negative(self):
        fields_to_check = (
            "l10n_ve_municipal_rate",
            "l10n_ve_municipal_minimum",
            "l10n_ve_municipal_minimum_mmv",
            "l10n_ve_municipal_tcmmv",
        )
        for field_name in fields_to_check:
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValidationError), self.env.cr.savepoint():
                    self.company.write({field_name: -1.0})

    def test_only_income_accounts_can_be_taxable(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.company.l10n_ve_municipal_taxable_account_ids = (
                self.counterpart_account
            )

    def test_venezuelan_fiscal_country_is_required(self):
        self.company.account_fiscal_country_id = self.env.ref("base.us")
        with self.assertRaises(UserError):
            self._create_wizard().action_compute()

    def test_company_isolation(self):
        other_company = self.env["res.company"].create(
            {
                "name": "Other Venezuelan Company",
                "currency_id": self.env.ref("base.USD").id,
                "country_id": self.env.ref("base.ve").id,
                "account_fiscal_country_id": self.env.ref("base.ve").id,
            }
        )
        self.env.user.company_ids |= other_company
        account_model = self.env["account.account"].with_company(other_company)
        other_income = account_model.create(
            {"name": "Other Sales", "code": "410101", "account_type": "income"}
        )
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.company.l10n_ve_municipal_taxable_account_ids = other_income
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.base_amount, 1400.0)

    def test_parent_company_accounts_are_valid_for_branch(self):
        branch = self.env["res.company"].create(
            {
                "name": "Venezuelan Branch",
                "parent_id": self.company.id,
                "country_id": self.env.ref("base.ve").id,
                "account_fiscal_country_id": self.env.ref("base.ve").id,
            }
        )
        branch.write(
            {
                "l10n_ve_municipal_taxable_account_ids": [
                    Command.set(self.income_account.ids)
                ],
                "l10n_ve_municipal_expense_account_id": self.expense_account.id,
                "l10n_ve_municipal_payable_account_id": self.payable_account.id,
                "l10n_ve_municipal_journal_id": self.journal.id,
            }
        )

    def test_entry_accounts_cannot_force_foreign_currency(self):
        foreign_expense = (
            self.env["account.account"]
            .with_company(self.company)
            .create(
                {
                    "name": "EUR Municipal Tax Expense",
                    "code": "660103",
                    "account_type": "expense",
                    "currency_id": self.env.ref("base.EUR").id,
                }
            )
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.company.l10n_ve_municipal_expense_account_id = foreign_expense

    def test_missing_entry_configuration_is_rejected(self):
        self.company.l10n_ve_municipal_journal_id = False
        with self.assertRaises(UserError):
            self._create_wizard().action_generate_entry()

    def test_ves_amount_requires_actual_rate(self):
        self._set_ves_rate()
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.amount_bs, 0.0)
        self._set_ves_rate(rate=36.0, rate_date=date(2025, 6, 1))
        self.env["res.currency.rate"].create(
            {
                "currency_id": self.ves.id,
                "name": date(2025, 6, 30),
                "rate": 1.0,
                "company_id": self.company.id,
            }
        )
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.amount_bs, 0.0)
        self._set_ves_rate(rate=36.0)
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.amount_bs, 1512.0)

    def test_only_accounting_managers_can_open_wizard(self):
        invoice_user = new_test_user(
            self.env,
            login="municipal_invoice_user",
            groups="account.group_account_invoice",
        )
        invoice_user.company_ids |= self.company
        invoice_user.company_id = self.company
        with self.assertRaises(AccessError):
            (
                self.env["l10n.ve.municipal.tax.wizard"]
                .with_user(invoice_user)
                .with_company(self.company)
                .create({"company_id": self.company.id, "year": 2025, "month": "6"})
            )
        manager_group = self.env.ref("account.group_account_manager")
        menu = self.env.ref("l10n_ve_municipal_tax.menu_l10n_ve_municipal_tax_wizard")
        action = self.env.ref(
            "l10n_ve_municipal_tax.action_l10n_ve_municipal_tax_wizard"
        )
        self.assertIn(manager_group, menu.group_ids)
        self.assertIn(manager_group, action.group_ids)
