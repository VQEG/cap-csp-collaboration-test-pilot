# FikoRE Co-Simulation Protocol

The co-simulation protocol specification consists of two documents:

- [FikoRE Co-simulation](fikore-cosim.md): architecture, roles, lifecycle, delivery semantics, and implementation requirements.
- [Co-simulation Message Reference](fikore-cosim-messages.md): the JSON wire schema and message examples.

Object-level delivery semantics are required. Socket framing and field names are FikoRE's `fikore-control-1` control protocol, which the pilot adopts rather than defining a second one.
