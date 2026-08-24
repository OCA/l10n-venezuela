from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action

from .edi_mixin import STATE_FAILED, STATE_NOT_SENT


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_edi_provider = fields.Selection(
        selection=[("none", "Ninguno")],
        string="Proveedor de facturacion digital",
        default="none",
        help=(
            "Imprenta o conector para enviar facturas de cliente "
            "confirmadas de este diario."
        ),
    )

    @api.model
    def _l10n_ve_edi_unsent_send_states(self):
        return [STATE_NOT_SENT, STATE_FAILED]

    @api.model
    def _l10n_ve_edi_digital_edi_available(self, companies):
        return bool(
            self.search_count(
                [
                    ("company_id", "in", companies.ids),
                    ("type", "=", "sale"),
                    ("l10n_ve_emission_medium", "=", "digital"),
                    ("l10n_ve_edi_provider", "!=", False),
                    ("l10n_ve_edi_provider", "!=", "none"),
                ]
            )
        )

    @api.model
    def _l10n_ve_edi_unsent_invoices(self, companies):
        invoices = self.env["account.move"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
                (
                    "l10n_ve_edi_send_state",
                    "in",
                    self._l10n_ve_edi_unsent_send_states(),
                ),
                ("journal_id.l10n_ve_emission_medium", "=", "digital"),
                ("journal_id.l10n_ve_edi_provider", "!=", False),
                ("journal_id.l10n_ve_edi_provider", "!=", "none"),
            ]
        )
        return invoices.filtered(lambda move: move._l10n_ve_edi_is_invoice_target())

    @api.model
    def _l10n_ve_edi_unsent_dispatch_guides(self, companies):
        if "stock.picking" not in self.env:
            return self.env["stock.picking"].browse()
        pickings = self.env["stock.picking"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "done"),
                ("picking_type_code", "=", "outgoing"),
                (
                    "l10n_ve_edi_send_state",
                    "in",
                    self._l10n_ve_edi_unsent_send_states(),
                ),
            ]
        )
        return pickings.filtered(
            lambda picking: picking._l10n_ve_edi_is_picking_target()
        )

    @api.model
    def _l10n_ve_edi_unsent_retentions(self, companies):
        retentions = self.env["account.retention"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "emitted"),
                (
                    "l10n_ve_edi_send_state",
                    "in",
                    self._l10n_ve_edi_unsent_send_states(),
                ),
            ]
        )
        return retentions.filtered(
            lambda retention: retention._l10n_ve_edi_is_retention_target()
        )

    @api.model
    def get_l10n_ve_edi_unsent_dashboard(self):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies or not self._l10n_ve_edi_digital_edi_available(
            ve_companies
        ):
            return {"visible": False, "title": "", "items": []}

        invoices = self._l10n_ve_edi_unsent_invoices(ve_companies)
        pickings = self._l10n_ve_edi_unsent_dispatch_guides(ve_companies)
        retentions = self._l10n_ve_edi_unsent_retentions(ve_companies)
        return {
            "visible": True,
            "title": _("Documentos sin enviar"),
            "items": [
                {
                    "key": "unsent_invoices",
                    "label": _("Facturas"),
                    "count": len(invoices),
                },
                {
                    "key": "unsent_dispatch_guides",
                    "label": _("Guías de despacho"),
                    "count": len(pickings),
                },
                {
                    "key": "unsent_retentions",
                    "label": _("Retenciones"),
                    "count": len(retentions),
                },
            ],
        }

    @api.model
    def action_l10n_ve_edi_unsent_dashboard_open(self, key):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies:
            raise UserError(_("No hay compañías venezolanas activas."))

        if key == "unsent_invoices":
            records = self._l10n_ve_edi_unsent_invoices(ve_companies)
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice_type"
            )
            action.update(
                {
                    "name": _("Facturas sin enviar"),
                    "domain": [("id", "in", records.ids)],
                    "context": {
                        **self.env.context,
                        "create": False,
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "unsent_dispatch_guides":
            records = self._l10n_ve_edi_unsent_dispatch_guides(ve_companies)
            action = self.env["ir.actions.actions"]._for_xml_id(
                "stock.action_picking_tree_all"
            )
            action.update(
                {
                    "name": _("Guías de despacho sin enviar"),
                    "domain": [("id", "in", records.ids)],
                    "context": {
                        **self.env.context,
                        "create": False,
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "unsent_retentions":
            records = self._l10n_ve_edi_unsent_retentions(ve_companies)
            return clean_action(
                {
                    "type": "ir.actions.act_window",
                    "name": _("Retenciones sin enviar"),
                    "res_model": "account.retention",
                    "view_mode": "list,form",
                    "domain": [("id", "in", records.ids)],
                    "context": {
                        **self.env.context,
                        "create": False,
                    },
                },
                self.env,
            )

        raise UserError(_("Indicador de tablero no reconocido."))
