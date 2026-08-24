# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nVeFiscalMachineSetupWizard(models.TransientModel):
    _name = "l10n.ve.fiscal.machine.setup.wizard"
    _description = "Venezuela Fiscal Machine Setup Wizard"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(string="Nombre")
    connection_type = fields.Selection(
        selection=[
            ("web_serial", "Web Serial (navegador)"),
        ],
        default="web_serial",
        required=True,
    )
    serial_port = fields.Char(string="Puerto de conexión")
    baudrate = fields.Selection(
        selection=[
            ("9600", "9600"),
            ("19200", "19200"),
            ("38400", "38400"),
            ("57600", "57600"),
            ("115200", "115200"),
        ],
        default="9600",
        required=True,
    )
    parity = fields.Selection(
        selection=[
            ("none", "Ninguna"),
            ("even", "Par"),
            ("odd", "Impar"),
        ],
        default="even",
        required=True,
    )
    data_bits = fields.Selection(
        selection=[("7", "7"), ("8", "8")],
        default="8",
        required=True,
    )
    stop_bits = fields.Selection(
        selection=[("1", "1"), ("2", "2")],
        default="1",
        required=True,
    )
    webserial_usb_vendor_id = fields.Integer(string="USB Vendor ID")
    webserial_usb_product_id = fields.Integer(string="USB Product ID")
    webserial_usb_serial_number = fields.Char(string="USB Serial Number")
    printer_type = fields.Selection(
        selection=[
            ("hka80", "HKA 80"),
            ("vmax801", "VMAX801"),
            ("other", "Otro"),
        ],
        default="hka80",
        required=True,
    )
    printer_model_code = fields.Char(string="Código de modelo")
    printer_model_name = fields.Char(string="Modelo")
    country_code = fields.Char(string="País")
    registered_serial = fields.Char(string="Serial fiscal")
    fiscal_rif = fields.Char(string="RIF fiscal")
    flag_21 = fields.Selection(
        selection=[
            ("00", "00"),
            ("01", "01"),
            ("02", "02"),
            ("11", "11"),
            ("12", "12"),
            ("30", "30"),
        ],
        default="00",
        required=True,
    )
    use_emulator = fields.Boolean(
        string="Usando emulador fiscal",
    )
    send_default_code_in_name = fields.Boolean(
        string="Enviar codigo en nombre de producto",
    )
    last_invoice_number = fields.Char(string="Última factura")
    last_credit_note_number = fields.Char(string="Última nota de crédito")
    last_debit_note_number = fields.Char(string="Última nota de débito")
    daily_closure_counter = fields.Char(string="Último Z")
    enq_status = fields.Integer()
    enq_error = fields.Integer()
    enq_status_label = fields.Char()
    enq_error_label = fields.Char()
    s1_raw = fields.Text()
    sv_raw = fields.Text()
    detect_state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("done", "Detectada"),
            ("error", "Error"),
        ],
        default="pending",
    )
    detect_message = fields.Char()
    requires_manual_identification = fields.Boolean(
        compute="_compute_requires_manual_identification",
    )

    _MANUAL_IDENTIFICATION_FIELDS = {"registered_serial", "fiscal_rif"}

    _WIZARD_DETECT_FIELDS = {
        "name",
        "connection_type",
        "serial_port",
        "baudrate",
        "parity",
        "data_bits",
        "stop_bits",
        "webserial_usb_vendor_id",
        "webserial_usb_product_id",
        "webserial_usb_serial_number",
        "printer_type",
        "printer_model_code",
        "printer_model_name",
        "country_code",
        "registered_serial",
        "fiscal_rif",
        "use_emulator",
        "send_default_code_in_name",
        "last_invoice_number",
        "last_credit_note_number",
        "last_debit_note_number",
        "daily_closure_counter",
        "enq_status",
        "enq_error",
        "enq_status_label",
        "enq_error_label",
        "s1_raw",
        "sv_raw",
        "detect_state",
        "detect_message",
    }

    @api.depends(
        "detect_state",
        "enq_status",
        "registered_serial",
        "fiscal_rif",
    )
    def _compute_requires_manual_identification(self):
        for wizard in self:
            wizard.requires_manual_identification = (
                wizard.detect_state == "done"
                and wizard.enq_status == 64
                and (not wizard.registered_serial or not wizard.fiscal_rif)
            )

    def apply_detect_result(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            payload = {}
        vals = {}
        for field_name in self._WIZARD_DETECT_FIELDS:
            if field_name not in payload:
                continue
            value = payload[field_name]
            if value is None:
                value = False
            if (
                field_name in self._MANUAL_IDENTIFICATION_FIELDS
                and not value
                and self[field_name]
            ):
                continue
            vals[field_name] = value
        if vals:
            self.write(vals)
        if not vals:
            return {}
        read_fields = set(vals.keys())
        read_fields.add("requires_manual_identification")
        if vals.get("detect_state") == "done":
            read_fields |= self._WIZARD_DETECT_FIELDS
        return self.read(sorted(read_fields))[0]

    def _get_detect_payload(self):
        self.ensure_one()
        return {
            "company_id": self.company_id.id,
            "name": self.name,
            "connection_type": self.connection_type,
            "serial_port": self.serial_port,
            "baudrate": self.baudrate,
            "parity": self.parity,
            "data_bits": self.data_bits,
            "stop_bits": self.stop_bits,
            "webserial_usb_vendor_id": self.webserial_usb_vendor_id,
            "webserial_usb_product_id": self.webserial_usb_product_id,
            "webserial_usb_serial_number": self.webserial_usb_serial_number,
            "printer_type": self.printer_type,
            "printer_model_code": self.printer_model_code,
            "printer_model_name": self.printer_model_name,
            "country_code": self.country_code,
            "registered_serial": self.registered_serial,
            "fiscal_rif": self.fiscal_rif,
            "use_emulator": self.use_emulator,
            "send_default_code_in_name": self.send_default_code_in_name,
            "last_invoice_number": self.last_invoice_number,
            "last_credit_note_number": self.last_credit_note_number,
            "last_debit_note_number": self.last_debit_note_number,
            "daily_closure_counter": self.daily_closure_counter,
            "enq_status": self.enq_status,
            "enq_error": self.enq_error,
            "enq_status_label": self.enq_status_label,
            "enq_error_label": self.enq_error_label,
            "s1_raw": self.s1_raw,
            "sv_raw": self.sv_raw,
        }

    def action_save_machine(self):
        self.ensure_one()
        if self.detect_state != "done":
            raise UserError(
                _("Seleccione el puerto y detecte la máquina fiscal antes de guardar.")
            )
        if not self.registered_serial:
            if self.enq_status == 64:
                raise UserError(
                    _(
                        "En modo entrenamiento la impresora no devuelve "
                        "el serial fiscal. Indíquelo manualmente antes de guardar."
                    )
                )
            raise UserError(
                _(
                    "No se detectó el serial fiscal de la impresora. "
                    "Indíquelo manualmente."
                )
            )
        machine_model = self.env["l10n.ve.fiscal.machine"]
        machine_id = machine_model.create_from_detect_payload(
            self._get_detect_payload()
        )
        machine = machine_model.browse(machine_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Máquina fiscal"),
            "res_model": "l10n.ve.fiscal.machine",
            "view_mode": "form",
            "res_id": machine.id,
            "target": "current",
        }
