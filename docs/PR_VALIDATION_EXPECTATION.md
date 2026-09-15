# PR validation expectation

Opening the draft PR should trigger the existing repository CI plus the autonomous-acquisition CI. We expect offline tests to pass without external credentials. The manually dispatched live shadow workflow is intentionally separate because it consumes the Upstox repository secret and tests current provider availability.
