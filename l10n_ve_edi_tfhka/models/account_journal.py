from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_edi_provider = fields.Selection(
        selection_add=[("tfhka", "The Factory HKA")],
    )
    l10n_ve_edi_tfhka_serie = fields.Char(
        string="Serie (TFHKA)",
        copy=False,
        help=(
            "Debe coincidir exactamente con la serie del rango en The Factory HKA. "
            "Deje vacío para enviar serie vacía al API (numeración unificada / sin "
            "serie en HKA). Para forzar vacío si existe series_correlative en el "
            "diario, guarde un guion (-) en este campo."
        ),
    )
    l10n_ve_edi_tfhka_sucursal = fields.Char(
        string="Sucursal / establecimiento (TFHKA)",
        size=6,
        copy=False,
        help=(
            "Código de sucursal en identificacionDocumento (máx. 6 caracteres). "
            "Debe coincidir con el rango en el portal TFHKA; si su integración "
            "válida usa sucursal vacía en el JSON, deje este campo vacío (no use "
            "00 salvo que en HKA el rango esté dado de alta con 00)."
        ),
    )
    l10n_ve_edi_tfhka_environment_digit = fields.Char(
        string="Dígito de ambiente (TFHKA)",
        size=1,
        default="0",
        copy=False,
        help=(
            "Dígito insertado en numeroDocumento después del año y mes (AAAAMM) "
            "para distinguir ambientes TFHKA distintos. Use 0 en producción "
            "(formato habitual). En pruebas u otros entornos asigne 1-9 para "
            "evitar colisiones de numeroDocumento con documentos ya emitidos "
            "en otro ambiente."
        ),
    )

    @api.constrains("l10n_ve_edi_tfhka_environment_digit")
    def _check_l10n_ve_edi_tfhka_environment_digit(self):
        for journal in self:
            raw = (journal.l10n_ve_edi_tfhka_environment_digit or "").strip()
            if not raw:
                continue
            if len(raw) != 1 or not raw.isdigit():
                raise ValidationError(
                    _(
                        "El dígito de ambiente TFHKA debe ser un solo carácter "
                        "numérico (0-9)."
                    )
                )

    def _tfhka_get_numero_documento_environment_digit(self):
        self.ensure_one()
        return self.env[
            "l10n_ve.edi.tfhka.document.mixin"
        ]._tfhka_normalize_environment_digit(self.l10n_ve_edi_tfhka_environment_digit)
