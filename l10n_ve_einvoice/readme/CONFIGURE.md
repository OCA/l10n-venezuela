1. On each relevant Venezuelan sales journal, select **Digital billing** as the
   emission medium.
2. In Accounting settings, select the electronic document provider and enter
   the provider configuration supplied for that company.
3. Keep the scheduled action disabled until a production provider adapter is
   installed and the company is authorized to issue digital documents.

Provider URL, user, and password fields are restricted to system
administrators. A concrete adapter that needs to read them while processing a
request from another user must do so in a narrowly scoped, explicit elevated
operation. Adapters must never include credentials or authentication material
in their neutral results or exception messages.
