from odoo import _, api, fields, models


class TypeWithholding(models.Model):
    _name = "account.withholding.type"
    _description = "Type Withholding"
    _order = "sequence, id"
    _sql_constraints = [
        (
            "unique_name",
            "UNIQUE(name)",
            "You cannot add withholdings with the same name",
        ),
        (
            "unique_value",
            "UNIQUE(value)",
            "You can not add withholdings with the same Value",
        ),
    ]

    def case_upper(self, string, field_name):
        if string:
            result = {"value": {field_name: str(string).strip().upper()}}
            return result

    name = fields.Char(store=True)
    value = fields.Float(store=True)
    sequence = fields.Integer(default=10)
    state = fields.Boolean(default=True, string="Active", store=True)

    @api.model
    def _l10n_ve_table_exists(self):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = %s)",
            [self._table],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_default_withholding_type_id(self):
        if not self._l10n_ve_table_exists():
            return False
        withholding_type = self.search(
            [("state", "=", True)], order="sequence, id", limit=1
        )
        return withholding_type.id

    @api.onchange("name")
    def upper_name(self):
        return self.case_upper(self.name, "name")

    @api.onchange("value")
    def onchange_template_id(self):
        res = {}
        if self.value:
            res = {
                "warning": {
                    "title": (_("Warning")),
                    "message": (_("Remember to use comma (,) as decimal separator.")),
                }
            }

        if res:
            return res
