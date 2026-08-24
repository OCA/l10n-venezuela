# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from .l10n_ve_fiscal_payment_method import DEFAULT_FISCAL_PAYMENT_METHODS


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_fiscal_flag_21 = fields.Selection(
        selection=[
            ("00", "00"),
            ("01", "01"),
            ("02", "02"),
            ("11", "11"),
            ("12", "12"),
            ("30", "30"),
        ],
        string="FLAG 21",
        default="30",
        required=True,
        help="Precisión de montos/cantidades en la máquina fiscal TFHKA.",
    )
    l10n_ve_fiscal_flag_50 = fields.Selection(
        selection=[
            ("00", "00 - Sin IGTF / sin pagos 20-24"),
            ("01", "01 - Con IGTF / pagos en divisas 20-24"),
        ],
        string="FLAG 50",
        default="01",
        required=True,
        help=(
            "00 bloquea medios de pago 20-24 y no calcula IGTF. "
            "01 habilita pagos en divisas e IGTF (cierre con comando 199)."
        ),
    )
    l10n_ve_fiscal_use_barcode = fields.Boolean(
        string="Código de barras al final de la factura",
        help=(
            "Si está activo, se envía el comando de código de barras (y) "
            "al pie del documento fiscal con el número de la factura."
        ),
    )
    l10n_ve_fiscal_footer = fields.Text(
        string="Pie de página",
        help=(
            "Hasta 8 líneas para el pie de página fiscal (PH91-PH98). "
            "Una línea por renglón. Requiere reporte Z previo para programarlo "
            "en la impresora."
        ),
    )
    l10n_ve_fiscal_payment_method_ids = fields.One2many(
        comodel_name="l10n.ve.fiscal.payment.method",
        inverse_name="company_id",
        string="Métodos de pago fiscales",
    )
    l10n_ve_fiscal_default_payment_method_id = fields.Many2one(
        comodel_name="l10n.ve.fiscal.payment.method",
        string="Método de pago fiscal por defecto",
        check_company=True,
        domain="[('company_id', '=', id)]",
        help=(
            "Método de pago fiscal usado al imprimir cuando la factura "
            "no tiene pagos conciliados."
        ),
    )

    def _l10n_ve_fiscal_footer_lines(self):
        self.ensure_one()
        lines = []
        for raw in (self.l10n_ve_fiscal_footer or "").splitlines():
            text = (raw or "").strip()
            if not text:
                continue
            lines.append(text[:40])
            if len(lines) >= 8:
                break
        return lines

    def _l10n_ve_fiscal_ensure_payment_methods(self):
        Method = self.env["l10n.ve.fiscal.payment.method"].sudo()
        for company in self:
            existing = {
                method.code: method
                for method in company.l10n_ve_fiscal_payment_method_ids
            }
            to_create = []
            for code, name in DEFAULT_FISCAL_PAYMENT_METHODS:
                if code in existing:
                    continue
                to_create.append(
                    {
                        "company_id": company.id,
                        "code": code,
                        "name": name,
                    }
                )
            if to_create:
                Method.create(to_create)
            if not company.l10n_ve_fiscal_default_payment_method_id:
                default_method = Method.search(
                    [("company_id", "=", company.id), ("code", "=", "01")],
                    limit=1,
                )
                if default_method:
                    company.l10n_ve_fiscal_default_payment_method_id = default_method

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._l10n_ve_fiscal_ensure_payment_methods()
        return companies

    def l10n_ve_fiscal_get_shared_config(self):
        self.ensure_one()
        self._l10n_ve_fiscal_ensure_payment_methods()
        methods = self.l10n_ve_fiscal_payment_method_ids.sorted("code")
        return {
            "flag_21": self.l10n_ve_fiscal_flag_21 or "30",
            "flag_50": self.l10n_ve_fiscal_flag_50 or "01",
            "use_barcode": bool(self.l10n_ve_fiscal_use_barcode),
            "footer_lines": self._l10n_ve_fiscal_footer_lines(),
            "payment_methods": [
                {"code": method.code, "name": method.name or ""} for method in methods
            ],
        }
