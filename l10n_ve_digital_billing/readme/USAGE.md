Posting an invoice, credit note, or debit note on a "Digital billing"
journal queues it ("To send"). Use the "Send to digital printing house"
button (or wait for the cron) to submit it; a synchronous provider such as
The Factory HKA returns the control number immediately and the document
moves to "Control number assigned". An asynchronous provider leaves it as
"Sent, control number pending" until "Query control number" retrieves it.

Use "Cancel at the printing house" to void the document with the provider;
this requires a reason and does not by itself cancel the journal entry or
issue a credit note.

Every call to the provider, successful or not, is recorded under Accounting /
Reporting / Digital printing house log, together with the request sent and
the response received.
