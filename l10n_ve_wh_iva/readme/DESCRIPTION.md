This addon manages Venezuelan VAT withholding under Administrative Ruling
SNAT/2025/000054 in both payment directions.

When a customer acting as a special taxpayer withholds VAT, the received voucher
number and amount are recorded during payment registration. The withheld amount
is posted to the configured receivable withholding account.

When the company is designated as a special taxpayer, vendor payments calculate
the applicable 75% or 100% VAT withholding. The addon creates the accounting
write-off and a legal voucher with a monthly, company-specific sequence. It also
provides the voucher PDF and the 16-column, tab-delimited TXT export for Form
99035.

The supplier control number is included when another installed addon provides
the optional `l10n_ve_control_number` field. This addon does not require that
field or any unreleased localization addon.
