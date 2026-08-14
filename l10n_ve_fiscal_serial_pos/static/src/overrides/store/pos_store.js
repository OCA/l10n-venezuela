/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import {
    l10nVeFiscalSerialPosGetFiscalMachineId,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

async function syncFiscalMachineFromPosOrder(pos, env) {
    const connection = env?.services?.l10n_ve_fiscal_connection;
    if (!connection?.setPrimaryMachine) {
        return false;
    }
    if (!l10nVeFiscalSerialPosIsFiscalMachine(pos)) {
        return false;
    }
    if (!connection.state.machines?.length && connection.loadSystrayData) {
        await connection.loadSystrayData();
    }
    const machineId = l10nVeFiscalSerialPosGetFiscalMachineId(pos);
    if (!machineId) {
        return false;
    }
    const previousId = Number(connection.state.machine?.id || 0) || 0;
    const ok = await connection.setPrimaryMachine(machineId);
    const nextId = Number(connection.state.machine?.id || 0) || 0;
    if (ok && nextId && nextId !== previousId && connection.checkConnection) {
        await connection.checkConnection({ requestPort: false });
    }
    return ok;
}

patch(PosStore.prototype, {
    async selectInvoiceJournal(order = this.get_order()) {
        const selectedJournal = await super.selectInvoiceJournal(...arguments);
        if (selectedJournal) {
            await syncFiscalMachineFromPosOrder(this, this.env);
            this.env?.bus?.trigger("L10N_VE_FISCAL_POS_JOURNAL_CHANGED", {
                journalId: selectedJournal.id,
                machineId: l10nVeFiscalSerialPosGetFiscalMachineId(this),
            });
        }
        return selectedJournal;
    },
});
