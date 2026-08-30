When a bridge URL is configured, POS validation first prints the fiscal
document. The order is not finalized until a fiscal number is returned.

If an invoice request times out, the next attempt checks the bridge's last
invoice. A matching UUID is recovered automatically. A different UUID or total
is reprinted. If an older bridge cannot return a UUID but the total matches,
the cashier must inspect the physical ticket and explicitly choose whether to
recover its number or print again. Credit notes are never retried blindly after
an ambiguous timeout.

Use **X Report** and **Z Report** from the POS control buttons. Z printing asks
for confirmation and stores the returned report number on the POS session.

For backend printing, open a posted customer invoice or credit note issued with
the **Fiscal machine** emission medium and click **Print Fiscal Document** from
the computer running the local bridge.
