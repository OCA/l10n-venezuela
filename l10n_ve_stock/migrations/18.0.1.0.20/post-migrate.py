from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    picking_model = env["ir.model"]._get("stock.picking")
    if not picking_model:
        return
    xmlids = (
        "stock.action_report_picking",
        "stock.action_report_delivery",
        "stock.action_report_picking_packages",
        "stock.return_label_report",
    )
    reports = env["ir.actions.report"]
    for xmlid in xmlids:
        report = env.ref(xmlid, raise_if_not_found=False)
        if report:
            reports |= report
    if reports:
        reports.sudo().write(
            {
                "binding_model_id": picking_model.id,
                "binding_type": "report",
            }
        )
