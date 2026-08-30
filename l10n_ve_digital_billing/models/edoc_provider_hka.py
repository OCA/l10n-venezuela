# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Adapter for The Factory HKA Venezuela.

Written against the provider's public documentation
(https://wiki.thefactoryhka.com.ve/doku.php?id=manual_de_integracion_venezuela):

- POST /api/Autenticacion  {usuario, clave} -> {token, expiracion}; the token
  lasts 12 hours and travels as "Authorization: Bearer <token>" everywhere
  else.
- POST /api/Emision        {documentoElectronico: {...}} -> a result with the
  control number returned SYNCHRONOUSLY (that is why _edoc_fetch is not
  implemented for HKA).
- POST /api/Anular         {serie, tipoDocumento, numeroDocumento,
  motivoAnulacion, fechaAnulacion, horaAnulacion}.

The wiki only publishes the demo environment's URL; production's is handed
over by the provider with the contract and configured on the company. Every
amount travels as a STRING (that is how the wiki's example JSON types them).
"""
import json
import re
from datetime import timedelta

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

DEMO_BASE_URL = "https://demoemisionv2.thefactoryhka.com.ve"
TIMEOUT = 60
# Renew the token a while before it actually expires, so an emission is never
# sent with a token on the verge of expiring.
TOKEN_MARGIN = timedelta(minutes=10)

# Document type per the /api/Emision response shown in the wiki (the sample
# invoice responds with tipoDocumento "01"). Confirm "02"/"03" against the
# field catalogue HKA hands over with the credentials.
DOC_TYPES = {"invoice": "01", "debit_note": "02", "credit_note": "03"}

# codigoImpuesto by rate: G general 16%, R reduced 8%, A additional 31%,
# E exempt. Same caveat: confirm against HKA's catalogue.
TAX_CODES = {16.0: "G", 8.0: "R", 31.0: "A"}


class L10nVeEdocProviderHka(models.AbstractModel):
    _name = "l10n.ve.edoc.provider.hka"
    _inherit = "l10n.ve.edoc.provider"
    _description = "The Factory HKA (Venezuela)"

    # ------------------------------------------------------------------
    # l10n.ve.edoc.provider contract
    # ------------------------------------------------------------------
    def _edoc_send(self, move, vals):
        company = move.company_id
        payload = self._hka_payload(move, vals)
        data = self._hka_post(company, "/api/Emision", payload)
        result = data.get("resultado") or {}
        return {
            "external_id": result.get("numeroDocumento") or vals["number"],
            "control_number": result.get("numeroControl") or None,
            "control_date": self._hka_parse_date(
                result.get("fechaAsignacionNumeroControl")
                or result.get("fechaAsignacion")),
        }

    def _edoc_fetch(self, move):
        raise UserError(_(
            "The Factory HKA assigns the control number in the emission "
            "call itself and does not expose a query method. If a call was "
            "left in an unknown state, check the document in the "
            "provider's portal before retrying, to avoid issuing it twice."))

    def _edoc_cancel(self, move, reason):
        company = move.company_id
        now = fields.Datetime.context_timestamp(move, fields.Datetime.now())
        payload = {
            "serie": company.l10n_ve_edoc_serie or "",
            "tipoDocumento": DOC_TYPES[move._l10n_ve_edoc_doc_type()],
            "numeroDocumento": move.name,
            "motivoAnulacion": reason,
            "fechaAnulacion": now.strftime("%d/%m/%Y"),
            "horaAnulacion": now.strftime("%H:%M:%S"),
        }
        self._hka_post(company, "/api/Anular", payload)
        return True

    def _edoc_test_connection(self):
        company = self.env.company
        data = self._hka_auth(company)
        return _(
            "Connected to The Factory HKA (%(environment)s). Token valid "
            "until %(expiry)s (UTC).",
            environment=_("demo") if company.l10n_ve_edoc_test
            else _("production"),
            expiry=self._hka_parse_expiry(data.get("expiracion")),
        )

    # ------------------------------------------------------------------
    # HTTP and token handling
    # ------------------------------------------------------------------
    def _hka_base_url(self, company):
        """Demo while "Test environment" is checked: this makes it
        impossible to point a test at production by a mistyped URL."""
        if company.l10n_ve_edoc_test:
            return DEMO_BASE_URL
        url = (company.l10n_ve_edoc_url or "").strip().rstrip("/")
        if not url:
            raise UserError(_(
                "Configure The Factory HKA's production URL in %s's "
                "Accounting Settings (the provider hands it over with the "
                "contract).", company.display_name))
        return url

    def _hka_auth(self, company):
        if not company.l10n_ve_edoc_user or not company.l10n_ve_edoc_password:
            raise UserError(_(
                "Configure The Factory HKA's username and password in %s's "
                "Accounting Settings.", company.display_name))
        response = requests.post(
            self._hka_base_url(company) + "/api/Autenticacion",
            json={"usuario": company.l10n_ve_edoc_user,
                  "clave": company.l10n_ve_edoc_password},
            timeout=TIMEOUT)
        data = self._hka_parse(response)
        if not data.get("token"):
            raise UserError(_(
                "The Factory HKA returned no token: %s",
                data.get("mensaje") or _("no message")))
        return data

    def _hka_token(self, company, force=False):
        """Token cached per company in ir.config_parameter: it lasts 12
        hours, and authenticating on every call would be one extra request
        per invoice."""
        icp = self.env["ir.config_parameter"].sudo()
        key = "l10n_ve_digital_billing.hka_token_%d" % company.id
        if not force:
            cached = icp.get_param(key)
            if cached:
                try:
                    value = json.loads(cached)
                    expiry = fields.Datetime.from_string(value["expiry"])
                    if fields.Datetime.now() < expiry - TOKEN_MARGIN:
                        return value["token"]
                except (ValueError, KeyError, TypeError):
                    pass
        data = self._hka_auth(company)
        icp.set_param(key, json.dumps({
            "token": data["token"],
            "expiry": fields.Datetime.to_string(
                self._hka_parse_expiry(data.get("expiracion"))),
        }))
        return data["token"]

    def _hka_post(self, company, path, payload):
        for attempt in (1, 2):
            token = self._hka_token(company, force=attempt == 2)
            response = requests.post(
                self._hka_base_url(company) + path, json=payload,
                headers={"Authorization": "Bearer %s" % token},
                timeout=TIMEOUT)
            # 401 with a cached token = revoked before its expiry (key
            # rotation, provider restart): renew ONCE.
            if response.status_code == 401 and attempt == 1:
                continue
            return self._hka_parse(response)

    def _hka_parse(self, response):
        try:
            data = response.json()
        except ValueError:
            raise UserError(_(
                "The Factory HKA responded HTTP %(status)s without JSON: "
                "%(body)s",
                status=response.status_code, body=response.text[:500]))
        # The wiki types "codigo" as a number in Autenticacion and as a
        # string in Emision: always compare it as a string.
        code = str(data.get("codigo", response.status_code))
        if code != "200":
            details = data.get("validaciones") or []
            raise UserError("The Factory HKA [%s]: %s%s" % (
                code,
                data.get("mensaje") or _("Provider error"),
                ("\n- " + "\n- ".join(details)) if details else ""))
        return data

    # ------------------------------------------------------------------
    # Translation: neutral dict -> HKA dialect
    # ------------------------------------------------------------------
    def _hka_payload(self, move, vals):
        company = move.company_id
        doc_date = self._hka_date(vals["date"])
        identification = {
            "tipoDocumento": DOC_TYPES[vals["doc_type"]],
            "numeroDocumento": vals["number"],
            "fechaEmision": doc_date,
            "horaEmision": vals.get("time") or "",
            "moneda": vals["currency"],
            "serie": company.l10n_ve_edoc_serie or "",
            "sucursal": company.l10n_ve_edoc_sucursal or "",
            # Best-effort human-readable value pending HKA's own catalogue of
            # accepted tipoDeVenta values.
            "tipoDeVenta": ("Contado" if vals.get("sale_type") == "cash"
                            else "Crédito"),
            # Idempotency: identifies this emission attempt to HKA.
            "transaccionId": "ODOO-%d-%d" % (company.id, move.id),
        }
        affected = vals.get("affected_document")
        if affected:
            identification.update({
                "serieFacturaAfectada": company.l10n_ve_edoc_serie or "",
                "numeroFacturaAfectada": affected["number"],
                "fechaFacturaAfectada": self._hka_date(affected["date"]),
                "montoFacturaAfectada": self._hka_amount(affected["amount"]),
                "comentarioFacturaAfectada": affected.get("reason") or "",
            })
        buyer = vals["buyer"]
        buyer_payload = {
            "tipoIdentificacion": buyer.get("id_type") or "",
            "numeroIdentificacion": buyer.get("id_number") or buyer["vat"],
            "razonSocial": buyer["name"],
            "direccion": buyer["address"],
            "pais": "VE",
            "notificar": "Si" if buyer.get("email") else "No",
            "telefono": [buyer["phone"]] if buyer.get("phone") else [],
            "correo": [buyer["email"]] if buyer.get("email") else [],
        }
        details = [{
            "numeroLinea": str(index),
            "codigoPLU": line.get("code") or "",
            "descripcion": line["description"],
            "cantidad": self._hka_amount(line["quantity"]),
            "unidadMedida": line.get("uom") or "",
            "precioUnitario": self._hka_amount(line["unit_price"]),
            "descuentoMonto": self._hka_amount(
                line.get("discount_amount", 0.0)),
            "precioItem": self._hka_amount(line["base"]),
            "codigoImpuesto": self._hka_tax_code(line),
            "tasaIVA": self._hka_amount(line["rate"]),
            "valorIVA": self._hka_amount(line.get("tax", 0.0)),
            "valorTotalItem": self._hka_amount(line.get("total", line["base"])),
        } for index, line in enumerate(vals["lines"], start=1)]
        totals = {
            "nroItems": str(vals.get("line_count", len(vals["lines"]))),
            "montoGravadoTotal": self._hka_amount(vals["taxed_total"]),
            "montoExentoTotal": self._hka_amount(vals["exempt_total"]),
            "subtotal": self._hka_amount(vals.get(
                "untaxed_total", vals["taxed_total"] + vals["exempt_total"])),
            "totalIVA": self._hka_amount(vals["tax_total"]),
            "montoTotalConIVA": self._hka_amount(vals["total"]),
            "totalAPagar": self._hka_amount(vals["total"]),
            "impuestosSubtotal": self._hka_tax_subtotals(vals),
            "formasPago": self._hka_payments(vals, doc_date),
        }
        return {"documentoElectronico": self._hka_clean({
            "encabezado": {
                "identificacionDocumento": identification,
                "comprador": buyer_payload,
                "totales": totals,
            },
            "detallesItems": details,
        })}

    def _hka_tax_code(self, line):
        if line["exempt"]:
            return "E"
        return TAX_CODES.get(line["rate"], "G")

    def _hka_tax_subtotals(self, vals):
        """impuestosSubtotal: one row per code/rate, summing the base and
        VAT of the matching lines. The neutral dict carries the rate per
        line just so this breakdown can be rebuilt without touching
        anything fiscal."""
        groups = {}
        for line in vals["lines"]:
            code = self._hka_tax_code(line)
            group = groups.setdefault(code, {
                "rate": 0.0 if line["exempt"] else line["rate"],
                "base": 0.0, "tax": 0.0})
            group["base"] += line["base"]
            group["tax"] += line.get("tax", 0.0)
        return [{
            "codigoTotalImp": code,
            "alicuotaImp": self._hka_amount(group["rate"]),
            "baseImponibleImp": self._hka_amount(group["base"]),
            "valorTotalImp": self._hka_amount(group["tax"]),
        } for code, group in groups.items()]

    def _hka_payments(self, vals, doc_date):
        payments = [{
            "descripcion": payment["description"],
            "fecha": self._hka_date(payment["date"]),
            "monto": self._hka_amount(payment["amount"]),
            "moneda": payment.get("currency") or vals["currency"],
        } for payment in vals.get("payments") or []]
        if not payments:
            # No reconciled payment at emission time (the usual case): a
            # single payment for the total, labelled with the sale type.
            payments = [{
                "descripcion": ("Contado" if vals.get("sale_type") == "cash"
                                else "Crédito"),
                "fecha": doc_date,
                "monto": self._hka_amount(vals["total"]),
                "moneda": vals["currency"],
            }]
        return payments

    # ------------------------------------------------------------------
    # Formats: string amounts, dd/mm/yyyy dates (as in the wiki's examples)
    # ------------------------------------------------------------------
    @staticmethod
    def _hka_amount(value, digits=2):
        return "%.*f" % (digits, value or 0.0)

    @staticmethod
    def _hka_date(value):
        return value.strftime("%d/%m/%Y") if value else ""

    @staticmethod
    def _hka_parse_date(value):
        match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (value or "").strip())
        if not match:
            return None
        day, month, year = match.groups()
        return fields.Date.to_date("%s-%s-%s" % (year, month, day))

    @staticmethod
    def _hka_parse_expiry(value):
        """The expiry travels as "2022-09-24T02:53:54.6190734Z": ISO in UTC
        with SEVEN decimals (.NET style), which fromisoformat chokes on; it
        is trimmed to seconds. Unreadable -> assume the documented 12-hour
        validity; the margin below does no harm either way."""
        match = re.match(
            r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", value or "")
        if match:
            return fields.Datetime.from_string("%s %s" % match.groups())
        return fields.Datetime.now() + timedelta(hours=12)

    @classmethod
    def _hka_clean(cls, value):
        """Recursively drop empty fields: better to omit the key than to
        send "" to someone else's validator (and it keeps the JSON in the
        log readable)."""
        if isinstance(value, dict):
            cleaned = {k: cls._hka_clean(v) for k, v in value.items()}
            return {k: v for k, v in cleaned.items()
                    if v not in ("", None, [], {})}
        if isinstance(value, list):
            return [cls._hka_clean(v) for v in value]
        return value
