from unittest import SkipTest

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPaymentAdvanceFullLocalization(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        required_fields = {
            "account.payment": {"is_retention", "l10n_ve_apply_igtf"},
            "account.payment.register": {
                "is_retention",
                "l10n_ve_apply_igtf",
                "l10n_ve_apply_advance",
            },
        }
        for model_name, field_names in required_fields.items():
            if not field_names.issubset(cls.env[model_name]._fields):
                raise SkipTest(
                    "The full Venezuelan localization is required for these tests."
                )

        cls.company = cls.env.company
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.venezuela = cls.env.ref("base.ve")
        cls.test_date = fields.Date.from_string("2026-01-15")
        cls.ves.active = True
        cls.usd.active = True
        cls.customer_advance_account = cls._create_account(
            "Customer Advances",
            "2180001",
            "liability_current",
        )
        cls.supplier_advance_account = cls._create_account(
            "Supplier Advances",
            "1180001",
            "asset_prepayments",
        )
        cls.partner_customer_advance_account = cls._create_account(
            "Partner Customer Advances",
            "2180002",
            "liability_current",
        )
        cls.igtf_account = cls._create_account(
            "IGTF Payable",
            "2180003",
            "liability_current",
        )
        cls.retention_account = cls._create_account(
            "IVA Retention Receivable",
            "1180002",
            "asset_current",
        )
        cls.retention_payable_account = cls._create_account(
            "IVA Retention Payable",
            "2180004",
            "liability_current",
        )

        cls.company.partner_id.with_context(l10n_ve_skip_igtf_account_check=True).write(
            {
                "country_id": cls.venezuela.id,
                "vat": "J770023598",
                "taxpayer_type": "special",
            }
        )
        cls.company.with_context(l10n_ve_skip_igtf_account_check=True).write(
            {
                "currency_id": cls.ves.id,
                "country_id": cls.venezuela.id,
                "account_fiscal_country_id": cls.venezuela.id,
                "l10n_ve_igtf_account_id": cls.igtf_account.id,
                "l10n_ve_igtf_percent": 3.0,
                "l10n_ve_igtf_currency_ids": [Command.set(cls.usd.ids)],
                "l10n_ve_igtf_allow_invoice_accrual": False,
            }
        )
        cls.env["account.tax.group"].search(
            [("company_id", "=", cls.company.id)]
        ).write({"country_id": cls.venezuela.id})
        cls.env["account.tax"].search([("company_id", "=", cls.company.id)]).write(
            {"country_id": cls.venezuela.id}
        )
        cls.sale_tax = cls.company_data["default_tax_sale"]
        cls.sale_tax.write(
            {
                "amount": 16.0,
                "price_include_override": "tax_excluded",
                "country_id": cls.venezuela.id,
            }
        )
        cls.purchase_tax = cls.company_data["default_tax_purchase"]
        cls.purchase_tax.write(
            {
                "amount": 16.0,
                "price_include_override": "tax_excluded",
                "country_id": cls.venezuela.id,
            }
        )
        cls._set_currency_rate()

        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.purchase_journal = cls.company_data["default_journal_purchase"]
        cls.bank_journal.currency_id = False
        cls.inbound_payment_method = cls.bank_journal.inbound_payment_method_line_ids[
            :1
        ]
        cls.outbound_payment_method = cls.bank_journal.outbound_payment_method_line_ids[
            :1
        ]
        cls.partner = (
            cls.env["res.partner"]
            .with_company(cls.company)
            .create(
                {
                    "name": "Advance Integration Customer",
                    "country_id": cls.venezuela.id,
                    "vat": "V12345678",
                    "property_account_receivable_id": cls.company_data[
                        "default_account_receivable"
                    ].id,
                    "property_account_payable_id": cls.company_data[
                        "default_account_payable"
                    ].id,
                }
            )
        )
        cls.retention_journal = cls.env["account.journal"].create(
            {
                "name": "Customer IVA Retentions",
                "code": "TIC",
                "type": "bank",
                "company_id": cls.company.id,
                "default_account_id": cls.retention_account.id,
            }
        )
        (
            cls.retention_journal.inbound_payment_method_line_ids
            | cls.retention_journal.outbound_payment_method_line_ids
        ).write({"payment_account_id": cls.retention_account.id})
        cls.company.iva_customer_retention_journal_id = cls.retention_journal
        cls.supplier_retention_journal = cls.env["account.journal"].create(
            {
                "name": "Supplier IVA Retentions",
                "code": "TIP",
                "type": "bank",
                "company_id": cls.company.id,
                "default_account_id": cls.retention_payable_account.id,
            }
        )
        (
            cls.supplier_retention_journal.inbound_payment_method_line_ids
            | cls.supplier_retention_journal.outbound_payment_method_line_ids
        ).write({"payment_account_id": cls.retention_payable_account.id})
        cls.company.iva_supplier_retention_journal_id = cls.supplier_retention_journal
        withholding_type = cls.env.ref(
            "l10n_ve_withholding.account_withholding_type_75",
            raise_if_not_found=False,
        )
        if withholding_type:
            cls.partner.withholding_type_id = withholding_type

    @classmethod
    def _create_account(cls, name, code, account_type):
        return cls.env["account.account"].create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "reconcile": True,
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )

    @classmethod
    def _set_currency_rate(cls):
        values = {
            "name": cls.test_date,
            "currency_id": cls.usd.id,
            "company_id": cls.company.id,
        }
        if "inverse_company_rate" in cls.env["res.currency.rate"]._fields:
            values["inverse_company_rate"] = 100.0
        else:
            values["rate"] = 0.01
        cls.env["res.currency.rate"].create(values)

    def setUp(self):
        super().setUp()
        self.partner.with_company(self.company).write(
            {
                "property_account_customer_advance_id": False,
                "property_account_supplier_advance_id": False,
            }
        )
        self.company.write(
            {
                "account_customer_advance_id": False,
                "account_supplier_advance_id": False,
                "l10n_ve_igtf_currency_ids": [Command.set(self.usd.ids)],
            }
        )

    def _configure_company_advance_accounts(self):
        self.company.write(
            {
                "account_customer_advance_id": self.customer_advance_account.id,
                "account_supplier_advance_id": self.supplier_advance_account.id,
            }
        )

    def _create_invoice(
        self,
        amount=100.0,
        currency=None,
        move_type="out_invoice",
        tax=None,
    ):
        account = (
            self.company_data["default_account_revenue"]
            if move_type == "out_invoice"
            else self.company_data["default_account_expense"]
        )
        journal = (
            self.sale_journal if move_type == "out_invoice" else self.purchase_journal
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "company_id": self.company.id,
                "journal_id": journal.id,
                "partner_id": self.partner.id,
                "currency_id": (currency or self.ves).id,
                "invoice_date": self.test_date,
                "date": self.test_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Advance integration line",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": account.id,
                            "tax_ids": [
                                Command.set(tax.ids) if tax else Command.clear()
                            ],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_standalone_payment(
        self,
        amount,
        payment_type="inbound",
        partner_type="customer",
        currency=None,
    ):
        method = (
            self.inbound_payment_method
            if payment_type == "inbound"
            else self.outbound_payment_method
        )
        payment = self.env["account.payment"].create(
            {
                "date": self.test_date,
                "amount": amount,
                "payment_type": payment_type,
                "partner_type": partner_type,
                "partner_id": self.partner.id,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": method.id,
                "currency_id": (currency or self.ves).id,
            }
        )
        payment.action_post()
        return payment

    def _create_payment_wizard(self, invoice, amount, currency=None, **values):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "company_id": self.company.id,
                    "journal_id": self.bank_journal.id,
                    "payment_date": self.test_date,
                    "amount": amount,
                    "currency_id": (currency or invoice.currency_id).id,
                    "group_payment": True,
                    **values,
                }
            )
        )

    def _create_iva_retention(self, invoice, retention_type, number):
        return self.env["account.retention"].create(
            {
                "name": "IVA Retention Integration",
                "type_retention": "iva",
                "type": retention_type,
                "partner_id": invoice.partner_id.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "number": number,
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "IVA Retention",
                            "move_id": invoice.id,
                            "invoice_amount": invoice.amount_untaxed,
                            "iva_amount": invoice.amount_tax,
                            "invoice_total": invoice.amount_total,
                            "aliquot": 75.0,
                            "retention_amount": invoice.amount_tax * 0.75,
                        }
                    )
                ],
            }
        )

    def _get_account_lines(self, payment, account):
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == account
        )

    def test_payment_without_advance_configuration_uses_partner_accounts(self):
        customer_payment = self._create_standalone_payment(100.0)
        supplier_payment = self._create_standalone_payment(
            80.0,
            payment_type="outbound",
            partner_type="supplier",
        )

        self.assertEqual(
            customer_payment.destination_account_id,
            self.partner.property_account_receivable_id,
        )
        self.assertEqual(
            supplier_payment.destination_account_id,
            self.partner.property_account_payable_id,
        )
        self.assertFalse(
            self._get_account_lines(customer_payment, self.customer_advance_account)
        )
        self.assertFalse(
            self._get_account_lines(supplier_payment, self.supplier_advance_account)
        )

    def test_company_configuration_routes_standalone_advances(self):
        self._configure_company_advance_accounts()

        customer_payment = self._create_standalone_payment(100.0)
        supplier_payment = self._create_standalone_payment(
            80.0,
            payment_type="outbound",
            partner_type="supplier",
        )

        self.assertEqual(
            customer_payment.destination_account_id,
            self.customer_advance_account,
        )
        self.assertEqual(
            supplier_payment.destination_account_id,
            self.supplier_advance_account,
        )
        self.assertTrue(
            self._get_account_lines(customer_payment, self.customer_advance_account)
        )
        self.assertTrue(
            self._get_account_lines(supplier_payment, self.supplier_advance_account)
        )

    def test_partner_configuration_overrides_company_configuration(self):
        self._configure_company_advance_accounts()
        self.partner.with_company(
            self.company
        ).property_account_customer_advance_id = self.partner_customer_advance_account

        payment = self._create_standalone_payment(100.0)

        self.assertEqual(
            payment.destination_account_id,
            self.partner_customer_advance_account,
        )
        self.assertTrue(
            self._get_account_lines(payment, self.partner_customer_advance_account)
        )

    def test_customer_overpayment_keeps_difference_as_advance(self):
        self._configure_company_advance_accounts()
        invoice = self._create_invoice()
        overpayment_amount = invoice.amount_residual + 20.0
        wizard = self._create_payment_wizard(invoice, overpayment_amount)
        wizard.payment_difference_handling = "advance"

        payment = wizard._create_payments()
        invoice.invalidate_recordset()
        advance_lines = self._get_account_lines(
            payment,
            self.customer_advance_account,
        )

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(payment.payment_has_invoice_lines)
        self.assertTrue(advance_lines)
        self.assertAlmostEqual(abs(sum(advance_lines.mapped("balance"))), 20.0)

    def test_customer_advance_can_be_applied_to_invoice(self):
        self._configure_company_advance_accounts()
        source_payment = self._create_standalone_payment(120.0)
        advance_line = self._get_account_lines(
            source_payment,
            self.customer_advance_account,
        )
        invoice = self._create_invoice()
        application_amount = invoice.amount_residual
        wizard = self._create_payment_wizard(
            invoice,
            application_amount,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )

        application_payment = wizard._create_payments()
        invoice.invalidate_recordset()
        advance_line.invalidate_recordset()

        self.assertTrue(application_payment.l10n_ve_is_advance_application)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(
            abs(advance_line.amount_residual),
            source_payment.amount - application_amount,
        )

    def test_empty_igtf_currency_configuration_does_not_tax_advance(self):
        self._configure_company_advance_accounts()
        self.company.l10n_ve_igtf_currency_ids = [Command.clear()]

        payment = self._create_standalone_payment(1.0, currency=self.usd)

        self.assertEqual(
            payment.destination_account_id,
            self.customer_advance_account,
        )
        self.assertFalse(self._get_account_lines(payment, self.igtf_account))

    def test_standalone_advance_in_igtf_currency_does_not_generate_igtf(self):
        self._configure_company_advance_accounts()

        payment = self._create_standalone_payment(1.0, currency=self.usd)

        self.assertEqual(
            payment.destination_account_id,
            self.customer_advance_account,
        )
        self.assertFalse(payment.l10n_ve_apply_igtf)
        self.assertFalse(self._get_account_lines(payment, self.igtf_account))

    def test_igtf_overpayment_keeps_surplus_as_advance(self):
        self._configure_company_advance_accounts()
        invoice = self._create_invoice(amount=100.0, currency=self.ves)
        payment_amount = (invoice.amount_residual + 50.0) / 100.0
        wizard = self._create_payment_wizard(
            invoice,
            payment_amount,
            currency=self.usd,
            l10n_ve_apply_igtf=True,
        )
        wizard.payment_difference_handling = "advance"

        payment = wizard._create_payments()
        invoice.invalidate_recordset()
        igtf_lines = self._get_account_lines(payment, self.igtf_account)
        advance_lines = self._get_account_lines(
            payment,
            self.customer_advance_account,
        )

        self.assertEqual(
            invoice.payment_state,
            "paid",
            (
                f"Residual: {invoice.amount_residual}; "
                f"IGTF: {sum(igtf_lines.mapped('balance'))}; "
                f"advance: {sum(advance_lines.mapped('balance'))}"
            ),
        )
        self.assertTrue(igtf_lines)
        self.assertAlmostEqual(
            abs(sum(igtf_lines.mapped("balance"))),
            self.ves.round(invoice.amount_total * 0.03),
        )
        self.assertTrue(advance_lines)

    def test_applying_advance_in_igtf_currency_does_not_generate_igtf(self):
        self._configure_company_advance_accounts()
        invoice = self._create_invoice(amount=1.0, currency=self.usd)
        source_payment = self._create_standalone_payment(
            invoice.amount_residual,
            currency=self.usd,
        )
        advance_line = self._get_account_lines(
            source_payment,
            self.customer_advance_account,
        )
        wizard = self._create_payment_wizard(
            invoice,
            invoice.amount_residual,
            currency=self.usd,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
            l10n_ve_apply_igtf=False,
        )

        payment = wizard._create_payments()

        self.assertTrue(payment.l10n_ve_is_advance_application)
        self.assertFalse(payment.l10n_ve_apply_igtf)
        self.assertFalse(self._get_account_lines(payment, self.igtf_account))

    def test_iva_retention_payment_does_not_become_advance_or_igtf(self):
        self._configure_company_advance_accounts()
        invoice = self._create_invoice(amount=100.0, tax=self.sale_tax)
        retention_line = self.env["account.retention.line"].create(
            {
                "name": "IVA Retention",
                "move_id": invoice.id,
                "invoice_amount": invoice.amount_untaxed,
                "iva_amount": invoice.amount_tax,
                "invoice_total": invoice.amount_total,
                "aliquot": 75.0,
                "retention_amount": invoice.amount_tax * 0.75,
            }
        )
        wizard = self._create_payment_wizard(
            invoice,
            retention_line.retention_amount,
            is_retention=True,
            voucher_date=self.test_date,
            retention_ref="20260100000001",
            retention_line_ids=[Command.set(retention_line.ids)],
        )
        wizard.journal_id = self.retention_journal

        payment = wizard._create_payments()

        self.assertTrue(payment.is_retention)
        self.assertTrue(payment.payment_has_invoice_lines)
        self.assertEqual(
            payment.destination_account_id,
            self.partner.property_account_receivable_id,
        )
        self.assertFalse(
            self._get_account_lines(payment, self.customer_advance_account)
        )
        self.assertFalse(self._get_account_lines(payment, self.igtf_account))

    def test_customer_iva_retention_from_form_does_not_become_advance(self):
        self._configure_company_advance_accounts()
        invoice = self._create_invoice(amount=100.0, tax=self.sale_tax)

        retention = self._create_iva_retention(
            invoice,
            "out_invoice",
            "20260100000002",
        )
        payment = retention.payment_ids

        self.assertTrue(payment.is_retention)
        self.assertEqual(
            payment.destination_account_id,
            self.partner.property_account_receivable_id,
        )
        self.assertFalse(
            self._get_account_lines(payment, self.customer_advance_account)
        )

        retention.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertFalse(
            self._get_account_lines(payment, self.customer_advance_account)
        )

    def test_supplier_iva_retention_from_form_does_not_become_advance(self):
        self._configure_company_advance_accounts()
        bill = self._create_invoice(
            amount=100.0,
            move_type="in_invoice",
            tax=self.purchase_tax,
        )

        retention = self._create_iva_retention(
            bill,
            "in_invoice",
            "20260100000003",
        )
        payment = retention.payment_ids

        self.assertTrue(payment.is_retention)
        self.assertEqual(
            payment.destination_account_id,
            self.partner.property_account_payable_id,
        )
        self.assertFalse(
            self._get_account_lines(payment, self.supplier_advance_account)
        )

        retention.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertFalse(
            self._get_account_lines(payment, self.supplier_advance_account)
        )

    def test_advance_application_requires_configured_account(self):
        invoice = self._create_invoice()
        unrelated_line = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        wizard = self._create_payment_wizard(
            invoice,
            10.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=unrelated_line.id,
        )

        with self.assertRaises(UserError):
            wizard._create_payments()
