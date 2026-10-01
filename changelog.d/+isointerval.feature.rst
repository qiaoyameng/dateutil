Added ``dateutil.parser.isointervalparse`` and
``dateutil.parser.isointervalparser``, which parse ISO-8601 interval strings
(``<start>/<end>``, ``<start>/<duration>``, ``<duration>/<end>`` and
explicitly open ends) into an ``ISOInterval`` carrying the resolved
endpoints, the openness of each boundary and the precision of the input.
Durations with years or months are applied with calendar semantics via
``relativedelta`` rather than being converted to a fixed number of seconds.
``isoparse`` now consistently rejects interval strings instead of
misinterpreting them.
