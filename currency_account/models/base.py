import json

from odoo import api, models


class Base(models.AbstractModel):
    _inherit = "base"

    _CURRENCY_ACCOUNT_DYNAMIC_PREFIXES = (
        "x_currency_id_",
        "x_amount_currency_",
        "x_subtotal_currency_",
        "x_price_unit_currency_",
        "x_cost_currency_",
    )

    @api.model
    def _compute_subtotal_currency_field(self, currency_id):
        return 0.0

    @api.model
    def _currency_account_group_xmlid(self, currency_id):
        return f"currency_account.group_currency_{currency_id}"

    @api.model
    def _currency_account_group_xmlid_from_field(self, field_name):
        try:
            currency_id = int(field_name.rsplit("_", 1)[-1])
        except (ValueError, IndexError):
            return None
        return self._currency_account_group_xmlid(currency_id)

    @api.model
    def _currency_account_user_has_field_access(self, field_name):
        if self.env.su or self.env.user.has_group("base.group_system"):
            return True
        xmlid = self._currency_account_group_xmlid_from_field(field_name)
        if not xmlid:
            return True
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return False
        return self.env.user.has_group(xmlid)

    @api.model
    def _currency_account_is_dynamic_currency_field(self, field_name):
        return any(
            field_name.startswith(prefix)
            for prefix in self._CURRENCY_ACCOUNT_DYNAMIC_PREFIXES
        )

    @api.model
    def _currency_account_filter_read_rows(self, rows):
        if self.env.su:
            return rows
        for row in rows:
            if "total_currencies" in row and row["total_currencies"]:
                row["total_currencies"] = self._currency_account_filter_total_currencies(
                    row["total_currencies"]
                )
            for key in list(row.keys()):
                if self._currency_account_is_dynamic_currency_field(
                    key
                ) and not self._currency_account_user_has_field_access(key):
                    del row[key]
        return rows

    @api.model
    def _currency_account_filter_total_currencies(self, value):
        if not value:
            return value
        totals = json.loads(value) if isinstance(value, str) else value
        if not isinstance(totals, dict):
            return value
        filtered = {
            key: entry
            for key, entry in totals.items()
            if self._currency_account_user_has_field_access(
                f"x_amount_currency_{key}"
            )
        }
        if not filtered:
            return False
        return json.dumps(filtered) if isinstance(value, str) else filtered
