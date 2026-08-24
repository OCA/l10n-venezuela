from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nVeStockPickingValidateConfirmation(models.TransientModel):
    _name = "l10n_ve.stock.picking.validate.confirmation"
    _description = "Confirmación de validación de guía de despacho"

    picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        string="Entregas",
        required=True,
    )
    l10n_ve_next_control_number = fields.Char(
        string="Próximo N° de control",
        compute="_compute_l10n_ve_next_control_number",
    )
    l10n_ve_confirmation_message = fields.Html(
        string="Mensaje",
        compute="_compute_l10n_ve_confirmation_message",
        sanitize=False,
    )

    @api.depends("picking_ids", "picking_ids.l10n_ve_control_number_placeholder")
    def _compute_l10n_ve_next_control_number(self):
        for wizard in self:
            numbers = [
                (picking.l10n_ve_control_number_placeholder or "").strip()
                for picking in wizard.picking_ids
                if (picking.l10n_ve_control_number_placeholder or "").strip()
            ]
            wizard.l10n_ve_next_control_number = ", ".join(dict.fromkeys(numbers))

    @api.depends("picking_ids", "l10n_ve_next_control_number")
    def _compute_l10n_ve_confirmation_message(self):
        for wizard in self:
            if len(wizard.picking_ids) == 1:
                picking_name = wizard.picking_ids.display_name
                number = wizard.l10n_ve_next_control_number or "—"
                wizard.l10n_ve_confirmation_message = Markup(
                    "<p>{}</p><p>{}</p><p>{}</p>"
                ).format(
                    _(
                        "Are you sure you want to confirm delivery "
                        "<strong>%(picking)s</strong>?"
                    )
                    % {"picking": picking_name},
                    _(
                        "This delivery will assign control number "
                        "<strong>%(number)s</strong>."
                    )
                    % {"number": number},
                    _(
                        "After validation, the document will be recorded as a "
                        "dispatch guide and cannot be adjusted soon."
                    ),
                )
            else:
                lines = "".join(
                    f"<li>{picking.display_name}</li>" for picking in wizard.picking_ids
                )
                number = wizard.l10n_ve_next_control_number or "—"
                wizard.l10n_ve_confirmation_message = Markup(
                    "<p>{}</p><ul>{}</ul><p>{}</p><p>{}</p>"
                ).format(
                    _("Are you sure you want to confirm these deliveries?"),
                    lines,
                    _(
                        "The following control numbers will be assigned: "
                        "<strong>%(number)s</strong>."
                    )
                    % {"number": number},
                    _(
                        "After validation, the documents will be recorded as "
                        "dispatch guides and cannot be adjusted soon."
                    ),
                )

    def action_confirm(self):
        pickings = self.picking_ids
        if not pickings:
            raise UserError(_("No hay entregas seleccionadas para validar."))
        return pickings.with_context(
            l10n_ve_dispatch_guide_validate_confirmed=True,
        ).button_validate()
