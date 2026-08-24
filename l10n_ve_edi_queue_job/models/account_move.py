from odoo import _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_edi_send_uses_queue_job(self):
        return True

    def _l10n_ve_edi_schedule_send(self):
        self.ensure_one()
        self.message_post(body=_("Solicitud de envio a Facturacion Digital encolada."))
        self.with_delay(
            description=f"EDI VE send invoice {self.name or self.id}",
            channel="root",
        )._job_l10n_ve_edi_send_invoice(self.id)
