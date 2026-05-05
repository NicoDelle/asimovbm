# Policy Interface

Participant code is loaded from local Python references in `module:attribute`
format. The client instantiates classes with no arguments, or uses callable
objects/functions directly.

The transformer receives a `StepMessage` containing raw sensor streams and task
events, and returns the policy observation. The policy receives that observation
and returns an action vector compatible with the robot package action mapping.

The client does not upload participant source, weights, or dependencies.
