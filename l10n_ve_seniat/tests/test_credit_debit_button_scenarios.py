# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestCreditDebitButtonScenarios(L10nVeSeniatCommon):
    """Matriz de visibilidad NC / ND / alerta ND adicional (casos 1–7)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE botones",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J99887766",
            }
        )
        cls._setup_payment_currencies()
        cls._setup_contingency_journal()
        cls._control_seq = 99000200

    @classmethod
    def _setup_payment_currencies(cls):
        cls.ves = cls.env.company.currency_id
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True
        cls.test_date = fields.Date.today()
        cls.usd_rate = 400.0
        rate = cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", cls.usd.id),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
            order="name desc",
        )
        if rate:
            rate.inverse_company_rate = cls.usd_rate
        else:
            cls.env["res.currency.rate"].create(
                {
                    "name": cls.test_date,
                    "currency_id": cls.usd.id,
                    "company_id": cls.env.company.id,
                    "inverse_company_rate": cls.usd_rate,
                }
            )
        if "l10n_ve_igtf_percent" in cls.env.company._fields:
            cls.env.company.partner_id.write({"taxpayer_type": "special"})
            cls.env.company.write(
                {
                    "l10n_ve_igtf_percent": 3.0,
                    "l10n_ve_igtf_currency_ids": [Command.set([cls.usd.id])],
                }
            )

    @classmethod
    def _setup_contingency_journal(cls):
        journal = cls.company_data["default_journal_sale"]
        book = cls.env["account.book"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        if not book:
            book = cls.env["account.book"].create(
                {
                    "name": "Talonario botones NC/ND",
                    "company_id": cls.env.company.id,
                    "number_from": 1,
                    "number_to": 99_999_999,
                }
            )
        section = cls.env["account.book.section"].search(
            [("book_id", "=", book.id)], limit=1
        )
        if not section:
            section = cls.env["account.book.section"].create(
                {
                    "book_id": book.id,
                    "name": "Ventas",
                    "number_from": 1,
                    "number_to": 99_999_999,
                }
            )
        journal.write(
            {
                "l10n_ve_emission_medium": "contingency",
                "l10n_ve_invoice_section_id": section.id,
                "l10n_ve_credit_note_section_id": section.id,
                "l10n_ve_debit_note_section_id": section.id,
            }
        )

    def _next_control_number(self):
        self._control_seq += 1
        return f"99-{self._control_seq:08d}"

    def _usd_amount_for_ves(self, amount_ves):
        return self.usd.round(amount_ves / self.usd_rate)

    def _assert_credit_debit_buttons(
        self,
        move,
        credit_note=False,
        debit_note=False,
        debit_alert=False,
        msg="",
    ):
        prefix = f"{msg}: " if msg else ""
        self.assertEqual(
            move.l10n_ve_show_credit_note_action,
            credit_note,
            f"{prefix}NC esperada={credit_note}",
        )
        self.assertEqual(
            move.l10n_ve_show_debit_note_action,
            debit_note,
            f"{prefix}ND esperada={debit_note}",
        )
        self.assertEqual(
            move.l10n_ve_show_unreversed_debit_note_alert,
            debit_alert,
            f"{prefix}alerta ND esperada={debit_alert}",
        )

    def _aliquot_taxes(self):
        TaxGroup = self.env["account.tax.group"]
        company = self.env.company
        taxes = []
        for group in TaxGroup._l10n_ve_get_report_tax_groups(company):
            tax = group._l10n_ve_get_representative_tax("sale")
            if tax:
                taxes.append(tax)
        return taxes

    def _resolve_aliquot_taxes(self):
        company = self.env.company
        Tax = self.env["account.tax"]
        TaxGroup = self.env["account.tax.group"]
        amount_by_type = {
            "exempt": 0.0,
            "reduced": 8.0,
            "general": 16.0,
            "extend": 31.0,
        }
        resolved = []
        for group in TaxGroup._l10n_ve_get_report_tax_groups(company):
            report_type = group._l10n_ve_get_report_type()
            tax = group._l10n_ve_get_representative_tax("sale")
            if not tax and report_type:
                tax = Tax.search(
                    [
                        ("company_id", "=", company.id),
                        ("type_tax_use", "=", "sale"),
                        ("amount", "=", amount_by_type.get(report_type, 0.0)),
                    ],
                    limit=1,
                )
            if tax:
                resolved.append(tax)
        if not resolved:
            resolved = [self.company_data["default_tax_sale"]]
        return resolved

    def _create_multi_aliquot_invoice(self):
        taxes = self._resolve_aliquot_taxes()
        prices = [1000.0, 2000.0, 3000.0, 4000.0]
        line_specs = [
            (tax, prices[idx % len(prices)], f"Producto alícuota {tax.amount}%")
            for idx, tax in enumerate(taxes)
        ]
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_date": self.test_date,
                "l10n_ve_control_number": self._next_control_number(),
                "l10n_ve_invoice_date": fields.Datetime.now(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": name,
                            "quantity": 1.0,
                            "price_unit": price,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set([tax.id])] if tax else [],
                        }
                    )
                    for tax, price, name in line_specs
                ],
            }
        )
        if not invoice.invoice_line_ids:
            raise AssertionError("La factura de prueba no tiene líneas.")
        invoice.action_post()
        return invoice

    def _register_payment(self, invoice, amount, currency, **extra):
        vals = {
            "payment_date": self.test_date,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": self.company_data["default_journal_bank"].id,
        }
        vals.update(extra)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(vals)
        )
        wizard._create_payments()
        invoice.invalidate_recordset()

    def _pay_invoice_bs(self, invoice):
        self._register_payment(
            invoice,
            invoice.amount_total,
            self.ves,
        )

    def _pay_invoice_mixed_bs_usd(self, invoice):
        half = self.ves.round(invoice.amount_total / 2.0)
        remainder = self.ves.round(invoice.amount_total - half)
        extra = {}
        if "l10n_ve_apply_igtf" in self.env["account.payment.register"]._fields:
            extra["l10n_ve_apply_igtf"] = True
        self._register_payment(
            invoice,
            self._usd_amount_for_ves(half),
            self.usd,
            **extra,
        )
        self._register_payment(invoice, remainder, self.ves)

    def _pay_invoice_total_plus_igtf_usd(self, invoice):
        igtf = self.ves.round(invoice.amount_total * 0.03)
        payment_ves = self.ves.round(invoice.amount_total + igtf)
        extra = {}
        if "l10n_ve_apply_igtf" in self.env["account.payment.register"]._fields:
            extra["l10n_ve_apply_igtf"] = True
        self._register_payment(
            invoice,
            self._usd_amount_for_ves(payment_ves),
            self.usd,
            **extra,
        )

    def _post_full_credit_note(self, invoice):
        credit = invoice._reverse_moves()
        credit.write(
            {
                "l10n_ve_control_number": self._next_control_number(),
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit.action_post()
        invoice.invalidate_recordset()
        return credit

    def _post_partial_credit_note(self, invoice, ratio=0.5):
        line = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type in (False, "product")
        )[:1]
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "journal_id": invoice.journal_id.id,
                "invoice_date": self.test_date,
                "l10n_ve_control_number": self._next_control_number(),
                "l10n_ve_invoice_date": fields.Datetime.now(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": line.name,
                            "product_id": line.product_id.id,
                            "quantity": line.quantity * ratio,
                            "price_unit": line.price_unit,
                            "account_id": line.account_id.id,
                            "tax_ids": [Command.set(line.tax_ids.ids)],
                        }
                    )
                ],
            }
        )
        credit.action_post()
        invoice.invalidate_recordset()
        return credit

    def _create_debit_note(self, invoice, price_multiplier=1.5):
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "date": self.test_date,
                    "reason": "cargo adicional",
                    "copy_lines": False,
                }
            )
        )
        wiz.create_debit()
        debit = self.env["account.move"].search(
            [("debit_origin_id", "=", invoice.id)], order="id desc", limit=1
        )
        debit.ensure_one()
        line_vals = []
        for line in invoice.invoice_line_ids.filtered(
            lambda l: l.display_type in (False, "product")
        ):
            line_vals.append(
                Command.create(
                    {
                        "name": line.name,
                        "quantity": line.quantity,
                        "price_unit": self.ves.round(
                            line.price_unit * price_multiplier
                        ),
                        "account_id": line.account_id.id,
                        "tax_ids": [Command.set(line.tax_ids.ids)],
                    }
                )
            )
        debit.write(
            {
                "invoice_line_ids": [Command.clear()] + line_vals,
                "l10n_ve_control_number": self._next_control_number(),
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        debit.action_post()
        invoice.invalidate_recordset()
        return debit

    def _create_credit_note_for_debit_notes(self, invoice, debit_notes):
        wizard = self.env["l10n_ve.account.move.debit.credit.wizard"].create(
            {
                "move_id": invoice.id,
                "debit_note_ids": [(6, 0, debit_notes.ids)],
                "reason": "Reversión ND adicional",
            }
        )
        result = wizard.action_create_credit_note()
        credit = self.env["account.move"].browse(result["res_id"])
        credit.write(
            {
                "l10n_ve_control_number": self._next_control_number(),
                "l10n_ve_invoice_date": fields.Datetime.now(),
            }
        )
        credit.action_post()
        invoice.invalidate_recordset()
        return credit

    def _assert_receivable_residual_zero(self, move, msg="", related_moves=None):
        moves = move
        if related_moves:
            moves = move | related_moves
        receivable_lines = moves.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        residual = sum(receivable_lines.mapped("amount_residual"))
        self.assertTrue(
            move.currency_id.is_zero(residual),
            f"{msg}: residual CXC={residual}",
        )

    def _assert_partner_receivable_zero(self, partner, msg=""):
        receivable_account = partner.property_account_receivable_id
        open_lines = self.env["account.move.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("account_id", "=", receivable_account.id),
                ("parent_state", "=", "posted"),
                ("reconciled", "=", False),
            ]
        )
        residual = sum(open_lines.mapped("amount_residual"))
        self.assertTrue(
            partner.currency_id.is_zero(residual),
            f"{msg}: saldo CXC partner={residual}",
        )

    def _reconcile_open_partner_receivable(self, partner):
        receivable_account = partner.property_account_receivable_id
        open_lines = self.env["account.move.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("account_id", "=", receivable_account.id),
                ("parent_state", "=", "posted"),
                ("reconciled", "=", False),
            ]
        )
        if open_lines:
            open_lines.reconcile()

    def test_case_1_invoice_paid_bs_buttons_visible(self):
        invoice = self._create_multi_aliquot_invoice()
        self._pay_invoice_bs(invoice)
        self.assertEqual(invoice.payment_state, "paid")
        self._assert_credit_debit_buttons(
            invoice, credit_note=True, debit_note=True, msg="Caso 1"
        )

    def test_case_2_invoice_paid_mixed_bs_usd_buttons_visible(self):
        invoice = self._create_multi_aliquot_invoice()
        self._pay_invoice_mixed_bs_usd(invoice)
        self._assert_credit_debit_buttons(
            invoice, credit_note=True, debit_note=True, msg="Caso 2"
        )

    def test_case_3_invoice_paid_total_plus_igtf_usd_buttons_visible(self):
        invoice = self._create_multi_aliquot_invoice()
        self._pay_invoice_total_plus_igtf_usd(invoice)
        self._assert_credit_debit_buttons(
            invoice, credit_note=True, debit_note=True, msg="Caso 3"
        )

    def test_case_4_all_aliquots_payment_variants_buttons_visible(self):
        payers = {
            "bs": self._pay_invoice_bs,
            "mixed": self._pay_invoice_mixed_bs_usd,
            "igtf_usd": self._pay_invoice_total_plus_igtf_usd,
        }
        for label, payer in payers.items():
            with self.subTest(payment=label):
                invoice = self._create_multi_aliquot_invoice()
                self.assertGreaterEqual(len(invoice.invoice_line_ids), 1)
                payer(invoice)
                self._assert_credit_debit_buttons(
                    invoice,
                    credit_note=True,
                    debit_note=True,
                    msg=f"Caso 4 ({label})",
                )

    def test_case_5_full_credit_note_hides_buttons_and_zeros_receivable(self):
        invoice = self._create_multi_aliquot_invoice()
        self._assert_credit_debit_buttons(
            invoice, credit_note=True, debit_note=True, msg="Caso 5 previo NC"
        )
        credit = self._post_full_credit_note(invoice)
        self._assert_credit_debit_buttons(
            invoice,
            credit_note=False,
            debit_note=True,
            debit_alert=False,
            msg="Caso 5 factura tras NC total",
        )
        self._assert_credit_debit_buttons(
            credit,
            credit_note=False,
            debit_note=False,
            msg="Caso 5 documento NC",
        )
        self._assert_receivable_residual_zero(
            invoice, "Caso 5 factura", related_moves=credit
        )
        self._assert_partner_receivable_zero(invoice.partner_id, "Caso 5")

    def test_case_6_debit_note_after_full_credit_shows_alert_then_hides(self):
        invoice = self._create_multi_aliquot_invoice()
        self._pay_invoice_mixed_bs_usd(invoice)
        self._post_full_credit_note(invoice)
        self._assert_credit_debit_buttons(
            invoice,
            credit_note=False,
            debit_note=True,
            debit_alert=False,
            msg="Caso 6 tras NC total sin ND",
        )
        debit = self._create_debit_note(invoice)
        self._assert_credit_debit_buttons(
            invoice,
            credit_note=False,
            debit_note=False,
            debit_alert=True,
            msg="Caso 6 tras ND adicional",
        )
        self._assert_credit_debit_buttons(
            debit,
            credit_note=False,
            debit_note=False,
            msg="Caso 6 documento ND",
        )
        debit_credit = self._create_credit_note_for_debit_notes(invoice, debit)
        self._assert_credit_debit_buttons(
            invoice,
            credit_note=False,
            debit_note=False,
            debit_alert=False,
            msg="Caso 6 tras NC por ND",
        )
        self._assert_credit_debit_buttons(
            debit_credit,
            credit_note=False,
            debit_note=False,
            msg="Caso 6 NC por ND",
        )

    def test_case_7_partial_credit_note_keeps_buttons_visible(self):
        invoice = self._create_multi_aliquot_invoice()
        self._pay_invoice_total_plus_igtf_usd(invoice)
        self._assert_credit_debit_buttons(
            invoice, credit_note=True, debit_note=True, msg="Caso 7 previo NC"
        )
        credit = self._post_partial_credit_note(invoice)
        self.assertFalse(invoice._l10n_ve_has_full_posted_credit_on_invoice())
        self._assert_credit_debit_buttons(
            invoice,
            credit_note=True,
            debit_note=True,
            debit_alert=False,
            msg="Caso 7 factura tras NC parcial",
        )
        self._assert_credit_debit_buttons(
            credit,
            credit_note=False,
            debit_note=False,
            msg="Caso 7 documento NC parcial",
        )
