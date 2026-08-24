# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nVeSeniatCommon(AccountTestInvoicingCommon):
    @classmethod
    def _create_product(cls, **create_values):
        sale_tax = cls.company_data.get("default_tax_sale")
        purchase_tax = cls.company_data.get("default_tax_purchase")
        if sale_tax:
            create_values["taxes_id"] = [Command.set(sale_tax.ids)]
        if purchase_tax:
            create_values["supplier_taxes_id"] = [Command.set(purchase_tax.ids)]
        return super()._create_product(**create_values)

    @classmethod
    def _l10n_ve_ensure_sql_defaults(cls, table_name, model_name):
        cr = cls.env.cr
        cr.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND is_nullable = 'NO'
              AND column_default IS NULL
              AND column_name <> 'id'
            """,
            (table_name,),
        )
        fallbacks = {
            "boolean": "false",
            "integer": "0",
            "bigint": "0",
            "smallint": "0",
            "numeric": "0",
            "double precision": "0",
            "real": "0",
            "character varying": "''",
            "character": "''",
            "text": "''",
            "date": "'2026-01-01'",
            "timestamp without time zone": "'2026-01-01'",
            "timestamp with time zone": "'2026-01-01'",
        }
        model_fields = (
            cls.env[model_name]._fields if model_name in cls.env else {}
        )
        for column_name, data_type in cr.fetchall():
            sql_default = fallbacks.get(data_type)
            field = model_fields.get(column_name)
            if field is not None:
                default = field.default
                if callable(default):
                    try:
                        default = default(cls.env[model_name])
                    except Exception:
                        default = None
                if default is not None and default is not False:
                    if field.type == "boolean":
                        sql_default = "true" if default else "false"
                    elif field.type in ("char", "text", "selection", "html"):
                        sql_default = "'%s'" % str(default).replace("'", "''")
                    elif field.type in ("integer", "float", "monetary"):
                        sql_default = str(default)
                    elif field.type == "many2one":
                        sql_default = str(int(getattr(default, "id", default)))
            if not sql_default:
                continue
            cr.execute(
                'ALTER TABLE "%s" ALTER COLUMN "%s" SET DEFAULT %s'
                % (table_name, column_name, sql_default)
            )

    @classmethod
    def _create_company(cls, **create_values):
        cls._l10n_ve_ensure_sql_defaults("res_company", "res.company")
        cls._l10n_ve_ensure_sql_defaults("product_template", "product.template")
        cls._l10n_ve_ensure_sql_defaults("product_product", "product.product")
        Company = cls.env["res.company"]
        for fname, field in Company._fields.items():
            if (
                fname in create_values
                or not field.store
                or field.compute
                or not field.required
            ):
                continue
            default = field.default
            if default is None:
                continue
            if callable(default):
                try:
                    default = default(Company)
                except Exception:
                    continue
            if default is None:
                continue
            if field.type == "many2one":
                default = getattr(default, "id", default)
            create_values.setdefault(fname, default)
        return super()._create_company(**create_values)

    @classmethod
    @AccountTestInvoicingCommon.setup_country("ve")
    @AccountTestInvoicingCommon.setup_chart_template("ve_seniat")
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.partner_id.write(
            {"vat": "J770023598", "country_id": cls.env.ref("base.ve").id}
        )
        cls.change_company_country(cls.env.company, cls.env.ref("base.ve"))
        cls._l10n_ve_normalize_default_taxes()
        cls._setup_l10n_ve_sale_journal_sections()
        cls._setup_l10n_ve_dispatch_guide_section()
        cls._l10n_ve_set_company_emission_medium_codes("free_form")
        cls.company_data["default_journal_sale"].write(
            {
                "l10n_ve_emission_medium": "free",
                "l10n_ve_free_form_print_medium": "pdf",
            }
        )
        cls._l10n_ve_normalize_fixture_products()
        cls._l10n_ve_normalize_fixture_partners()
        cls._l10n_ve_activate_test_currencies()

    @classmethod
    def _l10n_ve_activate_test_currencies(cls):
        for xmlid in ("base.VES", "base.USD", "base.EUR"):
            currency = cls.env.ref(xmlid, raise_if_not_found=False)
            if currency:
                currency.active = True

    @classmethod
    def _l10n_ve_normalize_fixture_partners(cls):
        ve = cls.env.ref("base.ve")
        for partner, vat in (
            (getattr(cls, "partner_a", None), "V12345678"),
            (getattr(cls, "partner_b", None), "V87654321"),
        ):
            if not partner:
                continue
            partner.write(
                {
                    "country_id": ve.id,
                    "vat": vat,
                }
            )

    @classmethod
    def _l10n_ve_normalize_default_taxes(cls):
        for tax_key in ("default_tax_sale", "default_tax_purchase"):
            tax = cls.company_data.get(tax_key)
            if not tax:
                continue
            tax = tax.sudo()
            vals = {
                "country_id": cls.env.ref("base.ve").id,
                "price_include_override": "tax_excluded",
            }
            if tax.amount_type == "percent" and tax.amount:
                # Keep chart amounts (typically 16%); only force exclude-from-price.
                pass
            elif tax.amount_type == "percent":
                vals["amount"] = 16.0
            tax.write(vals)
            children = tax.flatten_taxes_hierarchy() - tax
            if children:
                children.sudo().write(
                    {
                        "country_id": cls.env.ref("base.ve").id,
                        "price_include_override": "tax_excluded",
                    }
                )

    @classmethod
    def _l10n_ve_normalize_fixture_products(cls):
        sale_tax = cls.company_data.get("default_tax_sale")
        purchase_tax = cls.company_data.get("default_tax_purchase")
        for product in (
            getattr(cls, "product_a", None),
            getattr(cls, "product_b", None),
        ):
            if not product:
                continue
            vals = {}
            if sale_tax:
                vals["taxes_id"] = [Command.set(sale_tax.ids)]
            if purchase_tax:
                vals["supplier_taxes_id"] = [Command.set(purchase_tax.ids)]
            if vals:
                product.with_context(
                    l10n_ve_skip_product_tax_constraint=True
                ).sudo().write(vals)

    @classmethod
    def _l10n_ve_set_company_emission_medium_codes(cls, *codes):
        mediums = cls.env["l10n.ve.emission.medium"].search(
            [("code", "in", list(codes))]
        )
        cls.env.company.write({"l10n_ve_emission_medium_ids": [(6, 0, mediums.ids)]})

    @classmethod
    def _setup_l10n_ve_sale_journal_sections(cls):
        company = cls.env.company
        journal = cls.company_data["default_journal_sale"]
        book = cls.env["account.book"].create(
            {
                "name": "Talonario tests",
                "company_id": company.id,
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        sec = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Ventas",
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        journal.write(
            {
                "l10n_ve_invoice_section_id": sec.id,
                "l10n_ve_credit_note_section_id": sec.id,
            }
        )

    @classmethod
    def _setup_l10n_ve_dispatch_guide_section(cls):
        Warehouse = cls.env["stock.warehouse"]
        if "l10n_ve_dispatch_guide_section_id" not in Warehouse._fields:
            return
        company = cls.env.company
        warehouse = Warehouse.search([("company_id", "=", company.id)], limit=1)
        if not warehouse or warehouse.l10n_ve_dispatch_guide_section_id:
            return
        book_vals = {
            "name": "Talonario guias tests",
            "company_id": company.id,
            "number_from": 1,
            "number_to": 99_999_999,
        }
        if "l10n_ve_series_prefix" in cls.env["account.book"]._fields:
            book_vals["l10n_ve_series_prefix"] = "01"
        book = cls.env["account.book"].create(book_vals)
        section = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Guias despacho",
                "number_from": 40_000_000,
                "number_to": 49_999_999,
            }
        )
        warehouse.l10n_ve_dispatch_guide_section_id = section

    def _l10n_ve_set_company_taxpayer_for_igtf_notice(self, taxpayer_type="special"):
        company = self.env.company
        if (
            taxpayer_type == "special"
            and "l10n_ve_igtf_account_id" in company._fields
            and not company.l10n_ve_igtf_account_id
        ):
            account = False
            if hasattr(company, "_l10n_ve_get_default_igtf_account"):
                account = company._l10n_ve_get_default_igtf_account()
            if not account:
                account = (
                    self.env["account.account"]
                    .with_company(company)
                    .create(
                        {
                            "name": "IGTF Payable Test",
                            "code": "2102098",
                            "account_type": "liability_current",
                            "company_ids": [Command.set([company.id])],
                            "reconcile": True,
                        }
                    )
                )
            company.l10n_ve_igtf_account_id = account
        company.partner_id.taxpayer_type = taxpayer_type

    @classmethod
    def _l10n_ve_configure_journal_fiscal_machine(cls, journal, **extra):
        cls._l10n_ve_set_company_emission_medium_codes("fiscal_machine")
        vals = {"l10n_ve_emission_medium": "fiscal_machine"}
        if "l10n_ve_fiscal_machine_id" in journal._fields:
            machine_model = cls.env["l10n.ve.fiscal.machine"].sudo()
            machine = machine_model.search(
                [("company_id", "=", journal.company_id.id)], limit=1
            )
            if not machine:
                machine = machine_model.create(
                    {
                        "name": "Test Fiscal Machine",
                        "company_id": journal.company_id.id,
                        "registered_serial": "TESTSENIAT1",
                        "fiscal_rif": "J123456789",
                    }
                )
            vals["l10n_ve_fiscal_machine_id"] = machine.id
        vals.update(extra)
        journal.write(vals)

    @classmethod
    def _l10n_ve_configure_journal_digital(cls, journal, **extra):
        cls._l10n_ve_set_company_emission_medium_codes("digital_billing")
        vals = {
            "l10n_ve_emission_medium": "digital",
            "l10n_ve_invoice_section_id": False,
            "l10n_ve_credit_note_section_id": False,
            "l10n_ve_debit_note_section_id": False,
        }
        vals.update(extra)
        journal.write(vals)

    @classmethod
    def _l10n_ve_configure_journal_free(cls, journal, print_medium="pdf", **extra):
        cls._l10n_ve_set_company_emission_medium_codes("free_form")
        vals = {
            "l10n_ve_emission_medium": "free",
            "l10n_ve_free_form_print_medium": print_medium,
        }
        vals.update(extra)
        journal.write(vals)

    @classmethod
    def _l10n_ve_create_invoice(
        cls,
        move_type="out_invoice",
        partner=None,
        invoice_date=None,
        amounts=None,
        taxes=None,
        currency=None,
        journal=None,
        post=False,
        **extra,
    ):
        amounts = amounts or [100.0]
        if taxes is None:
            taxes = (
                cls.company_data["default_tax_sale"]
                if move_type.startswith("out_")
                else cls.company_data["default_tax_purchase"]
            )
        account = (
            cls.company_data["default_account_revenue"]
            if move_type.startswith("out_")
            else cls.company_data["default_account_expense"]
        )
        invoice_date = invoice_date or fields.Date.today()
        vals = {
            "move_type": move_type,
            "partner_id": (partner or cls.partner_a).id,
            "invoice_date": invoice_date,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "test line",
                        "quantity": 1.0,
                        "price_unit": amount,
                        "account_id": account.id,
                        "tax_ids": [Command.set(taxes.ids)],
                    }
                )
                for amount in amounts
            ],
        }
        if currency:
            vals["currency_id"] = currency.id
        if journal:
            vals["journal_id"] = journal.id
        vals.update(extra)
        move = cls.env["account.move"].create(vals)
        if post:
            move.action_post()
        return move
