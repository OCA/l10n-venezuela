import {Component, onWillStart, useRef, useState, useSubEnv} from "@odoo/owl";
import {AccountReportButtonsBar} from "@l10n_ve_reports/components/account_report/buttons_bar/buttons_bar";
import {AccountReportCogMenu} from "@l10n_ve_reports/components/account_report/cog_menu/cog_menu";
import {AccountReportController} from "@l10n_ve_reports/components/account_report/controller";
import {AccountReportEllipsis} from "@l10n_ve_reports/components/account_report/ellipsis/ellipsis";
import {AccountReportFilters} from "@l10n_ve_reports/components/account_report/filters/filters";
import {AccountReportHeader} from "@l10n_ve_reports/components/account_report/header/header";
import {AccountReportLine} from "@l10n_ve_reports/components/account_report/line/line";
import {AccountReportLineCell} from "@l10n_ve_reports/components/account_report/line_cell/line_cell";
import {AccountReportLineName} from "@l10n_ve_reports/components/account_report/line_name/line_name";
import {AccountReportSearchBar} from "@l10n_ve_reports/components/account_report/search_bar/search_bar";
import {ControlPanel} from "@web/search/control_panel/control_panel";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";
import {useSetupAction} from "@web/search/action_hook";

export class AccountReport extends Component {
    static template = "l10n_ve_reports.AccountReport";
    static props = {...standardActionServiceProps};
    static components = {
        ControlPanel,
        AccountReportButtonsBar,
        AccountReportCogMenu,
        AccountReportSearchBar,
    };

    static customizableComponents = [
        AccountReportEllipsis,
        AccountReportFilters,
        AccountReportHeader,
        AccountReportLine,
        AccountReportLineCell,
        AccountReportLineName,
    ];
    static defaultComponentsMap = [];

    setup() {
        this.rootRef = useRef("root");
        useSetupAction({
            rootRef: this.rootRef,
            getLocalState: () => {
                return {
                    keep_journal_groups_options: true,
                };
            },
        });
        if (this.props?.state?.keep_journal_groups_options !== undefined) {
            this.props.action.keep_journal_groups_options = true;
        }

        // Can not use 'control-panel-bottom-right' slot without this, as viewSwitcherEntries doesn't exist here.
        this.env.config.viewSwitcherEntries = [];

        this.orm = useService("orm");
        this.actionService = useService("action");
        this.controller = useState(new AccountReportController(this.props.action));
        this.initialQuery = this.props.action.context?.default_filter_accounts;

        for (const customizableComponent of AccountReport.customizableComponents)
            AccountReport.defaultComponentsMap[customizableComponent.name] =
                customizableComponent;

        onWillStart(async () => {
            await this.controller.load(this.env);
        });

        useSubEnv({
            controller: this.controller,
            component: this.getComponent.bind(this),
            template: this.getTemplate.bind(this),
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Custom overrides
    // -----------------------------------------------------------------------------------------------------------------
    static registerCustomComponent(customComponent) {
        registry
            .category("account_reports_custom_components")
            .add(customComponent.template, customComponent);
    }

    get cssCustomClass() {
        return this.controller.data.custom_display.css_custom_class || "";
    }

    getComponent(name) {
        const customComponents = this.controller.data.custom_display.components;

        if (customComponents && customComponents[name])
            return registry
                .category("account_reports_custom_components")
                .get(customComponents[name]);

        return AccountReport.defaultComponentsMap[name];
    }

    getTemplate(name) {
        const customTemplates = this.controller.data.custom_display.templates;

        if (customTemplates && customTemplates[name]) return customTemplates[name];

        return `l10n_ve_reports.${name}Customizable`;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Table
    // -----------------------------------------------------------------------------------------------------------------
    get tableClasses() {
        let classes = "";

        if (this.controller.options.columns.length > 1) {
            classes += " striped";
        }

        if (this.controller.options.horizontal_split) classes += " w-50 mx-2";

        return classes;
    }
}

registry.category("actions").add("account_report_oca", AccountReport);
