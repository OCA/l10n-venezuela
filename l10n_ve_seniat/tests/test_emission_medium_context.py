# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from uuid import uuid4

from odoo.tests import HttpCase, tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeEmissionMediumContext(L10nVeSeniatCommon):
    def test_company_emission_medium_codes_and_flags(self):
        company = self.env.company
        free = self.env.ref("l10n_ve_seniat.emission_medium_free_form")
        fiscal = self.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")
        company.write({"l10n_ve_emission_medium_ids": [(6, 0, [fiscal.id])]})
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("fiscal_machine",))
        self.assertTrue(company._l10n_ve_has_emission_medium("fiscal_machine"))
        self.assertFalse(company._l10n_ve_has_emission_medium("free_form"))
        self.assertTrue(company.l10n_ve_has_fiscal_machine)
        self.assertFalse(company.l10n_ve_has_free_form)
        self.assertFalse(company.l10n_ve_has_digital_billing)
        company.write({"l10n_ve_emission_medium_ids": [(6, 0, [free.id])]})
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("free_form",))
        self.assertTrue(company.l10n_ve_has_free_form)
        self.assertFalse(company.l10n_ve_has_fiscal_machine)


@tagged("post_install", "-at_install")
class TestL10nVeEmissionMediumSession(HttpCase):
    def test_session_info_contains_emission_medium_codes(self):
        fiscal = self.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")
        company = self.env.company
        company.write({"l10n_ve_emission_medium_ids": [(6, 0, [fiscal.id])]})
        self.authenticate("admin", "admin")
        payload = json.dumps({"jsonrpc": "2.0", "method": "call", "id": str(uuid4())})
        res = self.url_open(
            "/web/session/get_session_info",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["result"]
        self.assertIn("fiscal_machine", data.get("l10n_ve_emission_medium_codes", []))
        self.assertIn(
            "fiscal_machine",
            data.get("user_context", {}).get("l10n_ve_emission_medium_codes", []),
        )
        by_company = data.get("l10n_ve_emission_medium_codes_by_company", {})
        self.assertIn(
            "fiscal_machine",
            by_company.get(company.id, by_company.get(str(company.id), [])),
        )

    def test_load_menus_uses_cids_cookie_company(self):
        menu = self.env.ref(
            "l10n_ve_fiscal_serial.menu_seniat_fiscal_machines",
            raise_if_not_found=False,
        )
        if not menu:
            self.skipTest("l10n_ve_fiscal_serial is not installed.")
        fiscal = self.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")
        free = self.env.ref("l10n_ve_seniat.emission_medium_free_form")
        default_company = self.env.ref("base.main_company")
        other = self.env["res.company"].create(
            {"name": "HTTP Cids Menu Co", "country_id": self.env.ref("base.ve").id}
        )
        default_company.write({"l10n_ve_emission_medium_ids": [(6, 0, [free.id])]})
        other.write({"l10n_ve_emission_medium_ids": [(6, 0, [fiscal.id])]})
        admin = self.env.ref("base.user_admin")
        admin.write(
            {
                "company_id": default_company.id,
                "company_ids": [(4, other.id)],
                "groups_id": [(4, self.env.ref("l10n_ve_seniat.group_seniat").id)],
            }
        )
        self.authenticate("admin", "admin")
        self.env.registry.clear_cache()
        self.opener.cookies["cids"] = str(default_company.id)
        res_default = self.url_open("/web/webclient/load_menus/test-default")
        self.assertEqual(res_default.status_code, 200)
        menus_default = res_default.json()
        self.assertNotIn(str(menu.id), menus_default)
        self.assertNotIn(menu.id, menus_default)

        self.opener.cookies["cids"] = str(other.id)
        res_other = self.url_open("/web/webclient/load_menus/test-other")
        self.assertEqual(res_other.status_code, 200)
        menus_other = res_other.json()
        self.assertTrue(
            str(menu.id) in menus_other or menu.id in menus_other,
            "Fiscal machines menu must appear when cids points to fiscal company",
        )
