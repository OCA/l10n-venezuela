# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AuditlogValidationException(models.Model):
    _name = "auditlog.validation.exception"
    _description = "Auditlog - Validation and Business Errors Shown"
    _order = "create_date DESC"

    message = fields.Text(required=True, readonly=True)
    exception_class = fields.Char(
        string="Exception Type",
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
    http_path = fields.Char(readonly=True)
    ip_address = fields.Char(readonly=True, index=True)
    rpc_model = fields.Char(readonly=True)
    rpc_method = fields.Char(readonly=True)

    @api.model
    def _create_log_in_env(self, vals):
        """Create audit row using the current env (caller must use a fresh RW cursor and commit)."""
        self.sudo().create(vals)
