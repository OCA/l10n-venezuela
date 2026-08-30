# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Extensible selection: a third-party adapter can add its own key with
    # selection_add.
    l10n_ve_edoc_provider = fields.Selection(
        [
            ("l10n.ve.edoc.provider.hka", "The Factory HKA"),
            ("l10n.ve.edoc.provider.dummy", "Test provider (simulation only)"),
        ],
        string="Digital printing house provider",
    )
    l10n_ve_edoc_url = fields.Char(
        string="Provider URL (production)",
        help="Base URL of the PRODUCTION environment, without a path (the "
        'provider hands it over with the contract). While "Test '
        'environment" is checked this is ignored: the adapter uses '
        "the provider's own documented demo URL, so a test can never "
        "reach production by mistake.",
    )
    l10n_ve_edoc_user = fields.Char(string="Provider username")
    l10n_ve_edoc_password = fields.Char(string="Provider password")
    # Series and branch as two separate fields: the provider treats them as
    # two distinct document fields (one company can have several branches,
    # and several series per branch).
    l10n_ve_edoc_serie = fields.Char(string="Series")
    l10n_ve_edoc_sucursal = fields.Char(string="Branch")
    l10n_ve_edoc_test = fields.Boolean(
        string="Test environment",
        default=True,
        help="While checked, the provider's demo environment is used "
        "(with The Factory HKA, demoemisionv2.thefactoryhka.com.ve). "
        "Uncheck only once SENIAT has authorized the issuer.",
    )
