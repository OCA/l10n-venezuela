import {Component} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

class RedirectAction extends Component {
    static template = "l10n_ve_reports.redirectAction";
    static components = {Dialog};

    static props = {
        ...standardActionServiceProps,
        action: Object,
    };

    setup() {
        this.actionService = useService("action");
    }

    openClientAction() {
        this.actionService.doAction(this.props.action.params.depending_action);
    }

    close() {
        this.actionService.doAction({type: "ir.actions.act_window_close"});
    }
}

registry.category("actions").add("l10n_ve_reports.redirect_action", RedirectAction);
