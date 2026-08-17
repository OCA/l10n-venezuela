# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestCoverageExtraAccountMove(L10nVeSeniatCommon):
    def _ve_customer(self):
        return self.env["res.partner"].create(
            {
                "name": "Cliente cobertura",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )

    def test_seniat_invoice_tag_foreign_currency_includes_rate_text(self):
        self.env.company.partner_id.taxpayer_type = "formal"
        company_ccy = self.env.company.currency_id
        foreign = (
            self.env.ref("base.USD")
            if company_ccy != self.env.ref("base.USD")
            else self.env.ref("base.EUR")
        )
        today = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": today,
                "inverse_company_rate": 36.5,
            }
        )
        move = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=self._ve_customer(),
            invoice_date=today,
            amounts=[100.0],
            taxes=self.tax_sale_a,
            currency=foreign,
        )
        move.invalidate_recordset(["seniat_invoice_tag", "l10n_ve_inverse_rate"])
        tag = move.seniat_invoice_tag or ""
        self.assertIn("IGTF", tag)
        self.assertIn("tipo de cambio", tag.lower())
        self.assertGreater(move.l10n_ve_inverse_rate, 0.0)

    def test_out_refund_second_credit_exceeds_origin_total_raises(self):
        customer = self._ve_customer()
        invoice = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=customer,
            invoice_date=fields.Date.today(),
            amounts=[100.0],
            taxes=self.tax_sale_a,
            post=True,
        )
        credit_vals_base = {
            "move_type": "out_refund",
            "reversed_entry_id": invoice.id,
            "partner_id": customer.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "partial",
                        "quantity": 1.0,
                        "price_unit": 30.0,
                        "account_id": self.company_data["default_account_revenue"].id,
                        "tax_ids": [(6, 0, [self.company_data["default_tax_sale"].id])],
                    },
                )
            ],
        }
        credit1 = self.env["account.move"].create(credit_vals_base)
        credit1.action_post()
        credit2 = self.env["account.move"].create(
            {
                **credit_vals_base,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "partial 2",
                            "quantity": 1.0,
                            "price_unit": 80.0,
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
            credit2.action_post()
        self.assertIn("monto máximo", str(cm.exception).lower())

    def test_credit_note_foreign_amount_uses_line_balances(self):
        customer = self._ve_customer()
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": customer.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Credit USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        expected = abs(
            sum(
                credit.line_ids.filtered(
                    lambda line: line.display_type in ("product", "tax", "rounding")
                ).mapped("balance")
            )
        )
        self.assertEqual(credit._l10n_ve_to_company_abs_amount(), expected)
        self.assertEqual(
            credit._l10n_ve_to_company_abs_amount(),
            invoice._l10n_ve_to_company_abs_amount(),
        )

    def test_full_credit_note_usd_matches_origin_despite_total_rounding(self):
        customer = self._ve_customer()
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": False})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "rate": 0.0012968967594959428,
            }
        )
        tax = self.company_data["default_tax_sale"]
        line_vals = {
            "name": "SET ANILLO",
            "quantity": 1.0,
            "price_unit": 4.2067059522,
            "account_id": self.company_data["default_account_revenue"].id,
            "tax_ids": [(6, 0, [tax.id])] if tax else [],
        }
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [(0, 0, line_vals)],
            }
        )
        invoice.action_post()
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": customer.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [(0, 0, dict(line_vals))],
            }
        )
        self.assertEqual(
            credit._l10n_ve_to_company_abs_amount(),
            invoice._l10n_ve_to_company_abs_amount(),
        )
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_manual_credit_note_from_usd_invoice_posts_in_company_currency(self):
        customer = self._ve_customer()
        usd = self.env.ref("base.USD")
        date_invoice = fields.Date.to_date("2026-02-10")
        self.env["res.currency.rate"].create(
            {
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": customer.id,
                "currency_id": usd.id,
                "invoice_date": fields.Date.to_date("2026-02-20"),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Credit USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        credit.action_post()
        self.assertEqual(credit.currency_id, credit.company_currency_id)

    def test_reversal_wizard_creates_credit_note_in_company_currency(self):
        customer = self._ve_customer()
        usd = self.env.ref("base.USD")
        date_invoice = fields.Date.to_date("2026-03-10")
        self.env["res.currency.rate"].create(
            {
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC Bs"})
        )
        invoice.l10n_ve_invoice_original_printed = True
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self.assertEqual(credit.currency_id, credit.company_currency_id)
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        cred_line = credit.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        inv_line.ensure_one()
        cred_line.ensure_one()
        if "price_subtotal_currency" in inv_line._fields and inv_line.price_subtotal_currency:
            expected_subtotal = abs(inv_line.price_subtotal_currency)
        else:
            expected_subtotal = abs(inv_line.balance)
        expected_pu = expected_subtotal / (abs(inv_line.quantity) or 1.0)
        self.assertEqual(cred_line.price_unit, expected_pu)

    def test_manual_credit_note_keeps_foreign_currency_without_emission_medium(self):
        customer = self._ve_customer()
        usd = self.env.ref("base.USD")
        journal = self.company_data["default_journal_sale"]
        date_invoice = fields.Date.to_date("2026-04-10")
        journal.write({"l10n_ve_emission_medium": False})
        self.env["res.currency.rate"].create(
            {
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "journal_id": journal.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": customer.id,
                "journal_id": journal.id,
                "currency_id": usd.id,
                "invoice_date": fields.Date.to_date("2026-04-20"),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Credit USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        credit.action_post()
        self.assertEqual(credit.currency_id, usd)

    def test_reversal_wizard_keeps_foreign_currency_without_emission_medium(self):
        customer = self._ve_customer()
        usd = self.env.ref("base.USD")
        journal = self.company_data["default_journal_sale"]
        date_invoice = fields.Date.to_date("2026-05-10")
        journal.write({"l10n_ve_emission_medium": False})
        self.env["res.currency.rate"].create(
            {
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "journal_id": journal.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Invoice USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC misma moneda"})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self.assertEqual(credit.currency_id, usd)

    def test_debit_note_uses_debit_note_section_for_control_number(self):
        journal = self.company_data["default_journal_sale"]
        book = self.env["account.book"].create(
            {
                "name": "Talonario débito",
                "company_id": self.env.company.id,
                "number_from": 1,
                "number_to": 99999,
            }
        )
        sec_inv = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "F",
                "number_from": 1,
                "number_to": 500,
            }
        )
        sec_debit = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "D",
                "number_from": 501,
                "number_to": 1000,
            }
        )
        sec_cn = self.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "NC",
                "number_from": 1001,
                "number_to": 2000,
            }
        )
        journal.write(
            {
                "l10n_ve_invoice_section_id": sec_inv.id,
                "l10n_ve_debit_note_section_id": sec_debit.id,
                "l10n_ve_credit_note_section_id": sec_cn.id,
            }
        )
        invoice = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=self._ve_customer(),
            invoice_date=fields.Date.today(),
            amounts=[50.0],
            taxes=self.tax_sale_a,
            journal=journal,
            post=True,
        )
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
        self.assertTrue(debit_move.l10n_ve_control_number)
        doc = self.env["account.book.document"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", debit_move.id),
            ]
        )
        self.assertEqual(doc.number, 501)

    def test_ir_actions_report_pdf_without_ve_context_skips_flag(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente rep",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
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
        report = self.env.ref("account.account_invoices", raise_if_not_found=False)
        if not report:
            return
        report._render_qweb_pdf(report.report_name, move.ids)
        self.assertFalse(move.l10n_ve_invoice_original_printed)

    def test_seniat_tag_false_on_vendor_bill(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Prov cob",
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
                            "name": "C",
                            "quantity": 1.0,
                            "price_unit": 20.0,
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
        self.assertFalse(move.seniat_invoice_tag)

    def test_purchase_tax_data_on_vendor_refund_posted(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Prov NC",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J98765432",
            }
        )
        bill = self._l10n_ve_create_invoice(
            move_type="in_invoice",
            partner=supplier,
            invoice_date=fields.Date.today(),
            amounts=[90.0],
            taxes=self.tax_purchase_a,
            post=True,
        )
        refund = bill._reverse_moves(
            default_values_list=[
                {
                    "invoice_date": fields.Date.today(),
                }
            ],
        )
        refund.action_post()
        self.assertTrue(isinstance(refund.purchase_tax_data, dict))
        self.assertTrue(refund.purchase_tax_data)

    def test_entry_button_draft_allowed_in_ve(self):
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
                            "debit": 3.0,
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
                            "credit": 3.0,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        move.button_draft()
        self.assertEqual(move.state, "draft")

    def test_credit_note_limit_includes_posted_debit_notes(self):
        invoice = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=self._ve_customer(),
            invoice_date=fields.Date.today(),
            amounts=[100.0],
            taxes=self.tax_sale_a,
            post=True,
        )
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": fields.Date.today(),
                    "reason": "extra límite",
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
                            "name": "débito",
                            "quantity": 1.0,
                            "price_unit": 25.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, [self.tax_sale_a.id])],
                        },
                    )
                ]
            }
        )
        debit.action_post()
        credit_big = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "gran NC",
                            "quantity": 1.0,
                            "price_unit": 130.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, [self.company_data["default_tax_sale"].id])],
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            credit_big.action_post()

    def test_on_behalf_third_party_raises_on_invalid_third_vat(self):
        self.env.company.l10n_ve_on_behalf_of_third_party_enabled = True
        bad = self.env["res.partner"].create(
            {
                "name": "Tercero mal",
                "country_id": self.env.ref("base.ve").id,
                "vat": "invalid-rif",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self._ve_customer().id,
                "l10n_ve_third_party_partner_id": bad.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "L",
                            "quantity": 1.0,
                            "price_unit": 15.0,
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
        self.assertIn("tercero", str(cm.exception).lower())


@tagged("post_install", "-at_install")
class TestCoverageExtraNonVeCompany(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.us_accounting = cls.setup_other_company(
            name="US Seniat Cov Co",
            country_id=cls.env.ref("base.us").id,
        )

    def test_out_invoice_us_company_skips_ve_action_post_rules(self):
        company = self.us_accounting["company"]
        revenue = self.us_accounting["default_account_revenue"]
        tax = (
            self.env["account.tax"]
            .with_company(company)
            .search(
                [("company_id", "=", company.id), ("type_tax_use", "=", "sale")],
                limit=1,
            )
        )
        self.assertTrue(tax)
        partner = self.env["res.partner"].with_company(company).create(
            {
                "name": "Cliente US sin VAT",
                "country_id": self.env.ref("base.us").id,
            }
        )
        move = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": company.id,
                    "partner_id": partner.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Srv",
                                "quantity": 1.0,
                                "price_unit": 12.0,
                                "account_id": revenue.id,
                                "tax_ids": [(6, 0, tax.ids)],
                            },
                        )
                    ],
                }
            )
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertFalse(move.l10n_ve_control_number)
        name = move._get_name_invoice_report()
        self.assertNotEqual(name, "l10n_ve_seniat.report_invoice_document")

    def test_move_line_skips_ve_validation_for_us_company_invoice(self):
        company = self.us_accounting["company"]
        revenue = self.us_accounting["default_account_revenue"]
        tax = (
            self.env["account.tax"]
            .with_company(company)
            .search(
                [("company_id", "=", company.id), ("type_tax_use", "=", "sale")],
                limit=1,
            )
        )
        partner = self.env["res.partner"].create({"name": "Cliente US ml"})
        move = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": company.id,
                    "partner_id": partner.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Ln",
                                "quantity": 1.0,
                                "price_unit": 3.0,
                                "account_id": revenue.id,
                                "tax_ids": [(6, 0, tax.ids)],
                            },
                        )
                    ],
                }
            )
        )
        line = move.invoice_line_ids[0]
        line.write({"name": "Ln2"})


