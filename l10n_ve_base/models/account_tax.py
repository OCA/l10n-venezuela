# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import re

from odoo import api, fields, models

# Official l10n_ve (17/19) still ships 12% / 22% until odoo#285425.
# SENIAT rates since 2018 are 16% / 31% (G.O. Ext. 6.395). This module
# classifies those IVA taxes and rewrites leftover amounts/names in place.
# User-facing names: Exento, IVA 8%, IVA 16%, IVA 31%.
_L10N_VE_IVA_APPL_BY_RATE = (
    (0.0, "exento", None),
    (8.0, "reducido", None),
    (12.0, "general", 16.0),
    (16.0, "general", None),
    (22.0, "adicional", 31.0),
    (31.0, "adicional", None),
)
_L10N_VE_OFFICIAL_NAME = re.compile(
    r"^(0%\s*EXEMPT|0%\s*EXENTO|Exento|IVA\s*8%|8%|IVA\s*12%|12%|"
    r"IVA\s*16%|16%|IVA\s*22%|22%|IVA\s*31%|31%)$",
    re.IGNORECASE,
)
_L10N_VE_CLEAN_NAME = {
    "exento": "Exento",
    "reducido": "IVA 8%",
    "general": "IVA 16%",
    "adicional": "IVA 31%",
}


class AccountTax(models.Model):
    _inherit = "account.tax"

    appl_type = fields.Selection(
        selection=[
            ("exento", "Exempt"),
            ("sdcf", "Not entitled to tax credit (SDCF)"),
            ("general", "General Aliquot"),
            ("reducido", "Reduced Aliquot"),
            ("adicional", "General + Additional Aliquot"),
        ],
        string="Aliquot Type",
        help="Specify the aliquot type according to Venezuelan law for Fiscal Books. "
        "Filled automatically for official IVA rates; SDCF must be set by hand.",
    )

    @api.model
    def _l10n_ve_assign_appl_type(self):
        """Classify VE IVA and set company defaults.

        Rates: Exento, IVA 8%, IVA 16% and IVA 31%.
        """
        for tax in self._l10n_ve_iva_taxes():
            mapping = tax._l10n_ve_iva_rate_mapping()
            if not mapping:
                continue
            _rate, appl_type, new_amount = mapping
            values = {}
            if not tax.appl_type:
                values["appl_type"] = appl_type
            old_amount = tax.amount
            if new_amount is not None and abs(old_amount - new_amount) >= 0.1:
                values["amount"] = new_amount
            target_appl = tax.appl_type or appl_type
            source_name = tax.with_context(lang="en_US").name or tax.name or ""
            if target_appl in _L10N_VE_CLEAN_NAME and _L10N_VE_OFFICIAL_NAME.match(
                source_name.strip()
            ):
                new_name = _L10N_VE_CLEAN_NAME[target_appl]
                if not tax._l10n_ve_name_taken(new_name):
                    values["name"] = new_name
                label = tax._l10n_ve_clean_invoice_label(target_appl)
                for fname in ("description", "invoice_label"):
                    if fname in tax._fields:
                        values[fname] = label
            elif "amount" in values:
                for fname in ("description", "invoice_label"):
                    if fname not in tax._fields or fname in values:
                        continue
                    current = tax.with_context(lang="en_US")[fname] or tax[fname]
                    if current:
                        updated = tax._l10n_ve_replace_rate_label(
                            current, old_amount, values["amount"]
                        )
                        if str(updated) != str(current):
                            values[fname] = updated
            if values:
                tax._l10n_ve_write_tax_values(values, old_amount=old_amount)
        self.env["res.company"]._l10n_ve_set_default_iva_taxes()
        return True

    def _l10n_ve_write_tax_values(self, values, old_amount=None):
        """Update source and every active language. Tax names are translated."""
        self.ensure_one()
        trans_fnames = [
            fname
            for fname in ("name", "description", "invoice_label")
            if fname in values and fname in self._fields
        ]
        self.with_context(lang="en_US").write(values)
        if not trans_fnames:
            return
        new_amount = values.get("amount", old_amount)
        for lang in self.env["res.lang"].search([("active", "=", True)]):
            if lang.code == "en_US":
                continue
            tax = self.with_context(lang=lang.code)
            lang_vals = {}
            for fname in trans_fnames:
                if values.get(fname):
                    lang_vals[fname] = values[fname]
                    continue
                current = tax[fname]
                if (
                    current
                    and old_amount is not None
                    and new_amount is not None
                    and abs(new_amount - old_amount) >= 0.1
                ):
                    lang_vals[fname] = self._l10n_ve_replace_rate_label(
                        current, old_amount, new_amount
                    )
            if lang_vals:
                tax.write(lang_vals)

    @api.model
    def _l10n_ve_iva_taxes(self):
        taxes = self.with_context(active_test=False, lang="en_US").search(
            [
                ("amount_type", "=", "percent"),
                ("type_tax_use", "in", ("sale", "purchase")),
            ]
        )
        return taxes.filtered(
            lambda tax: tax._l10n_ve_iva_rate_mapping() and tax._l10n_ve_is_ve_iva_tax()
        )

    def _l10n_ve_is_ve_iva_tax(self):
        self.ensure_one()
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if ve and (
            self.country_id == ve
            or self.company_id.country_id == ve
            or self.company_id.account_fiscal_country_id == ve
        ):
            return True
        name = (self.with_context(lang="en_US").name or self.name or "").upper()
        return bool(
            _L10N_VE_OFFICIAL_NAME.match((self.name or "").strip())
            or _L10N_VE_OFFICIAL_NAME.match(name.strip())
            or any(token in name for token in ("IVA", "EXEMPT", "EXENTO", "VAT"))
        )

    def _l10n_ve_iva_rate_mapping(self):
        self.ensure_one()
        for rate, appl_type, new_amount in _L10N_VE_IVA_APPL_BY_RATE:
            if abs(self.amount - rate) < 0.1:
                return rate, appl_type, new_amount
        return None

    def _l10n_ve_name_taken(self, name):
        """True if another tax already uses this name in the company tree."""
        self.ensure_one()
        if not name or not self.company_id:
            return False
        company = self.company_id
        root = company.root_id if "root_id" in company._fields else company
        return bool(
            self.sudo().search_count(
                [
                    ("id", "!=", self.id),
                    ("name", "=", name),
                    ("type_tax_use", "=", self.type_tax_use),
                    ("tax_scope", "=", self.tax_scope),
                    ("country_id", "=", self.country_id.id),
                    ("company_id", "child_of", root.id),
                ]
            )
        )

    def _l10n_ve_clean_invoice_label(self, appl_type):
        """Name shown in tax list description and invoice label: IVA 16% (ventas)."""
        self.ensure_one()
        name = _L10N_VE_CLEAN_NAME[appl_type]
        side = "ventas" if self.type_tax_use == "sale" else "compras"
        if appl_type == "exento":
            return f"Exento ({side})"
        return f"{name} ({side})"

    @api.model
    def _l10n_ve_replace_rate_label(self, text, old_rate, new_rate):
        if not text:
            return text
        replacements = (
            (f"{old_rate:.1f}%", f"{new_rate:.1f}%"),
            (f"{old_rate:g}%", f"{new_rate:g}%"),
            (f"{old_rate:.0f}%", f"{new_rate:.0f}%"),
        )
        result = str(text)
        for old, new in replacements:
            result = result.replace(old, new)
        return result
