# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nVeEmissionMedium(models.Model):
    """Medios de emisión de facturas y otros documentos (SENIAT)."""

    _name = "l10n.ve.emission.medium"
    _description = "Medio de emisión SENIAT"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Código técnico para condicionar vistas y lógica de negocio.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code)",
            "El código del medio de emisión debe ser único.",
        ),
    ]

    def _l10n_ve_emission_medium_is_readonly(self):
        return not self.env.su

    @api.model_create_multi
    def create(self, vals_list):
        if self._l10n_ve_emission_medium_is_readonly():
            raise UserError(
                _("Los medios de emisión son de solo lectura y no pueden crearse.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if self._l10n_ve_emission_medium_is_readonly():
            raise UserError(
                _("Los medios de emisión son de solo lectura y no pueden modificarse.")
            )
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_superuser(self):
        if self._l10n_ve_emission_medium_is_readonly():
            raise UserError(
                _("Los medios de emisión son de solo lectura y no pueden eliminarse.")
            )
