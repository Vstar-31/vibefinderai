# Security Policy

## System and Scope
Review all first-party routes, communication endpoints, authentication helpers, outbound requests, browser messages, configuration and credential consumers. Frontend visibility does not replace backend authorization. Development and optional routes remain in scope when reachable in a supported configuration.

## Threat Model and Trust Boundaries
Untrusted callers can send HTTP requests, malformed inputs, object identifiers and browser messages. Authenticated users can act only on their own private records and connected provider accounts. Provider callbacks, third-party responses and imported content remain untrusted. Repository access does not authorize use of credentials. Deployment configuration and privileged operators are separate trust boundaries.

## Security Invariants
- Private reads and mutations require a verified, unexpired identity before sensitive work. JWT validation must require the intended algorithm, purpose and nonblank subject. Signing keys must be private and fail closed when absent or invalid.
- Every object access enforces ownership or an explicit public-sharing decision. Public health, sign-in, registration and sharing endpoints expose only their intended minimum data.
- Analytics and administrative operations require separate authorization. A missing optional authentication component must never expose an administrative route.
- Bearer tokens and provider credentials must not enter request URLs, OAuth state, application logs, frontend bundles or public responses.
- OAuth account linking requires a short-lived, single-use transaction bound to its initiating user, provider and browser. Callbacks must validate that binding before storing credentials.
- HTTPS with certificate verification protects credentials in transit. Outbound destinations, redirects and protocols must respect the capability granted to their caller.
- Proxies and expensive operations authenticate where appropriate and apply explicit operation, input, concurrency and resource limits. CORS is not authentication.
- Browser messages validate both origin and sender window; native bridge messages must come from the trusted application origin and conform to supported bounded message shapes.
- Tests exercise missing, malformed, expired and wrong-purpose credentials, other-user objects, OAuth state misuse and unauthorized message senders.

## Reportable Findings and Severity Context
Report a demonstrated or source-backed violation with a realistic attacker, meaningful boundary crossing and concrete impact. Preserve route-specific prerequisites and effective controls. Separate confidence from severity. Missing production evidence is a limitation, not proof that a broken source control is safe.

## Out of Scope, Exclusions, and Accepted Risk
No vulnerability classes or known security failures are accepted or suppressed by this policy. Routine intentional public behavior is assessed against its stated data and capability limits.

## Known Limitations and Compensating Controls
Source review and local tests do not prove deployed configuration, credential rotation, provider settings or production authorization. Record those unknowns explicitly. Do not contact services or use discovered credentials merely to establish validity.

The Themed.AI branch additionally exposes an embedded workspace and native WebView2 bridge. Browser-origin and sender checks apply independently to each listener; native host communication must not broaden a browser page's authority.
