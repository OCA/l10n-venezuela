# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.action import Action


class L10nVeAuditWebActionController(Action):
    @http.route()
    def load(self, action_id, context=None):
        result = super().load(action_id, context=context)
        if isinstance(result, dict) and result.get("id"):
            request.env[
                "auditlog.account.report.access"
            ].sudo()._try_log_ir_action_access(result)
        return result
