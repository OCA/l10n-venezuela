import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    reason = env["l10n.ve.discount.reason"].search(
        [("active", "=", True)], order="sequence, id", limit=1
    )
    if not reason:
        return
    cr.execute(
        """
        UPDATE l10n_ve_sale_order_discount AS discount
        SET reason_id = %(reason_id)s,
            name = reason.name
        FROM l10n_ve_discount_reason AS reason
        WHERE reason.id = %(reason_id)s
          AND discount.reason_id IS NULL
        """,
        {"reason_id": reason.id},
    )
    if cr.rowcount:
        _logger.info(
            "Assigned default discount reason to %s sale order discount records",
            cr.rowcount,
        )
