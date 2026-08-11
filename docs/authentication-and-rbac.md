# Local Authentication and RBAC

## Scope and warning

The Identity Service contains a local, synthetic authentication and
role-based authorization foundation. It is for an academic development
environment only and must not be exposed as a public production identity
service.

Implemented:

- strict JSON login with pre-hashed synthetic fixture users;
- Argon2id password verification;
- short-lived HS256 JWT access tokens;
- Bearer authentication;
- current-user resolution;
- current-role permission derivation;
- credential sign/revoke permission enforcement;
- holder/verifier wallet, challenge, presentation create/read/verify
  permission enforcement;
- admin-only presentation reconciliation permission;
- application-layer wallet, credential, challenge, and presentation object
  authorization after RBAC.

A MongoDB user repository and authentication adapter are now available as an
explicit opt-in. There is no registration, user provisioning API, refresh
token, logout, token blacklist, session cookie, MFA, rate limiting, external
identity provider, password reset, or account recovery.

## Architecture

```text
FastAPI auth router / Bearer dependency
             |
             v
AuthenticationService ---- AuthorizationService
       |          |                 |
       v          v                 v
UserProvider  AccessTokenService  Permission policy
   /   \          |
  v     v         v
Fixture MongoDB  PyJWT HS256
       |
       v
Argon2PasswordHasher
```

Domain models contain public users, roles, permissions, principals, and token
claims without framework or third-party cryptography types. Password hashes
exist only in the infrastructure authentication record. Routers do not verify
passwords, encode JWTs, read the fixture registry, or inspect role strings.

## Synthetic users

The registry is immutable and non-persistent. All usernames use the reserved
`.test` domain.

| User | ID | Role | Development-only password |
| --- | --- | --- | --- |
| Local Admin | `usr_local_admin` | `admin` | `Admin-Prototype-2026!` |
| Local Issuer | `usr_local_issuer` | `issuer` | `Issuer-Prototype-2026!` |
| Local Verifier | `usr_local_verifier` | `verifier` | `Verifier-Prototype-2026!` |
| Local Holder | `usr_local_holder` | `holder` | `Holder-Prototype-2026!` |
| Disabled Local User | `usr_local_disabled` | `verifier` (disabled) | `Disabled-Prototype-2026!` |

These passwords are public synthetic test inputs, not production credentials.
Application runtime records contain only pre-generated Argon2id hashes. Fixture
users can be disabled through configuration and are rejected in
production-like mode.

## Roles and permissions

| Role | Credential permissions | Wallet/challenge/presentation permissions | Managed-key permissions |
| --- | --- | --- | --- |
| `admin` | All | Enum permissions are broad; object ownership still applies; manual reconcile allowed | All key permissions; elevated compromise, destruction, and reconciliation routes |
| `issuer` | All | Legacy broad enum permissions; no wallet ownership bypass; manual reconcile explicitly denied | None |
| `verifier` | Validate, verify, self-read | Issue/read authorized challenges; read/verify related presentations | None |
| `holder` | Self-read only | Create/read owned wallets, list owned credentials, read authorized challenges, create/read owned presentations | Create/read/rotate/suspend/resume/revoke owned wallet keys |

Roles and permissions are closed enums. Duplicate roles are normalized and
unknown roles are rejected. JWT role claims are not the current authorization
authority: every protected request resolves `sub` in the user provider again,
checks enabled state, and compares token roles with the current user roles.
Permissions are then derived from the current registry state.

RBAC is not object ownership. Wallet, inventory, challenge, and presentation
services compare the current principal ID with persisted owner/issuer
relationships. Admin or issuer permission does not silently grant another
user's wallet, credential, holder DID, or presentation. Foreign and absent
object reads intentionally return the same `404`. The only administrative
override is the explicit, audited, admin-only stale-presentation reconciliation
operation; it does not bypass holder proof or credential binding checks.

## Password hashing

