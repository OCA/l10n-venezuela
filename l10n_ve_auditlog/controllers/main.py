# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)


class AuditlogLoginController(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        login = request.params.get("login", "")
        ip_address = self._get_remote_ip()
        user_agent = request.httprequest.headers.get("User-Agent", "")

        response = super().web_login(redirect=redirect, **kw)

        # Only log if there was a POST with login data
        if request.httprequest.method == "POST" and login:
            try:
                # Check if login was successful
                # After a successful login, request.session.uid is set
                if request.session.uid:
                    result = "success"
                    user_id = request.session.uid
                else:
                    result = "failed"
                    # Try to find the user by login to link it
                    user = (
                        request.env["res.users"]
                        .sudo()
                        .search([("login", "=", login)], limit=1)
                    )
                    user_id = user.id if user else False

                request.env["auditlog.login.attempt"].log_attempt(
                    login=login,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    result=result,
                    user_id=user_id,
                )
            except Exception:
                _logger.exception(
                    "Error logging login attempt for '%s'",
                    login,
                )

        return response

    def _get_remote_ip(self):
        """Get the real remote IP, considering proxy headers."""
        httprequest = request.httprequest
        forwarded_for = httprequest.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = httprequest.headers.get("X-Real-Ip")
        if real_ip:
            return real_ip.strip()
        return httprequest.remote_addr
