# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTerritorial(TransactionCase):
    def test_mastercore_catalog_is_loaded(self):
        capital = self.env.ref("l10n_ve_base.state_ve_1")
        libertador = self.env.ref("l10n_ve_base.municipio_101")
        altagracia = self.env.ref("l10n_ve_base.parroquia_10101")
        self.assertEqual(capital.name, "Distrito Capital")
        self.assertEqual(libertador.state_id, capital)
        self.assertEqual(altagracia.municipality_id, libertador)
        self.assertGreaterEqual(
            self.env["res.country.state"].search_count(
                [("country_id.code", "=", "VE")]
            ),
            24,
        )
        self.assertGreater(
            self.env["res.country.state.municipality"].search_count([]),
            300,
        )

    def test_partner_accepts_municipality_and_parish(self):
        record = self.env["res.partner"].create(
            {
                "name": "Contacto territorial",
                "country_id": self.env.ref("base.ve").id,
                "state_id": self.env.ref("l10n_ve_base.state_ve_1").id,
                "municipality_id": self.env.ref("l10n_ve_base.municipio_101").id,
                "parish_id": self.env.ref("l10n_ve_base.parroquia_10101").id,
                "vat": "J123456784",
                "person_type": "pjdo",
            }
        )
        self.assertEqual(record.municipality_id.code, "101")
        self.assertEqual(record.parish_id.code, "10101")

    def test_partner_form_address_fields_are_search_only(self):
        from lxml import etree

        arch = self.env["res.partner"].get_view(
            self.env.ref("base.view_partner_form").id, "form"
        )["arch"]
        tree = etree.fromstring(arch)
        address = "//div[contains(@class, 'o_address_format')]"
        for name in ("state_id", "municipality_id", "parish_id"):
            nodes = tree.xpath(f"{address}//field[@name='{name}']")
            self.assertTrue(nodes, name)
            for node in nodes:
                self.assertIn("no_create", node.get("options") or "", name)

    def test_catalog_municipality_view_still_allows_create(self):
        from lxml import etree

        arch = self.env["res.country.state.municipality"].get_view(
            self.env.ref("l10n_ve_base.view_res_country_state_municipality_tree").id,
            "list",
        )["arch"]
        root = etree.fromstring(arch)
        self.assertNotEqual(root.get("create"), "false")
