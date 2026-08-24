from odoo import Command, fields
from odoo.tools.misc import formatLang

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


class TestL10nVeIgtfCommon(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.company_data_ve = cls.company_data
        cls.revenue_account = cls.company_data_ve["default_account_revenue"]
        cls.receivable_account = cls.company_data_ve["default_account_receivable"]
        cls.bank_journal = cls.company_data_ve["default_journal_bank"]
        cls.sale_journal = cls.company_data_ve["default_journal_sale"]

        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.usd.rounding = 0.01
        cls.company.currency_id = cls.ves
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")

        cls.igtf_account = cls.company.l10n_ve_igtf_account_id
        if not cls.igtf_account:
            cls.igtf_account = (
                cls.env["account.account"]
                .with_company(cls.company)
                .create(
                    {
                        "name": "IGTF Payable Test",
                        "code": "2102099",
                        "account_type": "liability_current",
                        "company_ids": [Command.set([cls.company.id])],
                        "reconcile": True,
                    }
                )
            )

        cls.company.partner_id.write({"taxpayer_type": "special"})
        cls.company.write(
            {
                "l10n_ve_igtf_account_id": cls.igtf_account.id,
                "l10n_ve_igtf_percent": 3.0,
                "l10n_ve_igtf_currency_ids": [Command.set([cls.usd.id])],
                "l10n_ve_igtf_allow_invoice_accrual": False,
            }
        )

        cls.test_date = fields.Date.from_string("2026-03-12")
        cls.usd_inverse_rate = 438.21
        usd_rate = cls.env["res.currency.rate"].search(
            [
                ("name", "=", cls.test_date),
                ("currency_id", "=", cls.usd.id),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if usd_rate:
            usd_rate.inverse_company_rate = cls.usd_inverse_rate
        else:
            cls.env["res.currency.rate"].create(
                {
                    "name": cls.test_date,
                    "currency_id": cls.usd.id,
                    "company_id": cls.company.id,
                    "inverse_company_rate": cls.usd_inverse_rate,
                }
            )

        cls.partner = (
            cls.env["res.partner"]
            .with_company(cls.company)
            .create(
                {
                    "name": "IGTF Test Partner",
                    "vat": "V12345678",
                    "country_id": cls.env.ref("base.ve").id,
                    "invoice_sending_method": "manual",
                    "invoice_edi_format": False,
                    "property_account_receivable_id": cls.receivable_account.id,
                    "property_account_payable_id": cls.company_data_ve[
                        "default_account_payable"
                    ].id,
                    "company_id": False,
                }
            )
        )

    def _create_customer_invoice(self, amount, currency):
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": self.company.id,
                    "journal_id": self.sale_journal.id,
                    "partner_id": self.partner.id,
                    "currency_id": currency.id,
                    "invoice_date": self.test_date,
                    "date": self.test_date,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "IGTF Test Line",
                                "quantity": 1.0,
                                "price_unit": amount,
                                "account_id": self.revenue_account.id,
                                "tax_ids": [Command.clear()],
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()
        return invoice

    def _register_invoice_payment(
        self,
        invoice,
        amount,
        currency,
        apply_igtf=False,
        igtf_included=False,
        extra_vals=None,
        return_wizard=False,
    ):
        wizard = self._create_payment_register_wizard(
            invoice=invoice,
            amount=amount,
            currency=currency,
            apply_igtf=apply_igtf,
            igtf_included=igtf_included,
            extra_vals=extra_vals,
        )
        wizard_snapshot = {
            "l10n_ve_apply_igtf": bool(wizard.l10n_ve_apply_igtf),
            "l10n_ve_igtf_included": bool(wizard.l10n_ve_igtf_included),
            "l10n_ve_igtf_amount_company_currency": (
                wizard.l10n_ve_igtf_amount_company_currency
            ),
            "l10n_ve_igtf_amount_currency": wizard.l10n_ve_igtf_amount_currency,
            "l10n_ve_base_amount_company_currency": (
                wizard.l10n_ve_base_amount_company_currency
            ),
        }
        payments = wizard._create_payments()
        payment = payments[:1]
        self._assert_widget_payment_igtf_consistency(invoice, payment)
        if return_wizard:
            return payment, wizard_snapshot
        return payment

    def _create_payment_register_wizard(
        self,
        invoice,
        amount,
        currency,
        apply_igtf=False,
        igtf_included=False,
        extra_vals=None,
    ):
        extra_vals = extra_vals or {}
        wizard = (
            self.env["account.payment.register"]
            .with_company(self.company)
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "company_id": self.company.id,
                    "journal_id": self.bank_journal.id,
                    "payment_date": self.test_date,
                    "amount": amount,
                    "currency_id": currency.id,
                    "group_payment": True,
                    "l10n_ve_apply_igtf": apply_igtf,
                    "l10n_ve_igtf_included": igtf_included,
                    **extra_vals,
                }
            )
        )
        return wizard

    def _get_payment_igtf_line(self, payment):
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.company.l10n_ve_igtf_account_id
        )

    def _get_igtf_group_from_tax_totals(self, invoice):
        tax_totals = invoice.tax_totals or {}
        for subtotal in tax_totals.get("subtotals", []):
            for tax_group in subtotal.get("tax_groups", []):
                if "IGTF" in (tax_group.get("group_name") or ""):
                    return tax_group
        return None

    def _assert_no_writeoff_or_exchange_diff(
        self, invoice, payment, allow_exchange=False
    ):
        exchange_accounts = (
            self.company.income_currency_exchange_account_id
            | self.company.expense_currency_exchange_account_id
        )
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda line: (line.name == "Write-Off")
            or (line.account_id in exchange_accounts)
        )
        self.assertFalse(writeoff_lines)

        receivable_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        partials = (
            receivable_lines.matched_debit_ids | receivable_lines.matched_credit_ids
        )
        if not allow_exchange:
            self.assertFalse(partials.filtered("exchange_move_id"))

    def _usd_amount_for_ves(self, amount_ves):
        return self.usd.round(amount_ves / self.usd_inverse_rate)

    def _expected_igtf_company_from_payment_amount(self, payment_amount_usd):
        payment_amount_ves = self.ves.round(
            self.usd._convert(
                payment_amount_usd, self.ves, self.company, self.test_date
            )
        )
        return self.ves.round(payment_amount_ves * 0.03)

    def _assert_wizard_payment_consistency(self, wizard_data, payment):
        self.assertEqual(
            bool(wizard_data["l10n_ve_apply_igtf"]),
            bool(payment.l10n_ve_apply_igtf),
        )
        self.assertEqual(
            bool(wizard_data["l10n_ve_igtf_included"]),
            bool(payment.l10n_ve_igtf_included),
        )

        igtf_lines = self._get_payment_igtf_line(payment)
        payment_igtf_company = (
            abs(sum(igtf_lines.mapped("balance"))) if igtf_lines else 0.0
        )
        payment_igtf_currency = (
            abs(sum(igtf_lines.mapped("amount_currency"))) if igtf_lines else 0.0
        )

        self.assertAlmostEqual(
            wizard_data["l10n_ve_igtf_amount_company_currency"],
            payment_igtf_company,
            places=2,
        )
        self.assertAlmostEqual(
            wizard_data["l10n_ve_igtf_amount_currency"],
            payment_igtf_currency,
            places=2,
        )

        rate = self.company.l10n_ve_igtf_percent / 100.0
        payment_base_company = (
            self.ves.round(payment_igtf_company / rate) if rate else 0.0
        )
        self.assertAlmostEqual(
            wizard_data["l10n_ve_base_amount_company_currency"],
            payment_base_company,
            places=2,
        )

        self.assertAlmostEqual(
            payment.l10n_ve_igtf_amount_company_currency,
            payment_igtf_company,
            places=2,
        )
        self.assertAlmostEqual(
            payment.l10n_ve_igtf_amount_currency,
            payment_igtf_currency,
            places=2,
        )

    def _assert_widget_payment_igtf_consistency(self, invoice, payment):
        invoice.invalidate_recordset()
        widget = invoice.invoice_payments_widget or {}
        content = widget.get("content") or []
        widget_lines = (
            list(content.values()) if isinstance(content, dict) else list(content)
        )
        payment_line = next(
            (
                line
                for line in widget_lines
                if line.get("account_payment_id") == payment.id
                and not line.get("is_exchange")
            ),
            None,
        )
        self.assertTrue(payment_line)

        partial = self.env["account.partial.reconcile"].browse(
            payment_line.get("partial_id")
        )
        widget_currency = invoice.currency_id
        igtf_lines = self._get_payment_igtf_line(payment)
        total_igtf_company = payment.company_currency_id.round(
            abs(sum(igtf_lines.mapped("balance")))
        )

        if not partial.exists() or payment.company_currency_id.is_zero(
            total_igtf_company
        ):
            self.assertFalse(payment_line.get("l10n_ve_igtf_amount"))
            return

        pay_line = (
            partial.debit_move_id
            if partial.debit_move_id.payment_id == payment
            else partial.credit_move_id
            if partial.credit_move_id.payment_id == payment
            else False
        )
        self.assertTrue(pay_line)
        matched_partials = (
            pay_line.matched_debit_ids | pay_line.matched_credit_ids
        ).filtered(lambda pr: not pr.exchange_move_id)
        total_net_paymentline_widget = 0.0
        for pr in matched_partials:
            line_currency = (
                pr.debit_currency_id
                if pr.debit_move_id == pay_line
                else pr.credit_currency_id
            )
            amt = (
                abs(pr.debit_amount_currency)
                if pr.debit_move_id == pay_line
                else abs(pr.credit_amount_currency)
            )
            total_net_paymentline_widget += (
                amt
                if line_currency == widget_currency
                else line_currency._convert(
                    amt,
                    widget_currency,
                    payment.company_id,
                    pr.max_date,
                )
            )
        if widget_currency.is_zero(total_net_paymentline_widget):
            if not payment.l10n_ve_apply_igtf:
                self.assertFalse(payment_line.get("l10n_ve_igtf_amount"))
            return

        allocation_ratio = (
            payment_line.get("l10n_ve_net_amount", payment_line.get("amount", 0.0))
            / total_net_paymentline_widget
        )
        expected_company_igtf = payment.company_currency_id.round(
            total_igtf_company * allocation_ratio
        )
        expected_widget_igtf = widget_currency.round(
            payment.company_currency_id._convert(
                expected_company_igtf,
                widget_currency,
                payment.company_id,
                partial.max_date,
            )
        )

        widget_igtf_amount = payment_line.get("l10n_ve_igtf_amount", 0.0)
        self.assertAlmostEqual(widget_igtf_amount, expected_widget_igtf, places=2)
        self.assertEqual(
            payment_line.get("l10n_ve_igtf_amount_formatted"),
            formatLang(self.env, expected_widget_igtf, currency_obj=widget_currency),
        )
        self.assertEqual(
            payment_line.get("l10n_ve_igtf_amount_company_currency_formatted"),
            formatLang(
                self.env,
                expected_company_igtf,
                currency_obj=payment.company_currency_id,
            ),
        )
        invoice.invalidate_recordset()
