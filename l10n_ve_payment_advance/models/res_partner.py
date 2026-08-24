from odoo import api, fields, models

CUSTOMER_ADVANCE_ACCOUNT_TYPES = (
    "liability_payable",
    "liability_credit_card",
    "liability_current",
    "liability_non_current",
)

SUPPLIER_ADVANCE_ACCOUNT_TYPES = (
    "asset_current",
    "asset_non_current",
    "asset_prepayments",
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _get_customer_advance_account(self, partner, company):
        if not company:
            return self.env["account.account"]
        partner = (partner or self.env["res.partner"]).with_company(company)
        return (
            partner.property_account_customer_advance_id
            or company.account_customer_advance_id
        )

    @api.model
    def _get_supplier_advance_account(self, partner, company):
        if not company:
            return self.env["account.account"]
        partner = (partner or self.env["res.partner"]).with_company(company)
        return (
            partner.property_account_supplier_advance_id
            or company.account_supplier_advance_id
        )

    @api.model
    def _get_partner_advance_account(self, partner, company, partner_type):
        if partner_type == "supplier":
            return self._get_supplier_advance_account(partner, company)
        return self._get_customer_advance_account(partner, company)

    property_account_customer_advance_id = fields.Many2one(
        comodel_name="account.account",
        company_dependent=True,
        string="Cuenta de anticipos de cliente",
        domain=(
            "[('account_type', 'in', %s), ('deprecated', '=', False)]"  # noqa: UP031
            % (CUSTOMER_ADVANCE_ACCOUNT_TYPES,)
        ),
        ondelete="restrict",
        help=(
            "Cuenta de pasivo usada para anticipos de clientes en pagos sin "
            "factura y para el monto que excede una factura al registrar el pago."
        ),
    )
    property_account_supplier_advance_id = fields.Many2one(
        comodel_name="account.account",
        company_dependent=True,
        string="Cuenta de anticipos de proveedor",
        domain=(
            "[('account_type', 'in', %s), ('deprecated', '=', False)]"  # noqa: UP031
            % (SUPPLIER_ADVANCE_ACCOUNT_TYPES,)
        ),
        ondelete="restrict",
        help=(
            "Cuenta de activo usada para anticipos a proveedores en pagos sin "
            "factura y para el monto que excede una factura al registrar el pago."
        ),
    )
