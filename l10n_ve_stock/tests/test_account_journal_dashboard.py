from odoo.tests import tagged

from odoo.addons.l10n_ve_stock.tests.test_stock_picking_dispatch_guide import (
    TestL10nVeStockDispatchGuide,
)


@tagged("post_install", "-at_install")
class TestL10nVeSeniatInvoiceDashboardDispatch(TestL10nVeStockDispatchGuide):
    def test_dashboard_shows_unfactured_dispatch_guides(self):
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertTrue(picking.l10n_ve_control_number)

        data = self.env["account.journal"].get_l10n_ve_invoice_dashboard()
        self.assertTrue(data["visible"])
        keys = [item["key"] for item in data["items"]]
        self.assertIn("unfactured_dispatch_guides", keys)

        counts = {item["key"]: item["count"] for item in data["items"]}
        self.assertGreaterEqual(counts["unfactured_dispatch_guides"], 1)

        action = self.env["account.journal"].action_l10n_ve_invoice_dashboard_open(
            "unfactured_dispatch_guides"
        )
        self.assertEqual(action["res_model"], "stock.picking")
        self.assertIn(picking.id, action["domain"][0][2])
        list_view = self.env.ref(
            "l10n_ve_stock.stock_picking_unfactured_dispatch_guide_tree"
        )
        view_id = action.get("view_id")
        if isinstance(view_id, list | tuple):
            view_id = view_id[0]
        if view_id:
            self.assertEqual(view_id, list_view.id)
        else:
            self.assertIn((list_view.id, "list"), action.get("views") or [])
            self.assertEqual(
                (action.get("views") or [[None]])[0][0],
                list_view.id,
            )
        picking.invalidate_recordset(
            [
                "l10n_ve_dispatch_guide_date",
                "l10n_ve_dispatch_guide_time",
                "l10n_ve_dispatch_guide_user_id",
            ]
        )
        self.assertTrue(picking.l10n_ve_dispatch_guide_date)
        self.assertTrue(picking.l10n_ve_dispatch_guide_time)
        self.assertTrue(picking.l10n_ve_dispatch_guide_user_id)

    def test_dashboard_excludes_deliveries_without_control_number(self):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        warehouse.l10n_ve_dispatch_guide_section_id = False
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertFalse((picking.l10n_ve_control_number or "").strip())

        dispatch_guides, dispatch_available = self.env[
            "account.journal"
        ]._l10n_ve_seniat_unfactured_dispatch_guides(self.env.company)

        self.assertTrue(dispatch_available)
        self.assertNotIn(picking, dispatch_guides)
