# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestDigitalBilling(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.country_id = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")
        cls.company.l10n_ve_edoc_provider = "l10n.ve.edoc.provider.dummy"
        cls.tax_16 = cls.env["account.tax"].create({
            "name": "VAT 16% - edoc test",
            "amount": 16.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.tax_exempt = cls.env["account.tax"].create({
            "name": "Exempt - edoc test",
            "amount": 0.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.digital_journal = cls.env["account.journal"].create({
            "name": "Digital Billing Sales",
            "code": "DIGI",
            "type": "sale",
            "company_id": cls.company.id,
            "l10n_ve_emission_medium": "digital",
        })
        cls.free_journal = cls.company_data["default_journal_sale"]
        cls.free_journal.l10n_ve_emission_medium = "free"
        cls.partner = cls.env["res.partner"].with_context(
            no_vat_validation=True).create({
                "name": "Cliente Empresa, C.A.",
                "vat": "J-98765432-1",
                "street": "Av. Principal, Lecheria",
            })

    def _invoice(self, journal=None):
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": fields.Date.to_date("2026-07-25"),
            "journal_id": (journal or self.digital_journal).id,
            "invoice_line_ids": [
                Command.create({
                    "name": "Taxed service",
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "tax_ids": [Command.set(self.tax_16.ids)],
                }),
                Command.create({
                    "name": "Exempt supply",
                    "quantity": 2.0,
                    "price_unit": 25.0,
                    "tax_ids": [Command.set(self.tax_exempt.ids)],
                }),
            ],
        })
        move.action_post()
        return move

    def test_document_vals_split_taxed_and_exempt(self):
        # All the fiscal logic lives here, not in the adapter: this is what
        # lets the printing house be swapped without touching anything
        # fiscal.
        vals = self._invoice()._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["doc_type"], "invoice")
        self.assertEqual(vals["issuer"]["vat"], self.company.vat or "")
        self.assertEqual(vals["buyer"]["vat"], "J-98765432-1")
        self.assertAlmostEqual(vals["taxed_total"], 100.0, places=2)
        self.assertAlmostEqual(vals["exempt_total"], 50.0, places=2)
        self.assertAlmostEqual(vals["tax_total"], 16.0, places=2)
        exempt_line = next(ln for ln in vals["lines"] if ln["exempt"])
        self.assertAlmostEqual(exempt_line["rate"], 0.0, places=2)

    def test_document_vals_enriched_for_the_printing_house(self):
        # Fields the printing house requires that the adapter cannot invent:
        # emission time, split buyer identification, per-line code/uom/tax,
        # untaxed total and sale type.
        move = self._invoice()
        vals = move._l10n_ve_edoc_document_vals()
        self.assertRegex(vals["time"], r"^\d{2}:\d{2}:\d{2}$")
        self.assertEqual(vals["buyer"]["id_type"], "J")
        self.assertEqual(vals["buyer"]["id_number"], "987654321")
        self.assertEqual(vals["line_count"], 2)
        self.assertAlmostEqual(vals["untaxed_total"], 150.0, places=2)
        self.assertIn(vals["sale_type"], ("cash", "credit"))
        taxed_line = next(ln for ln in vals["lines"] if not ln["exempt"])
        self.assertAlmostEqual(taxed_line["tax"], 16.0, places=2)
        self.assertAlmostEqual(taxed_line["total"], 116.0, places=2)
        # No reconciled payment yet: none should travel, the adapter decides
        # the default from the sale type instead.
        self.assertEqual(vals["payments"], [])

    def test_credit_note_references_affected_document(self):
        # A credit note must reference the number, date and amount of the
        # document it affects.
        invoice = self._invoice()
        reversal = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "journal_id": self.digital_journal.id,
            "reason": "test",
        })
        refund = self.env["account.move"].browse(
            reversal.reverse_moves()["res_id"])
        vals = refund._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["doc_type"], "credit_note")
        self.assertEqual(vals["affected_document"]["number"], invoice.name)
        self.assertAlmostEqual(
            vals["affected_document"]["amount"], invoice.amount_total,
            places=2)

    def test_debit_note_references_affected_document(self):
        # A debit note is an out_invoice with debit_origin_id: without this
        # branch it would travel to the printing house as a plain invoice
        # and without the reference (number, date and amount of the
        # affected document).
        if "debit_origin_id" not in self.env["account.move"]._fields:
            self.skipTest("account_debit_note is not installed")
        invoice = self._invoice()
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "reason": "Late payment interest - test",
            "copy_lines": True,
        })
        debit = self.env["account.move"].browse(
            wizard.create_debit()["res_id"])
        debit.action_post()
        vals = debit._l10n_ve_edoc_document_vals()
        self.assertEqual(vals["doc_type"], "debit_note")
        affected = vals["affected_document"]
        self.assertEqual(affected["number"], invoice.name)
        self.assertEqual(affected["date"], invoice.invoice_date)
        self.assertAlmostEqual(
            affected["amount"], invoice.amount_total, places=2)

    def test_send_assigns_control_number_and_logs(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        self.assertTrue(move.l10n_ve_control_number)
        self.assertTrue(move.l10n_ve_control_date)
        log = self.env["l10n.ve.edoc.log"].search([("move_id", "=", move.id)])
        self.assertTrue(log, "every provider call leaves a log entry")
        self.assertTrue(log[0].ok)

    def test_control_number_written_through_fiscal_document_api(self):
        # The document is already posted and its fiscal data is locked by
        # l10n_ve_fiscal_document: a plain write is refused, but the
        # connector's own trusted write-back must still succeed.
        move = self._invoice()
        with self.assertRaises(UserError):
            move.l10n_ve_control_number = "00-99999999"
        move.action_l10n_ve_edoc_send()
        self.assertTrue(move.l10n_ve_control_number)

    def test_send_rejects_wrong_emission_medium(self):
        move = self._invoice(journal=self.free_journal)
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_send()

    def test_send_is_not_repeatable(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_send()

    def test_async_provider_needs_a_second_step(self):
        # With an asynchronous provider the emission response does not carry
        # the control number: the document stays 'sent' and is queried
        # afterwards.
        provider = self.env["l10n.ve.edoc.provider.dummy"]
        move = self._invoice()
        self.patch(type(provider), "_dummy_fetch_delay", 1)
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "sent")
        self.assertFalse(move.l10n_ve_control_number)
        move.action_l10n_ve_edoc_fetch()
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        self.assertTrue(move.l10n_ve_control_number)

    def test_provider_failure_does_not_break_accounting(self):
        # A provider failure leaves the document in 'error' with its log
        # entry, but NEVER rolls back the already-posted journal entry.
        move = self._invoice()

        def boom(self, move, vals):
            raise ValueError("the printing house is unreachable")

        self.patch(
            type(self.env["l10n.ve.edoc.provider.dummy"]), "_edoc_send", boom)
        move.action_l10n_ve_edoc_send()
        self.assertEqual(move.l10n_ve_edoc_state, "error")
        self.assertIn("unreachable", move.l10n_ve_edoc_error)
        self.assertEqual(move.state, "posted")
        log = self.env["l10n.ve.edoc.log"].search([("move_id", "=", move.id)])
        self.assertFalse(log[0].ok)

    def test_cancel_requires_emitted_document(self):
        move = self._invoice()
        with self.assertRaises(UserError):
            move.action_l10n_ve_edoc_cancel()

    def test_cancel_wizard_marks_cancelled_and_logs(self):
        move = self._invoice()
        move.action_l10n_ve_edoc_send()
        wizard = self.env["l10n.ve.edoc.cancel.wizard"].create({
            "move_id": move.id,
            "reason": "Error in the buyer's data - test",
        })
        wizard.action_confirm()
        self.assertEqual(move.l10n_ve_edoc_state, "cancelled")
        log = self.env["l10n.ve.edoc.log"].search([
            ("move_id", "=", move.id), ("endpoint", "=", "cancel")])
        self.assertTrue(log)
        self.assertTrue(log[0].ok)

    def test_cancel_failure_keeps_state_and_logs(self):
        # A provider failure while cancelling must NOT raise or lose the
        # 'assigned' state; it stays in the log and in the error field, just
        # like on sending.
        move = self._invoice()
        move.action_l10n_ve_edoc_send()

        def boom(self, move, reason):
            raise ValueError("the printing house rejects the cancellation")

        self.patch(
            type(self.env["l10n.ve.edoc.provider.dummy"]),
            "_edoc_cancel", boom)
        wizard = self.env["l10n.ve.edoc.cancel.wizard"].create({
            "move_id": move.id, "reason": "test"})
        result = wizard.action_confirm()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(move.l10n_ve_edoc_state, "assigned")
        self.assertIn("rejects", move.l10n_ve_edoc_error)
        log = self.env["l10n.ve.edoc.log"].search([
            ("move_id", "=", move.id), ("endpoint", "=", "cancel")])
        self.assertFalse(log[0].ok)

    def test_hka_url_resolution(self):
        # Always demo while testing (even with a URL configured): a test can
        # never reach production. Production requires the URL.
        provider = self.env["l10n.ve.edoc.provider.hka"]
        self.company.l10n_ve_edoc_test = True
        self.company.l10n_ve_edoc_url = "https://prod.example.com/"
        self.assertEqual(provider._hka_base_url(self.company),
                         "https://demoemisionv2.thefactoryhka.com.ve")
        self.company.l10n_ve_edoc_test = False
        self.assertEqual(provider._hka_base_url(self.company),
                         "https://prod.example.com")
        self.company.l10n_ve_edoc_url = False
        with self.assertRaises(UserError):
            provider._hka_base_url(self.company)

    def test_hka_payload_maps_the_neutral_dict(self):
        # Translation from the neutral dict to HKA's dialect, no network:
        # string amounts, split buyer, VAT breakdown by code and a default
        # payment. This is the shape documented in the provider's wiki.
        move = self._invoice()
        vals = move._l10n_ve_edoc_document_vals()
        payload = self.env["l10n.ve.edoc.provider.hka"]._hka_payload(
            move, vals)
        doc = payload["documentoElectronico"]
        identification = doc["encabezado"]["identificacionDocumento"]
        self.assertEqual(identification["tipoDocumento"], "01")
        self.assertEqual(identification["numeroDocumento"], move.name)
        self.assertRegex(identification["horaEmision"], r"^\d{2}:\d{2}:\d{2}$")
        buyer = doc["encabezado"]["comprador"]
        self.assertEqual(buyer["tipoIdentificacion"], "J")
        self.assertEqual(buyer["numeroIdentificacion"], "987654321")
        totals = doc["encabezado"]["totales"]
        self.assertEqual(totals["montoGravadoTotal"], "100.00")
        self.assertEqual(totals["montoExentoTotal"], "50.00")
        self.assertEqual(totals["totalIVA"], "16.00")
        self.assertEqual(totals["totalAPagar"], "166.00")
        self.assertEqual(
            {tax["codigoTotalImp"] for tax in totals["impuestosSubtotal"]},
            {"G", "E"})
        self.assertTrue(totals["formasPago"],
                        "with no reconciled payment, one travels for the total")
        self.assertEqual(totals["formasPago"][0]["monto"], "166.00")
        self.assertEqual(len(doc["detallesItems"]), 2)
        first_line = doc["detallesItems"][0]
        self.assertEqual(first_line["numeroLinea"], "1")
        self.assertEqual(first_line["tasaIVA"], "16.00")
        self.assertEqual(first_line["valorIVA"], "16.00")
        self.assertEqual(first_line["codigoImpuesto"], "G")

    def test_hka_payload_credit_note_references_affected(self):
        invoice = self._invoice()
        reversal = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "journal_id": self.digital_journal.id,
            "reason": "test partial cancellation",
        })
        refund = self.env["account.move"].browse(
            reversal.reverse_moves()["res_id"])
        vals = refund._l10n_ve_edoc_document_vals()
        payload = self.env["l10n.ve.edoc.provider.hka"]._hka_payload(
            refund, vals)
        identification = payload["documentoElectronico"]["encabezado"][
            "identificacionDocumento"]
        self.assertEqual(identification["tipoDocumento"], "03")
        self.assertEqual(identification["numeroFacturaAfectada"], invoice.name)
        self.assertEqual(identification["montoFacturaAfectada"], "166.00")
