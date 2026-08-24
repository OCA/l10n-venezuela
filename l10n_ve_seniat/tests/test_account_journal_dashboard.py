from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeSeniatInvoiceDashboard(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data["default_journal_sale"]
        cls.today = fields.Date.today()

    def _create_posted_customer_move(self, move_type):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "journal_id": self.journal.id,
                "invoice_date": self.today,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": move_type,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )

    def test_invoice_dashboard_counts_current_month(self):
        month_start = self.today.replace(day=1)
        invoice = self._create_posted_customer_move("out_invoice")
        invoice.action_post()
        credit = self._create_posted_customer_move("out_refund")
        credit.write({"reversed_entry_id": invoice.id})
        credit.action_post()

        data = self.env["account.journal"].get_l10n_ve_invoice_dashboard()
        self.assertTrue(data["visible"])
        counts = {item["key"]: item["count"] for item in data["items"]}
        self.assertGreaterEqual(counts["posted_invoices_month"], 1)
        self.assertGreaterEqual(counts["credit_notes_month"], 1)

        invoice_action = self.env[
            "account.journal"
        ].action_l10n_ve_invoice_dashboard_open("posted_invoices_month")
        self.assertEqual(invoice_action["res_model"], "account.move")
        self.assertIn(("invoice_date", ">=", month_start), invoice_action["domain"])
        self.assertIn(("move_type", "=", "out_invoice"), invoice_action["domain"])

        credit_action = self.env[
            "account.journal"
        ].action_l10n_ve_invoice_dashboard_open("credit_notes_month")
        self.assertIn(("move_type", "=", "out_refund"), credit_action["domain"])

    def test_invoice_dashboard_counts_overdue_unpaid_invoices(self):
        past_date = self.today - relativedelta(days=10)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.journal.id,
                "invoice_date": past_date,
                "invoice_date_due": self.today - relativedelta(days=5),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "overdue",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        self.assertIn(invoice.payment_state, ("not_paid", "partial"))

        data = self.env["account.journal"].get_l10n_ve_invoice_dashboard()
        counts = {item["key"]: item["count"] for item in data["items"]}
        self.assertGreaterEqual(counts["overdue_unpaid_invoices"], 1)

        action = self.env["account.journal"].action_l10n_ve_invoice_dashboard_open(
            "overdue_unpaid_invoices"
        )
        self.assertIn(("move_type", "=", "out_invoice"), action["domain"])
        self.assertIn(
            ("payment_state", "in", ("not_paid", "partial")), action["domain"]
        )
        self.assertIn(("invoice_date_due", "<", self.today), action["domain"])

    def test_invoice_dashboard_hidden_for_non_ve_company(self):
        self.change_company_country(self.env.company, self.env.ref("base.us"))
        data = self.env["account.journal"].get_l10n_ve_invoice_dashboard()
        self.assertFalse(data["visible"])
