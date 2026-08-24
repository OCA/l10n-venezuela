import logging
import re
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .seniat_field_mapper import partner_vals_from_seniat_parsed
from .seniat_rif_client import query_rif

_logger = logging.getLogger(__name__)

VE_CODE = "VE"
_XML_PJ_DOMICILIADA = "l10n_ve_withholding.type_person_three_l10n_ve_withholding"
_XML_PN_RESIDENTE = "l10n_ve_withholding.type_person_l10n_ve_withholding"


class ResPartner(models.Model):
    _inherit = "res.partner"

    taxpayer_type = fields.Selection(
        inverse="_inverse_l10n_ve_vat_seniat_taxpayer_type",
    )

    def _inverse_l10n_ve_vat_seniat_taxpayer_type(self):
        return

    @api.model
    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        for vals in vals_list:
            cid = vals.get("country_id")
            if not cid:
                continue
            country = self.env["res.country"].browse(cid)
            if country.code != VE_CODE:
                continue
            vat = vals.get("vat")
            if not vat:
                continue
            tid = self._l10n_ve_vat_seniat_default_type_person_id_for_vat(vat)
            if tid:
                vals["type_person_id"] = tid
        return vals_list

    def write(self, vals):
        res = super().write(vals)
        if "vat" not in vals or "type_person_id" in vals:
            return res
        for partner in self:
            if partner.type_person_id:
                continue
            if partner.country_id.code != VE_CODE or not partner.vat:
                continue
            tid = partner._l10n_ve_vat_seniat_default_type_person_id_for_vat(
                partner.vat
            )
            if tid:
                super(ResPartner, partner).write({"type_person_id": tid})
        return res

    @api.model
    def _l10n_ve_vat_seniat_default_type_person_id_for_vat(self, vat):
        v = (vat or "").strip().upper().replace("-", "").replace(" ", "")
        if v.startswith("VE"):
            v = v[2:]
        if not v:
            return False
        first = v[0].upper()
        xml_id = False
        if first == "J":
            xml_id = _XML_PJ_DOMICILIADA
        elif first == "V":
            xml_id = _XML_PN_RESIDENTE
        if not xml_id:
            return False
        try:
            return self.env.ref(xml_id).id
        except ValueError:
            return False

    def _l10n_ve_vat_seniat_rif_from_vat(self):
        self.ensure_one()
        vat = (self.vat or "").strip().upper()
        if not vat:
            raise UserError(_("Indique el NIF/RIF en el contacto antes de consultar."))
        vat = vat.replace("-", "").replace(" ", "")
        if vat.startswith("VE"):
            vat = vat[2:]
        if not re.match(r"^[JGP][0-9]{9}$|^[VE][0-9]{7,9}$", vat):
            raise UserError(
                _(
                    "El RIF no tiene un formato reconocible para la consulta SENIAT "
                    "(se espera letra J, G, P, V o E seguida de dígitos)."
                )
            )
        return vat

    def action_l10n_ve_vat_seniat_open_portal(self):
        self.ensure_one()
        if self.country_id and self.country_id.code != "VE":
            raise UserError(
                _("El enlace al SENIAT solo aplica a contactos de Venezuela.")
            )
        rif = self._l10n_ve_vat_seniat_rif_from_vat()
        url = (
            "http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp"
            f"?p_rif={quote(rif)}"
        )
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_l10n_ve_vat_seniat_query(self):
        self.ensure_one()
        if self.country_id and self.country_id.code != "VE":
            raise UserError(
                _("La consulta automática SENIAT solo aplica a contactos de Venezuela.")
            )
        rif = self._l10n_ve_vat_seniat_rif_from_vat()
        _logger.info(
            "l10n_ve_vat_seniat botón consulta partner_id=%s rif=%s",
            self.id,
            rif,
        )
        try:
            result = query_rif(rif)
        except RuntimeError as e:
            raise UserError(str(e)) from e
        except Exception as e:
            _logger.exception("SENIAT RIF lookup error partner=%s", self.id)
            raise UserError(
                _("No se pudo contactar el portal del SENIAT: %s") % (str(e),)
            ) from e

        if not result.get("ok"):
            reason = result.get("reason", "")
            if reason == "captcha_exhausted":
                _logger.warning(
                    "l10n_ve_vat_seniat captcha agotado partner_id=%s "
                    "rif=%s detalle=%r codes_tried=%s",
                    self.id,
                    rif,
                    result.get("detail"),
                    result.get("codes_tried"),
                )
                raise UserError(
                    _(
                        "No se pudo validar el captcha tras varios intentos. "
                        "Compruebe que Tesseract esté instalado y que el "
                        "servicio del SENIAT responda."
                    )
                )
            if reason == "unexpected_html":
                raise UserError(
                    _(
                        "La respuesta del SENIAT no se pudo interpretar "
                        "(formato inesperado)."
                    )
                )
            raise UserError(_("Consulta no completada: %s") % (reason,))

        if not result.get("contribuyente"):
            msg = _("No existe el contribuyente solicitado para el RIF indicado.")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("SENIAT"),
                    "message": msg,
                    "type": "warning",
                    "sticky": False,
                },
            }

        payload = {k: v for k, v in result.items() if k != "ok"}
        _logger.info(
            "SENIAT RIF lookup OK partner_id=%s commercial_partner_id=%s "
            "rif=%s data=%s",
            self.id,
            self.commercial_partner_id.id,
            rif,
            payload,
        )

        commercial = self.commercial_partner_id
        fiscal_vals = partner_vals_from_seniat_parsed(self.env, result)
        nombre_seniat = (result.get("nombre") or "").strip().strip('"').strip()
        if nombre_seniat:
            fiscal_vals["name"] = nombre_seniat
        if fiscal_vals:
            commercial.write(fiscal_vals)

        commercial.invalidate_recordset(
            ["name", "taxpayer_type", "withholding_type_id", "display_name"]
        )
        nombre_txt = nombre_seniat or commercial.name or commercial.display_name or ""

        tt_label = self._l10n_ve_vat_seniat_selection_label(commercial, "taxpayer_type")
        if not tt_label and result.get("seniat_tipo_contribuyente_label"):
            tt_label = result["seniat_tipo_contribuyente_label"].strip()
        if not tt_label:
            tt_label = _("No determinado")

        wh_label = ""
        if commercial.withholding_type_id:
            wh_label = commercial.withholding_type_id.display_name
        if not wh_label and result.get("seniat_retencion_pct_label"):
            wh_label = result["seniat_retencion_pct_label"].strip()
        if not wh_label:
            wh_label = _("No determinado")

        message = "\n".join(
            [
                _("Nombre: %s") % nombre_txt,
                _("Tipo de contribuyente: %s") % tt_label,
                _("Tipo de retención: %s") % wh_label,
            ]
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SENIAT"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }

    def _l10n_ve_vat_seniat_selection_label(self, partner, field_name):
        value = partner[field_name]
        if not value:
            return ""
        meta = partner.fields_get([field_name]).get(field_name) or {}
        pairs = meta.get("selection") or []
        return dict(pairs).get(value, "") or ""
