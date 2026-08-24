import {Component} from "@odoo/owl";

export class AccountReportDebugPopover extends Component {
    static template = "l10n_ve_reports.AccountReportDebugPopover";
    static props = {
        close: Function,
        expressionsDetail: Array,
        onClose: Function,
    };
}
