from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _l10n_ve_emission_medium_menu_rules(self):
        return {
            "fiscal_machine": (
                "l10n_ve_fiscal_serial.menu_seniat_fiscal_machines",
                "l10n_ve_reports.menu_seniat_report_sales_book_fiscal_machine",
            ),
        }

    @api.model
    def _l10n_ve_menu_ids_for_xmlids(self, xmlids):
        menu_ids = []
        for xmlid in xmlids:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu:
                continue
            menu_ids.extend(self.search([("id", "child_of", menu.id)]).ids)
        return menu_ids

    @api.model
    def _l10n_ve_emission_medium_menus_blacklist(self):
        company = self.env.company.sudo()
        blacklist = []
        for (
            emission_code,
            menu_xmlids,
        ) in self._l10n_ve_emission_medium_menu_rules().items():
            if company._l10n_ve_has_emission_medium(emission_code):
                continue
            blacklist.extend(self._l10n_ve_menu_ids_for_xmlids(menu_xmlids))
        return blacklist

    def _load_menus_blacklist(self):
        return (
            super()._load_menus_blacklist()
            + self._l10n_ve_emission_medium_menus_blacklist()
        )

    @api.model
    def load_menus(self, debug):
        if not self.env.context.get("allowed_company_ids"):
            company_ids = self.env["ir.http"]._l10n_ve_allowed_company_ids_from_request(
                self.env.user
            )
            if company_ids:
                return self.with_context(allowed_company_ids=company_ids).load_menus(
                    debug
                )
        return self._l10n_ve_load_menus_cached(debug)

    @api.model
    @tools.ormcache_context("self._uid", "self.env.company.id", "debug", keys=("lang",))
    def _l10n_ve_load_menus_cached(self, debug):
        return super().load_menus.__wrapped__(self, debug)
