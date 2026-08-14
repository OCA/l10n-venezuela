# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class AuditlogLog(models.Model):
    _name = "auditlog.log"
    _description = "Auditlog - Log"
    _order = "create_date desc"

    name = fields.Char("Resource Name", size=64)
    model_id = fields.Many2one(
        "ir.model", string="Model", index=True, ondelete="set null"
    )
    model_name = fields.Char(readonly=True)
    model_model = fields.Char(string="Technical Model Name", readonly=True)
    res_id = fields.Integer("Resource ID")
    res_ids = fields.Char("Resource IDs")
    user_id = fields.Many2one("res.users", string="User")
    method = fields.Char(size=64)
    line_ids = fields.One2many("auditlog.log.line", "log_id", string="Fields updated")
    http_session_id = fields.Many2one(
        "auditlog.http.session", string="Session", index=True
    )
    http_request_id = fields.Many2one(
        "auditlog.http.request", string="HTTP Request", index=True
    )
    log_type = fields.Selection(
        [("full", "Full log"), ("fast", "Fast log")], string="Type"
    )
    is_fiscal_event = fields.Boolean(
        string="Fiscal Event",
        compute="_compute_is_fiscal_event",
        store=True,
        index=True,
    )
    fiscal_event_type = fields.Selection(
        selection=[
            ("draft_invoice", "Draft invoice"),
            ("draft_invoice_from_order", "Draft invoice from sale order"),
            ("draft_credit_note", "Draft credit note"),
            ("draft_debit_note", "Draft debit note"),
            ("invoice_posted", "Invoice posted"),
            ("credit_note_posted", "Credit note posted"),
            ("debit_note_posted", "Debit note posted"),
            ("fiscal_print", "Fiscal machine print"),
            ("edi_dispatch", "Digital dispatch"),
            ("document_cancelled", "Document cancelled"),
            ("retention_draft", "Retention draft"),
            ("retention_emitted", "Retention emitted"),
            ("retention_edi", "Retention digital dispatch"),
            ("dispatch_guide", "Dispatch guide"),
        ],
        readonly=True,
        index=True,
    )
    fiscal_event_description = fields.Text(
        string="Event Description",
        readonly=True,
    )

    @api.depends("method", "fiscal_event_type", "fiscal_event_description")
    def _compute_is_fiscal_event(self):
        for record in self:
            record.is_fiscal_event = bool(
                record.method == "fiscal_event"
                or record.fiscal_event_type
                or record.fiscal_event_description
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Insert model_name and model_model field values upon creation."""
        for vals in vals_list:
            if not vals.get("model_id"):
                raise UserError(_("No model defined to create log."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        return super().create(vals_list)

    def write(self, vals):
        """Update model_name and model_model field values to reflect model_id
        changes."""
        if "model_id" in vals:
            if not vals["model_id"]:
                raise UserError(_("The field 'model_id' cannot be empty."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        return super().write(vals)

    def show_res_ids(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": self.model_id.model,
            "domain": [("id", "in", safe_eval(self.res_ids))],
            "name": _("Exported Records"),
        }

    @api.model
    def log_fiscal_event(self, record, event_type, description):
        record.ensure_one()
        model = self.env["ir.model"]._get(record._name)
        http_request = self.env["auditlog.http.request"].sudo()
        http_session = self.env["auditlog.http.session"].sudo()
        return self.sudo().create(
            {
                "model_id": model.id,
                "model_name": model.name,
                "model_model": model.model,
                "res_id": record.id,
                "name": (record.display_name or "")[:64],
                "user_id": self.env.uid,
                "method": "fiscal_event",
                "fiscal_event_type": event_type,
                "fiscal_event_description": description,
                "http_request_id": http_request.current_http_request(),
                "http_session_id": http_session.current_http_session(),
            }
        )


class AuditlogLogLine(models.Model):
    _name = "auditlog.log.line"
    _description = "Auditlog - Log details (fields updated)"

    field_id = fields.Many2one(
        "ir.model.fields", ondelete="set null", string="Field", index=True
    )
    log_id = fields.Many2one(
        "auditlog.log", string="Log", ondelete="cascade", index=True
    )
    old_value = fields.Text()
    new_value = fields.Text()
    old_value_text = fields.Text("Old value Text")
    new_value_text = fields.Text("New value Text")
    field_name = fields.Char("Technical name", readonly=True)
    field_description = fields.Char("Description", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure field_id is not empty on creation and store field_name and
        field_description."""
        for vals in vals_list:
            if not vals.get("field_id"):
                raise UserError(_("No field defined to create line."))
            field = self.env["ir.model.fields"].sudo().browse(vals["field_id"])
            vals.update(
                {"field_name": field.name, "field_description": field.field_description}
            )
        return super().create(vals_list)

    def write(self, vals):
        """Ensure field_id is set during write and update field_name and
        field_description values."""
        if "field_id" in vals:
            if not vals["field_id"]:
                raise UserError(_("The field 'field_id' cannot be empty."))
            field = self.env["ir.model.fields"].sudo().browse(vals["field_id"])
            vals.update(
                {"field_name": field.name, "field_description": field.field_description}
            )
        return super().write(vals)
