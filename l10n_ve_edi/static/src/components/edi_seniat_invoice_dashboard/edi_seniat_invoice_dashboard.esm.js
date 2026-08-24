/** @odoo-module */

import {SeniatInvoiceDashboard} from "@l10n_ve_seniat/components/seniat_invoice_dashboard/seniat_invoice_dashboard";
import {EdiUnsentDashboard} from "../edi_unsent_dashboard/edi_unsent_dashboard";

export class EdiSeniatInvoiceDashboard extends SeniatInvoiceDashboard {
    static components = {
        ...SeniatInvoiceDashboard.components,
        EdiUnsentDashboard,
    };
}
