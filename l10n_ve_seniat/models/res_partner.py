import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

VE_CODE = "VE"
VE_VAT_FIRST_LETTERS = frozenset("VEJCPG")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_ve_fiscal_locks_apply(self):
        country = self.env.company.account_fiscal_country_id
        return bool(country and country.code == VE_CODE)

    def _l10n_ve_override_locked_partner_fields(self):
        return self.env.user.has_group(
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
        )

    def _l10n_ve_lock_partner_fiscal_data_enabled(self):
        return self.env.company.l10n_ve_lock_partner_fiscal_data

    def _l10n_ve_validate_partner_vat_format_enabled(self):
        return self.env.company.l10n_ve_validate_partner_vat_format

    def _l10n_ve_has_posted_accounting_activity(self):
        self.ensure_one()
        commercial = self.commercial_partner_id
        return bool(
            self.env["account.move.line"]
            .sudo()
            .search(
                [
                    ("partner_id", "child_of", commercial.id),
                    ("parent_state", "=", "posted"),
                ],
                limit=1,
            )
        )

    def _l10n_ve_check_fiscal_lock_on_write(self, partners, vals):
        if (
            self._l10n_ve_fiscal_locks_apply()
            and self._l10n_ve_lock_partner_fiscal_data_enabled()
            and not self._l10n_ve_override_locked_partner_fields()
            and {"name", "vat"} & vals.keys()
        ):
            for partner in partners:
                if partner._l10n_ve_has_posted_accounting_activity():
                    raise UserError(
                        _(
                            "Cannot change the name or VAT of contact “%(name)s” "
                            "because it already has posted accounting entries, "
                            "invoices or related records. Ask a settings administrator "
                            "to apply the change."
                        )
                        % {"name": partner.display_name}
                    )

    def _l10n_ve_effective_country_for_write(self, vals):
        self.ensure_one()
        if "country_id" in vals:
            cid = vals["country_id"]
            if not cid:
                return self.env["res.country"]
            return self.env["res.country"].browse(cid)
        return self.country_id

    def _l10n_ve_taxpayer_country(self):
        self.ensure_one()
        if self.country_id:
            return self.country_id
        if not self.is_company:
            return self.env["res.country"]
        company = (
            self.env["res.company"]
            .sudo()
            .search([("partner_id", "=", self.id)], limit=1)
        )
        if not company:
            return self.env["res.country"]
        return company.country_id or company.account_fiscal_country_id

    @api.model
    def _l10n_ve_normalize_vat_leading_prefix(self, vat):
        if vat in (False, None):
            return vat
        if not isinstance(vat, str):
            vat = str(vat)
        stripped = vat.strip()
        if not stripped or stripped == "/":
            return vat
        if stripped[0].upper() in VE_VAT_FIRST_LETTERS:
            return stripped
        return f"V{stripped}"

    def _l10n_ve_write_vat_prefix_batches(self, vals):
        if self.env.context.get("skip_l10n_ve_vat_auto_prefix"):
            return None
        if "country_id" in vals and "vat" not in vals:
            nc = (
                self.env["res.country"].browse(vals["country_id"])
                if vals["country_id"]
                else self.env["res.country"]
            )
            if nc.code == VE_CODE:
                by_vat = {}
                for p in self:
                    if not p.vat:
                        continue
                    nv = self._l10n_ve_normalize_vat_leading_prefix(p.vat)
                    if nv != p.vat:
                        by_vat.setdefault(nv, self.browse())
                        by_vat[nv] |= p
                if not by_vat:
                    return None
                batches = []
                done = self.browse()
                for nv, recs in by_vat.items():
                    batches.append((recs, {**vals, "vat": nv}))
                    done |= recs
                rest = self - done
                if rest:
                    batches.append((rest, dict(vals)))
                return batches

        if "vat" not in vals or vals.get("vat") in (False, None):
            return None

        ve = self.filtered(
            lambda p: p._l10n_ve_effective_country_for_write(vals).code == VE_CODE
        )
        nve = self - ve
        if not ve:
            return None

        nv = self._l10n_ve_normalize_vat_leading_prefix(vals["vat"])
        if nve:
            return [
                (ve, {**vals, "vat": nv}),
                (nve, dict(vals)),
            ]
        vals["vat"] = nv
        return None

    def write(self, vals):
        vals = dict(vals)
        if "country_id" in vals:
            country = (
                self.env["res.country"].browse(vals["country_id"])
                if vals.get("country_id")
                else self.env["res.country"]
            )
            if not country or country.code != VE_CODE:
                vals["taxpayer_type"] = False
        batches = self._l10n_ve_write_vat_prefix_batches(vals)
        if batches is not None:
            res = True
            for recs, v in batches:
                self._l10n_ve_check_fiscal_lock_on_write(recs, v)
                res &= super(ResPartner, recs).write(v)
            return res

        self._l10n_ve_check_fiscal_lock_on_write(self, vals)
        return super().write(vals)

    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        if self.env.context.get("skip_l10n_ve_vat_auto_prefix"):
            return vals_list
        for vals in vals_list:
            cid = vals.get("country_id")
            if not cid:
                continue
            country = self.env["res.country"].browse(cid)
            if country.code != VE_CODE:
                vals["taxpayer_type"] = False
            if vals.get("vat") in (False, None):
                continue
            vals["vat"] = self._l10n_ve_normalize_vat_leading_prefix(vals["vat"])
        return vals_list

    def _default_res_country(self):
        return self.env.company.country_id.id or False

    def _default_vat(self):
        return False

    @api.depends(
        "complete_name",
        "email",
        "vat",
        "state_id",
        "country_id",
        "commercial_company_name",
    )
    @api.depends_context(
        "show_address",
        "partner_show_db_id",
        "address_inline",
        "show_email",
        "show_vat",
        "lang",
        "l10n_ve_display_name_vat_first",
    )
    def _compute_display_name(self):
        if (
            not self.env.context.get("l10n_ve_display_name_vat_first")
            or not self._l10n_ve_fiscal_locks_apply()
        ):
            return super()._compute_display_name()
        for partner in self:
            name = partner.with_context(lang=self.env.lang)._get_complete_name()
            if partner._context.get("show_address"):
                name = name + "\n" + partner._display_address(without_company=True)
            name = re.sub(r"\s+\n", "\n", name)
            if partner._context.get("partner_show_db_id"):
                name = f"{name} ({partner.id})"
            if partner._context.get("address_inline"):
                splitted_names = name.split("\n")
                name = ", ".join([n for n in splitted_names if n.strip()])
            if partner._context.get("show_email") and partner.email:
                name = f"{name} <{partner.email}>"
            vat = (partner.vat or "").strip()
            if vat and vat != "/":
                partner.display_name = f"{vat} - {name.strip()}"
            else:
                partner.display_name = name.strip()

    taxpayer_type = fields.Selection(
        [
            ("ordinary", "Ordinary"),
            ("formal", "Formal"),
            ("special", "Special"),
        ],
    )

    # TODO: prefix_vat isn't used anywhere
    prefix_vat = fields.Char(string="Prefix vat", compute="_compute_vat_prefix")
    municipality_id = fields.Many2one("res.country.municipality", "Municipality")
    parish_id = fields.Many2one("res.country.parish", "Parish")
    country_id = fields.Many2one("res.country", default=_default_res_country)
    vat = fields.Char(default=_default_vat)

    @api.depends("vat")
    def _compute_vat_prefix(self):
        for record in self:
            if record.vat:
                match = re.match(r"([VEJPG])([0-9]+)", record.vat, re.IGNORECASE)
                if match:
                    record.prefix_vat = match.group(1).upper()
                    continue
            record.prefix_vat = False

    @api.onchange("country_id")
    def _onchange_country_id_clear_taxpayer_type(self):
        if self.country_id and self.country_id.code != VE_CODE:
            self.taxpayer_type = False

    @api.onchange("municipality_id")
    def _onchange_municipality_id(self):
        self.parish_id = False

    @api.onchange("state_id")
    def _onchange_state_id(self):
        self.municipality_id = False
        self.parish_id = False

    @api.onchange("vat", "country_id")
    def _onchange_l10n_ve_vat_auto_prefix(self):
        if not self.country_id or self.country_id.code != VE_CODE:
            return
        if not self.vat:
            return
        nv = self._l10n_ve_normalize_vat_leading_prefix(self.vat)
        if nv != self.vat:
            self.vat = nv

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not self._l10n_ve_fiscal_locks_apply():
            return values
        name_val = values.get("name")
        if not name_val or not isinstance(name_val, str):
            return values
        term = name_val.strip()
        if not term or not self._l10n_ve_create_search_term_is_rif_like(term):
            return values
        if "vat" in fields_list:
            values["vat"] = term
        if "name" in fields_list:
            values["name"] = False
        return values

    @api.model
    def _l10n_ve_vat_search_variants(self, value):
        if not value:
            return []
        variants = {value}
        compact = re.sub(r"[\s\-_.]", "", value)
        if compact:
            variants.add(compact)
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 5:
            variants.add(digits)
        return list(variants)

    @api.model
    def _l10n_ve_create_search_term_is_rif_like(self, term):
        if not term:
            return False
        if self.check_vat_ve(term):
            return True
        if re.match(r"^[VEJPGCvecjpg]", term, re.I):
            if len(term) > 1 and term[1].isalpha():
                return False
            if re.search(r"\d", term):
                return True
        if (
            re.fullmatch(r"[\d.\-\sVEJPGCvecjpg]+", term, re.I)
            and len(re.sub(r"\D", "", term)) >= 6
        ):
            return True
        return False

    @api.model
    def _l10n_ve_name_search_should_query_vat_first(self, term):
        if not term or not self._l10n_ve_fiscal_locks_apply():
            return False
        t = term.strip()
        if self._l10n_ve_create_search_term_is_rif_like(t):
            return True
        digits = re.sub(r"\D", "", t)
        return len(digits) >= 5

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if not self._l10n_ve_fiscal_locks_apply():
            return domain
        if not value or not str(value).strip():
            return domain
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            return domain
        variant_domains = [
            [("vat", "ilike", v)]
            for v in self._l10n_ve_vat_search_variants(str(value).strip())
        ]
        return expression.OR([domain, *variant_domains])

    def check_vat_ve(self, vat):
        """Valida formato de RIF/CI venezolano.

        Parameters
        ----------
        vat : str
            Identificación fiscal a validar.

        Returns
        -------
        bool

        Notes
        -----
        Art. 13 num. 5-7 PA SNAT/2011/0071: RIF del emisor y adquiriente.
        Art. 7 num. 3 y 7 PA SNAT/2024/000102: datos del receptor digital.
        """

        vat_regex = re.compile(
            r"""
            ^([vecjpg])                          # group 1 - kind
            (
                (?:
                    (?P<optional_1>-)?                  # optional '-' (1)
                    [0-9]{2}
                    (?(optional_1)(?P<optional_2>[.])?) # optional '.' (2) only if (1)
                    [0-9]{3}
                    (?(optional_2)[.])                  # mandatory '.' if (2)
                    [0-9]{3}
                    (?(optional_1)-)                    # mandatory '-' if (1)
                |
                    [0-9]{7}                            # cédula compacta (ej. V7440703)
                )
            )                                       # group 2 - identifier number
            ([0-9])?                                # dígito verificador opcional
            $
        """,
            re.VERBOSE | re.IGNORECASE,
        )

        matches = re.fullmatch(vat_regex, vat)
        if not matches:
            return False

        return True

    @api.model
    @api.readonly
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        search_mode = self.env.context.get("res_partner_search_mode")
        if not self._l10n_ve_fiscal_locks_apply():
            if search_mode == "customer":
                args = [("customer_rank", ">=", 1)] + args
            elif search_mode == "supplier":
                args = [("supplier_rank", ">=", 1)] + args

        name_stripped = (name or "").strip()
        if not limit:
            limit = 100

        if not name_stripped or not self._l10n_ve_name_search_should_query_vat_first(
            name_stripped
        ):
            return super().name_search(name, args=args, operator=operator, limit=limit)

        vat_terms = self._l10n_ve_vat_search_variants(name_stripped)
        vat_domain = expression.OR([[("vat", "ilike", v)] for v in vat_terms])
        domain = expression.AND([vat_domain, args]) if args else vat_domain
        vat_ids = self.search(domain, limit=limit).ids

        standard = super().name_search(name, args=args, operator=operator, limit=limit)

        if not vat_ids:
            return standard

        seen = set()
        out = []
        for partner in self.browse(vat_ids):
            out.append((partner.id, partner.sudo().display_name))
            seen.add(partner.id)
            if len(out) >= limit:
                return out
        for pair in standard:
            if pair[0] not in seen:
                out.append(pair)
                seen.add(pair[0])
                if len(out) >= limit:
                    break
        return out

    def _l10n_ve_must_check_rif_vat_format(self):
        self.ensure_one()
        if self.env.context.get("skip_l10n_ve_vat_rif_format_check"):
            return False
        if not self._l10n_ve_validate_partner_vat_format_enabled():
            return False
        commercial = self.commercial_partner_id
        return (
            self.customer_rank > 0
            or self.supplier_rank > 0
            or commercial.customer_rank > 0
            or commercial.supplier_rank > 0
        )

    @api.constrains("vat", "country_id", "customer_rank", "supplier_rank")
    def _check_l10n_ve_vat_format(self):
        """Restricción ORM sobre formato de RIF en contactos venezolanos.

        Notes
        -----
        Art. 13 num. 5-7 PA SNAT/2011/0071: RIF en facturas.
        """

        for partner in self:
            if not partner.country_id or partner.country_id.code != VE_CODE:
                continue
            if not partner._l10n_ve_must_check_rif_vat_format():
                continue
            vat = (partner.vat or "").strip()
            if not vat or vat == "/":
                continue
            if not partner.check_vat_ve(vat):
                raise ValidationError(
                    _(
                        "El RIF («%(vat)s») no tiene un formato válido para contactos "
                        "venezolanos. Use [V/E/J/C/P/G] y el número (ej.: V7440703, "
                        "V12345678, J-12.345.678-9)."
                    )
                    % {"vat": vat}
                )

    @api.constrains("country_id", "taxpayer_type")
    def _check_taxpayer_type_country(self):
        for rec in self:
            if not rec.taxpayer_type:
                continue
            country = rec._l10n_ve_taxpayer_country()
            if not country or country.code != VE_CODE:
                raise ValidationError(
                    _(
                        "The taxpayer type can only be set for Venezuelan partners "
                        "(country code 'VE')."
                    )
                )
