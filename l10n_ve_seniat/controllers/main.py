# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http

from odoo.addons.web.controllers.home import Home


class HomeVersion(Home):
    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if hasattr(response, "qcontext"):
            response.qcontext["l10n_ve_version"] = http.request.env[
                "ir.http"
            ]._get_l10n_ve_version()
        return response
