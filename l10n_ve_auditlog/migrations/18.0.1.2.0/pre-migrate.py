# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT state
          FROM ir_module_module
         WHERE name = 'auditlog'
        """
    )
    row = cr.fetchone()
    if not row or row[0] not in ("installed", "to upgrade", "to remove"):
        return

    cr.execute(
        """
        SELECT m.name
          FROM ir_module_module m
          JOIN ir_module_module_dependency d ON d.module_id = m.id
         WHERE d.name = 'auditlog'
           AND m.state IN ('installed', 'to upgrade', 'to install')
           AND m.name NOT IN ('auditlog', 'l10n_ve_auditlog')
        """
    )
    dependents = [name for (name,) in cr.fetchall()]
    if dependents:
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'uninstalled',
                   latest_version = NULL
             WHERE name = ANY(%s)
            """,
            (dependents,),
        )

    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'l10n_ve_auditlog'
         WHERE module = 'auditlog'
        """
    )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled',
               latest_version = NULL
         WHERE name = 'auditlog'
        """
    )
