# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountJournalFiscalMachine(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")

    def _create_machine(self):
        return self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA Journal Test",
                "company_id": self.env.company.id,
                "registered_serial": "JOURNALTEST1",
                "fiscal_rif": "J123456789",
            }
        )

    def test_fiscal_machine_required_on_fiscal_journal(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        with self.assertRaises(ValidationError):
            journal.write({"l10n_ve_emission_medium": "fiscal_machine"})
        journal.write(
            {
                "l10n_ve_emission_medium": "fiscal_machine",
                "l10n_ve_fiscal_machine_id": machine.id,
            }
        )
        self.assertEqual(journal.l10n_ve_fiscal_machine_id, machine)

    def test_fiscal_machine_cleared_when_changing_medium(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        journal.write(
            {
                "l10n_ve_emission_medium": "fiscal_machine",
                "l10n_ve_fiscal_machine_id": machine.id,
            }
        )
        journal.write({"l10n_ve_emission_medium": "digital"})
        self.assertFalse(journal.l10n_ve_fiscal_machine_id)

    def test_print_payload_uses_journal_machine(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        machine.write({"flag_21": "01", "baudrate": "19200", "parity": "none", "use_emulator": True})
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_fiscal_machine_id=machine.id,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente MF",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345670",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Linea",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        move.action_post()
        payload = move.check_print_out_invoice()
        self.assertEqual(payload["fiscal_machine"]["machine_id"], machine.id)
        self.assertEqual(payload["fiscal_machine"]["registered_serial"], "JOURNALTEST1")
        self.assertEqual(payload["fiscal_machine"]["baudrate"], 19200)
        self.assertEqual(payload["fiscal_machine"]["parity"], "none")
        self.assertEqual(payload["flag_21"], "01")
        self.assertTrue(payload["use_emulator"])

    def test_print_result_updates_machine_counters(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        machine.write(
            {
                "last_invoice_number": "00000001",
                "last_credit_note_number": "00000002",
                "last_debit_note_number": "00000003",
            }
        )
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_fiscal_machine_id=machine.id,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente Contadores",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345671",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Linea",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        move.action_post()
        move.print_out_invoice(
            {
                "valid": True,
                "data": {
                    "sequence": "00000042",
                    "serial_machine": "JOURNALTEST1",
                    "mf_reportz": "0005",
                    "parsed_post": {
                        "LastInvoiceNumber": "00000042",
                        "LastCreditNoteNumber": "00000002",
                        "LastDebitNoteNumber": "00000003",
                        "DailyClosureCounter": "0004",
                    },
                },
            }
        )
        self.assertEqual(move.l10n_ve_invoice_number, "00000042")
        self.assertEqual(machine.last_invoice_number, "00000042")
        self.assertEqual(machine.last_credit_note_number, "00000002")
        self.assertEqual(machine.last_debit_note_number, "00000003")
        self.assertEqual(machine.daily_closure_counter, "0004")

    def test_fiscal_placeholders_from_machine_counters(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        machine.write(
            {
                "last_invoice_number": "00000010",
                "last_credit_note_number": "00000003",
                "daily_closure_counter": "0012",
            }
        )
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_fiscal_machine_id=machine.id,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente Placeholders",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345672",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Linea",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        self.assertEqual(
            move.l10n_ve_fiscal_serial_number_placeholder, "JOURNALTEST1"
        )
        self.assertEqual(
            move.l10n_ve_fiscal_invoice_number_placeholder, "00000011"
        )
        self.assertEqual(move.l10n_ve_fiscal_report_z_placeholder, "0013")
        move.write(
            {
                "l10n_ve_serial_number": "JOURNALTEST1",
                "l10n_ve_invoice_number": "00000011",
                "l10n_ve_report_z": "0013",
            }
        )
        self.assertFalse(move.l10n_ve_fiscal_serial_number_placeholder)
        self.assertFalse(move.l10n_ve_fiscal_invoice_number_placeholder)
        self.assertFalse(move.l10n_ve_fiscal_report_z_placeholder)
