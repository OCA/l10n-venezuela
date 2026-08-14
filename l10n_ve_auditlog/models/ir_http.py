# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request
from odoo.modules.registry import Registry
from odoo.tools import exception_to_unicode

from .audit_http import audit_get_remote_ip

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _handle_error(cls, exception):
        if request and request.db:
            if isinstance(exception, UserError) and not isinstance(
                exception,
                AccessDenied,
            ):
                params = getattr(request, "params", None) or {}
                rpc_model = (
                    params.get("model") if isinstance(params, dict) else False
                )
                rpc_method = (
                    params.get("method") if isinstance(params, dict) else False
                )
                path = ""
                if getattr(request, "httprequest", None):
                    path = request.httprequest.path or ""
                vals = {
                    "message": exception_to_unicode(exception),
                    "exception_class": type(exception).__name__,
                    "user_id": getattr(request, "uid", None) or False,
                    "http_path": path,
                    "ip_address": audit_get_remote_ip(request) or "",
                    "rpc_model": rpc_model or False,
                    "rpc_method": rpc_method or False,
                }
                cr = None
                try:
                    registry = Registry(request.db)
                    cr = registry.cursor()
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env["auditlog.validation.exception"]._create_log_in_env(vals)
                    cr.commit()
                except Exception:
                    _logger.exception(
                        "Failed to persist auditlog.validation.exception",
                    )
                finally:
                    if cr is not None:
                        cr.close()
        return super()._handle_error(exception)
