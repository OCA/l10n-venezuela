# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import timedelta

from odoo import api, fields, models


class L10nVeDbAuditLog(models.Model):
    _name = "l10n.ve.db.audit.log"
    _description = "PostgreSQL External Audit Log"
    _order = "logged_at DESC"
    _log_access = False

    table_name = fields.Char(required=True, readonly=True, index=True)
    record_id = fields.Integer(string="Record ID", readonly=True, index=True)
    operation = fields.Selection(
        [
            ("insert", "Insert"),
            ("update", "Update"),
            ("delete", "Delete"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    old_values = fields.Json(readonly=True)
    new_values = fields.Json(readonly=True)
    changed_values = fields.Json(readonly=True)
    changed_fields_text = fields.Text(
        string="Changed Fields",
        compute="_compute_changed_fields_text",
    )
    db_user = fields.Char(string="Database User", readonly=True, index=True)
    client_addr = fields.Char(string="Client Address", readonly=True, index=True)
    application_name = fields.Char(readonly=True)
    logged_at = fields.Datetime(required=True, readonly=True, index=True)

    @api.model
    def _build_changed_values(self, old_values, new_values, operation):
        if operation == "insert" and new_values:
            return {
                key: {"old": None, "new": value} for key, value in new_values.items()
            }
        if operation == "delete" and old_values:
            return {
                key: {"old": value, "new": None} for key, value in old_values.items()
            }
        if operation != "update" or not old_values or not new_values:
            return {}
        changed = {}
        for key, new_value in new_values.items():
            old_value = old_values.get(key)
            if old_value != new_value:
                changed[key] = {"old": old_value, "new": new_value}
        return changed

    @api.depends("changed_values", "old_values", "new_values", "operation")
    def _compute_changed_fields_text(self):
        for record in self:
            changed = record.changed_values
            if not changed:
                changed = record._build_changed_values(
                    record.old_values,
                    record.new_values,
                    record.operation,
                )
            lines = []
            if isinstance(changed, dict):
                for field_name in sorted(changed):
                    values = changed[field_name]
                    if not isinstance(values, dict):
                        lines.append(f"{field_name}: {values}")
                        continue
                    old_value = values.get("old")
                    new_value = values.get("new")
                    lines.append(
                        f"{field_name}: {record._format_audit_value(old_value)} "
                        f"-> {record._format_audit_value(new_value)}"
                    )
            record.changed_fields_text = "\n".join(lines)

    @api.model
    def _format_audit_value(self, value):
        if value in (None, False):
            return ""
        if isinstance(value, dict | list):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @api.model
    def autovacuum(self, days=90):
        limit_date = fields.Datetime.now() - timedelta(days=days)
        records = self.sudo().search([("logged_at", "<", limit_date)])
        if records:
            records.unlink()
        return True
