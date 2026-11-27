# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestBanksAndResponsibility(TransactionCase):
    def test_ve_banks_loaded(self):
        bank = self.env.ref("l10n_ve_base.bank_0102")
        self.assertEqual(bank.bic, "0102")
        self.assertEqual(bank.country.code, "VE")
        self.assertTrue(bank.name)

    def test_responsibility_types(self):
        especial = self.env.ref("l10n_ve_base.responsibility_especial")
        self.assertEqual(especial.code, "3")
        partner = self.env["res.partner"].create(
            {
                "name": "Contribuyente Especial",
                "country_id": self.env.ref("base.ve").id,
                "l10n_latam_identification_type_id": self.env.ref(
                    "l10n_ve_base.it_rif"
                ).id,
                "vat": "J123456784",
                "person_type": "pjdo",
                "l10n_ve_responsibility_type_id": especial.id,
            }
        )
        self.assertEqual(partner.l10n_ve_responsibility_type_id, especial)
