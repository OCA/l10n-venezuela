# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_edoc_provider = fields.Selection(
        related="company_id.l10n_ve_edoc_provider",
        readonly=False,
    )
    l10n_ve_edoc_url = fields.Char(
        related="company_id.l10n_ve_edoc_url",
        readonly=False,
        groups="base.group_system",
    )
    l10n_ve_edoc_user = fields.Char(
        related="company_id.l10n_ve_edoc_user",
        readonly=False,
        groups="base.group_system",
    )
    l10n_ve_edoc_password = fields.Char(
        related="company_id.l10n_ve_edoc_password",
        readonly=False,
        groups="base.group_system",
    )
    l10n_ve_edoc_serie = fields.Char(
        related="company_id.l10n_ve_edoc_serie",
        readonly=False,
    )
    l10n_ve_edoc_sucursal = fields.Char(
        related="company_id.l10n_ve_edoc_sucursal",
        readonly=False,
    )
    l10n_ve_edoc_test = fields.Boolean(
        related="company_id.l10n_ve_edoc_test",
        readonly=False,
    )
