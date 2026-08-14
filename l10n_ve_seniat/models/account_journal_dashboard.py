from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date
from odoo.addons.web.controllers.utils import clean_action


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _l10n_ve_seniat_ve_companies(self):
        return self.env.companies.filtered(
            lambda company: company.account_fiscal_country_id.code == "VE"
        )

    @api.model
    def _l10n_ve_seniat_current_month_bounds(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1), today

    @api.model
    def _l10n_ve_seniat_overdue_unpaid_invoices_domain(self, companies, today=None):
        today = today or fields.Date.context_today(self)
        return [
            ("company_id", "in", companies.ids),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("invoice_date_due", "<", today),
        ]

    @api.model
    def _l10n_ve_seniat_dispatch_guide_dashboard_available(self):
        if "stock.picking" not in self.env:
            return False
        picking_model = self.env["stock.picking"]
        return (
            "l10n_ve_is_ve_country" in picking_model._fields
            and callable(
                getattr(
                    picking_model,
                    "_l10n_ve_dispatch_outgoing_moves_fully_invoiced",
                    None,
                )
            )
        )

    @api.model
    def _l10n_ve_seniat_unfactured_dispatch_guides(self, companies):
        if "stock.picking" not in self.env:
            return self.env["account.move"].browse(), False
        if not self._l10n_ve_seniat_dispatch_guide_dashboard_available():
            return self.env["stock.picking"].browse(), False

        candidates = self.env["stock.picking"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "done"),
                ("picking_type_code", "=", "outgoing"),
                ("l10n_ve_control_number", "!=", False),
                ("l10n_ve_control_number", "!=", ""),
            ]
        )
        unfactured = candidates.filtered(
            lambda picking: picking.l10n_ve_is_ve_country
            and not picking._l10n_ve_dispatch_outgoing_moves_fully_invoiced()
        )
        return unfactured, True

    @api.model
    def get_l10n_ve_invoice_dashboard(self):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies:
            return {"visible": False, "items": [], "month_label": ""}

        month_start, today = self._l10n_ve_seniat_current_month_bounds()
        move_domain_base = [
            ("company_id", "in", ve_companies.ids),
            ("state", "=", "posted"),
            ("invoice_date", ">=", month_start),
            ("invoice_date", "<=", today),
        ]
        Move = self.env["account.move"]
        invoice_count = Move.search_count(
            move_domain_base + [("move_type", "=", "out_invoice")]
        )
        credit_count = Move.search_count(
            move_domain_base + [("move_type", "=", "out_refund")]
        )
        overdue_count = Move.search_count(
            self._l10n_ve_seniat_overdue_unpaid_invoices_domain(ve_companies, today)
        )
        dispatch_guides, dispatch_available = (
            self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
        )

        items = []
        if dispatch_available:
            items.append(
                {
                    "key": "unfactured_dispatch_guides",
                    "label": _("Guías de despacho no facturadas"),
                    "count": len(dispatch_guides),
                    "show_month_label": False,
                }
            )
        items.extend(
            [
                {
                    "key": "posted_invoices_month",
                    "label": _("Facturas confirmadas (mes)"),
                    "count": invoice_count,
                    "show_month_label": True,
                },
                {
                    "key": "credit_notes_month",
                    "label": _("Notas de crédito (mes)"),
                    "count": credit_count,
                    "show_month_label": True,
                },
                {
                    "key": "overdue_unpaid_invoices",
                    "label": _("Facturas vencidas sin pagar"),
                    "count": overdue_count,
                    "show_month_label": False,
                },
            ]
        )
        return {
            "visible": True,
            "month_label": format_date(self.env, month_start, date_format="MMMM y"),
            "items": items,
            "dispatch_email": self._l10n_ve_seniat_dispatch_email_dashboard_data(
                dispatch_available
            ),
        }

    @api.model
    def _l10n_ve_seniat_dispatch_email_dashboard_data(self, dispatch_available):
        company = self.env.company
        if not dispatch_available:
            return {
                "available": False,
                "can_send": False,
                "last_sent_label": False,
            }
        return {
            "available": True,
            "can_send": bool(
                getattr(company, "l10n_ve_dispatch_guide_enabled", True)
                and (company.l10n_ve_unfactured_dispatch_email_recipient or "").strip()
            ),
            "last_sent_label": company.l10n_ve_unfactured_dispatch_email_last_sent_label()
            or False,
        }

    @api.model
    def action_l10n_ve_send_unfactured_dispatch_guides_email(self):
        company = self.env.company
        company._l10n_ve_send_unfactured_dispatch_guides_email()
        return self._l10n_ve_seniat_dispatch_email_dashboard_data(True) | {
            "message": _("Correo de guías no facturadas enviado correctamente."),
        }

    @api.model
    def action_l10n_ve_invoice_dashboard_open(self, key):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies:
            raise UserError(_("No hay compañías venezolanas activas."))

        month_start, today = self._l10n_ve_seniat_current_month_bounds()
        move_domain_base = [
            ("company_id", "in", ve_companies.ids),
            ("state", "=", "posted"),
            ("invoice_date", ">=", month_start),
            ("invoice_date", "<=", today),
        ]

        if key == "unfactured_dispatch_guides":
            dispatch_guides, dispatch_available = (
                self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
            )
            if not dispatch_available:
                raise UserError(
                    _("Las guías de despacho requieren el módulo de inventario SENIAT.")
                )
            action = self.env["ir.actions.actions"]._for_xml_id(
                "stock.action_picking_tree_all"
            )
            action.update(
                {
                    "name": _("Guías de despacho no facturadas"),
                    "domain": [("id", "in", dispatch_guides.ids)],
                    "context": {
                        **self.env.context,
                        "create": False,
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "posted_invoices_month":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice"
            )
            action.update(
                {
                    "name": _("Facturas confirmadas (mes)"),
                    "domain": move_domain_base + [("move_type", "=", "out_invoice")],
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_invoice",
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "credit_notes_month":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_refund_type"
            )
            action.update(
                {
                    "name": _("Notas de crédito (mes)"),
                    "domain": move_domain_base + [("move_type", "=", "out_refund")],
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_refund",
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "overdue_unpaid_invoices":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice"
            )
            action.update(
                {
                    "name": _("Facturas vencidas sin pagar"),
                    "domain": self._l10n_ve_seniat_overdue_unpaid_invoices_domain(
                        ve_companies, today
                    ),
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_invoice",
                        "search_default_late": 1,
                        "search_default_posted": 1,
                    },
                }
            )
            return clean_action(action, self.env)

        raise UserError(_("Indicador de tablero no reconocido."))
