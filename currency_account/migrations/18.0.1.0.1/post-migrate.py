def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.currency"]._sync_currency_groups_for_existing_fields()
