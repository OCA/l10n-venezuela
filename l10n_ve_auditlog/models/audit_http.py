# Part of Odoo. See LICENSE file for full copyright and licensing details.


def audit_get_remote_ip(request):
    if not request or not getattr(request, "httprequest", None):
        return False
    httprequest = request.httprequest
    forwarded_for = httprequest.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = httprequest.headers.get("X-Real-Ip")
    if real_ip:
        return real_ip.strip()
    return httprequest.remote_addr
