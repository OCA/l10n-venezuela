# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_edoc_provider = fields.Selection(
        selection=[
            ("l10n.ve.edoc.provider.dummy", "Dummy (testing only)"),
        ],
        string="Electronic Document Provider",
        help="Technical model name of the provider adapter used by this company.",
    )
    l10n_ve_edoc_url = fields.Char(
        string="Provider URL",
        groups="base.group_system",
    )
    l10n_ve_edoc_user = fields.Char(
        string="Provider User",
        groups="base.group_system",
    )
    l10n_ve_edoc_password = fields.Char(
        string="Provider Password",
        groups="base.group_system",
    )
    l10n_ve_edoc_serie = fields.Char(string="Series")
    l10n_ve_edoc_sucursal = fields.Char(string="Branch")
    l10n_ve_edoc_test = fields.Boolean(
        string="Test Environment",
        default=True,
        help="Use the test environment exposed by the selected provider adapter.",
    )
