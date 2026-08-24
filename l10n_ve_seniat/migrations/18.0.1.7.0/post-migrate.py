# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT state
          FROM ir_module_module
         WHERE name = 'l10n_ve_loyalty'
        """
    )
    row = cr.fetchone()
    if not row or row[0] != "installed":
        _logger.error(
            "l10n_ve_loyalty is not installed after upgrade (state=%s). "
            "Install it manually or check addons_path.",
            row[0] if row else None,
        )
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    if "l10n.ve.discount.reason" not in env:
        _logger.error("Model l10n.ve.discount.reason missing after migration")
        return
    reasons = env["l10n.ve.discount.reason"].search_count([])
    _logger.info(
        "l10n_ve_loyalty migration OK: %s discount reasons available",
        reasons,
    )
