from odoo import _, models
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_pos_session_open(self):
        for session in self:
            company = session.company_id
            if (
                company.l10n_ve_igtf_feature_active
                and not company.l10n_ve_igtf_account_id
            ):
                raise ValidationError(
                    _(
                        "El IGTF está activo para esta compañía: "
                        "configure la cuenta IGTF "
                        "en Ajustes / Venezuela antes de abrir la "
                        "sesión del TPV."
                    )
                )
        return super().action_pos_session_open()
