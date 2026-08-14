# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.config"

    def l10n_ve_get_invoice_emission_preview(self, journal_id=False):
        data = super().l10n_ve_get_invoice_emission_preview(journal_id)
        data.update(
            {
                "next_fiscal_invoice_number": "",
                "next_fiscal_serial": "",
                "next_fiscal_report_z": "",
            }
        )
        if self.company_id.account_fiscal_country_id.code != "VE":
            return data
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id
            else self.invoice_journal_id
        )
        if not journal:
            journal = self.invoice_journal_id
        if not journal or journal.l10n_ve_emission_medium != "fiscal_machine":
            return data
        machine = journal.l10n_ve_fiscal_machine_id
        if not machine:
            return data
        AccountMove = self.env["account.move"]
        data["next_fiscal_serial"] = (machine.registered_serial or "").strip()
        data["next_fiscal_invoice_number"] = (
            AccountMove._l10n_ve_fiscal_serial_increment_counter(
                machine.last_invoice_number, min_width=8
            )
            or ""
        )
        data["next_fiscal_report_z"] = (
            AccountMove._l10n_ve_fiscal_serial_increment_counter(
                machine.daily_closure_counter, min_width=4
            )
            or ""
        )
        return data
