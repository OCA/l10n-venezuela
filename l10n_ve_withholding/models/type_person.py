from odoo import api, fields, models


class TypePerson(models.Model):
    _name = "type.person"
    _description = "Type Person"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description", required=True, store=True)
    state = fields.Boolean(default=True, string="Active?", store=True)

    @api.model
    def _l10n_ve_table_exists(self):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = %s)",
            [self._table],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_default_type_person_id(self):
        if not self._l10n_ve_table_exists():
            return False
        type_person = self.search([("state", "=", True)], order="sequence, id", limit=1)
        return type_person.id
