# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestRefSuffixMatch(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.partner_a
        if not cls.partner.vat:
            cls.partner.sudo().vat = "J123456789"
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.rule = cls.env["account.reconcile.model"].create(
            {
                "name": "VE Ref Suffix Test",
                "rule_type": "invoice_matching",
                "auto_reconcile": True,
                "unique_matching": True,
                "match_nature": "both",
                "match_same_currency": True,
                "allow_payment_tolerance": True,
                "payment_tolerance_type": "percentage",
                "payment_tolerance_param": 0.0,
                "match_text_location_label": True,
                "match_text_location_reference": True,
                "match_text_location_note": False,
                "match_ref_suffix_enabled": True,
                "match_ref_suffix_lengths": "6,4",
                "match_payment_before_invoice": True,
                "match_partner": False,
                "company_id": cls.company.id,
            }
        )

    def _create_invoice_line(self, amount, payment_reference, partner=None):
        Move = (
            self.env["account.move"]
            .sudo()
            .with_context(
                mail_create_nolog=True,
                tracking_disable=True,
                default_move_type="out_invoice",
            )
        )
        invoice_form = Form(Move)
        invoice_form.partner_id = partner or self.partner
        invoice_form.invoice_date = "2026-03-01"
        if not invoice_form._get_modifier("date", "invisible"):
            invoice_form.date = "2026-03-01"
        with invoice_form.invoice_line_ids.new() as line_form:
            line_form.name = "Test line"
            line_form.quantity = 1
            line_form.price_unit = amount
            line_form.tax_ids.clear()
        invoice = invoice_form.save()
        invoice.action_post()
        invoice.write(
            {
                "payment_reference": payment_reference,
                "ref": payment_reference,
            }
        )
        lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        line_types = [
            (line.account_id.account_type, line.balance) for line in invoice.line_ids
        ]
        self.assertTrue(
            lines,
            f"Invoice {invoice.name} has no AR/AP lines: {line_types}",
        )
        return lines[:1]

    def _create_payment_line(self, amount, payment_reference, partner=None):
        Payment = (
            self.env["account.payment"]
            .sudo()
            .with_context(
                mail_create_nolog=True,
                tracking_disable=True,
            )
        )
        payment = Payment.create(
            {
                "amount": amount,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": (partner or self.partner).id,
                "payment_reference": payment_reference,
                "memo": payment_reference,
                "destination_account_id": self.company_data[
                    "default_account_receivable"
                ].id,
                "journal_id": self.bank_journal.id,
            }
        )
        payment.action_post()
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type
            not in ("asset_receivable", "liability_payable")
            and line.payment_id
        )

    def _create_st_line(self, amount, payment_ref, ref=False):
        return (
            self.env["account.bank.statement.line"]
            .sudo()
            .create(
                {
                    "journal_id": self.bank_journal.id,
                    "amount": amount,
                    "date": "2026-03-10",
                    "payment_ref": payment_ref,
                    "ref": ref or payment_ref,
                    "partner_id": self.partner.id,
                }
            )
        )

    def test_exact_payment_match_auto(self):
        payment_line = self._create_payment_line(1000.0, "78131243")
        st_line = self._create_st_line(1000.0, "78131243")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertTrue(result)
        self.assertTrue(result["allow_auto_reconcile"])
        self.assertEqual(result["amls"], payment_line)

        applied = self.rule._apply_rules(st_line, st_line._retrieve_partner())
        self.assertEqual(applied.get("model"), self.rule)
        self.assertEqual(applied.get("amls"), payment_line)
        self.assertTrue(applied.get("auto_reconcile"))

    def test_invoice_suffix_six_auto(self):
        invoice_line = self._create_invoice_line(500.0, "513367")
        st_line = self._create_st_line(500.0, "000084732513367")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertTrue(result)
        self.assertTrue(result["allow_auto_reconcile"])
        self.assertEqual(result["amls"], invoice_line)

    def test_ambiguous_suffix_four_only_suggests(self):
        line_a = self._create_invoice_line(100.0, "11112222")
        line_b = self._create_invoice_line(100.0, "99992222")
        st_line = self._create_st_line(100.0, "55552222")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertTrue(result)
        self.assertFalse(result["allow_auto_reconcile"])
        self.assertEqual(result["amls"], line_a | line_b)

    def test_payment_has_priority_over_invoice(self):
        payment_line = self._create_payment_line(250.0, "3604277894")
        invoice_line = self._create_invoice_line(250.0, "3604277894")
        st_line = self._create_st_line(250.0, "3604277894")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertTrue(result)
        self.assertEqual(result["amls"], payment_line)
        self.assertNotIn(invoice_line.id, result["amls"].ids)

    def test_unreliable_ref_zero_is_ignored(self):
        self._create_invoice_line(8.0, "0")
        st_line = self._create_st_line(8.0, "0")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertFalse(result)

    def test_no_match_returns_none(self):
        self._create_invoice_line(80.0, "11111111")
        st_line = self._create_st_line(80.0, "99999999")
        result = self.rule._get_ref_suffix_amls_candidates(
            st_line, st_line._retrieve_partner()
        )
        self.assertFalse(result)
