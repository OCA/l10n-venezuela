import {
    AccountMoveLineListRenderer,
    AccountMoveLineListView,
} from "@l10n_ve_reports/components/move_line_list/move_line_list";
import {registry} from "@web/core/registry";

export class JournalReportAccountMoveLineReconcileListRenderer extends AccountMoveLineListRenderer {
    setup() {
        super.setup();
        this.props.list.groups?.forEach((group) => {
            group.list?.groups?.forEach((innerGroup) => {
                this.toggleGroup(innerGroup);
            });
        });
    }
}

export const JournalReportAccountMoveLineReconcileLineListView = {
    ...AccountMoveLineListView,
    Renderer: JournalReportAccountMoveLineReconcileListRenderer,
};

registry
    .category("views")
    .add(
        "account_move_line_journal_report_list_oca",
        JournalReportAccountMoveLineReconcileLineListView
    );
