# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountBook(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book_user = new_test_user(
            cls.env,
            login="l10n_ve_book_invoice_user",
            groups="account.group_account_invoice",
        )
    def _new_entry_move(self):
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )

    def _fill_correlatives(self, book, section, from_n, to_n):
        for n in range(int(from_n), int(to_n) + 1):
            move = self._new_entry_move()
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": section.id,
                    "number": n,
                    "res_model": "account.move",
                    "res_id": move.id,
                }
            )

    def test_setup_guide_html_and_compute_fields(self):
        html = self.env["account.book"].l10n_ve_setup_guide_html()
        self.assertIn("talonario", html.lower())
        book = self.env["account.book"].create(
            {
                "name": "Libro guía",
                "company_id": self.env.company.id,
                "number_from": 10,
                "number_to": 1000,
            }
        )
        self.assertTrue(book.paperformat_id)
        self.assertEqual(book.paperformat_id.header_spacing, 30)
        book.write({"l10n_ve_invoice_header_spacing": 55})
        book.paperformat_id.invalidate_recordset()
        self.assertEqual(book.paperformat_id.header_spacing, 55)
        sec = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "A",
                "number_from": 10,
                "number_to": 500,
            }
        )
        self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": sec.id,
                "number": 10,
                "res_model": "account.move",
                "res_id": self.env["account.move"].create(
                    {
                        "move_type": "entry",
                        "line_ids": [
                            (
                                0,
                                0,
                                {
                                    "name": "x",
                                    "account_id": self.company_data[
                                        "default_account_revenue"
                                    ].id,
                                    "debit": 1.0,
                                    "credit": 0.0,
                                },
                            ),
                            (
                                0,
                                0,
                                {
                                    "name": "y",
                                    "account_id": self.company_data[
                                        "default_account_expense"
                                    ].id,
                                    "debit": 0.0,
                                    "credit": 1.0,
                                },
                            ),
                        ],
                    }
                ).id,
            }
        )
        book.invalidate_recordset(
            ["section_count", "document_count", "l10n_ve_setup_guide"]
        )
        self.assertEqual(book.section_count, 1)
        self.assertEqual(book.document_count, 1)
        self.assertTrue(book.l10n_ve_setup_guide)

    def test_write_series_prefix_syncs_sequences(self):
        book = self.env["account.book"].create(
            {
                "name": "Sync prefijo",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 500,
                "l10n_ve_series_prefix": "00",
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 500,
            }
        )
        seq_before = section.l10n_ve_sequence_id
        self.assertTrue(seq_before)
        book.write({"l10n_ve_series_prefix": "10"})
        section.invalidate_recordset(["l10n_ve_sequence_id"])
        seq_after = section.l10n_ve_sequence_id
        self.assertTrue(seq_after)
        self.assertEqual((seq_after.prefix or "").rstrip("-"), "10")

    def test_action_l10n_ve_sync_section_sequences(self):
        book = self.env["account.book"].create(
            {
                "name": "Sync action",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 200,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "T",
                "number_from": 1,
                "number_to": 200,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        section.l10n_ve_sequence_id.sudo().write({"number_next": 99})
        book.action_l10n_ve_sync_section_sequences()
        self.assertEqual(section.l10n_ve_sequence_id.sudo().number_next, 2)

    def test_last_document_wrong_book_raises(self):
        book_a = self.env["account.book"].create(
            {
                "name": "A",
                "company_id": self.env.company.id,
                "number_from": 0,
                "number_to": 100,
            }
        )
        book_b = self.env["account.book"].create(
            {
                "name": "B",
                "company_id": self.env.company.id,
                "number_from": 0,
                "number_to": 100,
            }
        )
        section_b = self.env["account.book.section"].create(
            {
                "book_id": book_b.id,
                "name": "Sb",
                "number_from": 0,
                "number_to": 100,
            }
        )
        with self.assertRaises(ValidationError):
            book_a._l10n_ve_last_document_in_section_span(section_b)

    def test_next_correlative_exhausted_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Exhaust",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 10,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "One",
                "number_from": 5,
                "number_to": 5,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 5,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        with self.assertRaises(ValidationError):
            book._l10n_ve_next_correlative_number_for_section(section)

    def test_sections_overlap_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Overlap",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 1000,
            }
        )
        self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "X",
                "number_from": 1,
                "number_to": 50,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["account.book.section"].create(
                {
                    "book_id": book.id,
                    "name": "Y",
                    "number_from": 40,
                    "number_to": 80,
                }
            )

    def test_section_outside_book_range_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Rango libro",
                "company_id": self.env.company.id,
                "number_from": 10,
                "number_to": 100,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["account.book.section"].create(
                {
                    "book_id": book.id,
                    "name": "Fuera",
                    "number_from": 1,
                    "number_to": 50,
                }
            )

    def test_shrink_book_with_correlative_outside_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Encoger",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 10,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 10,
            }
        )
        self._fill_correlatives(book, section, 1, 5)
        with self.assertRaises(ValidationError):
            book.write({"number_to": 3})

    def test_unlink_book_removes_documents(self):
        book = self.env["account.book"].create(
            {
                "name": "Borrar",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 50,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 50,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        doc = self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        doc_id = doc.id
        book.unlink()
        self.assertFalse(self.env["account.book.document"].browse(doc_id).exists())

    def test_section_name_get_without_name(self):
        book = self.env["account.book"].create(
            {
                "name": "NG",
                "company_id": self.env.company.id,
                "number_from": 20,
                "number_to": 30,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": False,
                "number_from": 20,
                "number_to": 30,
            }
        )
        self.assertEqual(section.name_get()[0][1], "20-30")

    def test_section_write_book_id_recreates_sequence(self):
        book1 = self.env["account.book"].create(
            {
                "name": "B1",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        book2 = self.env["account.book"].create(
            {
                "name": "B2",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book1.id,
                "name": "Mover",
                "number_from": 1,
                "number_to": 50,
            }
        )
        old_seq_id = section.l10n_ve_sequence_id.id
        section.write({"book_id": book2.id})
        self.assertTrue(section.l10n_ve_sequence_id)
        self.assertNotEqual(section.l10n_ve_sequence_id.id, old_seq_id)

    def test_document_disallowed_model_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Mod",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 100,
            }
        )
        partner = self.env["res.partner"].create({"name": "X"})
        with self.assertRaises(ValidationError):
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": section.id,
                    "number": 1,
                    "res_model": "res.partner",
                    "res_id": partner.id,
                }
            )

    def test_document_write_number_forbidden(self):
        book = self.env["account.book"].create(
            {
                "name": "W",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 100,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        doc = self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        with self.assertRaises(ValidationError):
            doc.with_user(self.book_user).write({"number": 2})

    def test_document_unlink_without_context_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "U",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 100,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        doc = self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        with self.assertRaises(ValidationError):
            doc.with_user(self.book_user).unlink()

    def test_correlative_gap_in_section_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Gap",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 100,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        move2 = move.copy()
        with self.assertRaises(ValidationError):
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": section.id,
                    "number": 3,
                    "res_model": "account.move",
                    "res_id": move2.id,
                }
            )

    def test_correlative_wrong_section_span_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Span",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 100,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 10,
                "number_to": 20,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        with self.assertRaises(ValidationError):
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": section.id,
                    "number": 5,
                    "res_model": "account.move",
                    "res_id": move.id,
                }
            )

    def test_section_shrink_with_document_outside_new_range_raises(self):
        book = self.env["account.book"].create(
            {
                "name": "Shrink sec",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 10,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 10,
            }
        )
        self._fill_correlatives(book, section, 1, 5)
        with self.assertRaises(ValidationError):
            section.write({"number_to": 3})

    def test_source_record_compute_false_when_missing_record(self):
        book = self.env["account.book"].create(
            {
                "name": "Ref",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 10,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 10,
            }
        )
        bad_id = self.env["account.move"].search([], order="id desc", limit=1).id + 999_999
        doc = self.env["account.book.document"].create(
            {
                "book_id": book.id,
                "section_id": section.id,
                "number": 1,
                "res_model": "account.move",
                "res_id": bad_id,
            }
        )
        doc.invalidate_recordset(["source_record"])
        self.assertFalse(doc.source_record.exists())

    def test_selection_document_ref_includes_account_move(self):
        selection = self.env["account.book.document"]._selection_document_ref()
        codes = [c for c, _lbl in selection]
        self.assertIn("account.move", codes)

    def test_document_company_must_match_book_company(self):
        us_acc = self.setup_other_company(
            name="US book doc",
            country_id=self.env.ref("base.us").id,
        )
        us_company = us_acc["company"]
        book = self.env["account.book"].create(
            {
                "name": "Libro VE",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 50,
            }
        )
        section = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "S",
                "number_from": 1,
                "number_to": 50,
            }
        )
        revenue_us = us_acc["default_account_revenue"]
        tax_us = (
            self.env["account.tax"]
            .with_company(us_company)
            .search(
                [("company_id", "=", us_company.id), ("type_tax_use", "=", "sale")],
                limit=1,
            )
        )
        partner_us = self.env["res.partner"].with_company(us_company).create(
            {
                "name": "P us",
                "country_id": self.env.ref("base.us").id,
            }
        )
        move_us = (
            self.env["account.move"]
            .with_company(us_company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": us_company.id,
                    "partner_id": partner_us.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "x",
                                "quantity": 1.0,
                                "price_unit": 1.0,
                                "account_id": revenue_us.id,
                                "tax_ids": [(6, 0, tax_us.ids)],
                            },
                        )
                    ],
                }
            )
        )
        move_us.action_post()
        with self.assertRaises(ValidationError):
            self.env["account.book.document"].create(
                {
                    "book_id": book.id,
                    "section_id": section.id,
                    "number": 1,
                    "res_model": "account.move",
                    "res_id": move_us.id,
                }
            )
