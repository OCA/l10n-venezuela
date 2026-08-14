# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models
from odoo.http import request
from odoo.tools.safe_eval import safe_eval

from .audit_http import audit_get_remote_ip

_logger = logging.getLogger(__name__)

ACCOUNT_REPORT_CLIENT_TAGS = frozenset({"account_report_oca", "account_report"})


class AuditlogAccountReportAccess(models.Model):
    _name = "auditlog.account.report.access"
    _description = "Auditlog - Accounting Report Consultation"
    _order = "access_date DESC"

    access_date = fields.Datetime(
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        readonly=True,
        index=True,
        ondelete="set null",
    )
    source = fields.Selection(
        [
            ("action_access", "Open action (menu)"),
            ("qweb", "QWeb render (legacy)"),
            ("account_report", "Engine export (legacy)"),
        ],
        string="Source",
        required=True,
        readonly=True,
        index=True,
    )
    report_name = fields.Char(readonly=True)
    report_model = fields.Char(string="Report Model", readonly=True, index=True)
    account_report_id = fields.Many2one(
        "account.report",
        string="Financial Report",
        readonly=True,
        ondelete="set null",
    )
    file_generator = fields.Char(readonly=True)
    ir_action_id = fields.Integer(
        string="Action id",
        readonly=True,
        index=True,
        help="Database id in ir_actions (shared sequence for all action types).",
    )
    ir_action_type = fields.Char(
        string="ir.actions type",
        readonly=True,
        index=True,
    )
    ip_address = fields.Char(readonly=True, index=True)
    http_path = fields.Char(readonly=True)

    @api.model
    def _try_log_ir_action_access(self, action_dict):
        if not self._audit_should_log_http():
            return
        aid = action_dict.get("id")
        atype = action_dict.get("type")
        if not aid or not atype:
            return
        name = action_dict.get("name") or action_dict.get("display_name") or ""
        if atype == "ir.actions.act_window":
            res_model = action_dict.get("res_model") or ""
            if not (
                res_model.startswith("account.")
                or res_model == "account.report"
            ):
                return
            self._create_log_vals(
                source="action_access",
                report_name=name,
                report_model=res_model,
                account_report=False,
                file_generator=False,
                ir_action_id=aid,
                ir_action_type=atype,
            )
        elif atype == "ir.actions.report":
            report = self.env["ir.actions.report"].browse(aid)
            if not report.exists() or not report.model:
                return
            if not str(report.model).startswith("account."):
                return
            self._create_log_vals(
                source="action_access",
                report_name=name or report.name,
                report_model=report.model,
                account_report=False,
                file_generator=False,
                ir_action_id=aid,
                ir_action_type=atype,
            )
        elif atype == "ir.actions.client":
            tag = action_dict.get("tag") or ""
            if not (
                tag in ACCOUNT_REPORT_CLIENT_TAGS
                or "account_report" in tag
            ):
                return
            ctx = action_dict.get("context") or {}
            if isinstance(ctx, str):
                try:
                    ctx = safe_eval(ctx, {})
                except Exception:
                    ctx = {}
            report_id = ctx.get("report_id") if isinstance(ctx, dict) else None
            account_report = self.env["account.report"]
            report_rec = (
                account_report.browse(report_id)
                if report_id
                else account_report
            )
            self._create_log_vals(
                source="action_access",
                report_name=name,
                report_model="account.report",
                account_report=report_rec if report_rec.exists() else False,
                file_generator=False,
                ir_action_id=aid,
                ir_action_type=atype,
            )

    @api.model
    def _audit_should_log_http(self):
        if not request or not getattr(request, "env", None):
            return False
        if not getattr(request, "httprequest", None):
            return False
        return True

    @api.model
    def _create_log_vals(
        self,
        source,
        report_name,
        report_model,
        account_report,
        file_generator,
        ir_action_id=None,
        ir_action_type=None,
    ):
        path = ""
        if getattr(request, "httprequest", None):
            path = request.httprequest.path or ""
        try:
            vals = {
                "user_id": request.env.uid,
                "source": source,
                "report_name": report_name or "",
                "report_model": report_model or "",
                "file_generator": file_generator or False,
                "ip_address": audit_get_remote_ip(request) or "",
                "http_path": path,
                "ir_action_id": ir_action_id or False,
                "ir_action_type": ir_action_type or False,
            }
            if account_report:
                vals["account_report_id"] = account_report.id
            self.sudo().create(vals)
        except Exception:
            _logger.exception("Failed to log accounting report access")
