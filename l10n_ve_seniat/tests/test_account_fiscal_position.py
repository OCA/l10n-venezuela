# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


class TestAccountFiscalPosition(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fpos = cls.env["account.fiscal.position"]
        cls.ne_state = cls.env.ref("l10n_ve_seniat.res_country_state_17")
        cls.caracas_state = cls.env.ref("l10n_ve_seniat.res_country_state_1")
        cls.free_port_fpos = cls.env.ref(
            "l10n_ve_seniat.fiscal_position_puerto_libre",
            raise_if_not_found=False,
        )
        if not cls.free_port_fpos or cls.free_port_fpos.company_id != cls.env.company:
            cls.free_port_fpos = cls.Fpos.search(
                [
                    ("company_id", "=", cls.env.company.id),
                    ("auto_apply", "=", True),
                    ("state_ids", "in", cls.ne_state.ids),
                ],
                order="sequence, id",
                limit=1,
            )
        if not cls.free_port_fpos:
            cls.free_port_fpos = cls.Fpos.create(
                {
                    "name": "Puerto Libre",
                    "company_id": cls.env.company.id,
                    "auto_apply": True,
                    "vat_required": False,
                    "country_id": cls.env.ref("base.ve").id,
                    "state_ids": [(6, 0, cls.ne_state.ids)],
                    "sequence": 5,
                }
            )

    def test_free_port_fiscal_position_has_nueva_esparta(self):
        self.assertTrue(self.free_port_fpos.auto_apply)
        self.assertIn(self.ne_state, self.free_port_fpos.state_ids)

    def test_free_port_auto_apply_by_state(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente Puerto Libre",
                "country_id": self.env.ref("base.ve").id,
                "state_id": self.ne_state.id,
            }
        )
        fpos = self.Fpos._get_fiscal_position(partner)
        self.assertEqual(fpos, self.free_port_fpos)

    def test_free_port_not_applied_outside_states(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente Caracas",
                "country_id": self.env.ref("base.ve").id,
                "state_id": self.caracas_state.id,
            }
        )
        fpos = self.Fpos._get_fiscal_position(partner)
        self.assertNotEqual(fpos, self.free_port_fpos)
