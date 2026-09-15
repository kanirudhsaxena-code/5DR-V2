# Last-good-result preservation

An autonomous acquisition failure or BLOCKED shadow request must never overwrite the currently published last-good 5DR result. Acquisition state belongs to the new request only.

Production publication wiring must preserve this rule explicitly when the Console bridge is implemented.
