import {Component, onWillStart, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class EdiUnsentDashboard extends Component {
    static template = "l10n_ve_edi.EdiUnsentDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            visible: false,
            title: "",
            items: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const data = await this.orm.call(
            "account.journal",
            "get_l10n_ve_edi_unsent_dashboard",
            []
        );
        this.state.visible = data.visible;
        this.state.title = data.title || "";
        this.state.items = data.items || [];
    }

    async openItem(itemKey) {
        const action = await this.orm.call(
            "account.journal",
            "action_l10n_ve_edi_unsent_dashboard_open",
            [itemKey]
        );
        return this.actionService.doAction(action);
    }
}
