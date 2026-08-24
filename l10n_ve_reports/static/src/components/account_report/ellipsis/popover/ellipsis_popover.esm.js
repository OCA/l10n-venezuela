import {Component} from "@odoo/owl";

export class AccountReportEllipsisPopover extends Component {
    static template = "l10n_ve_reports.AccountReportEllipsisPopover";
    static props = {
        close: Function,
        name: String,
        copyEllipsisText: Function,
    };
}
