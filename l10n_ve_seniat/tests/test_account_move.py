# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMove(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        cls.partner_ve_no_vat = cls.env["res.partner"].create(
            {
                "name": "Partner sin RIF",
                "country_id": cls.env.ref("base.ve").id,
                "vat": False,
            }
        )
        cls.third_party_ve = cls.env["res.partner"].create(
            {
                "name": "Tercero VE",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "V12345678",
            }
        )
        cls.partner_foreign_no_vat = cls.env["res.partner"].create(
            {
                "name": "Partner extranjero sin VAT",
                "country_id": cls.env.ref("base.us").id,
                "vat": False,
            }
        )
        cls.partner_foreign_invalid_vat = cls.env["res.partner"].create(
            {
                "name": "Partner extranjero VAT libre",
                "country_id": cls.env.ref("base.us").id,
                "vat": "ABC123",
            }
        )
        cls.third_party_foreign_no_vat = cls.env["res.partner"].create(
            {
                "name": "Tercero extranjero sin VAT",
                "country_id": cls.env.ref("base.us").id,
                "vat": False,
            }
        )

    def _create_invoice_vals(self, partner, tax_ids=None, price_unit=100.0):
        return {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1.0,
                        "price_unit": price_unit,
                        "account_id": self.company_data["default_account_revenue"].id,
                        "tax_ids": [
                            (
                                6,
                                0,
                                tax_ids or [self.company_data["default_tax_sale"].id],
                            )
                        ],
                    },
                )
            ],
        }

    def _create_supplier_invoice_vals(self, partner, tax_ids=None, price_unit=100.0):
        tax_ids = tax_ids or [self.company_data["default_tax_purchase"].id]
        return {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1.0,
                        "price_unit": price_unit,
                        "account_id": self.company_data["default_account_expense"].id,
                        "tax_ids": [
                            (
                                6,
                                0,
                                tax_ids,
                            )
                        ],
                    },
                )
            ],
        }

    def test_out_invoice_post_requires_vat(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve_no_vat)
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("RIF", str(cm.exception))

    def test_l10n_ve_process_date_on_invoice_post(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.l10n_ve_process_date, fields.Date.today())

    def test_l10n_ve_process_date_on_entry_post_and_draft(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.today(),
                "line_ids": [
                    Command.create(
                        {
                            "name": "Debit",
                            "debit": 100.0,
                            "credit": 0.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Credit",
                            "debit": 0.0,
                            "credit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.l10n_ve_process_date, fields.Date.today())
        move.button_draft()
        self.assertFalse(move.l10n_ve_process_date)

    def test_out_invoice_post_skips_ve_rif_for_foreign_partner(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_foreign_no_vat)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_out_invoice_post_skips_ve_rif_format_for_foreign_partner(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_foreign_invalid_vat)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_out_invoice_post_invalid_vat_format_can_be_disabled(self):
        self.env.company.l10n_ve_validate_partner_vat_format = False
        partner = (
            self.env["res.partner"]
            .with_context(skip_l10n_ve_vat_rif_format_check=True)
            .create(
                {
                    "name": "Partner VE RIF flexible",
                    "country_id": self.env.ref("base.ve").id,
                    "vat": "ABC123",
                }
            )
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(partner)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_out_invoice_post_rejects_zero_total(self):
        tax = self.company_data["default_tax_sale"]
        with self.assertRaises(ValidationError) as cm:
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner_ve.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Product",
                                "quantity": 1.0,
                                "price_unit": 100.0,
                                "account_id": self.company_data[
                                    "default_account_revenue"
                                ].id,
                                "tax_ids": [(6, 0, [tax.id])],
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "name": "Credit",
                                "quantity": 1.0,
                                "price_unit": -100.0,
                                "account_id": self.company_data[
                                    "default_account_revenue"
                                ].id,
                                "tax_ids": [(6, 0, [tax.id])],
                            },
                        ),
                    ],
                }
            )
        self.assertIn("precio", str(cm.exception).lower())

    def test_out_invoice_post_rejects_multiple_taxes_per_line(self):
        tax_b = self.env["account.tax"].create(
            {
                "name": "Tax B Sale",
                "amount": 10.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.env.company.id,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line with 2 taxes",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [
                                        self.company_data["default_tax_sale"].id,
                                        tax_b.id,
                                    ]
                                )
                            ],
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError) as cm:
            move.action_post()
        self.assertIn("more than one tax", str(cm.exception))

    def test_out_invoice_post_without_book_sections_raises(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("talonario", str(cm.exception).lower())

    def test_out_invoice_post_with_control_number_skips_book_sections(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        vals = self._create_invoice_vals(self.partner_ve)
        vals["l10n_ve_control_number"] = "99-00009901"
        move = self.env["account.move"].create(vals)
        move.action_post()
        self.assertEqual(move.l10n_ve_control_number, "99-00009901")
        self.assertEqual(move.state, "posted")

    def test_out_invoice_post_success_generates_control_number(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertTrue(move.l10n_ve_control_number)
        self.assertTrue(move.l10n_ve_invoice_date)
        doc = self.env["account.book.document"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", move.id)]
        )
        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.number, 1)
        self.assertEqual(move.l10n_ve_control_number, "00-00000001")

    def test_draft_invoice_control_placeholder_preview(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertFalse((move.l10n_ve_control_number or "").strip())
        self.assertEqual(move.l10n_ve_control_number_placeholder, "00-00000001")

    def test_book_correlative_admin_unlink_clears_control_number(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        doc = self.env["account.book.document"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", move.id)]
        )
        self.assertEqual(len(doc), 1)
        doc.unlink()
        self.assertFalse(move.l10n_ve_control_number)

    def test_book_correlative_admin_write_updates_control_number(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        doc = self.env["account.book.document"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", move.id)]
        )
        doc.write({"number": 2})
        self.assertEqual(move.l10n_ve_control_number, "00-00000002")

    def test_book_correlative_forbids_gap(self):
        book = self.env["account.book"].search(
            [("name", "=", "Talonario tests")], limit=1
        )
        sec = book.section_ids[0]
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        draft = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        with self.assertRaises(ValidationError):
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": sec.id,
                    "number": 3,
                    "res_model": "account.move",
                    "res_id": draft.id,
                }
            )

    def test_button_cancel_out_invoice_requires_reason(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        with self.assertRaises(ValidationError) as cm:
            move.button_cancel()
        self.assertIn("motivo", str(cm.exception).lower())

    def test_ve_cancel_out_invoice_with_reason(self):
        reason = self.env.ref(
            "l10n_ve_seniat.l10n_ve_cancel_reason_print_fail",
            raise_if_not_found=False,
        )
        if not reason:
            reason = self.env["l10n_ve.invoice.cancel.reason"].search(
                [], limit=1
            )
        self.assertTrue(reason)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write({"l10n_ve_cancel_reason_id": reason.id})
        move.button_cancel()
        self.assertEqual(move.state, "cancel")
        self.assertEqual(move.l10n_ve_cancel_reason_id, reason)

    def test_cancel_wizard_blocked_for_fiscal_machine(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(journal)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        with self.assertRaises(UserError) as cm:
            move.action_l10n_ve_open_cancel_wizard()
        self.assertIn("máquina fiscal", str(cm.exception).lower())

    def test_cancel_wizard_blocked_for_fiscal_machine_credit_note(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(journal)
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        credit_note = invoice._reverse_moves()
        credit_note.action_post()
        self.assertFalse(credit_note.l10n_ve_show_cancel_wizard)
        with self.assertRaises(UserError):
            credit_note.action_l10n_ve_open_cancel_wizard()

    def test_cancel_wizard_blocked_for_fiscal_machine_debit_note(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(journal)
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": fields.Date.today(),
                    "reason": "test débito",
                    "copy_lines": True,
                }
            )
        )
        wiz.create_debit()
        debit_move = self.env["account.move"].search(
            [("debit_origin_id", "=", invoice.id)]
        )
        debit_move.ensure_one()
        debit_move.action_post()
        self.assertFalse(debit_move.l10n_ve_show_cancel_wizard)
        with self.assertRaises(UserError):
            debit_move.action_l10n_ve_open_cancel_wizard()

    def test_out_refund_post_without_reversed_entry_raises(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner_ve.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": 50.0,
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
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("documento origen", str(cm.exception))

    def test_reversal_wizard_requires_reason(self):
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": ""})
        )
        with self.assertRaises(UserError) as cm:
            wiz.reverse_moves()
        self.assertIn("motivo de reversión", str(cm.exception))

    def test_credit_debit_blocked_until_free_form_printed(self):
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": "free"})
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        self.assertFalse(invoice.l10n_ve_show_credit_debit_actions)
        with self.assertRaises(UserError) as cm:
            invoice.action_reverse()
        self.assertIn("forma libre", str(cm.exception))
        invoice.l10n_ve_invoice_original_printed = True
        self.assertTrue(invoice.l10n_ve_show_credit_debit_actions)

    def test_credit_debit_allowed_for_contingency_without_print(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        self.assertTrue(invoice.l10n_ve_show_credit_debit_actions)

    def test_credit_note_blocked_from_debit_note(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": fields.Date.today(),
                    "reason": "test débito",
                    "copy_lines": True,
                }
            )
        )
        wiz.create_debit()
        debit_move = self.env["account.move"].search(
            [("debit_origin_id", "=", invoice.id)]
        )
        debit_move.ensure_one()
        debit_move.write(
            {
                "l10n_ve_control_number": "99-00000100",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        debit_move.action_post()
        self.assertFalse(debit_move.l10n_ve_show_credit_note_action)
        self.assertFalse(debit_move.l10n_ve_show_debit_note_action)
        with self.assertRaises(UserError) as cm:
            debit_move.action_reverse()
        self.assertIn("nota de débito", str(cm.exception).lower())
        with self.assertRaises(UserError):
            debit_move._reverse_moves()

    def test_debit_note_blocked_from_credit_note(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000101",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        self.assertFalse(credit_note.l10n_ve_show_credit_note_action)
        self.assertFalse(credit_note.l10n_ve_show_debit_note_action)
        with self.assertRaises(UserError) as cm:
            credit_note.action_debit_note()
        self.assertIn("nota de crédito", str(cm.exception).lower())

    def test_debit_note_blocked_after_full_credit_note(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000102",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        self.assertTrue(invoice._l10n_ve_has_full_posted_credit_note())
        self.assertTrue(invoice.l10n_ve_show_debit_note_action)

    def test_debit_note_blocked_when_unreversed_debit_after_full_credit(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000102",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": fields.Date.today(),
                    "reason": "cargo adicional",
                    "copy_lines": False,
                }
            )
        )
        wiz.create_debit()
        debit = self.env["account.move"].search(
            [("debit_origin_id", "=", invoice.id)]
        )
        debit.ensure_one()
        debit.write(
            {
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "cargo ND",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, [self.tax_sale_a.id])],
                        },
                    )
                ],
                "l10n_ve_control_number": "99-00000103",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        debit.action_post()
        self.assertFalse(invoice.l10n_ve_show_debit_note_action)
        with self.assertRaises(UserError) as cm:
            invoice.action_debit_note()
        self.assertIn("débito adicional pendiente", str(cm.exception).lower())

    def test_credit_note_blocked_after_full_credit_note(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000105",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        self.assertTrue(invoice._l10n_ve_has_full_posted_credit_note())
        self.assertFalse(invoice.l10n_ve_show_credit_note_action)
        with self.assertRaises(UserError) as cm:
            invoice.action_reverse()
        self.assertIn("reversado completamente", str(cm.exception).lower())
        with self.assertRaises(UserError):
            invoice._reverse_moves()

    def test_credit_note_stat_button_on_invoice(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000099",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000104",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        self.assertEqual(invoice.l10n_ve_related_credit_note_count, 1)
        action = invoice.action_l10n_ve_view_credit_notes()
        self.assertEqual(set(action["domain"][0][2]), {credit_note.id})
        self.assertEqual(credit_note.l10n_ve_related_credit_note_count, 1)
        credit_action = credit_note.action_l10n_ve_view_credit_notes()
        self.assertEqual(set(credit_action["domain"][0][2]), {invoice.id})

    def test_unreversed_debit_note_alert_after_full_invoice_credit(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.write(
            {
                "l10n_ve_control_number": "99-00000110",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        invoice.action_post()
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": fields.Date.today(),
                    "reason": "cargo adicional",
                    "copy_lines": False,
                }
            )
        )
        wiz.create_debit()
        debit = self.env["account.move"].search(
            [("debit_origin_id", "=", invoice.id)]
        )
        debit.ensure_one()
        debit.write(
            {
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "cargo ND",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, [self.tax_sale_a.id])],
                        },
                    )
                ],
                "l10n_ve_control_number": "99-00000111",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        debit.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.write(
            {
                "l10n_ve_control_number": "99-00000112",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit_note.action_post()
        self.assertTrue(invoice._l10n_ve_has_full_posted_credit_on_invoice())
        self.assertFalse(invoice._l10n_ve_has_full_posted_credit_note())
        self.assertTrue(invoice.l10n_ve_show_unreversed_debit_note_alert)
        self.assertFalse(invoice.l10n_ve_show_debit_note_action)
        self.assertFalse(invoice.l10n_ve_show_credit_note_action)
        with self.assertRaises(UserError):
            invoice.action_debit_note()
        action = invoice.action_l10n_ve_open_credit_note_for_debit_notes()
        self.assertEqual(
            action["res_model"], "l10n_ve.account.move.debit.credit.wizard"
        )
        wizard = (
            self.env["l10n_ve.account.move.debit.credit.wizard"]
            .with_context(action.get("context", {}))
            .create({"reason": "reversión ND adicional"})
        )
        result = wizard.action_create_credit_note()
        debit_credit = self.env["account.move"].browse(result["res_id"])
        self.assertEqual(debit_credit.reversed_entry_id, invoice)
        self.assertEqual(debit_credit.l10n_ve_debit_note_reversed_ids, debit)
        debit_credit.write(
            {
                "l10n_ve_control_number": "99-00000113",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        debit_credit.action_post()
        self.assertFalse(invoice.l10n_ve_show_unreversed_debit_note_alert)

    def test_out_refund_post_with_reversed_entry_success(self):
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        credit_note = invoice._reverse_moves()
        credit_note.action_post()
        self.assertTrue(credit_note.l10n_ve_control_number)
        self.assertEqual(credit_note.reversed_entry_id, invoice)
        doc = self.env["account.book.document"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", credit_note.id),
            ]
        )
        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.number, 2)

    def test_correlative_sequences_independent_per_section(self):
        journal = self.company_data["default_journal_sale"]
        book = self.env["account.book"].create(
            {
                "name": "Talonario tramos VE",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 2000,
            }
        )
        sec_inv = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "FACTURAS",
                "number_from": 1,
                "number_to": 500,
            }
        )
        sec_cn = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "NOTAS",
                "number_from": 501,
                "number_to": 1000,
            }
        )
        journal.write(
            {
                "l10n_ve_invoice_section_id": sec_inv.id,
                "l10n_ve_credit_note_section_id": sec_cn.id,
            }
        )
        inv1 = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        inv1.action_post()
        self.assertEqual(inv1.l10n_ve_control_number, "00-00000001")
        inv2 = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        inv2.action_post()
        self.assertEqual(inv2.l10n_ve_control_number, "00-00000002")
        credit_note = inv1._reverse_moves()
        credit_note.action_post()
        self.assertEqual(credit_note.l10n_ve_control_number, "00-00000501")
        doc_cn = self.env["account.book.document"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", credit_note.id),
            ]
        )
        self.assertEqual(doc_cn.number, 501)

    def test_in_refund_post_without_reversed_entry_raises(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Proveedor VE",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J98765432",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": supplier.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_purchase"].id])
                            ],
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("documento origen", str(cm.exception))

    def test_on_behalf_of_third_party_disabled_config_raises(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = False
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": self.third_party_ve.id,
            }
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("habilitar", str(cm.exception))

    def test_on_behalf_of_third_party_computed_without_tercero_posts(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertFalse(move.l10n_ve_on_behalf_of_third_party)
        move.action_post()
        self.assertFalse(move.l10n_ve_on_behalf_of_third_party)

    def test_on_behalf_of_third_party_requires_third_party_vat(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        third_no_vat = self.env["res.partner"].create(
            {
                "name": "Tercero sin RIF",
                "country_id": self.env.ref("base.ve").id,
                "vat": False,
            }
        )
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": third_no_vat.id,
            }
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("RIF", str(cm.exception))

    def test_on_behalf_of_third_party_skips_ve_rif_for_foreign_third_party(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": self.third_party_foreign_no_vat.id,
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_on_behalf_of_third_party_post_success(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": self.third_party_ve.id,
            }
        )
        move.action_post()
        self.assertTrue(move.l10n_ve_control_number)
        self.assertEqual(move.l10n_ve_third_party_partner_id, self.third_party_ve)
        self.assertTrue(move.l10n_ve_on_behalf_of_third_party)

    def test_on_behalf_of_third_party_certified_copy_deadline(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": self.third_party_ve.id,
                "invoice_date": date(2024, 1, 15),
            }
        )
        move.action_post()
        self.assertEqual(move.l10n_ve_certified_copy_deadline, date(2024, 2, 5))

    def test_supplier_third_party_is_for_withholding(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        supplier = self.env["res.partner"].create(
            {
                "name": "Proveedor VE",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J87654321",
            }
        )
        move = self.env["account.move"].create(
            {
                **self._create_supplier_invoice_vals(supplier),
                "l10n_ve_third_party_partner_id": self.third_party_ve.id,
            }
        )
        move.action_post()
        self.assertEqual(move.l10n_ve_third_party_partner_id, self.third_party_ve)
        self.assertFalse(move.l10n_ve_on_behalf_of_third_party)
        self.assertFalse(move.l10n_ve_certified_copy_deadline)

    def test_on_behalf_of_third_party_report_print(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        move = self.env["account.move"].create(
            {
                **self._create_invoice_vals(self.partner_ve),
                "l10n_ve_third_party_partner_id": self.third_party_ve.id,
            }
        )
        move.action_post()
        move.action_print_pdf()

    def test_button_cancel_out_refund_requires_reason(self):
        reason = self.env.ref(
            "l10n_ve_seniat.l10n_ve_cancel_reason_paper_fail",
            raise_if_not_found=False,
        )
        if not reason:
            reason = self.env["l10n_ve.invoice.cancel.reason"].search(
                [], limit=1
            )
        self.assertTrue(reason)
        invoice = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        invoice.action_post()
        move = invoice._reverse_moves()
        move.action_post()
        with self.assertRaises(ValidationError) as cm:
            move.button_cancel()
        self.assertIn("motivo", str(cm.exception).lower())
        move.write({"l10n_ve_cancel_reason_id": reason.id})
        move.button_cancel()
        self.assertEqual(move.state, "cancel")

    def test_button_draft_out_invoice_raises(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        with self.assertRaises(ValidationError) as cm:
            move.button_draft()
        self.assertIn("reset to draft", str(cm.exception))
        self.assertIn("Venezuelan", str(cm.exception))

    def test_button_draft_in_invoice_allowed(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Supplier draft reset",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J98765432",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": supplier.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_purchase"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        self.assertTrue(move.show_reset_to_draft_button)
        move.button_draft()
        self.assertEqual(move.state, "draft")

    def test_extract_control_number_numeric(self):
        move = self.env["account.move"].new({})
        self.assertEqual(move._extract_control_number_numeric("00000001"), 1)
        self.assertEqual(move._extract_control_number_numeric("ABC-123"), 123)
        self.assertEqual(move._extract_control_number_numeric(""), 0)
        self.assertEqual(move._extract_control_number_numeric(None), 0)
        self.assertEqual(move._l10n_ve_control_number_parts("00-00000003"), ("00", 3))
        self.assertEqual(move._l10n_ve_control_number_parts("00000007"), ("00", 7))

    def test_seniat_invoice_tag_same_currency(self):
        self.env.company.partner_id.taxpayer_type = "formal"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertTrue(move.seniat_invoice_tag)
        self.assertIn("IGTF", move.seniat_invoice_tag)
        self.assertNotIn("tipo de cambio", move.seniat_invoice_tag)

    def test_write_control_number_triggers_validation(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        ctrl = move.l10n_ve_control_number
        move2 = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move2.action_post()
        with self.assertRaises(ValidationError) as cm:
            move2.write({"l10n_ve_control_number": ctrl})
        self.assertIn("ya está asignado", str(cm.exception).lower())

    def test_get_name_invoice_report_ve(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertEqual(
            move._get_name_invoice_report(),
            "l10n_ve_seniat.report_invoice_document",
        )

    def test_action_print_pdf(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.action_print_pdf()

    def test_action_print_pdf_continuous_without_escp_raises(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_free_form_print_medium = "continuous"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        with self.assertRaises(UserError) as cm:
            move.action_print_pdf()
        self.assertIn("l10n_ve_invoice_escp", str(cm.exception))

    def test_action_print_pdf_continuous_draft_raises(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_free_form_print_medium = "continuous"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        with self.assertRaises(UserError) as cm:
            move.action_print_pdf()
        self.assertIn("confirmar", str(cm.exception).lower())

    def test_action_print_pdf_draft_raises(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_free_form_print_medium = "pdf"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        with self.assertRaises(UserError) as cm:
            move.action_print_pdf()
        self.assertIn("confirmar", str(cm.exception).lower())

    def test_get_extra_print_items_draft_hides_pdf_download(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertEqual(move.get_extra_print_items(), [])

    def test_get_extra_print_items_posted_hides_pdf_download_without_original_print(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertEqual(move.get_extra_print_items(), [])
        self.assertTrue(move._l10n_ve_allows_invoice_portal_view())

    def test_portal_view_allowed_before_original_print_free_form(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "free"
        journal.l10n_ve_free_form_print_medium = "pdf"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertFalse(move.l10n_ve_invoice_original_printed)
        self.assertFalse(move._l10n_ve_allows_invoice_pdf_download())
        self.assertTrue(move._l10n_ve_allows_invoice_portal_view())

    def test_get_extra_print_items_posted_shows_pdf_download_after_original_print(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "free"
        journal.l10n_ve_free_form_print_medium = "pdf"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.l10n_ve_invoice_original_printed = True
        items = move.get_extra_print_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["key"], "download_pdf")
        self.assertEqual(items[0]["type"], "ir.actions.act_url")

    def test_get_extra_print_items_hides_pdf_download_for_continuous(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "free"
        journal.l10n_ve_free_form_print_medium = "continuous"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.l10n_ve_invoice_original_printed = True
        self.assertEqual(move.get_extra_print_items(), [])

    def test_get_extra_print_items_hides_pdf_download_for_digital(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "digital"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.l10n_ve_invoice_original_printed = True
        self.assertEqual(move.get_extra_print_items(), [])

    def test_hide_invoice_print_pdf_digital_not_sent(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "digital"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertTrue(move._l10n_ve_blocking_invoice_report_before_digital_sent())
        self.assertTrue(move.l10n_ve_hide_invoice_print_pdf)
        if "l10n_ve_edi_send_state" in move._fields:
            move.l10n_ve_edi_send_state = "sent"
            self.assertFalse(move.l10n_ve_hide_invoice_print_pdf)

    def test_get_extra_print_items_hides_pdf_download_for_fiscal_machine(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(journal)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.l10n_ve_invoice_original_printed = True
        self.assertTrue(move.l10n_ve_hide_invoice_preview_send)
        with self.assertRaises(UserError):
            move.preview_invoice()
        self.assertEqual(move.get_extra_print_items(), [])

    def test_invoice_pdf_filename_uses_name_and_vat(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertEqual(
            move._get_invoice_report_filename(),
            f"{move.name.replace('/', '_')}_{self.partner_ve.vat}.pdf",
        )
        self.assertEqual(
            move._get_report_base_filename(),
            f"{move.name.replace('/', '_')}_{self.partner_ve.vat}",
        )
        self.assertNotIn("proforma", move._get_invoice_report_filename().lower())
        self.assertNotIn("draft", move._get_invoice_report_filename().lower())

    def test_invoice_pdf_filename_without_vat(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.name = "FAC-00099"
        move.partner_id.vat = False
        self.assertEqual(move._get_invoice_report_filename(), "FAC-00099.pdf")

    def test_action_print_pdf_free_form_pdf_uses_pdf_report(self):
        layout = self.env.ref("web.external_layout_standard", raise_if_not_found=False)
        if layout:
            self.env.company.external_report_layout_id = layout
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_free_form_print_medium = "pdf"
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        action = move.action_print_pdf()
        self.assertEqual(action.get("type"), "ir.actions.report")
        self.assertEqual(action.get("report_type"), "qweb-pdf")

    def test_get_sale_tax_values_by_type(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        result = move.get_sale_tax_values_by_type("general")
        self.assertIn("base", result)
        self.assertIn("amount", result)
        result_empty = move.get_sale_tax_values_by_type("nonexistent")
        self.assertEqual(result_empty, {"base": 0.0, "amount": 0.0})

    def test_sale_tax_data_computed(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertTrue(isinstance(move.sale_tax_data, dict))

    def test_purchase_tax_data_computed(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Supplier",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J98765432",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": supplier.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_purchase"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        self.assertTrue(isinstance(move.purchase_tax_data, dict))

    def test_compute_l10n_ve_inverse_rate_same_currency(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertEqual(move.l10n_ve_inverse_rate, 1.0)

    def test_button_draft_with_force_draft_context(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        move.with_context(force_draft=True).button_draft()
        self.assertEqual(move.state, "draft")

    def test_contingency_journal_posts_with_manual_control_without_book(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write(
            {
                "l10n_ve_control_number": "99-00000055",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        move.action_post()
        self.assertEqual(move.l10n_ve_control_number, "99-00000055")
        self.assertFalse(
            self.env["account.book.document"].search(
                [("res_model", "=", "account.move"), ("res_id", "=", move.id)]
            )
        )

    def test_contingency_requires_control_before_post(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write({"l10n_ve_invoice_date": fields.Datetime.now()})
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("N° de control", str(cm.exception))
        self.assertIn("contingencia", str(cm.exception).lower())

    def test_digital_posts_without_control_before_post(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_digital(journal)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertFalse((move.l10n_ve_control_number or "").strip())
        self.assertTrue(move.l10n_ve_invoice_date)
        self.assertTrue(move.invoice_date)

    def test_fiscal_machine_posts_without_machine_fields_or_control(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
            l10n_ve_debit_note_section_id=False,
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertFalse((move.l10n_ve_control_number or "").strip())
        self.assertTrue(move.l10n_ve_invoice_date)
        self.assertTrue(move.invoice_date)
        self.assertFalse((move.l10n_ve_serial_number or "").strip())
        move.write(
            {
                "l10n_ve_serial_number": "SN-1",
                "l10n_ve_invoice_number": "FM-99",
                "l10n_ve_report_z": "Z-1",
            }
        )
        self.assertEqual(move.l10n_ve_serial_number, "SN-1")

    def test_fiscal_machine_posts_without_control_with_machine_fields_before_post(
        self,
    ):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
            l10n_ve_debit_note_section_id=False,
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write(
            {
                "l10n_ve_serial_number": "SN-1",
                "l10n_ve_invoice_number": "FM-99",
                "l10n_ve_report_z": "Z-1",
            }
        )
        move.action_post()
        self.assertFalse((move.l10n_ve_control_number or "").strip())
        self.assertEqual(move.l10n_ve_serial_number, "SN-1")

    def _form_arch(self):
        view = self.env.ref("l10n_ve_seniat.view_move_form")
        return view.get_combined_arch()

    def test_l10n_ve_invoice_date_ui_by_emission_medium(self):
        arch = self._form_arch()
        self.assertIn(
            "state == 'draft' and l10n_ve_journal_emission_medium != 'contingency'",
            arch,
        )
        list_arch = self.env.ref("l10n_ve_seniat.view_invoice_tree").get_combined_arch()
        self.assertIn('name="l10n_ve_invoice_date"', list_arch)
        self.assertNotIn('string="Invoice Date"', list_arch)
        self.assertIn('name="l10n_ve_control_number"', list_arch)
        self.assertIn('name="l10n_ve_invoice_number"', list_arch)
        self.assertIn('name="l10n_ve_report_z"', list_arch)
        self.assertIn('name="l10n_ve_serial_number"', list_arch)

    def test_free_posted_sets_l10n_ve_invoice_date(self):
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": "free"})
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertFalse(move.l10n_ve_invoice_date)
        move.action_post()
        self.assertTrue(move.l10n_ve_invoice_date)

    def test_digital_posted_sets_l10n_ve_invoice_date(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_digital(journal)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.action_post()
        self.assertTrue(move.l10n_ve_invoice_date)

    def test_post_raises_when_journal_emission_not_on_company(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_set_company_emission_medium_codes("fiscal_machine")
        journal.write({"l10n_ve_emission_medium": "free"})
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        with self.assertRaises(ValidationError) as cm:
            move.action_post()
        self.assertIn("no está configurado", str(cm.exception))

    def test_post_allows_empty_emission_medium_without_company_medium(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_set_company_emission_medium_codes("fiscal_machine")
        journal.write(
            {
                "l10n_ve_emission_medium": False,
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write({"l10n_ve_control_number": "00-00000001"})
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_post_allows_contingency_without_company_medium(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_set_company_emission_medium_codes("fiscal_machine")
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.write(
            {
                "l10n_ve_control_number": "99-00000077",
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_draft_invoice_date_editable_without_emission_medium(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": False,
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        custom_date = date(2024, 6, 15)
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        self.assertFalse(move.l10n_ve_journal_emission_medium)
        move.write({"invoice_date": custom_date})
        self.assertEqual(move.invoice_date, custom_date)
        move.action_post()
        self.assertEqual(move.invoice_date, custom_date)

    def test_invoice_date_due_cannot_be_before_invoice_date(self):
        move = self.env["account.move"].create(
            self._create_invoice_vals(self.partner_ve)
        )
        move.invoice_date = fields.Date.today()
        with self.assertRaises(ValidationError):
            move.invoice_date_due = fields.Date.today() - relativedelta(days=1)
