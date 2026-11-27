# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import ast
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

RIF_BODY = re.compile(r"^[VEJPGC]\d{6,9}$")
RIF_STRICT = re.compile(r"^[VEJPGC]\d{9}$")
CEDULA_V_BODY = re.compile(r"^V\d{6,8}$")
CEDULA_E_BODY = re.compile(r"^E\d{6,8}$")

# SENIAT letter on RIF / cédula → fiscal person type (Vauxoo 8.0 PNRE/PNNR/PJDO/PJND).
RIF_LETTER_PERSON_TYPE = {
    "V": "pnre",
    "E": "pnnr",
    "J": "pjdo",
    "C": "pjdo",
    "G": "pjdo",
    "P": "pjnd",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _l10n_ve_id_type(self, *xmlids):
        seen = []
        for xmlid in xmlids:
            if xmlid not in seen:
                seen.append(xmlid)
        for xmlid in seen:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                return record
        return self.env["l10n_latam.identification.type"]

    @api.model
    def _l10n_ve_default_identification_type(self):
        company = self.env.company
        country = company.account_fiscal_country_id or company.country_id
        if country and country.code == "VE":
            return self._l10n_ve_id_type(
                "l10n_ve_base.it_rif",
                "l10n_latam_base.it_vat",
            )
        return self._l10n_ve_id_type("l10n_latam_base.it_vat")

    l10n_latam_identification_type_id = fields.Many2one(
        "l10n_latam.identification.type",
        default=lambda self: self._l10n_ve_default_identification_type(),
    )
    vat = fields.Char(string="Número de Identificación")

    seniat_updated = fields.Boolean(
        help="Indicates if partner was updated using SENIAT",
    )
    wh_iva_rate = fields.Float(
        string="IVA Retention Rate (%)",
        digits="Account",
        help="Vat Withholding rate according to SENIAT",
    )
    wh_iva_agent = fields.Boolean(
        string="Wh. IVA Agent",
        help="Indicate if the partner is a withholding vat agent",
    )
    person_type = fields.Selection(
        selection=[
            ("pnre", "Natural Person Resident (PNRE)"),
            ("pnnr", "Natural Person Non Resident (PNNR)"),
            ("pjdo", "Legal Entity Domiciled (PJDO)"),
            ("pjnd", "Legal Entity Non Domiciled (PJND)"),
        ],
        default="pjdo",
        help="Venezuelan Fiscal Person Type for ISLR / IVA classification",
    )
    vat_subjected = fields.Boolean(
        string="VAT Subject",
        help="Indicates if SENIAT reports the partner as VAT taxpayer",
    )
    l10n_ve_responsibility_type_id = fields.Many2one(
        comodel_name="l10n_ve.responsibility.type",
        string="SENIAT Taxpayer Type",
        help="Ordinary, Formal or Special taxpayer (Mastercore l10n_ve_base).",
        ondelete="restrict",
    )
    municipality_id = fields.Many2one(
        comodel_name="res.country.state.municipality",
        ondelete="restrict",
        domain="[('state_id', '=', state_id)]",
    )
    parish_id = fields.Many2one(
        comodel_name="res.country.state.municipality.parish",
        ondelete="restrict",
        domain="[('municipality_id', '=', municipality_id)]",
    )
    l10n_ve_identification_locked = fields.Boolean(
        string="Identification Locked",
        compute="_compute_l10n_ve_identification_locked",
        help="VAT, identification type and person type cannot change after invoices, "
        "sales, purchases, payments or an open balance.",
    )

    @api.model
    def _l10n_ve_normalize_rif(self, vat):
        rif = re.sub(r"[^A-Za-z0-9]", "", vat or "").upper()
        if rif.startswith("VE") and len(rif) > 2 and rif[2] in "VEJPGC":
            rif = rif[2:]
        return rif

    @api.model
    def _l10n_ve_is_valid_rif(self, vat):
        return bool(RIF_BODY.match(self._l10n_ve_normalize_rif(vat)))

    @api.model
    def _l10n_ve_is_valid_cedula(self, vat, letter="V"):
        body = self._l10n_ve_normalize_rif(vat)
        pattern = CEDULA_V_BODY if letter == "V" else CEDULA_E_BODY
        return bool(pattern.match(body))

    @api.model
    def _l10n_ve_kind_from_number(self, vat):
        """Classify the number itself: rif, cedula_v, cedula_e, passport or False."""
        body = self._l10n_ve_normalize_rif(vat)
        if not body:
            return False
        if RIF_STRICT.match(body):
            return "rif"
        if CEDULA_V_BODY.match(body):
            return "cedula_v"
        if CEDULA_E_BODY.match(body):
            return "cedula_e"
        return False

    @api.model
    def _l10n_ve_type_from_kind(self, kind):
        mapping = {
            "rif": ("l10n_ve_base.it_rif", "l10n_latam_base.it_vat"),
            "cedula_v": ("l10n_ve_base.it_cedula_v",),
            "cedula_e": (
                "l10n_ve_base.it_cedula_e",
                "l10n_latam_base.it_fid",
            ),
            "passport": (
                "l10n_ve_base.it_pass",
                "l10n_latam_base.it_pass",
            ),
        }
        return self._l10n_ve_id_type(*mapping.get(kind, ()))

    def _l10n_ve_identification_kind(self):
        """Kind implied by the type. Do not guess RIF from the country."""
        self.ensure_one()
        itype = self.l10n_latam_identification_type_id
        if not itype:
            return False
        if itype == self._l10n_ve_id_type(
            "l10n_ve_base.it_rif", "l10n_latam_base.it_vat"
        ):
            return "rif"
        if itype == self._l10n_ve_id_type("l10n_ve_base.it_cedula_v"):
            return "cedula_v"
        if itype == self._l10n_ve_id_type(
            "l10n_ve_base.it_cedula_e", "l10n_latam_base.it_fid"
        ):
            return "cedula_e"
        if itype == self._l10n_ve_id_type(
            "l10n_ve_base.it_pass", "l10n_latam_base.it_pass"
        ):
            return "passport"
        if itype.is_vat and (not itype.country_id or itype.country_id.code == "VE"):
            return "rif"
        return False

    def _l10n_ve_identification_xmlid(self):
        self.ensure_one()
        itype = self.l10n_latam_identification_type_id
        if not itype:
            return False
        return itype.get_external_id().get(itype.id)

    @api.model
    def _l10n_ve_is_passport_xmlid(self, xmlid):
        return xmlid in (
            "l10n_ve_base.it_pass",
            "l10n_latam_base.it_pass",
        )

    def _l10n_ve_is_valid_fiscal_id(self, vat=None):
        self.ensure_one()
        number = vat if vat is not None else self.vat
        kind = self._l10n_ve_identification_kind() or self._l10n_ve_kind_from_number(
            number
        )
        if kind == "passport":
            return len(self._l10n_ve_normalize_rif(number)) >= 4
        if kind == "cedula_v":
            return self._l10n_ve_is_valid_cedula(number, "V")
        if kind == "cedula_e":
            return self._l10n_ve_is_valid_cedula(number, "E")
        return bool(RIF_STRICT.match(self._l10n_ve_normalize_rif(number)))

    def _l10n_ve_person_type_label(self, person_type):
        selection = self._fields["person_type"]._description_selection(self.env)
        return dict(selection).get(person_type, person_type or "")

    def _l10n_ve_suggested_person_type(self):
        """Person type implied by identification type and the SENIAT letter."""
        self.ensure_one()
        kind = self._l10n_ve_identification_kind()
        if kind == "cedula_v":
            return "pnre"
        if kind == "cedula_e":
            return "pnnr"
        if kind == "passport":
            return "pnnr"
        body = self._l10n_ve_normalize_rif(self.vat)
        if body:
            return RIF_LETTER_PERSON_TYPE.get(body[0])
        return False

    def _l10n_ve_allowed_person_types(self):
        self.ensure_one()
        kind = self._l10n_ve_identification_kind()
        if kind == "passport":
            return ("pnnr", "pjnd")
        suggested = self._l10n_ve_suggested_person_type()
        return (suggested,) if suggested else ()

    def _l10n_ve_needs_identification(self):
        self.ensure_one()
        if self.env.context.get("l10n_ve_skip_id_check"):
            return False
        if self.parent_id or self.employee:
            return False
        if self.user_ids and not self.partner_share:
            return False
        if self._l10n_ve_is_own_company_partner():
            return False
        if self.country_id:
            return self.country_id.code == "VE"
        company = self.company_id or self.env.company
        fiscal = company.account_fiscal_country_id or company.country_id
        return bool(self.is_company and fiscal and fiscal.code == "VE")

    def _l10n_ve_is_own_company_partner(self):
        """The company contact receives the country before it has a RIF."""
        self.ensure_one()
        return bool(
            self.id
            and self.env["res.company"]
            .sudo()
            .search_count([("partner_id", "=", self.id)])
        )

    def _l10n_ve_identification_key_value(self):
        """Normalized RIF, cédula or passport used to detect duplicates."""
        self.ensure_one()
        if not self.vat:
            return False
        kind = self._l10n_ve_identification_kind()
        number_kind = self._l10n_ve_kind_from_number(self.vat)
        if kind == "passport":
            body = self._l10n_ve_normalize_rif(self.vat)
            return body if len(body) >= 4 else False
        if kind in ("rif", "cedula_v", "cedula_e") or number_kind in (
            "rif",
            "cedula_v",
            "cedula_e",
        ):
            return self._l10n_ve_normalize_rif(self.vat) or False
        return False

    def _l10n_ve_find_duplicate_identification(self):
        """Another taxpayer with the same RIF, cédula or passport.

        Contacts of the same company share the parent number, because Odoo
        copies the commercial VAT onto them.
        """
        self.ensure_one()
        key = self._l10n_ve_identification_key_value()
        if not key or not self.id:
            return self.env["res.partner"]
        commercial_id = self.commercial_partner_id.id or self.id
        self.env.cr.execute(
            """
            SELECT id
              FROM res_partner
             WHERE id != %s
               AND COALESCE(commercial_partner_id, id) != %s
               AND vat IS NOT NULL
               AND (
                    CASE
                        WHEN upper(regexp_replace(
                            vat, '[^A-Za-z0-9]', '', 'g')) ~ '^VE[VEJPGC]'
                        THEN substring(upper(regexp_replace(
                            vat, '[^A-Za-z0-9]', '', 'g')) FROM 3)
                        ELSE upper(regexp_replace(
                            vat, '[^A-Za-z0-9]', '', 'g'))
                    END
               ) = %s
             LIMIT 1
            """,
            (self.id, commercial_id, key),
        )
        found = self.env.cr.fetchone()
        return self.browse(found[0]) if found else self.env["res.partner"]

    def _l10n_ve_identification_format_error(self):
        self.ensure_one()
        if not self.vat:
            return False
        kind = self._l10n_ve_identification_kind()
        number_kind = self._l10n_ve_kind_from_number(self.vat)
        if not kind and number_kind in ("rif", "cedula_v", "cedula_e"):
            kind = number_kind
        if kind == "passport":
            if len(self._l10n_ve_normalize_rif(self.vat)) < 4:
                return self.env._(
                    "The passport %s is not valid. Enter at least 4 characters.",
                    self.vat,
                )
            return False
        if kind == "cedula_v":
            if not self._l10n_ve_is_valid_cedula(self.vat, "V"):
                return self.env._(
                    "The Venezuelan ID %s is not valid. Use V plus 6 to 8 "
                    "digits (e.g. V12345678).",
                    self.vat,
                )
            return False
        if kind == "cedula_e":
            if not self._l10n_ve_is_valid_cedula(self.vat, "E"):
                return self.env._(
                    "The foreign ID %s is not valid. Use E plus 6 to 8 "
                    "digits (e.g. E12345678).",
                    self.vat,
                )
            return False
        if kind != "rif":
            return False
        if number_kind == "cedula_v":
            return self.env._(
                "The number %s is a Venezuelan ID (cédula), not a RIF. "
                "Choose «Cédula Venezolano» or enter the RIF with 9 digits "
                "(V + 8 digits + check digit).",
                self.vat,
            )
        if number_kind == "cedula_e":
            return self.env._(
                "The number %s is a foreign ID (cédula), not a RIF. "
                "Choose «Cédula Extranjera» or enter the RIF with 9 digits.",
                self.vat,
            )
        normalized = self._l10n_ve_normalize_rif(self.vat)
        if not RIF_STRICT.match(normalized) or not self.check_vat_ve(normalized):
            return self.env._(
                "The RIF %s is not valid. Use V/E/J/P/G/C, 8 digits and "
                "the SENIAT check digit (e.g. J123456784).",
                self.vat,
            )
        return False

    def _l10n_ve_person_type_error(self):
        self.ensure_one()
        allowed = self._l10n_ve_allowed_person_types()
        if not allowed or not self.person_type:
            return False
        if self.person_type in allowed:
            return False
        expected = ", ".join(self._l10n_ve_person_type_label(code) for code in allowed)
        return self.env._(
            "The identification type %(type)s and number %(vat)s are not "
            "compatible with person type %(person)s. Expected: %(expected)s.",
            type=self.l10n_latam_identification_type_id.display_name
            or self.env._("RIF"),
            vat=self.vat or "",
            person=self._l10n_ve_person_type_label(self.person_type),
            expected=expected,
        )

    @api.model
    def _l10n_ve_prepare_identification(self, vals, existing=None):
        """Align type and person type so RIF and cédula stay distinct."""
        if self.env.context.get("l10n_ve_skip_id_check"):
            return vals
        if (
            existing
            and existing.commercial_partner_id
            in existing._l10n_ve_commercials_with_activity()
        ):
            return vals
        vat = vals["vat"] if "vat" in vals else (existing.vat if existing else None)
        if "country_id" in vals:
            country = (
                self.env["res.country"].browse(vals["country_id"])
                if vals["country_id"]
                else False
            )
        else:
            country = existing.country_id if existing else False
        if country and country.code != "VE":
            return vals
        number_kind = self._l10n_ve_kind_from_number(vat)
        if not country and number_kind not in ("rif", "cedula_v", "cedula_e"):
            return vals

        explicit_type = "l10n_latam_identification_type_id" in vals
        if "l10n_latam_identification_type_id" in vals:
            itype = self.env["l10n_latam.identification.type"].browse(
                vals["l10n_latam_identification_type_id"] or 0
            )
        else:
            itype = existing.l10n_latam_identification_type_id if existing else False

        inferred = self._l10n_ve_type_from_kind(self._l10n_ve_kind_from_number(vat))
        generic = self.env.ref("l10n_latam_base.it_vat", raise_if_not_found=False)
        rif = self._l10n_ve_id_type("l10n_ve_base.it_rif", "l10n_latam_base.it_vat")
        if inferred and not explicit_type:
            if not itype or itype == generic or (itype == rif and inferred != rif):
                vals["l10n_latam_identification_type_id"] = inferred.id
                itype = inferred

        preview = self.new(
            {
                "vat": vat,
                "l10n_latam_identification_type_id": itype.id if itype else False,
            }
        )
        suggested = preview._l10n_ve_suggested_person_type()
        if suggested:
            current = vals.get("person_type")
            if existing and "person_type" not in vals:
                current = existing.person_type
            if not current:
                vals["person_type"] = suggested
        return vals

    def _l10n_ve_commercials_with_activity(self):
        """Partners with invoices, orders, payments or a balance."""
        commercials = self.mapped("commercial_partner_id")
        if not commercials:
            return self.env["res.partner"]
        locked = self.env["res.partner"]
        moves = (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("commercial_partner_id", "in", commercials.ids),
                    (
                        "move_type",
                        "in",
                        (
                            "out_invoice",
                            "out_refund",
                            "in_invoice",
                            "in_refund",
                            "out_receipt",
                            "in_receipt",
                        ),
                    ),
                    ("state", "=", "posted"),
                ]
            )
        )
        locked |= moves.commercial_partner_id
        remaining = commercials - locked
        if remaining and "account.payment" in self.env:
            payment = self.env["account.payment"].sudo()
            payments = payment.search(
                [
                    ("partner_id.commercial_partner_id", "in", remaining.ids),
                    ("state", "not in", ("draft", "cancel", "canceled", "rejected")),
                ]
            )
            locked |= payments.mapped("partner_id.commercial_partner_id")
            remaining = commercials - locked
        if remaining:
            locked |= remaining.filtered(
                lambda partner: partner.credit or partner.debit
            )
            remaining = commercials - locked
        if remaining and "sale.order" in self.env:
            orders = (
                self.env["sale.order"]
                .sudo()
                .search(
                    [
                        ("partner_id.commercial_partner_id", "in", remaining.ids),
                        ("state", "in", ("sale", "done")),
                    ]
                )
            )
            locked |= orders.mapped("partner_id.commercial_partner_id")
            remaining = commercials - locked
        if remaining and "purchase.order" in self.env:
            orders = (
                self.env["purchase.order"]
                .sudo()
                .search(
                    [
                        ("partner_id.commercial_partner_id", "in", remaining.ids),
                        ("state", "in", ("purchase", "done")),
                    ]
                )
            )
            locked |= orders.mapped("partner_id.commercial_partner_id")
        return locked

    def _compute_l10n_ve_identification_locked(self):
        locked = self._l10n_ve_commercials_with_activity()
        for partner in self:
            partner.l10n_ve_identification_locked = (
                partner.commercial_partner_id in locked
            )

    @api.model
    def _l10n_ve_identification_label(self):
        return self.env._("Número de Identificación")

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        """One label only. Core/es_ES maps Tax ID and country vat_label to NIF."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != "form":
            return arch, view
        label = self._l10n_ve_identification_label()
        for node in list(arch.xpath("//label[@for='vat']")):
            node.getparent().remove(node)
        for node in arch.xpath("//label[@for='l10n_latam_identification_type_id']"):
            node.set("string", label)
        for node in arch.xpath("//field[@name='vat']"):
            node.set("string", label)
            node.set("nolabel", "1")
        for node in arch.xpath("//field[@name='l10n_latam_identification_type_id']"):
            node.set("nolabel", "1")
        for node in arch.xpath("//field[@name='person_type']"):
            current = node.get("readonly") or ""
            if "l10n_ve_identification_locked" not in current:
                node.set("readonly", "parent_id or l10n_ve_identification_locked")
        self._l10n_ve_address_search_only(arch)
        return arch, view

    def _l10n_ve_address_search_only(self, arch):
        """State, municipality and parish on the address are pickers, not creators."""
        no_create = {
            "no_open": True,
            "no_create": True,
            "no_create_edit": True,
            "no_quick_create": True,
        }
        names = {"state_id", "city_id", "municipality_id", "parish_id"}
        for node in arch.xpath(
            "//div[contains(@class, 'o_address_format')]//field[@name]"
        ):
            if node.get("name") not in names:
                continue
            try:
                current = ast.literal_eval(node.get("options") or "{}")
            except (ValueError, SyntaxError):
                current = {}
            if not isinstance(current, dict):
                current = {}
            current.update(no_create)
            node.set("options", str(current))

    @api.onchange("state_id")
    def _onchange_state_id_territorial(self):
        if self.municipality_id and self.municipality_id.state_id != self.state_id:
            self.municipality_id = False
            self.parish_id = False

    @api.onchange("municipality_id")
    def _onchange_municipality_id_territorial(self):
        if self.parish_id and self.parish_id.municipality_id != self.municipality_id:
            self.parish_id = False
        if self.municipality_id and self.municipality_id.state_id:
            self.state_id = self.municipality_id.state_id
            if self.municipality_id.state_id.country_id:
                self.country_id = self.municipality_id.state_id.country_id

    def _l10n_ve_check_identification_lock(self, vals):
        if not {"vat", "l10n_latam_identification_type_id", "person_type"} & set(vals):
            return
        locked = self._l10n_ve_commercials_with_activity()
        for partner in self:
            if partner.commercial_partner_id not in locked:
                continue
            if "vat" in vals and self._l10n_ve_normalize_rif(
                vals.get("vat")
            ) != self._l10n_ve_normalize_rif(partner.vat):
                raise ValidationError(
                    self.env._(
                        "The identification number of %s cannot be changed "
                        "because the partner already has invoices, sales, "
                        "purchases, payments or an open balance.",
                        partner.display_name,
                    )
                )
            new_type = vals.get("l10n_latam_identification_type_id") or False
            old_type = partner.l10n_latam_identification_type_id.id or False
            if "l10n_latam_identification_type_id" in vals and new_type != old_type:
                raise ValidationError(
                    self.env._(
                        "The identification type of %s cannot be changed "
                        "because the partner already has invoices, sales, "
                        "purchases, payments or an open balance.",
                        partner.display_name,
                    )
                )
            if "person_type" in vals and vals.get("person_type") != partner.person_type:
                raise ValidationError(
                    self.env._(
                        "The person type of %s cannot be changed because "
                        "the partner already has invoices, sales, purchases, "
                        "payments or an open balance.",
                        partner.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._l10n_ve_prepare_identification(dict(vals)) for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("l10n_ve_skip_id_lock"):
            self._l10n_ve_check_identification_lock(vals)
        if self.env.context.get("l10n_ve_syncing_id") or self.env.context.get(
            "l10n_ve_skip_id_check"
        ):
            return super().write(vals)
        keys = {"vat", "l10n_latam_identification_type_id", "country_id", "person_type"}
        if not keys.intersection(vals):
            return super().write(vals)
        sync_ctx = {"l10n_ve_syncing_id": True, "l10n_ve_skip_id_lock": True}
        locked_keys = ("vat", "l10n_latam_identification_type_id", "person_type")
        if len(self) == 1:
            original = dict(vals)
            vals = self._l10n_ve_prepare_identification(dict(vals), existing=self)
            if self.l10n_ve_identification_locked:
                for key in locked_keys:
                    if key not in original:
                        vals.pop(key, None)
            return super(ResPartner, self.with_context(**sync_ctx)).write(vals)
        for partner in self:
            original = dict(vals)
            prepared = partner._l10n_ve_prepare_identification(
                dict(vals), existing=partner
            )
            if partner.l10n_ve_identification_locked:
                for key in locked_keys:
                    if key not in original:
                        prepared.pop(key, None)
            partner.with_context(**sync_ctx).write(prepared)
        return True

    @api.onchange("l10n_latam_identification_type_id", "vat")
    def _onchange_l10n_ve_identification(self):
        if self.country_id and self.country_id.code != "VE":
            return
        inferred = self._l10n_ve_type_from_kind(
            self._l10n_ve_kind_from_number(self.vat)
        )
        rif = self._l10n_ve_id_type("l10n_ve_base.it_rif", "l10n_latam_base.it_vat")
        if inferred and (
            not self.l10n_latam_identification_type_id
            or (self.l10n_latam_identification_type_id == rif and inferred != rif)
        ):
            self.l10n_latam_identification_type_id = inferred
        suggested = self._l10n_ve_suggested_person_type()
        if suggested:
            self.person_type = suggested

    @api.onchange("country_id")
    def _onchange_country_id_ve(self):
        if (
            self.country_id
            and self.state_id
            and self.state_id.country_id != self.country_id
        ):
            self.state_id = False
        if (
            self.municipality_id
            and self.municipality_id.state_id.country_id != self.country_id
        ):
            self.municipality_id = False
            self.parish_id = False
        self._onchange_l10n_ve_identification()

    @api.model
    def _l10n_ve_setup_identification_types(self):
        """Load Screenshot_34 catalog and hide generic LATAM VAT/Passport/Foreign ID."""
        for xmlid in (
            "l10n_latam_base.it_vat",
            "l10n_latam_base.it_fid",
            "l10n_latam_base.it_pass",
        ):
            generic = self.env.ref(xmlid, raise_if_not_found=False)
            if generic and generic.active:
                generic.active = False
        self.with_context(
            l10n_ve_skip_id_check=True,
            l10n_ve_skip_id_lock=True,
        )._l10n_ve_assign_identification_type()

    @api.model
    def _l10n_ve_assign_identification_type(self):
        """Fill empty or generic LATAM VAT only. Do not rewrite RIF/cédula/passport."""
        rif = self._l10n_ve_id_type("l10n_ve_base.it_rif", "l10n_latam_base.it_vat")
        generic_vat = self.env.ref("l10n_latam_base.it_vat", raise_if_not_found=False)
        if not rif:
            return
        domain = [
            ("country_id.code", "=", "VE"),
            "|",
            ("l10n_latam_identification_type_id", "=", False),
            (
                "l10n_latam_identification_type_id",
                "=",
                generic_vat.id if generic_vat else 0,
            ),
        ]
        for partner in self.search(domain):
            inferred = self._l10n_ve_type_from_kind(
                partner._l10n_ve_kind_from_number(partner.vat)
            )
            itype = inferred or rif
            values = {}
            if partner.l10n_latam_identification_type_id != itype:
                values["l10n_latam_identification_type_id"] = itype.id
            preview = partner.new(
                {
                    "vat": partner.vat,
                    "l10n_latam_identification_type_id": itype.id,
                }
            )
            suggested = preview._l10n_ve_suggested_person_type()
            allowed = preview._l10n_ve_allowed_person_types()
            if suggested and (
                not partner.person_type
                or (allowed and partner.person_type not in allowed)
            ):
                values["person_type"] = suggested
            if values:
                partner.write(values)

    def _check_vat(self, validation="error"):
        """Block an invalid RIF on save. Cédula and passport are not VAT checksums."""
        skip = self.filtered(
            lambda partner: partner._l10n_ve_identification_kind()
            in ("cedula_v", "cedula_e", "passport")
        )
        return super(ResPartner, self - skip)._check_vat(validation=validation)

    def check_vat_ve(self, vat):
        return super().check_vat_ve(self._l10n_ve_normalize_rif(vat))

    @api.constrains(
        "vat", "country_id", "l10n_latam_identification_type_id", "person_type"
    )
    def _check_unique_ve_vat(self):
        if self.env.context.get("l10n_ve_skip_id_check"):
            return
        for partner in self:
            if partner._l10n_ve_needs_identification():
                if not partner.l10n_latam_identification_type_id:
                    raise ValidationError(
                        self.env._(
                            "A Venezuelan partner requires an identification type."
                        )
                    )
                if not partner.vat:
                    raise ValidationError(
                        self.env._(
                            "A Venezuelan partner requires an identification number."
                        )
                    )
                if not partner.person_type:
                    raise ValidationError(
                        self.env._("A Venezuelan partner requires a person type.")
                    )
            error = partner._l10n_ve_identification_format_error()
            if error:
                raise ValidationError(error)
            combo = partner._l10n_ve_person_type_error()
            if combo:
                raise ValidationError(combo)
            duplicate = partner._l10n_ve_find_duplicate_identification()
            if duplicate:
                raise ValidationError(
                    self.env._(
                        "The identification number %(number)s is already "
                        "assigned to %(partner)s.",
                        number=partner.vat,
                        partner=duplicate.display_name,
                    )
                )

    def action_update_from_seniat(self):
        self.ensure_one()
        if self.l10n_ve_identification_locked:
            raise ValidationError(
                self.env._(
                    "The identification of %s cannot be updated from SENIAT "
                    "because the partner already has invoices, sales, "
                    "purchases, payments or an open balance.",
                    self.display_name,
                )
            )
        if not self.vat:
            raise ValidationError(
                self.env._("Please provide a VAT / RIF number first.")
            )
        info = self.env["seniat.url"].get_seniat_partner_info(self.vat)
        if info:
            venezuela = self.env.ref("base.ve", raise_if_not_found=False)
            values = {
                "name": info.get("name") or self.name,
                "wh_iva_agent": info.get("wh_iva_agent", False),
                "wh_iva_rate": info.get("wh_iva_rate", 0.0),
                "vat_subjected": info.get("vat_subjected", False),
                "seniat_updated": True,
                "vat": info.get("vat") or self.vat,
            }
            rif = self._l10n_ve_id_type("l10n_ve_base.it_rif", "l10n_latam_base.it_vat")
            if rif:
                values["l10n_latam_identification_type_id"] = rif.id
            if venezuela and not self.country_id:
                values["country_id"] = venezuela.id
            letter = self._l10n_ve_normalize_rif(values.get("vat") or self.vat)
            if letter:
                values["person_type"] = RIF_LETTER_PERSON_TYPE.get(
                    letter[0], self.person_type
                )
            self.write(values)
        else:
            raise ValidationError(
                self.env._(
                    "Could not retrieve partner information from SENIAT for VAT: %s",
                    self.vat,
                )
            )
