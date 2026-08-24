import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useEffect,
    useState,
} from "@odoo/owl";
import {
    l10nVeFiscalSerialPosGetFiscalMachineId,
    l10nVeFiscalSerialPosGetInvoiceJournal,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print.esm";
import {CONNECTION_STATUS} from "@l10n_ve_fiscal_serial/fiscal_connection/fiscal_connection_service";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {Navbar} from "@point_of_sale/app/navbar/navbar";
import {patch} from "@web/core/utils/patch";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import {useService} from "@web/core/utils/hooks";

function systrayTargetMachineId(component, machineId) {
    return (
        Number(machineId) ||
        Number(component.props.fiscalMachineId) ||
        Number(l10nVeFiscalSerialPosGetFiscalMachineId(component.pos)) ||
        false
    );
}

async function reconnectSystrayIfChanged(connection, previousId, ok, reconnect) {
    const nextId = Number(connection.state.machine?.id || 0) || 0;
    if (reconnect && ok && nextId && nextId !== previousId) {
        await connection.checkConnection({requestPort: false});
    }
    return ok;
}

function _posFiscalSystrayJournal(pos) {
    const selectedOrderUuid = pos.selectedOrderUuid;
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    const journal =
        order?.invoice_journal_id || pos.config?.invoice_journal_id || false;
    return {
        journal,
        selectedOrderUuid,
        journalId: journal?.id,
        emissionMedium: journal?.l10n_ve_emission_medium,
        machine: journal?.l10n_ve_fiscal_machine_id,
        machineId: journal?.l10n_ve_fiscal_machine_id?.id,
    };
}

export class PosFiscalMachineSystray extends Component {
    static template = "l10n_ve_fiscal_serial_pos.PosFiscalMachineSystray";
    static components = {Dropdown};
    static props = {
        fiscalMachineId: {optional: true},
        invoiceJournalId: {optional: true},
    };

    setup() {
        this.pos = usePos();
        this.connection = useService("l10n_ve_fiscal_connection");
        this.state = useState(this.connection.state);
        this._onJournalChanged = (ev) => {
            const detail = ev?.detail || {};
            this._syncMachineFromJournal({
                reconnect: true,
                machineId: detail.machineId,
            });
        };
        onWillStart(async () => {
            await this.connection.bootstrap();
            await this.connection.loadSystrayData();
            await this._syncMachineFromJournal({reconnect: true});
        });
        onMounted(() => {
            this.connection.refreshAuthorization();
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
                this._syncMachineFromJournal({reconnect: true});
            },
            () => [
                this.props.fiscalMachineId || false,
                this.props.invoiceJournalId || false,
            ]
        );
    }

    async _syncMachineFromJournal({reconnect = false, machineId = false} = {}) {
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return false;
        }
        if (!this.connection.state.machines?.length) {
            await this.connection.loadSystrayData();
        }
        const targetMachineId = systrayTargetMachineId(this, machineId);
        if (!targetMachineId || !this.connection.setPrimaryMachine) {
            return false;
        }
        const previousId = Number(this.connection.state.machine?.id || 0) || 0;
        const ok = await this.connection.setPrimaryMachine(targetMachineId);
        return reconnectSystrayIfChanged(this.connection, previousId, ok, reconnect);
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
        await this._syncMachineFromJournal({reconnect: true});
        if (this.state.visible && this.state.machine) {
            await this.connection.checkConnection();
        }
    }

    async onCheckConnection() {
        await this._syncMachineFromJournal({reconnect: false});
        await this.connection.checkConnection();
    }

    async onConnect() {
        await this._syncMachineFromJournal({reconnect: false});
        await this.connection.connect();
    }
}

Navbar.components = {
    ...Navbar.components,
    PosFiscalMachineSystray,
};

patch(Navbar.prototype, {
    get fiscalSystrayJournalId() {
        const tracked = _posFiscalSystrayJournal(this.pos);
        return tracked.journalId || false;
    },
    get fiscalSystrayMachineId() {
        const tracked = _posFiscalSystrayJournal(this.pos);
        const machine = tracked.machine;
        if (!machine) {
            return false;
        }
        return typeof machine === "object" ? machine.id : machine;
    },
    get showFiscalMachineSystray() {
        const isFiscal = l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
        return (
            isFiscal ||
            Boolean(
                this.fiscalSystrayJournalId && this.fiscalSystrayMachineId && isFiscal
            )
        );
    },
});
