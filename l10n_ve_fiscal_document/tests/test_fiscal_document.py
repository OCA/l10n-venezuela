# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import SQL

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ve_fiscal_document import post_init_hook


@tagged("post_install", "-at_install")
class TestL10nVeFiscalDocument(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.country_id = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.sale_journal.l10n_ve_emission_medium = "free"
        cls.purchase_journal = cls.company_data["default_journal_purchase"]
        cls.partner = cls.env["res.partner"].create({"name": "Fiscal Partner"})

    def _create_invoice(self, move_type="out_invoice"):
        purchase = move_type.startswith("in_")
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": (
                    self.purchase_journal.id if purchase else self.sale_journal.id
                ),
                "invoice_date": date(2026, 8, 29),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Fiscal line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                                if purchase
                                else "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )

    def test_post_snapshots_emission_medium(self):
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()
        invoice.write(
            {
                "l10n_ve_control_number": "00-00001234",
                "l10n_ve_control_date": date(2026, 8, 29),
            }
        )

        invoice.action_post()
        self.sale_journal.l10n_ve_emission_medium = "free"

        self.assertEqual(invoice.l10n_ve_emission_medium, "digital")
        self.assertEqual(invoice.l10n_ve_control_number, "00-00001234")
        self.assertTrue(invoice.l10n_ve_fiscal_data_locked)

    def test_direct_post_snapshots_emission_medium(self):
        self.sale_journal.l10n_ve_emission_medium = "fiscal_machine"
        invoice = self._create_invoice()

        invoice._post(soft=False)

        self.assertEqual(invoice.l10n_ve_emission_medium, "fiscal_machine")
        self.assertTrue(invoice.l10n_ve_fiscal_data_locked)

    def test_posted_customer_fiscal_data_is_immutable(self):
        invoice = self._create_invoice()
        invoice.action_post()

        for field_name, value in (
            ("l10n_ve_control_number", "00-00000001"),
            ("l10n_ve_control_date", date(2026, 8, 29)),
            ("l10n_ve_emission_medium", "free"),
        ):
            with self.subTest(field_name=field_name), self.assertRaises(UserError):
                invoice.write({field_name: value})

    def test_fiscal_document_cannot_be_reset_cancelled_or_deleted(self):
        invoice = self._create_invoice()
        invoice.action_post()

        self.assertTrue(invoice.l10n_ve_fiscal_data_locked)
        with self.assertRaises(UserError):
            invoice.button_draft()
        with self.assertRaises(UserError):
            invoice.button_cancel()
        with self.assertRaises(UserError):
            invoice.write({"state": "draft"})
        with self.assertRaises(UserError):
            invoice.write({"state": "cancel"})
        with self.assertRaises(UserError):
            invoice.unlink()

    def test_direct_state_write_cannot_bypass_posting(self):
        invoice = self._create_invoice()

        with self.assertRaises(UserError):
            invoice.write({"state": "posted"})
        with self.assertRaises(UserError):
            invoice.with_context(l10n_ve_fiscal_document_posting=True).write(
                {"state": "posted"}
            )

    def test_technical_fields_cannot_be_set_directly(self):
        invoice = self._create_invoice()
        for field_name, value in (
            ("l10n_ve_emission_medium", "digital"),
            ("l10n_ve_fiscal_data_locked", True),
        ):
            with self.subTest(operation="write", field_name=field_name):
                with self.assertRaises(UserError):
                    invoice.write({field_name: value})
            with self.subTest(operation="create", field_name=field_name):
                with self.assertRaises(UserError):
                    self.env["account.move"].create(
                        {"move_type": "entry", field_name: value}
                    )

    def test_post_requires_emission_medium(self):
        self.sale_journal.l10n_ve_emission_medium = False
        invoice = self._create_invoice()

        with self.assertRaises(UserError):
            invoice.action_post()

    def test_post_init_locks_historical_documents(self):
        invoice = self._create_invoice()
        invoice.action_post()
        invoice.flush_recordset(
            ["l10n_ve_fiscal_data_locked", "l10n_ve_emission_medium"]
        )
        self.env.cr.execute(
            SQL(
                "UPDATE account_move "
                "SET l10n_ve_fiscal_data_locked = FALSE, "
                "l10n_ve_emission_medium = NULL WHERE id = %s",
                invoice.id,
            )
        )
        invoice.invalidate_recordset(
            ["l10n_ve_fiscal_data_locked", "l10n_ve_emission_medium"]
        )

        post_init_hook(self.env)

        self.assertTrue(invoice.l10n_ve_fiscal_data_locked)
        self.assertFalse(invoice.l10n_ve_emission_medium)
        with self.assertRaises(UserError):
            invoice.l10n_ve_control_number = "00-00000003"

    def test_fiscal_country_change_does_not_unlock_historical_data(self):
        invoice = self._create_invoice()
        invoice.action_post()

        self.company.account_fiscal_country_id = self.env.ref("base.us")

        with self.assertRaises(UserError):
            invoice.l10n_ve_control_number = "00-00000004"

    def test_posted_vendor_control_data_remains_correctable(self):
        bill = self._create_invoice("in_invoice")
        bill.action_post()
        post_init_hook(self.env)

        bill.write(
            {
                "l10n_ve_control_number": "00-00000002",
                "l10n_ve_control_date": date(2026, 8, 29),
            }
        )

        self.assertEqual(bill.l10n_ve_control_number, "00-00000002")

    def test_credit_note_remains_available_for_correction(self):
        invoice = self._create_invoice()
        invoice.action_post()

        credit_note = invoice._reverse_moves(
            [{"date": date(2026, 8, 29), "ref": "Fiscal correction"}]
        )
        credit_note.action_post()

        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.reversed_entry_id, invoice)
        self.assertTrue(credit_note.l10n_ve_fiscal_data_locked)

    def test_copy_does_not_reuse_fiscal_identification(self):
        invoice = self._create_invoice()
        invoice.write(
            {
                "l10n_ve_control_number": "00-00001234",
                "l10n_ve_control_date": date(2026, 8, 29),
            }
        )

        duplicate = invoice.copy()

        self.assertFalse(duplicate.l10n_ve_control_number)
        self.assertFalse(duplicate.l10n_ve_control_date)
        self.assertFalse(duplicate.l10n_ve_emission_medium)
        self.assertFalse(duplicate.l10n_ve_fiscal_data_locked)

    def test_non_venezuelan_document_does_not_snapshot_medium(self):
        self.company.account_fiscal_country_id = self.env.ref("base.us")
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()

        invoice.action_post()
        post_init_hook(self.env)

        self.assertFalse(invoice.l10n_ve_emission_medium)
        self.assertFalse(invoice.l10n_ve_fiscal_data_locked)

    def test_set_control_number_after_posting(self):
        # The only supported integration point for a fiscal machine or an
        # authorized digital printing house connector: they only learn the
        # control number once the document is already posted and totalled.
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()
        invoice.action_post()

        invoice._l10n_ve_set_control_number("00-00001325", date(2026, 8, 29))

        self.assertEqual(invoice.l10n_ve_control_number, "00-00001325")
        self.assertEqual(invoice.l10n_ve_control_date, date(2026, 8, 29))

    def test_set_control_number_defaults_date_to_today(self):
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()
        invoice.action_post()

        invoice._l10n_ve_set_control_number("00-00001325")

        self.assertEqual(
            invoice.l10n_ve_control_date, fields.Date.context_today(invoice)
        )

    def test_set_control_number_requires_posted_document(self):
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()

        with self.assertRaises(UserError):
            invoice._l10n_ve_set_control_number("00-00001325")

    def test_set_control_number_does_not_overwrite(self):
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_invoice()
        invoice.action_post()
        invoice._l10n_ve_set_control_number("00-00001325")

        with self.assertRaises(UserError):
            invoice._l10n_ve_set_control_number("00-00009999")
