# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_FISCAL_PAYMENT_METHODS = [
    ("01", "EFECTIVO 01"),
    ("02", "EFECTIVO 02"),
    ("03", "PAGO MOVIL 01"),
    ("04", "PAGO MOVIL 02"),
    ("05", "PAGO MOVIL 03"),
    ("06", "PAGO MOVIL 04"),
    ("07", "TRANSFERENCIA 01"),
    ("08", "TRANSFERENCIA 02"),
    ("09", "TRANSFERENCIA 03"),
    ("10", "TRANSFERENCIA 04"),
    ("11", "PDV 01"),
    ("12", "PDV 02"),
    ("13", "PDV 03"),
    ("14", "PDV 04"),
    ("15", "CREDITO 01"),
    ("16", "CREDITO 02"),
    ("17", "CREDITO 03"),
    ("18", "CREDITO 04"),
    ("19", "DIVISA 02"),
    ("20", "DIVISA 01"),
    ("21", "ZELLE"),
    ("22", "DIVISA 03"),
    ("23", "DIVISA 04"),
    ("24", "Monedero D"),
]


class L10nVeFiscalPaymentMethod(models.Model):
    _name = "l10n.ve.fiscal.payment.method"
    _description = "Método de pago fiscal TFHKA"
    _order = "code, id"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
        index=True,
    )
    code = fields.Char(
        string="Código",
        required=True,
        size=2,
        help="Código del medio de pago en la máquina fiscal (01-24).",
    )
    name = fields.Char(
        string="Nombre",
        required=True,
        size=14,
        help="Descriptor del medio de pago (máximo 14 caracteres).",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for method in self:
            code = method.code or ""
            name = method.name or ""
            method.display_name = f"{code} - {name}".strip(" -")

    _sql_constraints = [
        (
            "code_company_uniq",
            "unique(code, company_id)",
            "Ya existe un método de pago fiscal con este código en la compañía.",
        ),
    ]

    @api.constrains("code")
    def _check_code(self):
        for method in self:
            code = (method.code or "").strip()
            if not code.isdigit() or not (1 <= int(code) <= 24):
                raise ValidationError(
                    _("El código del método de pago debe estar entre 01 y 24.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("code")
            if code is not None:
                vals["code"] = str(code).strip().zfill(2)
            name = vals.get("name")
            if name is not None:
                vals["name"] = str(name).strip()[:14]
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "code" in vals and vals["code"] is not None:
            vals["code"] = str(vals["code"]).strip().zfill(2)
        if "name" in vals and vals["name"] is not None:
            vals["name"] = str(vals["name"]).strip()[:14]
        return super().write(vals)

    def to_pe_command(self):
        self.ensure_one()
        return f"PE{self.code}{(self.name or '')[:14]}"
