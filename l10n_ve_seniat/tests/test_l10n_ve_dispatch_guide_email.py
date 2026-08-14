from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeDispatchGuideEmail(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "email": "company@example.com",
                "l10n_ve_unfactured_dispatch_email_recipient": "alerts@example.com",
            }
        )

    def test_send_dispatch_email_updates_last_sent(self):
        if "stock.picking" not in self.env:
            self.skipTest("stock no instalado")
        if not self.env["account.journal"]._l10n_ve_seniat_dispatch_guide_dashboard_available():
            self.skipTest("l10n_ve_stock no instalado")

        self.assertFalse(self.company.l10n_ve_unfactured_dispatch_email_last_sent)
        self.company._l10n_ve_send_unfactured_dispatch_guides_email()
        self.assertTrue(self.company.l10n_ve_unfactured_dispatch_email_last_sent)
        mail = self.env["mail.mail"].search(
            [("email_to", "=", "alerts@example.com")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(mail)
        self.assertIn("Guías de despacho", mail.subject or "")

    def test_send_dispatch_email_requires_recipient(self):
        self.company.l10n_ve_unfactured_dispatch_email_recipient = False
        with self.assertRaises(UserError):
            self.company._l10n_ve_send_unfactured_dispatch_guides_email()

    def test_cron_respects_interval(self):
        self.company.write(
            {
                "l10n_ve_unfactured_dispatch_email_schedule_enabled": True,
                "l10n_ve_unfactured_dispatch_email_interval_number": 7,
                "l10n_ve_unfactured_dispatch_email_interval_type": "days",
                "l10n_ve_unfactured_dispatch_email_last_sent": fields.Datetime.now(),
            }
        )
        self.assertFalse(self.company._l10n_ve_dispatch_email_interval_elapsed())

    def test_settings_enable_syncs_cron(self):
        cron = self.env.ref("l10n_ve_seniat.ir_cron_unfactured_dispatch_guides_email")
        cron.active = False
        vals = {
            "l10n_ve_unfactured_dispatch_email_schedule_enabled": True,
            "l10n_ve_unfactured_dispatch_email_recipient": "cron@example.com",
        }
        if "l10n_ve_dispatch_guide_enabled" in self.company._fields:
            vals["l10n_ve_dispatch_guide_enabled"] = True
        self.company.write(vals)
        self.assertTrue(cron.active)

    def test_dashboard_includes_dispatch_email_data(self):
        data = self.env["account.journal"].get_l10n_ve_invoice_dashboard()
        self.assertIn("dispatch_email", data)
        if data["dispatch_email"]["available"]:
            self.assertTrue(data["dispatch_email"]["can_send"])

    def test_manual_send_action_returns_last_sent(self):
        if not self.env["account.journal"]._l10n_ve_seniat_dispatch_guide_dashboard_available():
            self.skipTest("l10n_ve_stock no instalado")
        result = self.env["account.journal"].action_l10n_ve_send_unfactured_dispatch_guides_email()
        self.assertTrue(result["last_sent_label"])
        self.assertIn("message", result)

    def test_implementer_data_used_in_dispatch_email(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ve_seniat.implementer_name", "AndyEng IT"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ve_seniat.implementer_vat", "J123456789"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ve_seniat.implementer_email", "implementador@example.com"
        )
        data = self.company.l10n_ve_get_implementer_data()
        self.assertEqual(data["name"], "AndyEng IT")
        self.assertEqual(data["vat"], "J123456789")
        self.assertEqual(data["email"], "implementador@example.com")
        self.assertTrue(self.company.l10n_ve_implementer_is_configured())
        self.assertIn(
            "implementador@example.com",
            self.company.l10n_ve_implementer_email_from(),
        )

        if not self.env["account.journal"]._l10n_ve_seniat_dispatch_guide_dashboard_available():
            self.skipTest("l10n_ve_stock no instalado")

        self.company._l10n_ve_send_unfactured_dispatch_guides_email()
        mail = self.env["mail.mail"].search(
            [("email_to", "=", "alerts@example.com")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(mail)
        self.assertIn("implementador@example.com", mail.email_from or "")
        self.assertIn("AndyEng IT", mail.body_html or "")
