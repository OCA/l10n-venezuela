from odoo.tests import tagged

from odoo.addons.stock.tests.common import TestStockCommon


@tagged("post_install", "-at_install")
class TestL10nVeStockReturnTransferReason(TestStockCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {"account_fiscal_country_id": cls.env.ref("base.ve").id}
        )

    def test_return_incoming_picking_without_transfer_reason(self):
        picking_in = self.PickingObj.create(
            {
                "picking_type_id": self.picking_type_in,
                "location_id": self.supplier_location,
                "location_dest_id": self.stock_location,
            }
        )
        move = self.MoveObj.create(
            {
                "name": self.productA.name,
                "product_id": self.productA.id,
                "product_uom_qty": 5,
                "product_uom": self.uom_unit.id,
                "picking_id": picking_in.id,
                "location_id": self.supplier_location,
                "location_dest_id": self.stock_location,
            }
        )
        picking_in.action_confirm()
        picking_in.action_assign()
        move.quantity = 5
        picking_in.move_ids.picked = True
        picking_in.button_validate()

        return_wizard = (
            self.env["stock.return.picking"]
            .with_context(
                active_id=picking_in.id,
                active_ids=picking_in.ids,
                active_model="stock.picking",
            )
            .create({})
        )
        return_wizard.product_return_moves.quantity = 5
        action = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(action["res_id"])

        self.assertTrue(return_picking.return_id)
        self.assertFalse(return_picking._l10n_ve_requires_internal_transfer_reason())

        return_picking.action_confirm()
        return_picking.action_assign()
        return_picking.move_ids.quantity = 5
        return_picking.move_ids.picked = True
        return_picking.button_validate()
