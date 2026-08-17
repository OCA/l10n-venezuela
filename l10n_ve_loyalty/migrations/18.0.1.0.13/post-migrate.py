from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    views = env["ir.ui.view"].search(
        [
            ("model", "=", "l10n.ve.account.move.post.discount.wizard"),
            ("inherit_id", "=", False),
            ("mode", "=", "primary"),
            ("arch_db", "ilike", "available_untaxed_amount"),
        ]
    )
    external_ids = views.get_external_id()
    views.filtered(lambda view: not external_ids.get(view.id)).unlink()
