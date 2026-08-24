import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TFHKA_API_URL_TEST = "https://demoemisionv2.thefactoryhka.com.ve"
DEFAULT_BASE_URL = TFHKA_API_URL_TEST
DEFAULT_TIMEOUT = 30
ICP_BASE_URL = "l10n_ve_edi_tfhka.base_url"
ICP_API_ENVIRONMENT = "l10n_ve_edi_tfhka.api_environment"
ICP_PRODUCTION_URL = "l10n_ve_edi_tfhka.production_url"
ICP_TIMEOUT = "l10n_ve_edi_tfhka.timeout"

HEADER_CONTENT_TYPE = "Content-Type"
HEADER_ACCEPT = "Accept"
HEADER_AUTHORIZATION = "Authorization"
HEADER_CONTENT_TYPE_JSON = "application/json"
HEADER_BEARER = "Bearer"

KEY_MENSAJE = "mensaje"
KEY_MESSAGE = "message"
KEY_ERROR = "error"
KEY_VALIDACIONES = "validaciones"
KEY_TOKEN = "token"
KEY_RAW = "raw"
KEY_CODIGO = "codigo"

PATH_ANULAR = "/api/Anular"
PATH_APLICAR_RETENCION = "/api/AplicarRetencion"
PATH_ASIGNAR_NUMERACIONES = "/api/AsignarNumeraciones"
PATH_AUTENTICACION = "/api/Autenticacion"
PATH_CONSULTA_NUMERACIONES = "/api/ConsultaNumeraciones"
PATH_CORREO_ENVIAR = "/api/Correo/Enviar"
PATH_CORREO_RASTREO = "/api/Correo/Rastreo"
PATH_CORREO_ENVIA_ORDEN = "/api/Correo/EnviaOrden"
PATH_CORREO_RASTREO_ORDEN = "/api/Correo/RastreoOrden"
PATH_DESCARGA_ARCHIVO = "/api/DescargaArchivo"
PATH_EMISION = "/api/Emision"
PATH_EMISION_ARC = "/api/EmisionARC"
PATH_ESTADO_DOCUMENTO = "/api/EstadoDocumento"
PATH_ESTADO_LOTE = "/api/EstadoLote"
PATH_LISTADO_DOCUMENTOS = "/api/ListadoDocumentos"
PATH_LISTADO_ASIGNACIONES = "/api/ListadoAsignaciones"
PATH_ULTIMO_DOCUMENTO = "/api/UltimoDocumento"

METHOD_POST = "POST"
METHOD_GET = "GET"
METHOD_DELETE = "DELETE"

HTTP_ERROR_MESSAGES = {
    400: "Error en la estructura del request.",
    401: "No autorizado. Verifique token y credenciales.",
    500: "Error interno del servidor TFHKA.",
    502: "Bad Gateway: respuesta invalida del upstream.",
    503: "Servicio no disponible temporalmente en TFHKA.",
    504: "Timeout de gateway en TFHKA.",
}

API_ERROR_MESSAGES = {
    100: "Error en el procesamiento de documentos (insercion en base de datos).",
    200: "Documento procesado exitosamente.",
    201: "Documento duplicado.",
    202: (
        "Verifique la informacion en puntos de facturacion para "
        "asignacion automatica."
    ),
    203: "Documento no procesado por validacion (campos obligatorios o formato).",
    204: "Error al generar numero de control.",
    205: "No cumple las validaciones minimas (Art. 28).",
    210: "Informacion minima registrada correctamente.",
    211: "La informacion minima ya habia sido registrada previamente (duplicado).",
    400: "Error en la estructura del request.",
    401: "No autorizado (token o credenciales).",
    500: "Error interno en el procesamiento.",
}

API_SUCCESS_CODES = {200, 210, 211}


