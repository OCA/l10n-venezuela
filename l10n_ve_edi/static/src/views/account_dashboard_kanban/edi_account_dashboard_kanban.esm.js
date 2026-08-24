import {EdiSeniatInvoiceDashboard} from "../../components/edi_seniat_invoice_dashboard/edi_seniat_invoice_dashboard";
import {SeniatDashboardKanbanRenderer} from "@l10n_ve_seniat/views/account_dashboard_kanban/seniat_account_dashboard_kanban";
import {accountDashboardKanbanView} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_view";
import {registry} from "@web/core/registry";

export class EdiDashboardKanbanRenderer extends SeniatDashboardKanbanRenderer {
    static components = {
        ...SeniatDashboardKanbanRenderer.components,
        EdiSeniatInvoiceDashboard,
    };
    static template = "l10n_ve_edi.DashboardKanbanRenderer";
}

registry.category("views").add(
    "account_dashboard_kanban",
    {
        ...accountDashboardKanbanView,
        Renderer: EdiDashboardKanbanRenderer,
    },
    {force: true}
);
