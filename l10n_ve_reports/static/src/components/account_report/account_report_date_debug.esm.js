const PREFIX = "[l10n_ve_reports:account_report:date]";

export function logAccountReportDate(phase, payload = {}) {
    const safe = {...payload};
    if (safe.date && typeof safe.date === "object") {
        safe.date = {
            filter: safe.date.filter,
            period: safe.date.period,
            period_type: safe.date.period_type,
            mode: safe.date.mode,
            date_from: safe.date.date_from,
            date_to: safe.date.date_to,
            string: safe.date.string,
        };
    }
    if (safe.loadOptionsDate && typeof safe.loadOptionsDate === "object") {
        safe.loadOptionsDate = {
            filter: safe.loadOptionsDate.filter,
            period: safe.loadOptionsDate.period,
            period_type: safe.loadOptionsDate.period_type,
            mode: safe.loadOptionsDate.mode,
            date_from: safe.loadOptionsDate.date_from,
            date_to: safe.loadOptionsDate.date_to,
            string: safe.loadOptionsDate.string,
        };
    }
    if (safe.optionsDate && typeof safe.optionsDate === "object") {
        try {
            safe.optionsDateSnapshot = JSON.stringify(safe.optionsDate);
        } catch {
            safe.optionsDateSnapshot = "(unserializable)";
        }
        delete safe.optionsDate;
    }
    globalThis.console.info(PREFIX, phase, safe);
}
