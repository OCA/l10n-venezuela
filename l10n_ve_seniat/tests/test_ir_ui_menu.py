# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeIrUiMenu(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")
        cls.menu = cls.env.ref(
            "l10n_ve_fiscal_serial.menu_seniat_fiscal_machines",
            raise_if_not_found=False,
        )
        cls.report_menu = cls.env.ref(
            "l10n_ve_reports.menu_seniat_report_sales_book_fiscal_machine",
            raise_if_not_found=False,
        )
        cls.fiscal_medium = cls.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")

    def test_fiscal_machine_menu_hidden_without_medium(self):
        if not self.menu:
            self.skipTest("l10n_ve_fiscal_serial is not installed.")
        self.env.company.write({"l10n_ve_emission_medium_ids": [(5, 0, 0)]})
        self.env.registry.clear_cache()
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertIn(self.menu.id, blacklist)
        menus = self.env["ir.ui.menu"].load_menus(False)
        self.assertNotIn(self.menu.id, menus)

    def test_fiscal_machine_menu_visible_from_company_medium(self):
        if not self.menu:
            self.skipTest("l10n_ve_fiscal_serial is not installed.")
        self.env.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [self.fiscal_medium.id])]}
        )
        self.env.registry.clear_cache()
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertNotIn(self.menu.id, blacklist)
        menus = self.env["ir.ui.menu"].load_menus(False)
        self.assertIn(self.menu.id, menus)

    def test_fiscal_machine_report_menu_hidden_without_medium(self):
        if not self.report_menu:
            self.skipTest("l10n_ve_reports fiscal machine menu is not installed.")
        self.env.company.write({"l10n_ve_emission_medium_ids": [(5, 0, 0)]})
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertIn(self.report_menu.id, blacklist)

    def test_fiscal_machine_report_menu_visible_from_company_medium(self):
        if not self.report_menu:
            self.skipTest("l10n_ve_reports fiscal machine menu is not installed.")
        self.env.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [self.fiscal_medium.id])]}
        )
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertNotIn(self.report_menu.id, blacklist)

    def test_load_menus_respects_active_company(self):
        if not self.menu:
            self.skipTest("l10n_ve_fiscal_serial is not installed.")
        company = self.env.company
        other_company = self.env["res.company"].create(
            {"name": "Other Co Menu Test", "country_id": self.env.ref("base.ve").id}
        )
        company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [self.fiscal_medium.id])]}
        )
        other_company.write({"l10n_ve_emission_medium_ids": [(5, 0, 0)]})
        self.env.user.company_ids |= other_company
        self.env.registry.clear_cache()
        menus_with = (
            self.env["ir.ui.menu"]
            .with_context(allowed_company_ids=[company.id])
            .load_menus(False)
        )
        menus_without = (
            self.env["ir.ui.menu"]
            .with_context(allowed_company_ids=[other_company.id])
            .load_menus(False)
        )
        self.assertIn(self.menu.id, menus_with)
        self.assertNotIn(self.menu.id, menus_without)
