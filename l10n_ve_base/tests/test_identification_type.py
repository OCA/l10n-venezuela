# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestIdentificationType(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.it_rif = cls.env.ref("l10n_ve_base.it_rif")
        cls.it_cedula_v = cls.env.ref("l10n_ve_base.it_cedula_v")
        cls.it_cedula_e = cls.env.ref("l10n_ve_base.it_cedula_e")
        cls.it_pass = cls.env.ref("l10n_ve_base.it_pass")

    def test_catalog_matches_screenshot_34(self):
        self.assertEqual(self.it_rif.country_id, self.ve)
        self.assertTrue(self.it_rif.is_vat)
        self.assertEqual(self.it_cedula_v.country_id, self.ve)
        self.assertFalse(self.it_cedula_e.country_id)
        self.assertFalse(self.it_pass.country_id)
        self.assertTrue(self.it_rif.active)
        self.assertTrue(self.it_cedula_v.active)
        self.assertTrue(self.it_cedula_e.active)
        self.assertTrue(self.it_pass.active)
        for xmlid in (
            "l10n_latam_base.it_vat",
            "l10n_latam_base.it_fid",
            "l10n_latam_base.it_pass",
        ):
            generic = self.env.ref(xmlid, raise_if_not_found=False)
            if generic:
                self.assertFalse(generic.active, xmlid)

    def test_rif_and_cedula_are_validated_by_type(self):
        Partner = self.env["res.partner"]
        Partner.create(
            {
                "name": "RIF ok",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_rif.id,
                "vat": "J123456784",
                "person_type": "pjdo",
            }
        )
        Partner.create(
            {
                "name": "Cédula V ok",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_cedula_v.id,
                "vat": "V7440703",
                "person_type": "pnre",
            }
        )
        Partner.create(
            {
                "name": "Cédula E ok",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_cedula_e.id,
                "vat": "E1234567",
                "person_type": "pnnr",
            }
        )
        Partner.create(
            {
                "name": "Pasaporte ok",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_pass.id,
                "vat": "AB123456",
                "person_type": "pnnr",
            }
        )
        with self.assertRaises(ValidationError):
            Partner.create(
                {
                    "name": "Cédula V con J",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_cedula_v.id,
                    "vat": "J123456784",
                    "person_type": "pnre",
                }
            )
        with self.assertRaises(ValidationError):
            Partner.create(
                {
                    "name": "RIF cédula corta",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_rif.id,
                    "vat": "V7440703",
                    "person_type": "pnre",
                }
            )

    def test_ve_partner_requires_vat(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Cliente sin número",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_rif.id,
                    "person_type": "pjdo",
                }
            )

    def test_person_type_must_match_identification(self):
        Partner = self.env["res.partner"]
        with self.assertRaises(ValidationError):
            Partner.create(
                {
                    "name": "Cédula V como PJDO",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_cedula_v.id,
                    "vat": "V7440703",
                    "person_type": "pjdo",
                }
            )
        with self.assertRaises(ValidationError):
            Partner.create(
                {
                    "name": "RIF J como PNRE",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_rif.id,
                    "vat": "J123456784",
                    "person_type": "pnre",
                }
            )
        with self.assertRaises(ValidationError):
            Partner.create(
                {
                    "name": "Cédula E como PJDO",
                    "country_id": self.ve.id,
                    "l10n_latam_identification_type_id": self.it_cedula_e.id,
                    "vat": "E1234567",
                    "person_type": "pjdo",
                }
            )
        Partner.create(
            {
                "name": "RIF V como PNRE",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_rif.id,
                "vat": "V123456781",
                "person_type": "pnre",
            }
        )
        Partner.create(
            {
                "name": "Pasaporte PJND",
                "country_id": self.ve.id,
                "l10n_latam_identification_type_id": self.it_pass.id,
                "vat": "AB123456",
                "person_type": "pjnd",
            }
        )

    def test_cedula_number_is_not_validated_as_rif(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cédula sin mezclar RIF",
                "country_id": self.ve.id,
                "vat": "V7440703",
            }
        )
        self.assertEqual(partner.l10n_latam_identification_type_id, self.it_cedula_v)
        self.assertEqual(partner.person_type, "pnre")

    def test_rif_keeps_checksum_and_nine_digits(self):
        partner = self.env["res.partner"].create(
            {
                "name": "RIF sociedad",
                "country_id": self.ve.id,
                "vat": "J123456784",
            }
        )
        self.assertEqual(partner.l10n_latam_identification_type_id, self.it_rif)
        self.assertEqual(partner.person_type, "pjdo")
