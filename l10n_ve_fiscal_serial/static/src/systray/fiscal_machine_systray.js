/** @odoo-module **/

import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { CONNECTION_STATUS } from "../fiscal_connection/fiscal_connection_service";

export class FiscalMachineSystray extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachineSystray";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.connection = useService("l10n_ve_fiscal_connection");
        // Subscribe to the service reactive state so heartbeat updates re-render
        // the systray without requiring another user click.
        this.state = useState(this.connection.state);
        onWillStart(async () => {
            await this.connection.bootstrap();
        });
        onMounted(() => {
            void this.connection.refreshAuthorization();
        });
    }

    get statusLabel() {
        switch (this.state.status) {
            case CONNECTION_STATUS.CONNECTING:
                return "Comprobando…";
            case CONNECTION_STATUS.CONNECTED:
                return this.state.portOpen ? "Conectada" : "Verificada";
            case CONNECTION_STATUS.ERROR:
                return this.state.portOpen ? "Sin respuesta" : "Sin conexión";
            case CONNECTION_STATUS.UNSUPPORTED:
                return "No compatible";
            case CONNECTION_STATUS.IDLE:
                return this.state.portAuthorized ? "Autorizada" : "Desconectada";
            default:
                return "";
        }
    }

    get portStatusLabel() {
        if (this.state.portOpen) {
            return "Abierto";
        }
        if (this.state.portAuthorized) {
            return "Cerrado (autorizado)";
        }
        return "Cerrado (sin autorizar)";
    }

    get statusClass() {
        switch (this.state.status) {
            case CONNECTION_STATUS.CONNECTING:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning";
            case CONNECTION_STATUS.CONNECTED:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-success";
            case CONNECTION_STATUS.ERROR:
                return this.state.portOpen
                    ? "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning"
                    : "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-danger";
            case CONNECTION_STATUS.UNSUPPORTED:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-danger";
            case CONNECTION_STATUS.IDLE:
                return this.state.portAuthorized
                    ? "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning"
                    : "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-muted";
            default:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-muted";
        }
    }

    get lastCheckLabel() {
        if (!this.state.lastCheckAt) {
            return "Sin comprobación ENQ reciente";
        }
        return new Date(this.state.lastCheckAt).toLocaleString();
    }

    machineLabel(machine) {
        const serial = (machine.registered_serial || "").trim();
        if (serial && machine.name && !machine.name.includes(serial)) {
            return `${machine.name} (${serial})`;
        }
        return machine.name || serial || `Máquina #${machine.id}`;
    }

    async onDropdownOpened() {
        await this.connection.loadSystrayData();
        if (this.state.visible && this.state.machine) {
            await this.connection.checkConnection();
        }
    }

    async onSelectMachine(ev) {
        const machineId = Number(ev.target.value) || 0;
        if (!machineId) {
            return;
        }
        const changed = await this.connection.setPrimaryMachine(machineId);
        if (changed && this.state.visible && this.state.machine) {
            await this.connection.checkConnection({ requestPort: false });
        }
    }

    async onCheckConnection() {
        await this.connection.checkConnection();
    }

    async onConnect() {
        await this.connection.connect();
    }

    async onOpenMachines() {
        await this.connection.openMachines();
    }
}

registry.category("systray").add(
    "l10n_ve_fiscal_serial.FiscalMachineSystray",
    {
        Component: FiscalMachineSystray,
        isDisplayed: (env) => env.services.l10n_ve_fiscal_connection?.state?.visible,
        sequence: 45,
    }
);
