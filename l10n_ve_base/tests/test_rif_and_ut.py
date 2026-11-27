# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRifAndUt(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.ut = cls.env["l10n.ut"]

    def test_valid_rif_letters(self):
        Partner = self.env["res.partner"]
        person_by_letter = {"V": "pnre", "J": "pjdo", "G": "pjdo", "C": "pjdo"}
        for vat in ("V123456781", "J123456784", "G200000007", "C123456709"):
            partner = Partner.create(
                {
                    "name": f"RIF {vat}",
                    "country_id": self.ve.id,
                    "vat": vat,
                    "person_type": person_by_letter[vat[0]],
                }
            )
            self.assertTrue(partner._l10n_ve_is_valid_rif(partner.vat))

    def test_normalize_ve_prefix(self):
        Partner = self.env["res.partner"]
        self.assertEqual(Partner._l10n_ve_normalize_rif("VEJ123456789"), "J123456789")
        self.assertEqual(Partner._l10n_ve_normalize_rif("j-12.345.678-9"), "J123456789")

    def test_invalid_rif_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "RIF inválido",
                    "country_id": self.ve.id,
                    "vat": "X1234567",
                }
            )

    def test_invalid_rif_checksum_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "RIF dígito malo",
                    "country_id": self.ve.id,
                    "vat": "J123456789",
                }
            )

    def test_duplicate_rif_rejected(self):
        vals = {
            "name": "Primero",
            "country_id": self.ve.id,
            "vat": "J111111110",
            "person_type": "pjdo",
        }
        self.env["res.partner"].create(vals)
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(dict(vals, name="Duplicado"))

    def test_duplicate_rif_ignores_punctuation(self):
        self.env["res.partner"].create(
            {
                "name": "Primero",
                "country_id": self.ve.id,
                "vat": "J123456784",
                "person_type": "pjdo",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Duplicado con guiones",
                    "country_id": self.ve.id,
                    "vat": "j-12345678-4",
                    "person_type": "pjdo",
                }
            )

    def test_duplicate_cedula_rejected(self):
        self.env["res.partner"].create(
            {
                "name": "Cédula",
                "country_id": self.ve.id,
                "vat": "V7440703",
            }
        )
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Cédula repetida",
                    "country_id": self.ve.id,
                    "vat": "v-7440703",
                }
            )

    def test_company_contact_can_share_parent_rif(self):
        company = self.env["res.partner"].create(
            {
                "name": "Empresa",
                "is_company": True,
                "country_id": self.ve.id,
                "vat": "J123456784",
                "person_type": "pjdo",
            }
        )
        contact = self.env["res.partner"].create(
            {
                "name": "Contacto",
                "parent_id": company.id,
                "type": "contact",
                "vat": "J-12345678-4",
            }
        )
        self.assertEqual(contact.commercial_partner_id, company)

    def test_ut_2025_is_43(self):
        amount = self.ut.get_amount_ut("2025-09-01")
        self.assertAlmostEqual(amount, 43.0, places=2)

    def test_amount_to_ves_same_currency(self):
        ves = self.ut.get_ves_currency()
        self.assertAlmostEqual(self.ut.amount_to_ves(100.0, ves, "2025-09-01"), 100.0)

    def test_ves_symbol_is_bs(self):
        ves = self.env.ref("base.VES")
        ve = self.env.ref("base.ve")
        self.assertEqual(ves.symbol, "Bs")
        self.assertEqual(ves.full_name, "Venezuelan bolívar soberano")
        self.assertEqual(ves.position, "after")
        self.assertFalse(ves.currency_unit_label)
        self.assertFalse(ves.currency_subunit_label)
        self.assertTrue(ves.active)
        self.assertEqual(ve.currency_id, ves)
        self.assertEqual(ves.name, "VES")

    def test_amount_to_ves_zero_skips_rate(self):
        usd = self.env.ref("base.USD")
        self.assertEqual(self.ut.amount_to_ves(0.0, usd, "2026-09-14"), 0.0)

    def test_amount_to_ves_vef_needs_no_bcv_rate(self):
        vef = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if not vef:
            self.skipTest("VEF currency is not installed")
        self.assertAlmostEqual(self.ut.amount_to_ves(100.0, vef, "2026-09-14"), 100.0)

    def test_amount_to_ves_without_rate_raises(self):
        currency = self.env["res.currency"].create(
            {
                "name": "ZZZ",
                "symbol": "Z",
            }
        )
        ves = self.ut.get_ves_currency()
        if currency == ves:
            self.skipTest("Company currency is the test currency")
        with self.assertRaises(UserError):
            self.ut.amount_to_ves(10.0, currency, "2025-09-01")

    def test_commercials_with_activity_ignores_partner_without_documents(self):
        """A partner with no posted documents is not locked."""
        partner = self.env["res.partner"].create(
            {
                "name": "Partner init path",
                "country_id": self.ve.id,
                "vat": "J555555554",
                "person_type": "pjdo",
            }
        )
        self.assertFalse(partner in partner._l10n_ve_commercials_with_activity())
        partner.write({"country_id": self.ve.id})