`argon2-cffi==25.1.0` performs Argon2id hashing and verification. Project code
does not implement a password hash algorithm. Every fixture stores its
parameters in the Argon2id hash record; the adapter verifies those records
without exposing them. Test-only adapter instances may use smaller memory
parameters to keep unit tests fast.

These parameters are bounded prototype choices, not production tuning.
Production deployment requires workload-specific benchmarking, resource
limits, rehash policy, secret handling, monitoring, and independent review.

Unknown usernames still run Argon2 verification against a fallback hash to
reduce simple timing-based user enumeration. Login failures return the same
public code and message for unknown usernames, wrong passwords, and disabled
fixture accounts.

## JWT access tokens

`PyJWT==2.13.0` performs JWT serialization, signature verification, issuer
validation, and audience validation. Only `HS256` is allowed. `alg=none` and
all other algorithms are rejected before decode.

Required claims:

| Claim | Meaning |
| --- | --- |
| `iss` | Configured local token issuer |
| `sub` | Internal synthetic user ID |
| `aud` | `identity-service` by default |
| `iat` | UTC issue time |
| `nbf` | UTC not-before time |
| `exp` | Mandatory short expiration |
| `jti` | Cryptographically random token identifier |
| `roles` | Closed role snapshot, rechecked against current provider state |
| `token_use` | Must equal `access` |

The default lifetime is 900 seconds and default clock skew is 10 seconds.
Signature, algorithm, issuer, audience, required claims, token use, current
time window, maximum lifetime, role allowlist, user existence, user enabled
state, and role consistency are checked.

HS256 uses one shared secret and is deliberately limited to this local
prototype. A production system needs managed signing keys, rotation, access
policy, audit, incident handling, and preferably an externally reviewed
identity architecture.

## Configuration

| Variable | Development default |
| --- | --- |
| `IDENTITY_ENVIRONMENT` | `development` |
| `IDENTITY_AUTH_ENABLED` | `true` |
| `IDENTITY_AUTH_JWT_ISSUER` | `secure-ssi-identity-service` |
| `IDENTITY_AUTH_JWT_AUDIENCE` | `identity-service` |
| `IDENTITY_AUTH_ACCESS_TOKEN_SECONDS` | `900` |
| `IDENTITY_AUTH_JWT_ALGORITHM` | `HS256` |
| `IDENTITY_AUTH_JWT_SECRET` | Empty; uses an explicitly public development fallback |
| `IDENTITY_AUTH_FIXTURE_USERS_ENABLED` | `true` |
| `IDENTITY_AUTH_CLOCK_SKEW_SECONDS` | `10` |
| `IDENTITY_AUTH_USER_PROVIDER` | `synthetic` |
| `MAX_AUTH_REQUEST_BYTES` | `4096` |

The secret must contain at least 32 UTF-8 bytes. Only HS256 is accepted.
Lifetime and clock skew have bounded ranges. In `production`, `prod`, or
`staging`, a missing secret fails startup and fixture users must be disabled.
The development fallback is public source material and provides no production
security.

Selecting `mongodb` requires enabled Mongo persistence and pre-provisioned
users with Argon2 hashes. The synthetic provider remains the default; no
database users are seeded automatically. See
[mongodb-persistence.md](mongodb-persistence.md).

## HTTP API

### Create a token

```http
POST /api/v1/auth/token
Content-Type: application/json
```

```json
{
  "username": "issuer@example.test",
  "password": "Issuer-Prototype-2026!"
}
```

Success returns `200`, `Cache-Control: no-store`, and `Pragma: no-cache`:

```json
{
  "accessToken": "<short-lived-jwt>",
  "tokenType": "Bearer",
  "expiresIn": 900,
  "user": {
    "id": "usr_local_issuer",
    "username": "issuer@example.test",
    "displayName": "Local Issuer",
    "roles": ["issuer"],
    "permissions": [
      "auth:self:read",
      "credentials:sign",
      "credentials:validate",
      "credentials:verify"
    ]
  }
}
```

### Read the current user

