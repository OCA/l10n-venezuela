# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Repair manual discounts stored as JSON strings by POS serialize()."""
    cr.execute(
        """
        SELECT id, l10n_ve_manual_global_discounts
          FROM pos_order
         WHERE l10n_ve_manual_global_discounts IS NOT NULL
           AND jsonb_typeof(l10n_ve_manual_global_discounts) = 'string'
        """
    )
    rows = cr.fetchall()
    for order_id, raw_value in rows:
        data = raw_value
        for _attempt in range(3):
            if isinstance(data, list):
                break
            if isinstance(data, str) and data:
                try:
                    data = json.loads(data)
                except (TypeError, ValueError, json.JSONDecodeError):
                    data = []
                    break
                continue
            data = []
            break
        if not isinstance(data, list):
            data = []
        cr.execute(
            """
            UPDATE pos_order
               SET l10n_ve_manual_global_discounts = %s::jsonb
             WHERE id = %s
            """,
            [json.dumps(data), order_id],
        )
    if rows:
        _logger.info(
            "l10n_ve_loyalty_pos: normalized %s pos.order manual discount values",
            len(rows),
        )