class L10nVeEdiTfhkaApiService(models.AbstractModel):
    _name = "l10n_ve_edi_tfhka.api.service"
    _description = "Servicio API TFHKA Venezuela"

    @api.model
    def _base_url(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(ICP_BASE_URL, default=DEFAULT_BASE_URL)
        )
        return value.rstrip("/")

    @api.model
    def _timeout(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(ICP_TIMEOUT, default=str(DEFAULT_TIMEOUT))
        )
        try:
            return int(value)
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT

    @api.model
    def _build_headers(self, token=None):
        headers = {
            HEADER_CONTENT_TYPE: HEADER_CONTENT_TYPE_JSON,
            HEADER_ACCEPT: HEADER_CONTENT_TYPE_JSON,
        }
        if token:
            headers[HEADER_AUTHORIZATION] = f"{HEADER_BEARER} {token}"
        return headers

    @api.model
    def _format_validacion_entry(self, item):
        if isinstance(item, dict):
            try:
                return json.dumps(item, ensure_ascii=False)
            except TypeError:
                return str(item)
        return str(item)

    @api.model
    def _join_validaciones(self, vals):
        if not isinstance(vals, list) or not vals:
            return ""
        return "; ".join(self._format_validacion_entry(v) for v in vals)

    @api.model
    def _append_validaciones_to_message(self, base, data):
        if not isinstance(data, dict):
            return base or ""
        vals = data.get(KEY_VALIDACIONES)
        val_text = self._join_validaciones(vals)
        if not val_text:
            return base or ""
        base = base or ""
        if base.strip() == val_text.strip():
            return base
        if val_text in base.replace("\n", " "):
            return base
        if base:
            return f"{base}\nValidaciones: {val_text}"
        return f"Validaciones: {val_text}"

    @api.model
    def _extract_error_message(self, data):
        if not isinstance(data, dict):
            return str(data)
        base = None
        if data.get(KEY_MENSAJE):
            base = data[KEY_MENSAJE]
        elif data.get(KEY_MESSAGE):
            base = data[KEY_MESSAGE]
        elif data.get(KEY_ERROR):
            error = data[KEY_ERROR]
            if isinstance(error, str):
                base = error
            elif isinstance(error, dict):
                if error.get(KEY_MESSAGE):
                    base = error[KEY_MESSAGE]
                else:
                    try:
                        base = json.dumps(error, ensure_ascii=False)
                    except TypeError:
                        base = str(error)
        elif data.get(KEY_VALIDACIONES) and isinstance(
            data.get(KEY_VALIDACIONES), list
        ):
            base = self._join_validaciones(data[KEY_VALIDACIONES])
        else:
            try:
                base = json.dumps(data, ensure_ascii=False)
            except TypeError:
                base = str(data)
        base = base or ""
        return self._append_validaciones_to_message(base, data)

    @api.model
    def _tfhka_validation_operational_hint(self, data):
        if not isinstance(data, dict):
            return ""
        blob = (self._extract_error_message(data) or "").lower()
        vals = data.get(KEY_VALIDACIONES)
        if isinstance(vals, list) and vals:
            blob += " " + self._join_validaciones(vals).lower()
        if "rango de numeración" in blob or "rango de numeracion" in blob:
            return (
                "\n\n"
                "Acción sugerida: En The Factory HKA debe existir un rango de "
                "numeración activo para su contribuyente, tipo de documento "
                "(factura/ND/NC), establecimiento y serie que coincidan con lo "
                "que envía Odoo (campos serie y sucursal en el payload; "
                "sucursal se configura en el diario TFHKA). Asigne rangos en "
                "el portal TFHKA o con su distribuidor HKA; si la serie en "
                "Odoo (diario o prefijo del nombre) no coincide con la "
                "registrada en HKA, también puede fallar. Ambiente demo: use "
                "credenciales y datos de prueba que tengan numeración de "
                "demostración."
            )
        if "numeración" in blob or "numeracion" in blob:
            return (
                "\n\n"
                "Revise en el portal The Factory HKA que su RIF tenga "
                "numeración habilitada para este tipo de comprobante."
            )
        return ""

    @api.model
    def _normalize_api_code(self, data):
        if not isinstance(data, dict):
            return None
        raw_code = data.get(KEY_CODIGO)
        if raw_code is None:
            return None
        try:
            return int(raw_code)
        except (TypeError, ValueError):
            return None

    @api.model
    def _raise_for_http_status(self, response, data, url=None):
        if response.ok:
            return
        base_message = (
            HTTP_ERROR_MESSAGES.get(response.status_code) or "Error HTTP en TFHKA."
        )
        api_message = self._extract_error_message(data) or response.text
        req_url = url or getattr(response, "url", "") or ""
        try:
            body = (
                json.dumps(data, ensure_ascii=False)
                if isinstance(data, dict)
                else str(data)
            )
        except TypeError:
            body = str(data)
        if len(body) > 16000:
            body = body[:16000] + "…(truncado)"
        _logger.error(
            "TFHKA HTTP error url=%s status=%s texto=%s json=%s",
            req_url,
            response.status_code,
            (response.text or "")[:2000],
            body,
        )
        raise UserError(
            f"TFHKA HTTP {response.status_code}. {base_message} Detalle: {api_message}"
        )

    @api.model
    def _raise_for_api_code(self, data, url=None, extra_success_codes=None):
        code = self._normalize_api_code(data)
        if code is None:
            return
        allowed = set(API_SUCCESS_CODES)
        if extra_success_codes:
            allowed |= set(extra_success_codes)
        if code in allowed:
            return
        detail = self._extract_error_message(data)
        if code == 99 and detail:
            normalized = detail.lower()
            if "ya ha sido enviado previamente" in normalized:
                return
        message = (
            API_ERROR_MESSAGES.get(code) or "Codigo de respuesta API no documentado."
        )
        try:
            raw = (
                json.dumps(data, ensure_ascii=False)
                if isinstance(data, dict)
                else str(data)
            )
        except TypeError:
            raw = str(data)
        if len(raw) > 20000:
            raw = raw[:20000] + "…(truncado)"
        vals = data.get(KEY_VALIDACIONES) if isinstance(data, dict) else None
        _logger.error(
            "TFHKA API rechazo url=%s codigo=%s mensaje_catalogo=%s "
            "validaciones=%s respuesta=%s",
            url or "",
            code,
            message,
            vals,
            raw,
        )
        hint = self._tfhka_validation_operational_hint(data)
        body = f"TFHKA codigo {code}. {message}"
        if detail and detail.strip() != message.strip():
            body += f" Detalle: {detail}"
        body += hint
        raise UserError(body)

    @api.model
    def _request(
        self,
        method,
        path,
        payload=None,
        token=None,
        timeout=None,
        extra_success_codes=None,
    ):
        url = f"{self._base_url()}{path}"
        request_timeout = timeout or self._timeout()
        body = payload or {}
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self._build_headers(token=token),
                json=body,
                timeout=request_timeout,
            )
        except requests.Timeout as exc:
            raise UserError(_("Tiempo de espera agotado en la API de TFHKA.")) from exc
        except requests.RequestException as exc:
            raise UserError(f"Error de conexion con TFHKA: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {KEY_RAW: response.text}

        self._raise_for_http_status(response, data, url=url)
        self._raise_for_api_code(data, url=url, extra_success_codes=extra_success_codes)
        return data

    @api.model
    def authenticate(self, usuario, clave, timeout=None):
        payload = {"usuario": usuario, "clave": clave}
        response = self._request(
            method=METHOD_POST,
            path=PATH_AUTENTICACION,
            payload=payload,
            timeout=timeout,
        )
        token = response.get(KEY_TOKEN)
        if not token:
            error_message = self._extract_error_message(response)
            raise UserError(
                f"No fue posible obtener el token JWT de TFHKA: {error_message}"
            )
        return response

    @api.model
    def cancel_document(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST, PATH_ANULAR, payload=payload, token=token, timeout=timeout
        )

    @api.model
    def apply_retention(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_APLICAR_RETENCION,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def delete_retention(self, payload, token, timeout=None):
        return self._request(
            METHOD_DELETE,
            PATH_APLICAR_RETENCION,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def get_retention(self, payload, token, timeout=None):
        return self._request(
            METHOD_GET,
            PATH_APLICAR_RETENCION,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def assign_numerations(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_ASIGNAR_NUMERACIONES,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def query_numerations(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_CONSULTA_NUMERACIONES,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def send_email(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_CORREO_ENVIAR,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def track_email(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_CORREO_RASTREO,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def send_order_email(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_CORREO_ENVIA_ORDEN,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def track_order_email(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_CORREO_RASTREO_ORDEN,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def download_file(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_DESCARGA_ARCHIVO,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def issue_document(self, payload, token, timeout=None, extra_success_codes=None):
        return self._request(
            METHOD_POST,
            PATH_EMISION,
            payload=payload,
            token=token,
            timeout=timeout,
            extra_success_codes=extra_success_codes,
        )

    @api.model
    def issue_arc(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST, PATH_EMISION_ARC, payload=payload, token=token, timeout=timeout
        )

    @api.model
    def get_document_status(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_ESTADO_DOCUMENTO,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def get_batch_status(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST, PATH_ESTADO_LOTE, payload=payload, token=token, timeout=timeout
        )

    @api.model
    def list_documents(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_LISTADO_DOCUMENTOS,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def list_assignments(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_LISTADO_ASIGNACIONES,
            payload=payload,
            token=token,
            timeout=timeout,
        )

    @api.model
    def get_last_document(self, payload, token, timeout=None):
        return self._request(
            METHOD_POST,
            PATH_ULTIMO_DOCUMENTO,
            payload=payload,
            token=token,
            timeout=timeout,
        )
