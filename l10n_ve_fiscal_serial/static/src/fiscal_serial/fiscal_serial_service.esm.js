import {registry} from "@web/core/registry";
import {
    PrinterStatus,
    SVPrinterData,
    TfhkaFiscal,
    createTfhkaFiscal,
    encodeLatin1,
} from "./tfhka_serial";
import {
    TfhkaWebSerialTransport,
    formatWebSerialError,
    formatWebSerialPortLabel,
    readWebSerialPortInfo,
} from "./tfhka_transport_webserial";
import {getSampleHkaInvoiceLines} from "./tfhka_invoice_samples";
import {
    FLAG_21,
    TAX_MAP,
    TfhkaFiscalMachine,
    createTfhkaFiscalMachine,
} from "./tfhka_fiscal_machine";
import {
    autoDetectFiscalMachine,
    parseTfhkaSvStatusResponse,
} from "../fiscal_machine/fiscal_machine_detect";
import {verifyConnectedFiscalMachine} from "../fiscal_machine/fiscal_machine_verify";
import {
    FiscalSerialAuditLogger,
    createFiscalSerialAuditLogger,
} from "./fiscal_serial_audit";
import {
    mfReportzFromDailyClosureString,
    parseTfhkaS1StatusResponse,
} from "./tfhka_s1_parser";

export const l10nVeFiscalSerialService = {
    dependencies: [],
    start() {
        return {
            createTfhkaFiscal,
            TfhkaFiscal,
            PrinterStatus,
            SVPrinterData,
            TfhkaWebSerialTransport,
            encodeLatin1,
            formatWebSerialError,
            getSampleHkaInvoiceLines,
            createTfhkaFiscalMachine,
            TfhkaFiscalMachine,
            FLAG_21,
            TAX_MAP,
            parseTfhkaS1StatusResponse,
            mfReportzFromDailyClosureString,
            parseTfhkaSvStatusResponse,
            autoDetectFiscalMachine,
            verifyConnectedFiscalMachine,
            formatWebSerialPortLabel,
            readWebSerialPortInfo,
            createFiscalSerialAuditLogger,
            FiscalSerialAuditLogger,
            isSupported: () => TfhkaWebSerialTransport.isSupported(),
        };
    },
};

registry.category("services").add("l10n_ve_fiscal_serial", l10nVeFiscalSerialService);
registry.category("l10n_ve_fiscal_serial").add("TfhkaFiscal", TfhkaFiscal);
