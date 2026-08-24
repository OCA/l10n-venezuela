from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_igtf.tests.common import TestL10nVeIgtfCommon


@tagged("post_install", "-at_install", "l10n_ve_integration")
class TestL10nVeCrossModuleFlows(TestL10nVeIgtfCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls._l10n_ve_configure_journal_free(cls.sale_journal)

    def test_invoice_post_assigns_control_number(self):
        invoice = self._l10n_ve_create_invoice(
            partner=self.partner,
            amounts=[100.0],
            taxes=self.env["account.tax"],
            journal=self.sale_journal,
            invoice_date=self.test_date,
            currency=self.ves,
            post=True,
        )
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.l10n_ve_control_number)
        self.assertIn("l10n_ve_igtf_collected_amount_company_currency", invoice._fields)
        self.assertIn("generate_iva_retention", invoice._fields)

    def test_invoice_igtf_payment_keeps_seniat_and_advance_fields(self):
        invoice = self._create_customer_invoice(amount=100.0, currency=self.ves)
        payment, wizard = self._register_invoice_payment(
            invoice=invoice,
            amount=self._usd_amount_for_ves(100.0),
            currency=self.usd,
            apply_igtf=True,
            igtf_included=False,
            return_wizard=True,
        )
        self.assertTrue(payment)
        self.assertTrue(wizard["l10n_ve_apply_igtf"])
        self.assertGreater(wizard["l10n_ve_igtf_amount_company_currency"], 0.0)
        self.assertEqual(invoice.state, "posted")
        register_fields = self.env["account.payment.register"]._fields
        self.assertIn("l10n_ve_apply_advance", register_fields)
        self.assertTrue(invoice.l10n_ve_control_number)

    def test_sale_order_creates_posted_invoice(self):
        self._l10n_ve_configure_journal_digital(self.sale_journal)
        product = (
            self.env["product.template"]
            .create(
                {
                    "name": "Integration product",
                    "company_id": self.company.id,
                    "list_price": 100.0,
                    "taxes_id": [
                        Command.set(self.company_data["default_tax_sale"].ids)
                    ],
                    "supplier_taxes_id": [
                        Command.set(self.company_data["default_tax_purchase"].ids)
                    ],
                }
            )
            .product_variant_ids[:1]
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        if hasattr(order, "action_l10n_ve_create_invoice"):
            order.action_l10n_ve_create_invoice()
        else:
            order._create_invoices()
        invoice = order.invoice_ids[:1]
        self.assertTrue(invoice)
        self.assertEqual(invoice.move_type, "out_invoice")
        if invoice.state == "draft":
            invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.partner_id, self.partner)

    def test_vendor_bill_exposes_withholding_flags(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.from_string("2026-03-12"),
                "ref": "INT-BILL-001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Purchase",
                            "quantity": 1.0,
                            "price_unit": 500.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    self.company_data["default_tax_purchase"].ids
                                )
                            ],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertIn("generate_iva_retention", bill._fields)
        self.assertIn("apply_islr_retention", bill._fields)
        self.assertFalse(bill.generate_iva_retention)
