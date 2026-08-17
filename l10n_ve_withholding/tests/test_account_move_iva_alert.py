from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMoveIvaAlert(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_no_withholding = cls.env["res.partner"].create(
            {
                "name": "Proveedor sin retención",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J111111111",
                "withholding_type_id": False,
            }
        )
        cls.partner_with_withholding = cls.env["res.partner"].create(
            {
                "name": "Proveedor con retención",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J222222222",
            }
        )

    def _create_vendor_bill(self, partner):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
            }
        )

    def test_missing_withholding_alert_when_generate_iva_retention(self):
        move = self._create_vendor_bill(self.partner_no_withholding)
        move.generate_iva_retention = True
        self.assertTrue(move.l10n_ve_missing_iva_withholding_type)

    def test_no_alert_without_generate_iva_retention(self):
        move = self._create_vendor_bill(self.partner_no_withholding)
        self.assertFalse(move.l10n_ve_missing_iva_withholding_type)

    def test_no_alert_when_partner_has_withholding_type(self):
        move = self._create_vendor_bill(self.partner_with_withholding)
        move.generate_iva_retention = True
        self.assertFalse(move.l10n_ve_missing_iva_withholding_type)

    def test_no_alert_when_invoice_is_posted(self):
        move = self._create_vendor_bill(self.partner_no_withholding)
        move.generate_iva_retention = True
        move.state = "posted"
        self.assertFalse(move.l10n_ve_missing_iva_withholding_type)

    def test_validate_iva_retention_requires_explicit_withholding_type(self):
        move = self._create_vendor_bill(self.partner_no_withholding)
        move.generate_iva_retention = True
        with self.assertRaises(UserError):
            move._validate_iva_retention()
