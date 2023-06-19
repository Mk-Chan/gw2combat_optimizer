# gw2combat_optimizer

This repository is an addon to [gw2combat](https://github.com/Mk-Chan/gw2combat). It requires running `gw2combat` in
server mode `./gw2combat --server`.
It is primarily a tool to optimize combat simulations.

Currently the tool provides a prompt loop which tracks the state of the first actor in the encounter json.
The default encounter is `resources/encounter.json`.

The prompt loop allows you to enter commands to modify the state of the actor, perform simulations and search for
optimal rotations using implemented algorithms.

Currently, this optimizer specifically works with Power Longbow SLB.
