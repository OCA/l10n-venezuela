# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def _get_l10n_ve_version(self):
        Module = self.env["ir.module.module"].sudo()
        module = Module.search([("name", "=", "l10n_ve_seniat")], limit=1)
        version = module.installed_version if module else ""
        if not version:
            return ""
        enterprise = Module.search(
            [("name", "=", "web_enterprise"), ("state", "=", "installed")],
            limit=1,
        )
        edition = "Enterprise" if enterprise else "Community"
        return f"Odoo {edition} v{version}"

    @classmethod
    def _l10n_ve_allowed_company_ids_from_request(cls, user):
        """Company ids from the webclient cids cookie (active company switch)."""
        if not request:
            return []
        cids = request.httprequest.cookies.get("cids")
        if not cids:
            return []
        try:
            company_ids = [int(cid) for cid in cids.replace(",", "-").split("-") if cid]
        except ValueError:
            return []
        if not company_ids:
            return []
        allowed = set(user._get_company_ids())
        return [cid for cid in company_ids if cid in allowed]

    def _l10n_ve_with_request_companies(self):
        company_ids = self._l10n_ve_allowed_company_ids_from_request(self.env.user)
        if not company_ids:
            return self
        if list(self.env.context.get("allowed_company_ids") or []) == company_ids:
            return self
        return self.with_context(allowed_company_ids=company_ids)

    def _l10n_ve_emission_medium_codes_for_companies(self, companies):
        return {
            company.id: list(company.sudo()._l10n_ve_emission_medium_codes())
            for company in companies
        }

    def session_info(self):
        self = self._l10n_ve_with_request_companies()
        session = super().session_info()
        session["l10n_ve_version"] = self._get_l10n_ve_version()
        company = self.env.company.sudo()
        codes = list(company._l10n_ve_emission_medium_codes())
        session["l10n_ve_emission_medium_codes"] = codes
        allowed_companies = self.env.user.company_ids
        session["l10n_ve_emission_medium_codes_by_company"] = (
            self._l10n_ve_emission_medium_codes_for_companies(allowed_companies)
        )
        user_context = session.get("user_context")
        if user_context is not None:
            user_context["l10n_ve_emission_medium_codes"] = codes
        return session
