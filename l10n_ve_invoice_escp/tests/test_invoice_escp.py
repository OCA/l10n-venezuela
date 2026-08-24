from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_invoice_escp.report.invoice_escp import (
    _l10n_ve_escp_invoice_margin_lines,
    _l10n_ve_max_product_table_lines,
    build_move_escp_bytes,
)
from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeInvoiceEscp(L10nVeSeniatCommon):
    def test_build_escp_contains_factura_title(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Cliente ESCP",
                        "country_id": self.env.ref("base.ve").id,
                        "vat": "J12345670",
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "L",
                            "quantity": 1.0,
                            "price_unit": 10.0,
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
        move.action_post()
        raw = build_move_escp_bytes(move)
        self.assertIn(b"FACTURA", raw)
        self.assertTrue(len(raw) > 50)

    def test_escp_margin_lines_from_talonario(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        book = journal.l10n_ve_invoice_section_id.book_id
        book.l10n_ve_escp_invoice_margin_lines = 3
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Cliente margen",
                        "country_id": self.env.ref("base.ve").id,
                        "vat": "J12345674",
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "L",
                            "quantity": 1.0,
                            "price_unit": 1.0,
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
        move.action_post()
        self.assertEqual(_l10n_ve_escp_invoice_margin_lines(move), 3)

    def test_get_payload_requires_continuous_journal(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="pdf")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Cliente ESCP 2",
                        "country_id": self.env.ref("base.ve").id,
                        "vat": "J12345671",
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "L",
                            "quantity": 1.0,
                            "price_unit": 5.0,
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
        move.action_post()
        with self.assertRaises(UserError):
            move.l10n_ve_invoice_escp_get_payload()

    def test_continuous_print_action_is_client(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Cliente ESCP 3",
                        "country_id": self.env.ref("base.ve").id,
                        "vat": "J12345672",
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "L",
                            "quantity": 1.0,
                            "price_unit": 1.0,
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
        move.action_post()
        action = move._l10n_ve_get_free_form_continuous_print_action()
        self.assertEqual(action.get("type"), "ir.actions.client")
        self.assertEqual(action.get("tag"), "l10n_ve_invoice_escp_print")
        self.assertEqual(action.get("target"), "new")
        self.assertEqual(action.get("params", {}).get("move_id"), move.id)

    def test_pad_product_lines_to_book_max(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        book = journal.l10n_ve_invoice_section_id.book_id
        book.l10n_ve_max_invoice_lines = 4
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": "Cliente pad",
                        "country_id": self.env.ref("base.ve").id,
                        "vat": "J12345673",
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Una linea",
                            "quantity": 1.0,
                            "price_unit": 2.0,
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
        move.action_post()
        self.assertEqual(_l10n_ve_max_product_table_lines(move), 4)
        raw = build_move_escp_bytes(move).decode("cp858", errors="replace")
        blank_slots = sum(
            1 for ln in raw.split("\n") if ln == " " * len(ln) and len(ln) > 50
        )
        self.assertGreaterEqual(blank_slots, 3)
