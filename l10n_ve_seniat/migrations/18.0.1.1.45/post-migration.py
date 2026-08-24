import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if version is None:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    books = env["account.book"].search([])
    books._l10n_ve_ensure_paperformat()
    _logger.info(
        "l10n_ve_seniat: formatos de papel creados/actualizados para %s talonarios",
        len(books),
    )
