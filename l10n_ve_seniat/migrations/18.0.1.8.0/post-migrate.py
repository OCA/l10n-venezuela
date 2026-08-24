def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in (
        "ir_cron_unfactured_dispatch_guides_email",
        "mail_template_unfactured_dispatch_guides",
    ):
        record = env.ref(f"l10n_ve_seniat.{xmlid}", raise_if_not_found=False)
        if record:
            record.unlink()
