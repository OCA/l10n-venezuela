# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestEinvoice(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.country_id = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")
        cls.company.l10n_ve_edoc_provider = "l10n.ve.edoc.provider.dummy"
        cls.company_data["default_journal_sale"].l10n_ve_emission_medium = "free"
        cls.tax_group = cls.env["account.tax.group"].create(
            {
                "name": "Test electronic document taxes",
                "company_id": cls.company.id,
            }
        )
        cls.tax_16 = cls.env["account.tax"].create(
            {
                "name": "Test electronic document VAT 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        cls.tax_exempt = cls.env["account.tax"].create(
            {
                "name": "Test electronic document exempt tax",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        cls.digital_journal = cls.env["account.journal"].create(
            {
                "name": "Digital Billing Sales",
                "code": "DIGI",
                "type": "sale",
                "company_id": cls.company.id,
                "l10n_ve_emission_medium": "digital",
            }
        )
        cls.partner = (
            cls.env["res.partner"]
            .with_context(no_vat_validation=True)
            .create(
                {
                    "name": "Customer Company",
                    "vat": "J-98765432-1",
                    "street": "Main Avenue",
                }
            )
        )

    def _invoice(self, journal=None):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.to_date("2026-07-25"),
                "journal_id": (journal or self.digital_journal).id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Taxed service",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Exempt item",
                            "quantity": 2.0,
                            "price_unit": 25.0,
                            "tax_ids": [Command.set(self.tax_exempt.ids)],
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def test_document_vals_split_taxed_and_exempt(self):
        vals = self._invoice()._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["tipo_documento"], "factura")
        self.assertEqual(vals["emisor"]["rif"], self.company.vat or "")
        self.assertEqual(vals["comprador"]["rif"], "J-98765432-1")
        self.assertAlmostEqual(vals["total_base"], 100.0, places=2)
        self.assertAlmostEqual(vals["total_exento"], 50.0, places=2)
        self.assertAlmostEqual(vals["total_iva"], 16.0, places=2)
        exempt_line = next(line for line in vals["lineas"] if line["exento"])
        self.assertAlmostEqual(exempt_line["alicuota"], 0.0, places=2)

    def test_document_vals_are_provider_neutral(self):
        vals = self._invoice()._l10n_ve_edoc_document_vals()
        self.assertRegex(vals["hora"], r"^\d{2}:\d{2}:\d{2}$")
        self.assertEqual(vals["comprador"]["tipo_identificacion"], "J")
        self.assertEqual(vals["comprador"]["numero_identificacion"], "987654321")
        self.assertEqual(vals["nro_items"], 2)
        self.assertAlmostEqual(vals["subtotal"], 150.0, places=2)
        self.assertIn(vals["tipo_venta"], ("contado", "credito"))
        taxed = next(line for line in vals["lineas"] if not line["exento"])
        self.assertAlmostEqual(taxed["iva"], 16.0, places=2)
        self.assertAlmostEqual(taxed["total"], 116.0, places=2)
        self.assertEqual(vals["formas_pago"], [])

    def test_credit_note_references_affected_document(self):
        invoice = self._invoice()
        reversal = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": self.digital_journal.id,
                    "reason": "Test reversal",
                }
            )
        )
        refund = self.env["account.move"].browse(reversal.reverse_moves()["res_id"])
        vals = refund._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["tipo_documento"], "nota_credito")
        self.assertEqual(vals["documento_afectado"]["numero"], invoice.name)
        self.assertAlmostEqual(
            vals["documento_afectado"]["monto"], invoice.amount_total, places=2
        )

    def test_debit_note_references_affected_document(self):
        if "debit_origin_id" not in self.env["account.move"]._fields:
            self.skipTest("account_debit_note is not installed")
        invoice = self._invoice()
        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "Late payment interest", "copy_lines": True})
        )
        debit = self.env["account.move"].browse(wizard.create_debit()["res_id"])
        debit.action_post()
        vals = debit._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["tipo_documento"], "nota_debito")
        self.assertEqual(vals["documento_afectado"]["numero"], invoice.name)
        self.assertAlmostEqual(
            vals["documento_afectado"]["monto"], invoice.amount_total, places=2
        )

    def test_send_assigns_control_number_and_logs(self):
        move = self._invoice()
        self.assertEqual(move.l10n_ve_edoc_state, "to_send")
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        self.assertTrue(move.l10n_ve_control_number)
        self.assertTrue(move.l10n_ve_control_date)
        log = self.env["l10n.ve.edoc.log"].search([("move_id", "=", move.id)])
        self.assertTrue(log)
        self.assertTrue(log[0].ok)

    def test_control_number_uses_safe_assignment_api(self):
        move = self._invoice()
        with self.assertRaises(UserError):
            move.l10n_ve_control_number = "00-99999999"
        move.action_l10n_ve_edoc_send()
        self.assertTrue(move.l10n_ve_control_number)

    def test_send_rejects_wrong_emission_medium(self):
        move = self._invoice(journal=self.company_data["default_journal_sale"])
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_send()

    def test_send_is_not_repeatable(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_send()

    def test_async_provider_needs_fetch(self):
        provider = self.env["l10n.ve.edoc.provider.dummy"]
        move = self._invoice()
        self.patch(type(provider), "_dummy_fetch_delay", 1)
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "sent")
        self.assertFalse(move.l10n_ve_control_number)
        move.action_l10n_ve_edoc_fetch()
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        self.assertTrue(move.l10n_ve_control_number)

    def test_cron_sends_and_fetches(self):
        provider = self.env["l10n.ve.edoc.provider.dummy"]
        move = self._invoice()
        self.patch(type(provider), "_dummy_fetch_delay", 1)
        self.env["account.move"]._l10n_ve_edoc_cron()
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")

    def test_cancel_requires_issued_document(self):
        move = self._invoice()
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_cancel()

    def test_cancel_wizard_marks_cancelled_and_logs(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()
        wizard = self.env["l10n.ve.edoc.cancel.wizard"].create(
            {"move_id": move.id, "reason": "Incorrect customer data"}
        )
        wizard.action_confirm()
        self.assertEqual(move.l10n_ve_edoc_state, "cancelled")
        log = self.env["l10n.ve.edoc.log"].search(
            [("move_id", "=", move.id), ("endpoint", "=", "cancel")]
        )
        self.assertTrue(log)
        self.assertTrue(log[0].ok)

    def test_cancel_failure_keeps_state_and_logs(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()

        def fail(self, move, reason):
            raise ValueError("Provider rejected the cancellation")

        self.patch(type(self.env["l10n.ve.edoc.provider.dummy"]), "_edoc_cancel", fail)
        wizard = self.env["l10n.ve.edoc.cancel.wizard"].create(
            {"move_id": move.id, "reason": "Test"}
        )
        result = wizard.action_confirm()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        log = self.env["l10n.ve.edoc.log"].search(
            [("move_id", "=", move.id), ("endpoint", "=", "cancel")]
        )
        self.assertFalse(log[0].ok)

    def test_provider_failure_does_not_break_accounting(self):
        move = self._invoice()

        def fail(self, move, vals):
            raise ValueError("Provider is unavailable")

        self.patch(type(self.env["l10n.ve.edoc.provider.dummy"]), "_edoc_send", fail)
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "error")
        self.assertEqual(move.state, "posted")
        log = self.env["l10n.ve.edoc.log"].search([("move_id", "=", move.id)])
        self.assertFalse(log[0].ok)

    def test_log_redacts_secret_values(self):
        move = self._invoice()
        move._l10n_ve_edoc_log(
            "test",
            {"token": "request-secret", "nested": {"password": "hidden"}},
            "authorization=Bearer-value",
            ok=False,
        )
        log = self.env["l10n.ve.edoc.log"].search(
            [("move_id", "=", move.id), ("endpoint", "=", "test")], limit=1
        )
        self.assertNotIn("request-secret", log.request)
        self.assertNotIn("hidden", log.request)
        self.assertNotIn("Bearer-value", log.response)
        self.assertIn("[REDACTED]", log.request)

    def test_log_rule_and_credential_field_security_are_installed(self):
        rule = self.env.ref("l10n_ve_einvoice.l10n_ve_edoc_log_company_rule")
        self.assertEqual(rule.domain_force, "[('company_id', 'in', company_ids)]")
        for field_name in (
            "l10n_ve_edoc_url",
            "l10n_ve_edoc_user",
            "l10n_ve_edoc_password",
        ):
            self.assertEqual(
                self.env["res.company"]._fields[field_name].groups,
                "base.group_system",
            )
