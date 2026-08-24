from lxml import etree

from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def read(self, fields=None, load="_classic_read"):
        res = super().read(fields=fields, load=load)
        return self._currency_account_filter_read_rows(res)

    @api.model
    def search_read(
        self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs
    ):
        res = super().search_read(
            domain,
            fields,
            offset=offset,
            limit=limit,
            order=order,
            **read_kwargs,
        )
        return self._currency_account_filter_read_rows(res)

    def _compute_product_cost_currency_field(self, currency_id):
        self.ensure_one()
        currency = self.env["res.currency"].browse(currency_id)
        company = self.company_id or self.env.company
        company_cc = company.currency_id
        cost = self.standard_price or 0.0
        if not company_cc or currency == company_cc:
            return company_cc.round(cost) if company_cc else cost
        Move = self.env["account.move"].sudo()
        last_bill = Move.search(
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("currency_id", "=", currency_id),
                ("company_id", "=", company.id),
                ("invoice_currency_rate", ">", 0),
            ],
            order="invoice_date desc, date desc, id desc",
            limit=1,
        )
        if not last_bill:
            return 0.0
        rate = last_bill.invoice_currency_rate
        return currency.round(cost * rate)

    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ("list", "form"):
            self._inject_product_cost_currency_fields(arch)
        return arch, view

    def _inject_product_cost_currency_fields(self, arch):
        amount_fields = self.env["ir.model.fields"].sudo().search(
            [
                ("model", "=", self._name),
                ("name", "like", "x_cost_currency_%"),
            ]
        )
        if not amount_fields:
            return
        ref_nodes = arch.xpath("//field[@name='standard_price']")
        if not ref_nodes:
            return
        ref_node = ref_nodes[-1]
        parent = ref_node.getparent()
        idx = list(parent).index(ref_node)
        offset = 0
        for af in amount_fields:
            currency_id = af.name.rsplit("_", 1)[-1]
            group_xmlid = self._currency_account_group_xmlid(currency_id)
            if af.currency_field:
                currency_el = etree.Element("field")
                currency_el.set("name", af.currency_field)
                currency_el.set("column_invisible", "True")
                currency_el.set("groups", group_xmlid)
                parent.insert(idx + 1 + offset, currency_el)
                offset += 1
            field_el = etree.Element("field")
            field_el.set("name", af.name)
            field_el.set("optional", "show")
            field_el.set("readonly", "1")
            field_el.set("groups", group_xmlid)
            parent.insert(idx + 1 + offset, field_el)
            offset += 1