@tagged("post_install", "-at_install")
class TestCoverageExtraInstallMode(L10nVeSeniatCommon):
    def test_install_mode_action_post_calls_super_only(self):
        move = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=self.env["res.partner"].create(
                {
                    "name": "Inst",
                    "country_id": self.env.ref("base.ve").id,
                    "vat": "J12345678",
                }
            ),
            invoice_date=fields.Date.today(),
            amounts=[11.0],
            taxes=self.tax_sale_a,
            post=False,
        )
        move.with_context(install_mode=True).action_post()
        self.assertEqual(move.state, "posted")

    def test_get_sale_tax_values_by_type_on_new_move(self):
        move = self.env["account.move"].new({"company_id": self.env.company.id})
        self.assertEqual(
            move.get_sale_tax_values_by_type("general"),
            {"base": 0.0, "amount": 0.0},
        )


@tagged("post_install", "-at_install")
class TestCoverageExtraResPartner(L10nVeSeniatCommon):
    def test_name_search_finds_partner_by_vat_digit_group(self):
        unique_vat = "J55544433"
        p = self.env["res.partner"].create(
            {
                "name": "Cliente búsqueda VAT",
                "country_id": self.env.ref("base.ve").id,
                "vat": unique_vat,
                "customer_rank": 1,
            }
        )
        found = (
            self.env["res.partner"]
            .with_context(res_partner_search_mode="customer")
            .name_search("55544433")
        )
        ids = [f[0] for f in found]
        self.assertIn(p.id, ids)

    def test_write_country_to_ve_normalizes_existing_numeric_vat_batch(self):
        p = self.env["res.partner"].create(
            {
                "name": "Extranjero luego VE",
                "country_id": self.env.ref("base.us").id,
                "vat": "12345678",
            }
        )
        p.write({"country_id": self.env.ref("base.ve").id})
        self.assertEqual(p.vat, "V12345678")

    def test_prefix_vat_false_when_vat_does_not_match_pattern(self):
        p = self.env["res.partner"].create(
            {
                "name": "Sin prefijo parse",
                "country_id": self.env.ref("base.us").id,
                "vat": "not-a-rif",
            }
        )
        self.assertFalse(p.prefix_vat)

    def test_form_onchange_ve_vat_auto_prefix(self):
        with Form(self.env["res.partner"]) as f:
            f.name = "Onchange VAT"
            f.country_id = self.env.ref("base.ve")
            f.vat = "88888888"
            partner = f.save()
        self.assertEqual(partner.vat, "V88888888")

    def test_vat_search_variants_and_rif_like_helpers(self):
        Partner = self.env["res.partner"]
        self.assertIn("J12345678", Partner._l10n_ve_vat_search_variants("J-12345678"))
        self.assertTrue(Partner._l10n_ve_create_search_term_is_rif_like("J12345678"))
        self.assertFalse(Partner._l10n_ve_create_search_term_is_rif_like(""))
        self.assertIs(Partner._l10n_ve_normalize_vat_leading_prefix(False), False)
        self.assertEqual(Partner._l10n_ve_normalize_vat_leading_prefix("/"), "/")
        self.assertEqual(
            Partner._l10n_ve_normalize_vat_leading_prefix(12345678), "V12345678"
        )

    def test_write_vat_splits_ve_and_non_ve_partners(self):
        ve = self.env["res.partner"].create(
            {
                "name": "Mix VE",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        us = self.env["res.partner"].create(
            {
                "name": "Mix US",
                "country_id": self.env.ref("base.us").id,
            }
        )
        (ve | us).write({"vat": "12345678"})
        self.assertEqual(ve.vat, "V12345678")
        self.assertEqual(us.vat, "12345678")

    def test_prepare_create_skips_vat_normalize_with_context(self):
        vals_list = [
            {
                "name": "Ctx",
                "country_id": self.env.ref("base.ve").id,
                "vat": "12345678",
            }
        ]
        out = (
            self.env["res.partner"]
            .with_context(skip_l10n_ve_vat_auto_prefix=True)
            ._prepare_create_values(vals_list)
        )
        self.assertEqual(out[0]["vat"], "12345678")
