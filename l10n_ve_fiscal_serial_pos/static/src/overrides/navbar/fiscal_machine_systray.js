/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useEffect,
    useState,
} from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { CONNECTION_STATUS } from "@l10n_ve_fiscal_serial/fiscal_connection/fiscal_connection_service";
import {
    l10nVeFiscalSerialPosGetFiscalMachineId,
    l10nVeFiscalSerialPosGetInvoiceJournal,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

export class PosFiscalMachineSystray extends Component {
    static template = "l10n_ve_fiscal_serial_pos.PosFiscalMachineSystray";
    static components = { Dropdown };
    static props = {
        fiscalMachineId: { optional: true },
        invoiceJournalId: { optional: true },
    };

    setup() {
        this.pos = usePos();
        this.connection = useService("l10n_ve_fiscal_connection");
        this.state = useState(this.connection.state);
        this._onJournalChanged = (ev) => {
            const detail = ev?.detail || {};
            void this._syncMachineFromJournal({
                reconnect: true,
                machineId: detail.machineId,
            });
        };
        onWillStart(async () => {
            await this.connection.bootstrap();
            await this.connection.loadSystrayData();
            await this._syncMachineFromJournal({ reconnect: true });
        });
        onMounted(() => {
            void this.connection.refreshAuthorization();
            this.env.bus.addEventListener(
                "L10N_VE_FISCAL_POS_JOURNAL_CHANGED",
                this._onJournalChanged
            );
        });
        onWillUnmount(() => {
            this.env.bus.removeEventListener(
                "L10N_VE_FISCAL_POS_JOURNAL_CHANGED",
                this._onJournalChanged
            );
        });
        useEffect(
            () => {
                void this._syncMachineFromJournal({ reconnect: true });
            },
            () => [
                this.props.fiscalMachineId || false,
                this.props.invoiceJournalId || false,
            ]
        );
    }

    async _syncMachineFromJournal({ reconnect = false, machineId = false } = {}) {
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return false;
        }
        if (!this.connection.state.machines?.length) {
            await this.connection.loadSystrayData();
        }
        const targetMachineId =
            Number(machineId) ||
            Number(this.props.fiscalMachineId) ||
            Number(l10nVeFiscalSerialPosGetFiscalMachineId(this.pos)) ||
            false;
        if (!targetMachineId || !this.connection.setPrimaryMachine) {
            return false;
        }
        const previousId = Number(this.connection.state.machine?.id || 0) || 0;
        const ok = await this.connection.setPrimaryMachine(targetMachineId);
        const nextId = Number(this.connection.state.machine?.id || 0) || 0;
        if (reconnect && ok && nextId && nextId !== previousId) {
            await this.connection.checkConnection({ requestPort: false });
        }
        return ok;
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

    get invoiceJournalLabel() {
        const journal = l10nVeFiscalSerialPosGetInvoiceJournal(this.pos);
        return journal?.display_name || journal?.name || "";
    }

    async onDropdownOpened() {
        await this.connection.loadSystrayData();
        await this._syncMachineFromJournal({ reconnect: true });
        if (this.state.visible && this.state.machine) {
            await this.connection.checkConnection();
        }
    }

    async onCheckConnection() {
        await this._syncMachineFromJournal({ reconnect: false });
        await this.connection.checkConnection();
    }

    async onConnect() {
        await this._syncMachineFromJournal({ reconnect: false });
        await this.connection.connect();
    }
}

Navbar.components = {
    ...Navbar.components,
    PosFiscalMachineSystray,
};

function _posFiscalSystrayJournal(pos) {
    void pos.selectedOrderUuid;
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    const journal = order?.invoice_journal_id || pos.config?.invoice_journal_id || false;
    void journal?.id;
    void journal?.l10n_ve_emission_medium;
    void journal?.l10n_ve_fiscal_machine_id;
    void journal?.l10n_ve_fiscal_machine_id?.id;
    return journal;
}

patch(Navbar.prototype, {
    get fiscalSystrayJournalId() {
        const journal = _posFiscalSystrayJournal(this.pos);
        return journal?.id || false;
    },
    get fiscalSystrayMachineId() {
        const journal = _posFiscalSystrayJournal(this.pos);
        const machine = journal?.l10n_ve_fiscal_machine_id;
        if (!machine) {
            return false;
        }
        return typeof machine === "object" ? machine.id : machine;
    },
    get showFiscalMachineSystray() {
        void this.fiscalSystrayJournalId;
        void this.fiscalSystrayMachineId;
        return l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
    },
});
