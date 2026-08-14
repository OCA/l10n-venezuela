from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.l10n_ve_igtf.tests.common import TestL10nVeIgtfCommon


class TestL10nVeEdiIgtfAutoSend(TestL10nVeIgtfCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.l10n_ve_igtf_allow_invoice_accrual = True
        cls.company.partner_id.write({"vat": "J123456789"})
        digital_medium = cls.env.ref("l10n_ve_seniat.emission_medium_digital_billing")
        cls.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [digital_medium.id])]}
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
        invoice = self._create_customer_invoice(100.0, self.usd)
        invoice.journal_id = self.digital_journal
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
            invoice = self._create_customer_invoice(100.0, self.usd)
            invoice.journal_id = self.digital_journal
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
