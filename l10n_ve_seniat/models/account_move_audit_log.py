# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.http import request


class AccountMoveAuditLog(models.Model):
    _name = "account.move.audit.log"
    _description = "Account Move Audit Log"
    _order = "create_date desc"
    _rec_name = "move_name"

    move_id = fields.Many2one(
        "account.move",
        string="Move",
        ondelete="set null",
        index=True,
    )
    move_name = fields.Char(
        string="Move Name",
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    action = fields.Selection(
        [
            ("create", "Created"),
            ("write", "Modified"),
            ("unlink", "Deleted"),
        ],
        string="Action",
        required=True,
        readonly=True,
    )
    ip_address = fields.Char(
        string="IP Address",
        readonly=True,
    )
    create_date = fields.Datetime(
        string="Date",
        required=True,
        readonly=True,
    )
    changes = fields.Text(
        string="Changes",
        readonly=True,
        help="Detailed information about the changes made",
    )

    @api.model
    def _get_ip_address(self):
        """Get the IP address from the request if available."""
        try:
            if request and hasattr(request, "httprequest"):
                return request.httprequest.remote_addr
        except Exception:
            pass
        return False

    @api.model
    def log_action(self, move, action, changes=None):
        """Create an audit log entry for the given move and action."""
        ip_address = self._get_ip_address()
        vals = {
            "move_id": move.id,
            "move_name": move.name or f"Move ID: {move.id}",
            "user_id": self.env.user.id,
            "action": action,
            "ip_address": ip_address or "",
            "changes": changes or "",
        }
        return self.create(vals)
