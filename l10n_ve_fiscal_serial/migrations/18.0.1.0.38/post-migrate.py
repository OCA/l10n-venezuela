import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([])
    companies._l10n_ve_fiscal_ensure_payment_methods()
    _logger.info(
        "Ensured fiscal payment methods for %s companies",
        len(companies),
    )
