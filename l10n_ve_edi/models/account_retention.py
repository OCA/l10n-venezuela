import base64
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .edi_mixin import STATE_FAILED, STATE_QUEUED, STATE_SENT


class AccountRetention(models.Model):
    _name = "account.retention"
    _inherit = ["account.retention", "l10n_ve.edi.mixin"]

    @api.depends(
        "type_retention",
        "type",
        "company_id.iva_supplier_retention_journal_id",
        "company_id.islr_supplier_retention_journal_id",
        "company_id.municipal_supplier_retention_journal_id",
        "company_id.iva_customer_retention_journal_id",
        "company_id.islr_customer_retention_journal_id",
        "company_id.municipal_customer_retention_journal_id",
    )
    def _compute_l10n_ve_edi_journal_id(self):
        for retention in self:
            retention.l10n_ve_edi_journal_id = retention._l10n_ve_edi_get_edi_journal()

    def _l10n_ve_edi_get_edi_journal(self):
        self.ensure_one()
        company = self.company_id
        journals = {
            ("iva", "in_invoice"): company.iva_supplier_retention_journal_id,
            ("iva", "out_invoice"): company.iva_customer_retention_journal_id,
            ("islr", "in_invoice"): company.islr_supplier_retention_journal_id,
            ("islr", "out_invoice"): company.islr_customer_retention_journal_id,
            (
                "municipal",
                "in_invoice",
            ): company.municipal_supplier_retention_journal_id,
            (
                "municipal",
                "out_invoice",
            ): company.municipal_customer_retention_journal_id,
        }
        return (
            journals.get((self.type_retention, self.type))
            or self.env["account.journal"]
        )

    def _l10n_ve_edi_get_digital_emission_journal(self):
        self.ensure_one()
        return self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
                ("l10n_ve_emission_medium", "=", "digital"),
                ("l10n_ve_edi_provider", "!=", False),
                ("l10n_ve_edi_provider", "!=", "none"),
            ],
            limit=1,
        )

    def _l10n_ve_edi_retention_uses_digital(self):
        self.ensure_one()
        if self.type != "in_invoice":
            return False
        if self.type_retention not in ("iva", "islr"):
            return False
        journal = self._l10n_ve_edi_get_edi_journal()
        return bool(
            journal.l10n_ve_edi_provider and journal.l10n_ve_edi_provider != "none"
        )

    def _l10n_ve_edi_get_retention_edi_provider(self):
        self.ensure_one()
        journal = self._l10n_ve_edi_get_edi_journal()
        if (
            journal
            and journal.l10n_ve_edi_provider
            and journal.l10n_ve_edi_provider != "none"
        ):
            return journal.l10n_ve_edi_provider
        digital_journal = self._l10n_ve_edi_get_digital_emission_journal()
        return digital_journal.l10n_ve_edi_provider if digital_journal else False

    def _l10n_ve_edi_get_tfhka_reference_journal(self):
        self.ensure_one()
        retention_journal = self._l10n_ve_edi_get_edi_journal()
        if retention_journal and retention_journal.l10n_ve_edi_provider == "tfhka":
            return retention_journal
        if retention_journal and getattr(
            retention_journal, "l10n_ve_edi_tfhka_serie", False
        ):
            return retention_journal
        return self._l10n_ve_edi_get_digital_emission_journal()

    l10n_ve_edi_show_tab = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_tab",
        string="Show EDI Tab",
    )

    @api.depends(
        "type",
        "type_retention",
        "company_id.iva_supplier_retention_journal_id.l10n_ve_edi_provider",
        "company_id.islr_supplier_retention_journal_id.l10n_ve_edi_provider",
    )
    def _compute_l10n_ve_edi_show_tab(self):
        for retention in self:
            retention.l10n_ve_edi_show_tab = (
                retention._l10n_ve_edi_retention_uses_digital()
            )

    def _l10n_ve_edi_is_retention_target(self):
        self.ensure_one()
        if self.state != "emitted":
            return False
        return self._l10n_ve_edi_retention_uses_digital()

    def _l10n_ve_edi_retention_blocking_print_before_digital_sent(self):
        self.ensure_one()
        if not self._l10n_ve_edi_retention_uses_digital():
            return False
        return self.state == "emitted" and self.l10n_ve_edi_send_state != "sent"

    def _l10n_ve_edi_get_company_partner(self):
        self.ensure_one()
        return self.company_id.partner_id.commercial_partner_id

    def _l10n_ve_edi_get_subject_partner(self):
        self.ensure_one()
        return self.partner_id.commercial_partner_id

    def _l10n_ve_edi_get_company_vat(self):
        self.ensure_one()
        company_partner = self._l10n_ve_edi_get_company_partner()
        return company_partner.vat or self.company_id.vat

    def _l10n_ve_edi_get_subject_identification(self):
        self.ensure_one()
        partner = self._l10n_ve_edi_get_subject_partner()
        return self._l10n_ve_edi_parse_ve_vat(partner.vat)

    def _l10n_ve_edi_get_seller_identification(self):
        self.ensure_one()
        return self._l10n_ve_edi_parse_ve_vat(self._l10n_ve_edi_get_company_vat())

    def _l10n_ve_edi_validate_parties_identification(self):
        self.ensure_one()
        subject = self._l10n_ve_edi_get_subject_partner()
        subject_prefix, subject_number = self._l10n_ve_edi_get_subject_identification()
        if not subject_prefix or not subject_number:
            raise UserError(
                _(
                    "El RIF del sujeto retenido no es valido o falta para el "
                    "payload EDI. Valor actual: %(vat)s"
                )
                % {"vat": subject.vat or "VACIO"}
            )
        company_vat = self._l10n_ve_edi_get_company_vat()
        seller_prefix, seller_number = self._l10n_ve_edi_get_seller_identification()
        if not seller_prefix or not seller_number:
            raise UserError(
                _(
                    "El RIF del agente de retencion (su empresa) no es "
                    "valido o falta para el payload EDI. Valor leido: "
                    "%(vat)s"
                )
                % {"vat": company_vat or "VACIO"}
            )

    def _l10n_ve_edi_create_payload_attachment(self, payload):
        self.ensure_one()
        filename = (self.number or self.name or f"retention_{self.id}").replace(
            "/", "_"
        )
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        datas = base64.b64encode(content.encode("utf-8"))
        return (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": f"l10n_ve_edi_payload_{filename}.json",
                    "type": "binary",
                    "datas": datas,
                    "mimetype": "application/json",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )

    def _build_payload_to_send(self):
        self.ensure_one()
        if not self._l10n_ve_edi_retention_uses_digital():
            raise UserError(
                _(
                    "La empresa no tiene facturacion digital configurada. Configure un "
                    "diario de ventas con medio digital y proveedor EDI."
                )
            )
        provider = self._l10n_ve_edi_get_retention_edi_provider()
        if not provider:
            raise UserError(
                _(
                    "No hay proveedor EDI disponible para retenciones. "
                    "Configure facturacion digital en un diario de ventas "
                    "o en el diario de retencion."
                )
            )
        if not self.number:
            raise UserError(
                _(
                    "El comprobante debe tener numero antes de enviarse a "
                    "facturacion digital."
                )
            )
        if not self.retention_line_ids:
            raise UserError(_("El comprobante no tiene lineas de retencion."))
        self._l10n_ve_edi_validate_parties_identification()
        self._l10n_ve_edi_validate_retention_invoice_fiscal_data()
        return self._l10n_ve_edi_build_payload_for_provider(provider)

    def _l10n_ve_edi_get_vendor_invoice_fiscal_number(self, move):
        for candidate in (
            getattr(move, "l10n_ve_invoice_number", None),
            move.ref,
        ):
            if candidate and re.sub(r"\D", "", str(candidate)):
                return str(candidate).strip()
        return False

    def _l10n_ve_edi_validate_retention_invoice_fiscal_data(self):
        self.ensure_one()
        if self.type != "in_invoice":
            return
        for line in self.retention_line_ids:
            move = line.move_id
            if not move or move.move_type not in ("in_invoice", "in_refund"):
                continue
            if not (move.l10n_ve_control_number or "").strip():
                raise UserError(
                    _(
                        "La factura de proveedor «%(invoice)s» no tiene "
                        "numero de control fiscal. Abra la factura, "
                        "indique el N° de control impreso por el proveedor "
                        "e intente enviar la retencion de nuevo."
                    )
                    % {"invoice": move.display_name}
                )
            if not self._l10n_ve_edi_get_vendor_invoice_fiscal_number(move):
                raise UserError(
                    _(
                        "La factura de proveedor «%(invoice)s» no tiene "
                        "numero de factura fiscal. Indique el numero "
                        "impreso en el documento del proveedor (campo "
                        "«N° Factura proveedor» o referencia) e intente "
                        "de nuevo."
                    )
                    % {"invoice": move.display_name}
                )

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        raise UserError(
            _(
                "No hay modulo instalado para el proveedor EDI %(code)s. "
                "Instale el conector correspondiente (por ejemplo "
                "l10n_ve_edi_tfhka para TFHKA)."
            )
            % {"code": provider}
        )

    def _l10n_ve_edi_send_uses_queue_job(self):
        return False

    def _l10n_ve_edi_prepare_send(self, reuse_payload=False):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id if reuse_payload else False
        if not attachment:
            payload = self._build_payload_to_send()
            attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write(
            {
                "l10n_ve_edi_payload_attachment_id": attachment.id,
                "l10n_ve_edi_send_state": STATE_QUEUED,
                "l10n_ve_edi_last_error": False,
                "l10n_ve_edi_response_json": False,
            }
        )
        return attachment

    def _l10n_ve_edi_schedule_send(self):
        self.ensure_one()
        self._run_job()

    def _l10n_ve_edi_enqueue_send(self, reuse_payload=False):
        self.ensure_one()
        self._l10n_ve_edi_prepare_send(reuse_payload=reuse_payload)
        self._l10n_ve_edi_schedule_send()

    def action_l10n_ve_edi_send(self):
        for retention in self:
            if retention.state != "emitted":
                raise UserError(
                    _("Solo se pueden enviar comprobantes de retencion emitidos.")
                )
            if not retention._l10n_ve_edi_is_retention_target():
                raise UserError(
                    _(
                        "El diario de retencion no tiene proveedor de "
                        "facturacion digital configurado o el documento "
                        "no aplica."
                    )
                )
            if retention.l10n_ve_edi_send_state == STATE_QUEUED:
                raise UserError(
                    _("Ya hay una solicitud de envio en cola para este documento.")
                )
            if retention.l10n_ve_edi_send_state == STATE_SENT:
                raise UserError(_("El documento ya fue enviado a facturacion digital."))
            retention._l10n_ve_edi_enqueue_send(reuse_payload=False)
        return True

    def action_l10n_ve_edi_retry_send(self):
        return self.action_l10n_ve_edi_send()

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        provider = self._l10n_ve_edi_get_retention_edi_provider()
        return {
            "success": False,
            "error": _(
                "Proveedor EDI no soportado o modulo no instalado: %(provider)s."
            )
            % {"provider": provider or "none"},
        }

    def _l10n_ve_edi_on_dispatch_success(self, response):
        self.ensure_one()

    def _run_job(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id
        error_message = False
        if not attachment or not attachment.datas:
            error_message = _("Falta el adjunto con el payload EDI.")
        else:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
            dispatch = self._l10n_ve_edi_dispatch_payload(payload)
            if dispatch.get("success"):
                response = dispatch.get("response")
                try:
                    self._l10n_ve_edi_on_dispatch_success(response)
                except (UserError, ValidationError) as exc:
                    error_message = str(exc)
                    response_json = False
                    if response is not None:
                        response_json = json.dumps(
                            response, ensure_ascii=False, indent=2
                        )
                    self.write(
                        {
                            "l10n_ve_edi_send_state": STATE_SENT,
                            "l10n_ve_edi_sent_at": fields.Datetime.now(),
                            "l10n_ve_edi_last_error": error_message,
                            "l10n_ve_edi_response_json": response_json,
                        }
                    )
                    self.message_post(
                        body=_(
                            "El envio a facturacion digital fue exitoso, pero hubo una "
                            "incidencia de validacion en Odoo: %(error)s"
                        )
                        % {"error": error_message}
                    )
                    return True
                response_json = False
                if response is not None:
                    response_json = json.dumps(response, ensure_ascii=False, indent=2)
                self.write(
                    {
                        "l10n_ve_edi_send_state": STATE_SENT,
                        "l10n_ve_edi_sent_at": fields.Datetime.now(),
                        "l10n_ve_edi_last_error": False,
                        "l10n_ve_edi_response_json": response_json,
                    }
                )
                self.message_post(
                    body=_("Comprobante enviado exitosamente a facturacion digital.")
                )
                return True
            error_message = dispatch.get("error") or _(
                "El conector EDI no completo el envio."
            )
        if error_message:
            self.write(
                {
                    "l10n_ve_edi_send_state": STATE_FAILED,
                    "l10n_ve_edi_last_error": error_message,
                }
            )
            self.message_post(
                body=_("Fallo el envio a facturacion digital. Motivo: %(error)s")
                % {"error": error_message}
            )
        return False

    @api.model
    def _job_l10n_ve_edi_send_retention(self, retention_id):
        retention = self.sudo().browse(retention_id).exists()
        if not retention:
            return False
        return retention._run_job()
