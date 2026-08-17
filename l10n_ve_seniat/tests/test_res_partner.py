# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestResPartner(L10nVeSeniatCommon):
    def test_check_vat_ve_valid_formats(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        valid_vats = [
            "V12345678",
            "V7440703",
            "E12345678",
            "J12345678",
            "G12345678",
            "J-12.345.678-9",
        ]
        for vat in valid_vats:
            partner.vat = vat
            self.assertTrue(
                partner.check_vat_ve(partner.vat), f"VAT {vat} should be valid"
            )

    def test_check_vat_ve_invalid_formats(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        invalid_vats = ["12345678", "X12345678", "V123", "V12345678901"]
        for vat in invalid_vats:
            self.assertFalse(partner.check_vat_ve(vat), f"VAT {vat} should be invalid")

    def test_ve_vat_constraint_allows_invalid_when_not_customer_nor_supplier(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        partner.write({"vat": "V123"})
        self.assertEqual(partner.vat, "V123")

    def test_ve_vat_constraint_rejects_invalid_on_write_when_customer(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        with self.assertRaises(ValidationError):
            partner.write({"vat": "V123"})

    def test_ve_vat_constraint_can_be_disabled(self):
        self.env.company.l10n_ve_validate_partner_vat_format = False
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        partner.write({"vat": "V123"})
        self.assertEqual(partner.vat, "V123")

    def test_ve_vat_constraint_skipped_with_context(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Sync partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        partner.with_context(skip_l10n_ve_vat_rif_format_check=True).write(
            {"vat": "no-rif"}
        )
        self.assertEqual(partner.vat, "Vno-rif")

    def test_compute_vat_prefix(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        self.assertEqual(partner.prefix_vat, "J")

    def test_taxpayer_type_ve_not_auto_set(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        self.assertFalse(partner.taxpayer_type)

    def test_taxpayer_type_ve_can_be_set_and_cleared(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "taxpayer_type": "formal",
            }
        )
        self.assertEqual(partner.taxpayer_type, "formal")
        partner.write({"taxpayer_type": False})
        self.assertFalse(partner.taxpayer_type)

    def test_taxpayer_type_non_ve(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.us").id}
        )
        self.assertFalse(partner.taxpayer_type)

    def test_ve_vat_auto_prefix_on_create(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente número",
                "country_id": self.env.ref("base.ve").id,
                "vat": "12345678",
            }
        )
        self.assertEqual(partner.vat, "V12345678")

    def test_ve_vat_auto_prefix_on_write(self):
        partner = self.env["res.partner"].create(
            {"name": "Cliente", "country_id": self.env.ref("base.ve").id}
        )
        partner.write({"vat": "12345678"})
        self.assertEqual(partner.vat, "V12345678")

    def test_ve_vat_auto_prefix_keeps_letter_prefix(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Jurídico",
                "country_id": self.env.ref("base.ve").id,
                "vat": "j12345678",
            }
        )
        self.assertEqual(partner.vat, "j12345678")

    def test_name_search_customer_mode(self):
        partners = (
            self.env["res.partner"]
            .with_context(res_partner_search_mode="customer")
            .name_search("Partner")
        )
        self.assertTrue(isinstance(partners, list))

    def test_name_search_supplier_mode(self):
        partners = (
            self.env["res.partner"]
            .with_context(res_partner_search_mode="supplier")
            .name_search("Partner")
        )
        self.assertTrue(isinstance(partners, list))

    def test_default_get_create_edit_prefills_vat_ve(self):
        defaults = (
            self.env["res.partner"]
            .with_context(default_name="J-12.345.678-9")
            .default_get(["name", "vat"])
        )
        self.assertEqual(defaults.get("vat"), "J-12.345.678-9")
        self.assertFalse(defaults.get("name"))

    def test_default_get_razon_social_no_prefill_vat(self):
        defaults = (
            self.env["res.partner"]
            .with_context(default_name="Venezolana de Envases C.A.")
            .default_get(["name", "vat"])
        )
        self.assertEqual(defaults.get("name"), "Venezolana de Envases C.A.")

    def test_check_taxpayer_type_country_constraint(self):
        partner = self.env["res.partner"].create(
            {"name": "US Partner", "country_id": self.env.ref("base.us").id}
        )
        with self.assertRaises(ValidationError) as cm:
            partner.taxpayer_type = "ordinary"
        self.assertIn("Venezuelan", str(cm.exception))

    def test_taxpayer_type_company_fiscal_ve_without_partner_country(self):
        ve = self.env.ref("base.ve")
        company = self.env["res.company"].create({"name": "Empresa VE nueva"})
        company.account_fiscal_country_id = ve
        partner = company.partner_id
        self.assertFalse(partner.country_id)
        partner.write({"taxpayer_type": "ordinary"})
        self.assertEqual(partner.taxpayer_type, "ordinary")

    def test_partner_name_vat_locked_after_posted_move(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente fiscal",
                "country_id": self.env.ref("base.ve").id,
                "vat": "V12345678",
            }
        )
        invoice = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=partner,
            amounts=[1000.0],
            taxes=self.tax_sale_a,
            post=True,
        )
        self.assertEqual(invoice.state, "posted")
        user = new_test_user(
            self.env,
            login="l10n_ve_partner_lock_user",
            groups="account.group_account_invoice,base.group_partner_manager",
        )
        self.assertFalse(
            user.has_group("l10n_ve_seniat.group_l10n_ve_override_locked_master_data")
        )
        partner_as_user = partner.with_user(user)
        with self.assertRaises(UserError):
            partner_as_user.write({"name": "Otro nombre"})
        with self.assertRaises(UserError):
            partner_as_user.write({"vat": "V87654321"})
        partner.write({"name": "Nombre admin", "vat": "V87654321"})
        self.assertEqual(partner.name, "Nombre admin")
        self.assertEqual(partner.vat, "V87654321")

    def test_partner_name_vat_lock_can_be_disabled(self):
        self.env.company.l10n_ve_lock_partner_fiscal_data = False
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente fiscal",
                "country_id": self.env.ref("base.ve").id,
                "vat": "V12345678",
            }
        )
        invoice = self._l10n_ve_create_invoice(
            move_type="out_invoice",
            partner=partner,
            amounts=[1000.0],
            taxes=self.tax_sale_a,
            post=True,
        )
        self.assertEqual(invoice.state, "posted")
        user = new_test_user(
            self.env,
            login="l10n_ve_partner_lock_disabled_user",
            groups="account.group_account_invoice,base.group_partner_manager",
        )
        partner.with_user(user).write({"name": "Otro nombre", "vat": "V87654321"})
        self.assertEqual(partner.name, "Otro nombre")
        self.assertEqual(partner.vat, "V87654321")
