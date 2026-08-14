# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_OLD_FLAG_21 = "l10n_ve_fiscal_serial_flag_21"


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_ui_view
           SET active = FALSE
         WHERE active = TRUE
           AND arch_db::text ILIKE %s
        """,
        ("%" + _OLD_FLAG_21 + "%",),
    )
    if cr.rowcount:
        _logger.info(
            "Deactivated %s view(s) referencing removed field %s",
            cr.rowcount,
            _OLD_FLAG_21,
        )
