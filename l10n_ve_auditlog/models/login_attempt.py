# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AuditlogLoginAttempt(models.Model):
    _name = "auditlog.login.attempt"
    _description = "Auditlog - Login Attempt"
    _order = "attempt_date DESC"

    login = fields.Char("Login / Email", required=True, readonly=True, index=True)
    ip_address = fields.Char("IP Address", required=True, readonly=True, index=True)
    user_agent = fields.Char("User Agent", readonly=True)
    result = fields.Selection(
        [("success", "Success"), ("failed", "Failed")],
        string="Result",
        required=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        readonly=True,
        index=True,
        ondelete="set null",
    )
    attempt_date = fields.Datetime(
        "Attempt Date",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )

    @api.model
    def log_attempt(self, login, ip_address, user_agent, result, user_id=False):
        """Log a login attempt. Called with sudo() from the controller."""
        try:
            self.sudo().create(
                {
                    "login": login,
                    "ip_address": ip_address,
                    "user_agent": user_agent or "",
                    "result": result,
                    "user_id": user_id,
                }
            )
        except Exception:
            _logger.exception("Failed to log login attempt for '%s'", login)
