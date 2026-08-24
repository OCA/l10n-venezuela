# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestBankCashBookReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.bank_report = cls.env.ref("l10n_ve_reports.bank_book_report")
        cls.cash_report = cls.env.ref("l10n_ve_reports.cash_book_report")
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.bank_account = cls.bank_journal.default_account_id
        cls.cash_journal = cls.env["account.journal"].search(
            [
                ("company_id", "=", cls.company_data["company"].id),
                ("type", "=", "cash"),
            ],
            limit=1,
        )
        cls.cash_account = cls.cash_journal.default_account_id
        cls.counterpart_account = cls.company_data["default_account_revenue"]

        cls.opening_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2024-12-31"),
                "journal_id": cls.bank_journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": 1000.0,
                            "credit": 0.0,
                            "name": "Saldo inicial banco",
                            "account_id": cls.bank_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 1000.0,
                            "name": "Contrapartida apertura banco",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.opening_move.action_post()

        cls.deposit_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2025-01-10"),
                "journal_id": cls.bank_journal.id,
                "ref": "DEP-001",
                "line_ids": [
                    Command.create(
                        {
                            "debit": 500.0,
                            "credit": 0.0,
                            "name": "Deposito en banco",
                            "account_id": cls.bank_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 500.0,
                            "name": "Ingreso por deposito",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.deposit_move.action_post()

        cls.payment_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2025-01-15"),
                "journal_id": cls.bank_journal.id,
                "ref": "PAG-001",
                "line_ids": [
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 200.0,
                            "name": "Pago desde banco",
                            "account_id": cls.bank_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 200.0,
                            "credit": 0.0,
                            "name": "Egreso por pago",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.payment_move.action_post()

        cls.cash_opening_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2024-12-31"),
                "journal_id": cls.cash_journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": 300.0,
                            "credit": 0.0,
                            "name": "Saldo inicial caja",
                            "account_id": cls.cash_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 300.0,
                            "name": "Contrapartida apertura caja",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.cash_opening_move.action_post()

        cls.cash_in_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2025-01-12"),
                "journal_id": cls.cash_journal.id,
                "ref": "CAJ-001",
                "line_ids": [
                    Command.create(
                        {
                            "debit": 150.0,
                            "credit": 0.0,
                            "name": "Cobro en efectivo",
                            "account_id": cls.cash_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 150.0,
                            "name": "Ingreso en caja",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.cash_in_move.action_post()

    def _get_report_lines(self, report, date_from, date_to, journal=None):
        options = self._generate_options(report, date_from, date_to)
        if journal:
            options = self._update_multi_selector_filter(
                options, "journals", journal.ids
            )
        report_info = report.get_report_information(options)
        return report_info["lines"]

    def _get_line_column_values(self, line, report):
        values = {}
        for index, column in enumerate(report.column_ids):
            column_data = line["columns"][index]
            if isinstance(column_data, dict):
                values[column.expression_label] = column_data.get(
                    "no_format", column_data.get("name")
                )
            else:
                values[column.expression_label] = column_data
        return values

    def test_bank_book_opening_balance_and_running_balance(self):
        lines = self._get_report_lines(
            self.bank_report,
            "2025-01-01",
            "2025-01-31",
            self.bank_journal,
        )
        movement_lines = [
            line for line in lines if line.get("caret_options") == "account.move.line"
        ]
        self.assertEqual(len(movement_lines), 2)

        first_line_values = self._get_line_column_values(
            movement_lines[0], self.bank_report
        )
        second_line_values = self._get_line_column_values(
            movement_lines[1], self.bank_report
        )
        self.assertEqual(first_line_values["debit"], 500.0)
        self.assertEqual(first_line_values["credit"], 0.0)
        self.assertEqual(first_line_values["balance"], 1500.0)
        self.assertEqual(second_line_values["debit"], 0.0)
        self.assertEqual(second_line_values["credit"], 200.0)
        self.assertEqual(second_line_values["balance"], 1300.0)

        total_lines = [line for line in lines if line.get("class") == "total"]
        self.assertTrue(total_lines)
        journal_total_values = self._get_line_column_values(
            total_lines[0], self.bank_report
        )
        self.assertEqual(journal_total_values["previous_balance"], 1000.0)
        self.assertEqual(journal_total_values["debit"], 500.0)
        self.assertEqual(journal_total_values["credit"], 200.0)
        self.assertEqual(journal_total_values["balance"], 1300.0)

    def test_cash_book_only_shows_cash_journal(self):
        lines = self._get_report_lines(
            self.cash_report,
            "2025-01-01",
            "2025-01-31",
            self.cash_journal,
        )
        line_names = " ".join(line.get("name", "") for line in lines)
        self.assertIn(self.cash_journal.display_name, line_names)
        self.assertNotIn(self.bank_journal.display_name, line_names)

        movement_lines = [
            line for line in lines if line.get("caret_options") == "account.move.line"
        ]
        self.assertEqual(len(movement_lines), 1)
        movement_values = self._get_line_column_values(
            movement_lines[0], self.cash_report
        )
        self.assertEqual(movement_values["debit"], 150.0)
        self.assertEqual(movement_values["balance"], 450.0)

    def test_bank_book_excludes_cash_journal(self):
        lines = self._get_report_lines(
            self.bank_report,
            "2025-01-01",
            "2025-01-31",
        )
        line_names = " ".join(line.get("name", "") for line in lines)
        self.assertIn(self.bank_journal.display_name, line_names)
        self.assertNotIn(self.cash_journal.display_name, line_names)
