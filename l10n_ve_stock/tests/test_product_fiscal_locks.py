from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeStockProductFiscalLocks(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not getattr(cls, "tax_sale_b", None):
            cls.tax_sale_b = cls.tax_sale_a.copy({"name": "sale_tax_b_dup"})
        cls.locked_user = new_test_user(
            cls.env,
            login="ve_stock_fiscal_locked",
            groups="base.group_user,stock.group_stock_manager,"
            "sales_team.group_sale_salesman,account.group_account_invoice",
        )
        cls.unlocked_user = new_test_user(
            cls.env,
            login="ve_stock_fiscal_unlock",
            groups="base.group_user,stock.group_stock_manager,"
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data",
        )

    def test_product_requires_exactly_one_sale_tax_ve(self):
        ProductTemplate = self.env["product.template"].with_user(self.locked_user)
        # Empty taxes_id is auto-filled by l10n_ve_seniat create(); two taxes must fail.
        with self.assertRaises(ValidationError):
            ProductTemplate.create(
                {
                    "name": "Dos impuestos",
                    "is_storable": True,
                    "company_id": self.env.company.id,
                    "taxes_id": [
                        Command.set((self.tax_sale_a + self.tax_sale_b).ids)
                    ],
                }
            )
        tmpl = ProductTemplate.create(
            {
                "name": "Un impuesto",
                "is_storable": True,
                "company_id": self.env.company.id,
                "taxes_id": [Command.set(self.tax_sale_a.ids)],
                "supplier_taxes_id": [
                    Command.set(self.company_data["default_tax_purchase"].ids)
                ],
            }
        )
        with self.assertRaises(ValidationError):
            tmpl.with_context(l10n_ve_skip_auto_exent_taxes=True).write(
                {"taxes_id": [Command.clear()]}
            )

    def test_product_default_code_and_taxes_locked_after_done_move(self):
        product = self._create_product(
            name="Prod bloqueo",
            is_storable=True,
            default_code="REF-001",
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        tmpl = product.product_tmpl_id
        picking_type_in = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(picking_type_in)
        supplier_loc = self.env.ref("stock.stock_location_suppliers")
        stock_loc = picking_type_in.default_location_dest_id
        picking_in = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type_in.id,
                "location_id": supplier_loc.id,
                "location_dest_id": stock_loc.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "picking_id": picking_in.id,
                "location_id": supplier_loc.id,
                "location_dest_id": stock_loc.id,
            }
        )
        picking_in.action_confirm()
        picking_in.action_assign()
        move.move_line_ids.quantity = 1
        move.move_line_ids.picked = True
        picking_in._action_done()

        tmpl_locked = tmpl.with_user(self.locked_user)
        with self.assertRaises(UserError):
            tmpl_locked.write({"default_code": "REF-002"})
        with self.assertRaises(UserError):
            tmpl_locked.write({"taxes_id": [Command.set(self.tax_sale_b.ids)]})

        tmpl.with_user(self.unlocked_user).write({"default_code": "REF-002"})
        self.assertEqual(tmpl.default_code, "REF-002")
