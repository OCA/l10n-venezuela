On Venezuelan bank statements (Banesco, Provincial, Mercantil, and others)
the bank reference is often longer than the one stored on the payment or
invoice. Usually only the last 6 or 4 digits match.

This module covers that case without forcing ambiguous matches: if there are
several candidates, it only suggests them and leaves validation to the user.
