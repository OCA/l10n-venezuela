# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeFiscalMachine(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")

    def test_create_from_detect_payload(self):
        machine_model = self.env["l10n.ve.fiscal.machine"]
        payload = {
            "company_id": self.env.company.id,
            "name": "HKA 80 (ABC1234567)",
            "connection_type": "web_serial",
            "serial_port": "USB:2341-0043",
            "baudrate": "9600",
            "parity": "even",
            "data_bits": "8",
            "stop_bits": "1",
            "printer_type": "hka80",
            "printer_model_code": "Z1F",
            "printer_model_name": "SRP812",
            "country_code": "VE",
            "registered_serial": "ABC1234567",
            "fiscal_rif": "J123456789",
            "flag_21": "30",
            "last_invoice_number": "00000001",
            "enq_status": 64,
            "enq_error": 64,
            "enq_status_label": "Modo entrenamiento y en espera",
            "enq_error_label": "Sin error fiscal (STS2=0x40, manual TFHKA)",
            "s1_raw": "S1\n00000001\nABC1234567",
            "sv_raw": "SVZ1FVE",
        }
        machine_id = machine_model.create_from_detect_payload(payload)
        machine = machine_model.browse(machine_id)
        self.assertEqual(machine.registered_serial, "ABC1234567")
        self.assertEqual(machine.printer_model_name, "SRP812")
        self.assertEqual(machine.serial_port, "USB:2341-0043")

        machine_id_again = machine_model.create_from_detect_payload(payload)
        self.assertEqual(machine_id_again, machine.id)

    def test_apply_s1_counters(self):
        machine = self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA counters",
                "company_id": self.env.company.id,
                "registered_serial": "SER1234567",
                "daily_closure_counter": "0138",
                "last_invoice_number": "00000010",
            }
        )
        result = machine.apply_s1_counters(
            {
                "daily_closure_counter": "0139",
                "last_invoice_number": "00000010",
            }
        )
        self.assertEqual(machine.daily_closure_counter, "0139")
        self.assertEqual(result["daily_closure_counter"], "0139")

    def test_apply_port_update_from_detect(self):
        machine = self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA PC1",
                "company_id": self.env.company.id,
                "registered_serial": "SER1234567",
                "serial_port": "USB:1111-2222",
                "webserial_usb_vendor_id": 0x1111,
                "webserial_usb_product_id": 0x2222,
            }
        )
        result = machine.apply_port_update_from_detect(
            {
                "registered_serial": "SER1234567",
                "serial_port": "USB:2341-0043",
                "webserial_usb_vendor_id": 0x2341,
                "webserial_usb_product_id": 0x0043,
                "webserial_usb_serial_number": "ABCD",
                "baudrate": "9600",
                "parity": "even",
                "enq_status": 0,
                "enq_error": 64,
                "enq_status_label": "En espera",
                "enq_error_label": "Sin error",
            }
        )
        self.assertEqual(machine.serial_port, "USB:2341-0043")
        self.assertEqual(machine.webserial_usb_vendor_id, 0x2341)
        self.assertEqual(machine.webserial_usb_product_id, 0x0043)
        self.assertEqual(machine.webserial_usb_serial_number, "ABCD")
        self.assertEqual(result["serial_port"], "USB:2341-0043")
        with self.assertRaises(ValidationError):
            machine.apply_port_update_from_detect(
                {
                    "registered_serial": "OTRA999999",
                    "serial_port": "USB:9999-9999",
                }
            )

    def test_systray_data_hidden_without_fiscal_machine_medium(self):
        machine_model = self.env["l10n.ve.fiscal.machine"]
        self.env.company.write({"l10n_ve_emission_medium_ids": [(5, 0, 0)]})
        data = machine_model.l10n_ve_fiscal_serial_get_systray_data()
        self.assertFalse(data["visible"])

    def test_systray_data_with_fiscal_machine(self):
        machine_model = self.env["l10n.ve.fiscal.machine"]
        medium = self.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")
        self.env.company.write({"l10n_ve_emission_medium_ids": [(6, 0, [medium.id])]})
        machine = machine_model.create(
            {
                "name": "HKA Systray Test",
                "company_id": self.env.company.id,
                "registered_serial": "SYSTRAY123",
                "serial_port": "USB:1234-5678",
            }
        )
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_fiscal_machine_id=machine.id,
        )
        data = machine_model.l10n_ve_fiscal_serial_get_systray_data()
        self.assertTrue(data["visible"])
        self.assertEqual(data["primary_machine_id"], machine.id)
        self.assertEqual(len(data["machines"]), 1)
        self.assertEqual(data["machines"][0]["registered_serial"], "SYSTRAY123")

    def test_apply_detect_result(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {"company_id": self.env.company.id}
        )
        wizard.apply_detect_result(
            {
                "detect_state": "done",
                "detect_message": "OK",
                "registered_serial": "XYZ9876543",
                "name": "HKA 80 (XYZ9876543)",
                "enq_status": 64,
                "enq_error": 64,
            }
        )
        self.assertEqual(wizard.detect_state, "done")
        self.assertEqual(wizard.registered_serial, "XYZ9876543")
        result = wizard.apply_detect_result(
            {
                "detect_state": "done",
                "detect_message": "OK",
                "registered_serial": "XYZ9876543",
                "name": "HKA 80 (XYZ9876543)",
                "enq_status": 64,
                "enq_error": 64,
                "serial_port": "USB:2341-0043",
            }
        )
        self.assertEqual(result["detect_state"], "done")
        self.assertEqual(result["serial_port"], "USB:2341-0043")
        self.assertIn("requires_manual_identification", result)
        result = wizard.apply_detect_result({"detect_message": "Actualizado"})
        self.assertEqual(result["detect_message"], "Actualizado")

    def test_apply_detect_result_preserves_manual_identification(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {
                "company_id": self.env.company.id,
                "registered_serial": "MANUAL123",
                "fiscal_rif": "J123456789",
            }
        )
        wizard.apply_detect_result(
            {
                "detect_state": "done",
                "enq_status": 64,
                "registered_serial": None,
                "fiscal_rif": None,
            }
        )
        self.assertEqual(wizard.registered_serial, "MANUAL123")
        self.assertEqual(wizard.fiscal_rif, "J123456789")
        self.assertFalse(wizard.requires_manual_identification)

        wizard.write({"fiscal_rif": False})
        self.assertTrue(wizard.requires_manual_identification)

    def test_action_open_setup_wizard(self):
        action = self.env["l10n.ve.fiscal.machine"].action_open_setup_wizard()
        self.assertEqual(action["res_model"], "l10n.ve.fiscal.machine.setup.wizard")
        self.assertEqual(action["target"], "new")
        self.assertTrue(action["res_id"])
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].browse(
            action["res_id"]
        )
        self.assertTrue(wizard.exists())
        self.assertEqual(wizard.company_id, self.env.company)
