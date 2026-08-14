/** @odoo-module **/

const TFHKA_TRAINING_STS1 = 64;

function normalizeSerial(value) {
    return String(value || "").trim().toUpperCase();
}

export async function verifyConnectedFiscalMachine(driver, expected, helpers = {}) {
    const { parseTfhkaS1StatusResponse } = helpers;
    if (!driver) {
        throw new Error("Driver fiscal no disponible.");
    }
    if (!expected || !expected.machine_id) {
        throw new Error("No hay máquina fiscal configurada en el diario.");
    }
    if (expected.use_emulator) {
        return {
            training_mode: false,
            emulator_mode: true,
            verified: true,
            message:
                "Modo emulador activo: se omitió la verificación del serial fiscal.",
        };
    }
    let statusOk = await driver.readFpStatus();
    if (!statusOk && typeof driver.transport?.drainInput === "function") {
        try {
            await driver.transport.drainInput(300);
        } catch {
            // ignore
        }
        statusOk = await driver.readFpStatus();
    }
    if (!statusOk) {
        throw new Error(
            driver.estado || "No se pudo leer el estado ENQ de la impresora conectada."
        );
    }
    const sts1 = parseInt(driver.status || "0", 10);
    if (sts1 === TFHKA_TRAINING_STS1) {
        return {
            training_mode: true,
            verified: true,
            message:
                "Impresora en modo entrenamiento: se omitió la verificación del serial fiscal.",
        };
    }
    const expectedSerial = normalizeSerial(expected.registered_serial);
    if (!expectedSerial) {
        throw new Error(
            "La máquina fiscal configurada en el diario no tiene serial fiscal registrado."
        );
    }
    const s1Result = await driver.uploadStatusCmdToString("S1");
    if (!s1Result?.ok || !s1Result.content) {
        throw new Error("No se pudo leer el estado S1 de la impresora conectada.");
    }
    const s1Parsed = parseTfhkaS1StatusResponse
        ? parseTfhkaS1StatusResponse(s1Result.content)
        : null;
    const connectedSerial = normalizeSerial(s1Parsed?.RegisteredMachineNumber);
    if (!connectedSerial) {
        throw new Error(
            "La impresora conectada no devolvió el serial fiscal. Verifique el puerto seleccionado."
        );
    }
    if (connectedSerial !== expectedSerial) {
        throw new Error(
            `La impresora conectada (${connectedSerial}) no coincide con la máquina fiscal configurada en el diario (${expectedSerial}).`
        );
    }
    return {
        training_mode: false,
        verified: true,
        connected_serial: connectedSerial,
        message: "La impresora conectada coincide con la máquina fiscal del diario.",
    };
}
