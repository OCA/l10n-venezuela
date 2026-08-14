# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentMethodLineFiscal(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")
        cls.company._l10n_ve_fiscal_ensure_payment_methods()
        cls.fiscal_method_01 = cls.env["l10n.ve.fiscal.payment.method"].search(
            [("company_id", "=", cls.company.id), ("code", "=", "01")],
            limit=1,
        )
        cls.fiscal_method_07 = cls.env["l10n.ve.fiscal.payment.method"].search(
            [("company_id", "=", cls.company.id), ("code", "=", "07")],
            limit=1,
        )

    def test_payment_line_fiscal_method_used_in_payload(self):
        bank_journal = self.company_data["default_journal_bank"]
        payment_line = bank_journal.inbound_payment_method_line_ids[:1]
        self.assertTrue(payment_line)
        payment_line.l10n_ve_fiscal_payment_method_id = self.fiscal_method_07

        sale_journal = self.company_data["default_journal_sale"]
        machine = self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA Pay Line Test",
                "company_id": self.company.id,
                "registered_serial": "PAYLINETEST1",
                "fiscal_rif": "J123456789",
            }
        )
        self._l10n_ve_configure_journal_fiscal_machine(
            sale_journal,
            l10n_ve_fiscal_machine_id=machine.id,
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": sale_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Producto",
                            "quantity": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        move.action_post()
        payment = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create(
                {
                    "journal_id": bank_journal.id,
                    "payment_method_line_id": payment_line.id,
                }
            )
            ._create_payments()
        )
        self.assertEqual(payment.payment_method_line_id, payment_line)
        lines = move._l10n_ve_fiscal_serial_payment_lines_payload()
        self.assertTrue(lines)
        self.assertEqual(lines[0]["payment_method"], "07")

    def test_fallback_uses_company_default_payment_method(self):
        self.company.l10n_ve_fiscal_default_payment_method_id = self.fiscal_method_07
        sale_journal = self.company_data["default_journal_sale"]
        machine = self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA Default Pay Test",
                "company_id": self.company.id,
                "registered_serial": "DEFAULTPAY01",
                "fiscal_rif": "J123456789",
            }
        )
        self._l10n_ve_configure_journal_fiscal_machine(
            sale_journal,
            l10n_ve_fiscal_machine_id=machine.id,
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": sale_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Producto",
                            "quantity": 1,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )
        move.action_post()
        lines = move._l10n_ve_fiscal_serial_payment_lines_payload()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["payment_method"], "07")
        self.assertEqual(lines[0]["amount"], 0)
