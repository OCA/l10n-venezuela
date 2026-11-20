# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


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
        cls.withholding_account = account_model.create(
            {
                "name": "Municipal Withholdings Suffered",
                "code": "113105",
                "account_type": "asset_current",
            }
        )
        # Core base data ships no Venezuelan states, so create test ones.
        state_model = cls.env["res.country.state"]
        cls.ve_state = state_model.create(
            {
                "name": "Test State One",
                "code": "T1",
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.other_ve_state = state_model.create(
            {
                "name": "Test State Two",
                "code": "T2",
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.municipality = cls.env["l10n.ve.municipality"].create(
            {"name": "Valencia", "state_id": cls.ve_state.id}
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
                "l10n_ve_municipality_id": cls.municipality.id,
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
        self.company.l10n_ve_municipality_id = self.env["l10n.ve.municipality"].create(
            {"name": "Naguanagua", "state_id": self.ve_state.id}
        )
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
        with self.assertRaises(UserError):
            self._create_wizard().action_generate_entry()
        provision_domain = [
            ("company_id", "=", self.company.id),
            ("l10n_ve_municipal_tax_period", "!=", False),
        ]
        self.assertFalse(self.env["account.move"].search(provision_domain))
        self.company.account_fiscal_country_id = self.env.ref("base.ve")
        self._create_wizard().action_generate_entry()
        self.assertEqual(self.env["account.move"].search_count(provision_domain), 1)

    def test_minimum_is_greater_of_fixed_and_mmv(self):
        self._set_ves_rate(rate=36.0)
        self.company.write(
            {
                "l10n_ve_municipal_minimum": 150.0,
                "l10n_ve_municipal_minimum_mmv": 30.0,
                "l10n_ve_municipal_tcmmv": 120.0,
            }
        )
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.minimum_amount, 150.0)
        self.assertEqual(wizard.tax_amount, 150.0)

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

    def test_wizard_reachable_from_accounting_menu(self):
        menu = self.env.ref(
            "l10n_ve_municipal_tax.menu_l10n_ve_municipal_tax_wizard_entries"
        )
        action = self.env.ref(
            "l10n_ve_municipal_tax.action_l10n_ve_municipal_tax_wizard"
        )
        self.assertEqual(menu.parent_id, self.env.ref("account.menu_finance_entries"))
        self.assertEqual(menu.action, action)
        self.assertEqual(menu.group_ids, self.env.ref("account.group_account_manager"))

    def _set_withholdings(self, amount, move_date=date(2025, 6, 18)):
        self.company.l10n_ve_municipal_withholding_account_id = self.withholding_account
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": self.journal.id,
                    "date": move_date,
                    "line_ids": [
                        Command.create(
                            {
                                "name": "Withheld by customer",
                                "account_id": self.withholding_account.id,
                                "debit": amount,
                                "credit": 0.0,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Customer collection",
                                "account_id": self.counterpart_account.id,
                                "debit": 0.0,
                                "credit": amount,
                            }
                        ),
                    ],
                }
            )
        )
        move.action_post()
        return move

    def _withholding_balance(self):
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.withholding_account.id),
                ("parent_state", "=", "posted"),
            ]
        )
        return sum(lines.mapped("balance"))

    def test_municipality_unique_per_state(self):
        municipality_model = self.env["l10n.ve.municipality"]
        municipality_model.create(
            {"name": "Valencia", "state_id": self.other_ve_state.id}
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                municipality_model.create(
                    {"name": "Valencia", "state_id": self.ve_state.id}
                )

    def test_withholding_lower_than_tax(self):
        self._set_withholdings(30.0)
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.tax_amount, 42.0)
        self.assertEqual(wizard.withholding_available, 30.0)
        self.assertEqual(wizard.withholding_amount, 30.0)
        self.assertEqual(wizard.net_amount, 12.0)
        action = wizard.action_generate_entry()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(len(move.line_ids), 3)
        self.assertEqual(sum(move.line_ids.mapped("balance")), 0.0)
        lines = {line.account_id: line for line in move.line_ids}
        self.assertEqual(lines[self.expense_account].debit, 42.0)
        self.assertEqual(lines[self.withholding_account].credit, 30.0)
        self.assertEqual(lines[self.payable_account].credit, 12.0)

    def test_withholding_higher_than_tax(self):
        self._set_withholdings(100.0)
        action = self._create_wizard().action_generate_entry()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(len(move.line_ids), 2)
        self.assertEqual(
            move.line_ids.account_id, self.expense_account | self.withholding_account
        )
        self.assertFalse(
            move.line_ids.filtered(lambda line: line.account_id == self.payable_account)
        )
        self.assertEqual(
            move.line_ids.filtered("credit").account_id, self.withholding_account
        )
        self.assertEqual(move.line_ids.filtered("credit").credit, 42.0)
        move.action_post()
        self.assertEqual(self._withholding_balance(), 58.0)

    def test_second_period_consumes_carried_withholding(self):
        self._set_withholdings(100.0)
        june = self.env["account.move"].browse(
            self._create_wizard().action_generate_entry()["res_id"]
        )
        june.action_post()
        self._create_move(2000.0, date(2025, 7, 10))
        july_wizard = self._create_wizard(month="7")
        july_wizard.action_compute()
        self.assertEqual(july_wizard.tax_amount, 60.0)
        self.assertEqual(july_wizard.withholding_available, 58.0)
        self.assertEqual(july_wizard.withholding_amount, 58.0)
        self.assertEqual(july_wizard.net_amount, 2.0)
        july = self.env["account.move"].browse(
            july_wizard.action_generate_entry()["res_id"]
        )
        july.action_post()
        self.assertEqual(self._withholding_balance(), 0.0)
        payable_line = july.line_ids.filtered(
            lambda line: line.account_id == self.payable_account
        )
        self.assertEqual(payable_line.credit, 2.0)

    def test_without_withholding_account_entry_is_unchanged(self):
        self._set_withholdings(30.0)
        self.company.l10n_ve_municipal_withholding_account_id = False
        wizard = self._create_wizard()
        wizard.action_compute()
        self.assertEqual(wizard.withholding_available, 0.0)
        self.assertEqual(wizard.withholding_amount, 0.0)
        self.assertEqual(wizard.net_amount, 42.0)
        move = self.env["account.move"].browse(wizard.action_generate_entry()["res_id"])
        self.assertEqual(len(move.line_ids), 2)
        self.assertEqual(
            move.line_ids.account_id, self.expense_account | self.payable_account
        )
        self.assertEqual(move.line_ids.filtered("credit").credit, 42.0)

    def test_withholding_account_must_be_asset(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.company.l10n_ve_municipal_withholding_account_id = self.payable_account