```http
GET /api/v1/auth/me
Authorization: Bearer <access-token>
```

The response returns the current public user, roles, permissions, and
`authenticationSource: local-synthetic-fixture` or `mongodb`. It never returns
the raw JWT, password, password hash, or JWT secret.

### Sign a credential

```http
POST /api/v1/credentials/sign
Authorization: Bearer <access-token>
```

`admin` and `issuer` can sign. `verifier` receives `403`. Authentication and
authorization are evaluated before the credential signing method is called.

### Revoke a credential

```text
POST /api/v1/credentials/{credentialId}/revoke
Authorization: Bearer <access-token>
```

The request requires `credentials:revoke`. Only current enabled `admin` and
`issuer` principals receive that permission. A `verifier` receives `403`
before the revocation service is called. Revocation is a terminal,
optimistically versioned MongoDB transition and cannot be undone.

### Holder wallet, challenge, and presentation operations

```text
POST /api/v1/wallets
GET /api/v1/wallets/{walletId}
GET /api/v1/wallets/{walletId}/credentials
POST /api/v1/presentation-challenges
GET /api/v1/presentation-challenges/{challengeId}
POST /api/v1/presentations/create
POST /api/v1/presentations/verify
GET /api/v1/presentations/{presentationId}
POST /api/v1/presentations/{presentationId}/reconcile
```

All require Bearer authentication and an explicit permission. Wallet and
inventory operations also require owner equality. Challenge reads require the
issuing verifier or the owner of the requested holder DID. Presentation reads
require the wallet owner or challenge issuer. Creation requires the wallet
owner and exact credential ownership. Reconciliation requires the admin role
in addition to `presentations:reconcile`.

### Managed-key operations

The eleven routes under `/api/v1/wallets/{walletId}/keys` require explicit
`wallet:key:*` or `admin:key:reconcile` permissions. Holder create, read,
rotate, suspend, resume, and revoke operations also enforce persisted wallet
and key ownership. Normal admin read permission does not bypass ownership.
Compromise, delayed destruction/cancellation, and manual reconciliation are
explicit elevated admin operations. Issuer and verifier roles receive no
managed-holder-key permissions. Foreign and absent key reads intentionally
return the same `404`; rejected foreign access is durably audited when a
matching key can safely be identified.

Creation and rotation also require `Idempotency-Key`. Destruction requires a
reason and exact key-ID confirmation. See
[external-kms-key-lifecycle.md](external-kms-key-lifecycle.md).

The following remain public:

- `GET /health`;
- `GET /api/v1/credentials/capabilities`;
- `GET /api/v1/credentials/{credentialId}/status`;
- `POST /api/v1/credentials/validate`;
- `POST /api/v1/credentials/verify`;
- `POST /api/v1/auth/token`.

## Authentication errors

Errors retain the central API shape:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid username or password.",
    "details": []
  },
  "requestId": "request-123"
}
```

`401` means credentials are absent or cannot authenticate a current enabled
user. It includes `WWW-Authenticate: Bearer` where appropriate. `403` means a
valid authenticated user lacks the required permission. Configuration failures
return a sanitized `500`.

## Logging and token lifecycle

Passwords, request bodies, Authorization headers, full JWTs, password hashes,
JWT secrets, credential proof values, and credentials are not logged.
Request IDs are correlation values only and are not durable audit records.

Access tokens are short-lived, but there is no immediate blacklist or token
revocation after issuance. Disabled and role state is rechecked on every
request, which prevents a token from overriding current provider state. The
new Mongo repositories do not implement token revocation or refresh-token
rotation; those workflows remain explicitly deferred.

## Dependency notes

- `argon2-cffi==25.1.0`: production/stable typed package, MIT license; wraps
  the established Argon2 implementation.
- `PyJWT==2.13.0`: production/stable package, MIT license; provides the bounded
  JWT implementation used here.

Both are pinned. Dependency health, release changes, cryptographic guidance,
and production configuration must be reviewed before any external deployment.
