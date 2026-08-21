# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionIvaDebitNote(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor retención ND",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J556677889",
                "supplier_rank": 1,
            }
        )
        cls.test_date = fields.Date.today()

    def _create_vendor_bill(self, ref="FAC-RET-001"):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "ref": ref,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _create_debit_note(self, bill, ref="ND-RET-001"):
        debit = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": bill.partner_id.id,
                "journal_id": bill.journal_id.id,
                "invoice_date": self.test_date,
                "ref": ref,
                "debit_origin_id": bill.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Cargo ND",
                            "quantity": 1.0,
                            "price_unit": 200.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    )
                ],
            }
        )
        debit.action_post()
        return debit

    def _create_iva_retention_for_move(self, move):
        retention = self.env["account.retention"].create(
            {
                "name": "Retención IVA ND test",
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": move.partner_id.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "number": "2026010001",
                "state": "emitted",
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Línea IVA",
                            "move_id": move.id,
                            "invoice_amount": move.amount_untaxed,
                            "iva_amount": move.amount_tax,
                            "invoice_total": move.amount_total,
                            "aliquot": 75.0,
                            "retention_amount": move.amount_tax * 0.75,
                        }
                    )
                ],
            }
        )
        return retention

    def test_retention_iva_txt_marks_debit_note_as_type_02(self):
        bill = self._create_vendor_bill()
        debit = self._create_debit_note(bill)
        retention = self._create_iva_retention_for_move(debit)
        wizard = self.env["wizard.retention.iva"].create({})
        data = wizard._retention_iva(retention)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["Tipo de documento"], "02")
        self.assertEqual(
            data[0]["Número del documento afectado"],
            bill.ref,
        )
        self.assertEqual(data[0]["Número de documento"], debit.ref)

    def test_retention_iva_txt_marks_invoice_as_type_01(self):
        bill = self._create_vendor_bill(ref="FAC-RET-002")
        retention = self._create_iva_retention_for_move(bill)
        wizard = self.env["wizard.retention.iva"].create({})
        data = wizard._retention_iva(retention)
        self.assertEqual(data[0]["Tipo de documento"], "01")
        self.assertEqual(data[0]["Número del documento afectado"], "0")

    def test_retention_exposes_affected_invoice_reference_and_action(self):
        bill = self._create_vendor_bill(ref="FAC-RET-003")
        retention = self._create_iva_retention_for_move(bill)
        line = retention.retention_line_ids

        self.assertEqual(retention.affected_invoice_ids, bill)
        self.assertEqual(line.supplier_invoice_reference, bill.ref)
        self.assertEqual(
            line.affected_invoice_display_name,
            f"{bill.ref} ({bill.name})",
        )
        self.assertEqual(
            retention.affected_invoice_display_names,
            f"{bill.ref} ({bill.name})",
        )

        bill.l10n_ve_invoice_number = "FM-RET-003"
        self.assertEqual(
            line.affected_invoice_display_name,
            f"{bill.ref} ({bill.name})",
        )

        bill.l10n_ve_control_number = "99-00000003"
        self.assertEqual(
            line.affected_invoice_display_name,
            f"99-00000003 ({bill.name})",
        )

        open_action = line.action_open_invoice()
        self.assertEqual(open_action["res_model"], "account.move")
        self.assertEqual(open_action["res_id"], bill.id)

    def test_emitted_retention_can_be_printed_from_vendor_bill(self):
        bill = self._create_vendor_bill(ref="FAC-RET-004")
        retention = self._create_iva_retention_for_move(bill)

        self.assertEqual(bill.iva_retention_id, retention)
        print_action = bill.action_print_iva_retention()
        self.assertEqual(print_action["type"], "ir.actions.report")
        self.assertEqual(
            print_action["report_name"],
            "l10n_ve_withholding.retention_voucher_template",
        )
