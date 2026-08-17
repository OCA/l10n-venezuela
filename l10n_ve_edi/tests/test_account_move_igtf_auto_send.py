from unittest import SkipTest
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_igtf.tests.common import TestL10nVeIgtfCommon


@tagged("post_install", "-at_install")
class TestL10nVeEdiIgtfAutoSend(TestL10nVeIgtfCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        provider_selection = dict(
            cls.env["account.journal"]
            ._fields["l10n_ve_edi_provider"]
            ._description_selection(cls.env)
        )
        if "tfhka" not in provider_selection:
            raise SkipTest("Requires an EDI provider module (l10n_ve_edi_tfhka)")
        cls.company.l10n_ve_igtf_allow_invoice_accrual = True
        cls.company.partner_id.write({"vat": "J123456789"})
        digital_medium = cls.env.ref("l10n_ve_seniat.emission_medium_digital_billing")
        cls.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [digital_medium.id])]}
        )
        cls.sale_journal.write(
            {
                "l10n_ve_emission_medium": "digital",
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        cls.digital_journal = cls.env["account.journal"].with_company(cls.company).create(
            {
                "name": "Ventas digital IGTF",
                "code": "VEDG",
                "type": "sale",
                "l10n_ve_emission_medium": "digital",
                "l10n_ve_edi_provider": "tfhka",
            }
        )

    def _create_usd_invoice_with_igtf_accrual(self):
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": self.company.id,
                    "journal_id": self.digital_journal.id,
                    "partner_id": self.partner.id,
                    "currency_id": self.usd.id,
                    "invoice_date": self.test_date,
                    "date": self.test_date,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "IGTF EDI Test Line",
                                "quantity": 1.0,
                                "price_unit": 100.0,
                                "account_id": self.revenue_account.id,
                                "tax_ids": [Command.clear()],
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()
        self.assertTrue(invoice.l10n_ve_igtf_invoice_has_igtf_accrual())
        return invoice

    def test_auto_send_digital_when_igtf_accrual_on_post(self):
        with patch.object(
            type(self.env["account.move"]),
            "_l10n_ve_edi_enqueue_send",
            autospec=True,
        ) as mock_enqueue:
            invoice = self._create_usd_invoice_with_igtf_accrual()
            mock_enqueue.assert_called_once()
            mock_enqueue.assert_called_with(invoice, reuse_payload=False)

    def test_no_auto_send_without_igtf_accrual(self):
        self.company.l10n_ve_igtf_allow_invoice_accrual = False
        with patch.object(
            type(self.env["account.move"]),
            "_l10n_ve_edi_enqueue_send",
            autospec=True,
        ) as mock_enqueue:
            invoice = (
                self.env["account.move"]
                .with_company(self.company)
                .create(
                    {
                        "move_type": "out_invoice",
                        "company_id": self.company.id,
                        "journal_id": self.digital_journal.id,
                        "partner_id": self.partner.id,
                        "currency_id": self.usd.id,
                        "invoice_date": self.test_date,
                        "date": self.test_date,
                        "invoice_line_ids": [
                            Command.create(
                                {
                                    "name": "IGTF EDI Test Line",
                                    "quantity": 1.0,
                                    "price_unit": 100.0,
                                    "account_id": self.revenue_account.id,
                                    "tax_ids": [Command.clear()],
                                }
                            )
                        ],
                    }
                )
            )
            invoice.action_post()
            self.assertFalse(invoice.l10n_ve_igtf_invoice_has_igtf_accrual())
            mock_enqueue.assert_not_called()

    def test_no_auto_send_when_already_sent(self):
        invoice = self._create_usd_invoice_with_igtf_accrual()
        invoice.l10n_ve_edi_send_state = "sent"
        with patch.object(
            type(self.env["account.move"]),
            "_l10n_ve_edi_enqueue_send",
            autospec=True,
        ) as mock_enqueue:
            invoice._l10n_ve_edi_try_auto_send_on_igtf_accrual()
            mock_enqueue.assert_not_called()
