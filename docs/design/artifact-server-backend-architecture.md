# Artifact Review Backend Architecture

## Scope

This document designs the C#/.NET backend that replaces the HTTP serving parts of `review-serve.py` while preserving the parity contract in `docs/design/artifact-server-parity-spec.md`.

The first implementation target is server parity. The existing Python `push`, `feedback`, and deployment CLI paths can keep working during migration because the .NET backend reads and writes the same staging tree and SQLite database.

Non-goals for the first backend slice:

- No new authentication model.
- No heavyweight ORM.
- No dynamic deep-zoom tile generation.
- No same-origin HTTP publish route for active content.
- No path that tears down host Tailscale Serve mappings.

## Stack and project layout

### Runtime choice

Use ASP.NET Core Minimal APIs on the current .NET LTS SDK, targeting `net10.0` unless the implementation environment only has an older supported LTS SDK already standardized for this repo.

Minimal APIs fit the parity surface because the routes are small, explicit, and mostly map directly to current `BaseHTTPRequestHandler` methods. MVC would add controllers, model binding conventions, and filter behavior that are not needed for parity and can hide contract details that must stay exact.

### NuGet dependencies

| Package | Purpose | Notes |
|---|---|---|
| `Microsoft.Data.Sqlite` | Existing `feedback.db` access | Required. Use direct SQL and migrations. |
| `Microsoft.AspNetCore.StaticFiles` | MIME mapping | Usually part of the shared framework, add only if needed. |
| `Microsoft.AspNetCore.Mvc.Testing` | In-process API tests | Test project only. |
| `xunit` | API and persistence tests | Test project only. |
| `FluentAssertions` | Readable test assertions | Test project only, optional. |

Do not add Entity Framework Core unless a later implementation proves direct SQL cannot keep the schema contract clear. The existing schema is small, stable, and query shapes are simple.

### Directory layout

```text
apps/artifact-review/backend/
  ArtifactReview.sln
  src/
    ArtifactReview.Backend/
      ArtifactReview.Backend.csproj
      Program.cs
      AppOptions.cs
      Routes/
        ApiRoutes.cs
        ReviewRoutes.cs
        StaticArtifactRoutes.cs
        VendoredAssetRoutes.cs
      Artifacts/
        ArtifactIdentity.cs
        ArtifactPaths.cs
        ArtifactUrlResolution.cs
        DirectoryGallery.cs
        HtmlFeedbackInjection.cs
      Feedback/
        AnchorValidation.cs
        FeedbackJson.cs
        RequestLimits.cs
        UploadValidation.cs
      Persistence/
        FeedbackDatabase.cs
        FeedbackSchema.cs
        FeedbackQueries.cs
        FeedbackWrites.cs
      Board/
        BoardMirror.cs
        BoardCommand.cs
      Security/
        PublishPolicy.cs
        RemoteFetchGuard.cs
        ResponseHeaders.cs
      Web/
        ReviewPages.cs
        PageFeedbackWidget.cs
        StaticAssets.cs
  tests/
    ArtifactReview.Backend.Tests/
      ArtifactReview.Backend.Tests.csproj
      ApiParityTests.cs
      FeedbackDatabaseTests.cs
      StaticArtifactTests.cs
      PublishPolicyTests.cs
      RemoteFetchGuardTests.cs
      TestArtifactServer.cs
```

Names use the domain object or effect. Avoid `Manager`, `Helper`, and broad `Service` types. `Routes` files only map HTTP endpoints to named functions. Business behavior lives under the domain folders.

### Configuration

Use environment variables matching the current server:

| Variable | Default | Meaning |
|---|---|---|
| `REVIEW_SERVE_HOST` | `127.0.0.1` for local run, `0.0.0.0` in container | Kestrel bind host. |
| `REVIEW_SERVE_PORT` | `9099` | Kestrel bind port. |
| `REVIEW_SERVE_STAGE_ROOT` | `/tmp/claude-artifacts` | Staged artifact symlink tree. |
| `REVIEW_SERVE_FEEDBACK_ROOT` | `~/.local/share/claude-artifacts` | Durable DB and upload root. |
| `REVIEW_SERVE_ASSETS_ROOT` | bundled backend static asset directory | Vendored OpenSeadragon, Annotorious, CSS, and images. |
| `REVIEW_SERVE_PUBLISH_ENABLED` | `0` | HTTP publish route is disabled until the non-active policy is implemented and tested. |

Kestrel should bind with explicit URLs built from host and port:

```text
http://{REVIEW_SERVE_HOST}:{REVIEW_SERVE_PORT}
```

## API contract

The backend must match the current HTTP contract exactly unless a row below says otherwise. JSON names stay snake_case where the Python server emits snake_case.

| Method | Route | .NET route function | Request DTO | Response DTO | Status codes | Parity notes |
|---|---|---|---|---|---|---|
| GET | `/` | `GetRootIndex` | none | HTML bytes | 200, normal static 404 | Serve `/tmp/claude-artifacts/index.html`. This remains the healthcheck route. |
| GET | `/_/assets/{**rel}` | `GetVendoredAsset` | route `rel` | asset bytes | 200, 404 | Resolve under `REVIEW_SERVE_ASSETS_ROOT`; reject traversal after full path resolution. |
| GET | `/_/api/settings` | `GetSettings` | none | `Dictionary<string,string>` | 200, 500 `{error}` | Opens or creates DB and returns all rows from `setting`. |
| GET | `/_/api/uploads/{id:int}` | `GetUpload` | route `id` | upload bytes | 200, 404, 410, 500 | Preserve `Content-Type`, `Content-Length`, `X-Content-Type-Options: nosniff`, and inline or attachment disposition rules. |
| GET | `/_/api/threads` | `ListThreads` | query `artifact`, `sub_path`, or `url` | `ThreadListResponse` | 200, 404, 500 | Resolve by explicit artifact or by static URL path. `sub_path` defaults to empty. |
| POST | `/_/api/threads` | `CreateThread` | multipart form | `CreateThreadResponse` | 201, 400, 411, 413, 500 | Requires `Content-Length`; creates one thread, one opening reply, optional uploads, optional bd ticket. |
| POST | `/_/api/threads/{id:int}/replies` | `CreateReply` | multipart form | `CreateReplyResponse` | 201, 400, 404, 411, 413, 500 | Requires existing thread; best-effort bd comment if mirrored. |
| POST | `/_/api/threads/{id:int}/resolve` | `SetThreadResolved` | optional JSON object | `ResolveThreadResponse` | 200, 400, 404, 411, 413 | Empty body toggles. `{ "resolved": value }` coerces value to bool like Python `bool(...)`. |
| GET | `/_/api/comments` | `ListLegacyComments` | query `artifact`, `sub_path`, or `url` | `LegacyCommentListResponse` | 200, 404, 500 | Page-anchor shim only. |
| POST | `/_/api/comments` | `CreateLegacyComment` | multipart form | `CreateLegacyCommentResponse` | 201, 400, 411, 413, 500 | Creates a page-level thread and opening reply. Mirrors like `CreateThread`. |
| GET | `/_/review` | `GetReviewPage` | query `artifact`, `view`, `src`, `path` | HTML | 200, 400, 404 | No view renders gallery. `view=image` renders simple-image OpenSeadragon. `view=code` renders escaped line viewer. |
| GET | `/{project}/{subdir}/{**rel}` | `GetStaticArtifact` | path segments | static bytes or generated HTML | 200, 301, 404, standard static statuses | Serve staged files. Rewrite `text/html` responses with feedback widget. Generate themed directory gallery when no `index.html` exists. |
| GET | `/{project}/{subdir}/{dir}/` | `GetStaticArtifactDirectory` | path segments | generated HTML or static index | 200, standard static statuses | Same route function as static artifact. Direct child dirs, images, code files, and raw fallback links match Python behavior. |
| POST | `/_/api/publish` | `PublishArtifact` | disabled by default | not part of parity | 404 or 501 while disabled | Not in current deployed parity surface. If implemented, it must use the publish policy in this document and reject active types. |

### DTO shapes

Use records for JSON responses and multipart projections. JSON serialization must preserve names from the parity spec:

```text
ThreadListResponse: artifact_id, sub_path, threads[]
ThreadDto: id, sub_path, anchor_kind, anchor, resolved, author, created_at, created_at_iso, bd_ticket, replies[]
ReplyDto: id, body, author, created_at, created_at_iso, uploads[]
UploadDto: id, filename, stored_path, mime, size, created_at, created_at_iso
LegacyCommentDto: id, thread_id, sub_path, body, author, created_at, created_at_iso, resolved, uploads[]
```

Use `JsonPropertyName` rather than changing public property names to snake_case. C# property names stay idiomatic, for example `ArtifactId` with `[JsonPropertyName("artifact_id")]`.

### Request validation

Keep the current limits:

| Input | Rule |
|---|---|
| Request body | `Content-Length` required, integer, non-negative, max 500 MB. |
| Comment body | Required after trim, max 20,000 chars, stored trimmed. |
| Author | Optional after trim. If absent, use `setting.author` when present. |
| Upload file | Max 100 MB each. |
| Upload name | Basename only, replace non `[A-Za-z0-9._-]` with `_`, strip leading dots, cap 200 chars, collision suffix `-1`, `-2`. |
| Anchor JSON | Max 8 KiB, object only for non-page anchors. |
| Page anchor | `anchor_data` absent or blank. |
| Image anchor | `FragmentSelector` only, value matches `xywh=(pixel:|percent:)?n,n,n,n`; reject `SvgSelector`. |
| Code anchor | `line` integer >= 1; optional `end_line` integer >= `line`; reject booleans. |

Multipart handling should reject non-multipart POSTs before reading the body. Do not buffer entire uploads into memory. Stream each allowed file to a temporary file under the final upload directory, then move into place after size and name checks pass.

## Data layer

### Storage locations

Use the same paths as `review-serve.py`:

| Resource | Path |
|---|---|
| Stage root | `/tmp/claude-artifacts` |
| Root index | `/tmp/claude-artifacts/index.html` |
| Server pid | `/tmp/claude-artifacts/.serve.pid` |
| Server port | `/tmp/claude-artifacts/.serve.port` |
| Server log | `/tmp/claude-artifacts/.serve.log` |
| Feedback DB | `~/.local/share/claude-artifacts/feedback.db` |
| Upload files | `~/.local/share/claude-artifacts/uploads/<reply-id>/<filename>` |

The .NET server must not move the database or restage artifacts. Existing Python `push` and `feedback` commands continue to work because they read and write these same locations.

### SQLite access

Use `Microsoft.Data.Sqlite` with direct SQL:

- Connection string points at `feedback.db` with a 10 second timeout.
- Open one connection per HTTP operation.
- Execute `PRAGMA foreign_keys = ON` after every open.
- Run schema creation and v1 to v2 migration during startup.
- Also allow `GetSettings` to ensure schema, preserving the current route behavior.
- Use transactions for every multi-row write and the migration.
- Store epoch seconds as `INTEGER` and render ISO timestamps as UTC strings.

A small `FeedbackDatabase` type owns connection creation and schema migration. Query and write functions receive an open connection and transaction when needed. This keeps tests able to assert exact SQL behavior without a hidden ORM layer.

### Schema mapping

| Existing table | .NET record or query model | Notes |
|---|---|---|
| `artifact_index` | `ArtifactIndexRow` | Primary key `(project, subdir)`. Used by URL resolution and feedback read-back. |
| `setting` | `SettingRow` | Keys include `schema_version`, `author`, `bd_mirror`. |
| `thread` | `ThreadRow` | Canonical feedback thread. `anchor_data` stored as compact JSON or null. |
| `reply` | `ReplyRow` | Belongs to `thread`. Opening reply created in same transaction as thread. |
| `upload` | `UploadRow` | May point at `reply_id` or legacy `comment_id`. New writes use `reply_id`. |
| `comment` | `LegacyCommentRow` | Existing flat comment table retained for migration and feedback compatibility. |

Indexes must be created exactly as in the parity spec:

```text
idx_index_artifact on artifact_index(artifact_id)
idx_comment_artifact_path on comment(artifact_id, sub_path)
idx_thread_artifact_path on thread(artifact_id, sub_path)
idx_reply_thread on reply(thread_id)
idx_upload_reply on upload(reply_id)
idx_upload_comment on upload(comment_id)
```

### Migration behavior

Preserve the current idempotent migration:

1. Create missing v2 tables and indexes.
2. If `setting.schema_version` is absent or less than `2`, rebuild legacy `upload` when it lacks `reply_id`.
3. Copy each legacy `comment` row into one page-level `thread` and one opening `reply` in comment id order.
4. Remap uploads for the legacy comment to the new reply.
5. Set `setting.schema_version` to `2`.
6. Commit all migration work in one transaction.

Tests should run this migration against a real temporary SQLite file with seeded v1 data.

### bd-board mirror behavior

Keep the mirror behavior exactly. It is best effort and never fails an HTTP write.

| Trigger | .NET action | Failure behavior |
|---|---|---|
| Create thread | If `setting.bd_mirror == "1"`, find the artifact project, run `agent-workbench hub path <project>`, then run `bd create <title>` with `BEADS_DIR` set to that path. Store the first whitespace token of stdout in `thread.bd_ticket`. | Swallow missing CLI, timeout, non-zero exit, parse failure, DB update failure, and unknown project. Return the HTTP success without a ticket. |
| Add reply | If `thread.bd_ticket` exists, run `bd comment <ticket> <reply body>` in the same board. | Best effort warning only. |
| Resolve or reopen | If `thread.bd_ticket` exists, run `bd close <ticket>` when resolved, else `bd reopen <ticket>`. | Best effort warning only. |

`BoardMirror` should use `ProcessStartInfo` with an explicit environment dictionary and short timeout. It must never invoke a shell. It must not assume the CLI exists in the container.

## Static and artifact serving

### Route ordering

Register routes in this order:

1. `/_/api/*`
2. `/_/assets/*`
3. `/_/review`
4. `/`
5. `/{project}/{subdir}/{**rel}` catch-all static artifact route

The reserved `/_/` namespace remains safe because project and subdir names must match `^[a-z0-9][a-z0-9_-]*$`.

### Artifact-id resolution

For static URL resolution:

1. Split the URL path.
2. Require at least two segments.
3. Validate `project` and `subdir` with the parity name regex.
4. Look up `(project, subdir)` in `artifact_index`.
5. If found, use stored `artifact_id`; otherwise use `<project>/<subdir>`.
6. Join remaining segments with `/` as `sub_path`.

For review pages, resolve the artifact location by `artifact_id`. `src` and `path` are relative paths under the staged artifact root. The final file path must be resolved and verified under the staged root before reading.

### Staging path mapping

The server serves from the existing symlink tree:

```text
/tmp/claude-artifacts/<project>/<subdir> -> pushed source directory
```

The server does not create or rewrite those symlinks in the backend parity slice. The existing push CLI keeps responsibility for staging and for updating `artifact_index`.

Preserve these current footguns unless a later CLI migration deliberately fixes them with tests:

- Push can destroy a self-referencing staging symlink target.
- Symlink targets outside the container mounts serve 404 from the container.
- Reachable files under pushed symlink targets are reachable.
- `/tmp` staging wipes on reboot.

### HTML feedback injection

For raw static `text/html` artifact responses:

- Decode enough to inject the page feedback widget before `</body>`.
- Append the widget if no closing body tag exists.
- Omit `Content-Length` after rewriting.
- Preserve user text safety by rendering comments with `textContent` in the widget.
- Fetch settings and threads with the same URLs used by the current widget.

Non-HTML files stream normally. Upload responses and published non-active files must include `X-Content-Type-Options: nosniff`.

### Directory gallery

When a static path is a directory and no `index.html` exists, render themed gallery HTML that lists direct children only:

| Child type | Link target |
|---|---|
| Directory | Raw directory URL with trailing slash. |
| Image extension | `/_/review?artifact=<id>&src=<rel>&view=image` |
| Code extension | `/_/review?artifact=<id>&src=<rel>&view=code` |
| Other file | Raw static URL. |

Image and code extension lists must match the parity spec.

### Review pages and tile behavior

`/_/review?artifact=<id>` renders a gallery for the artifact root or the requested `path`.

`view=image` renders OpenSeadragon in simple-image mode:

- Load `/_/assets/openseadragon/openseadragon.min.js`.
- Load `/_/assets/annotorious/annotorious-openseadragon.min.js`.
- Load `/_/assets/annotorious/annotorious.min.css`.
- Use `tileSources: { type: 'image', url: IMAGE_URL }`.
- Use `prefixUrl: '/_/assets/openseadragon/images/'`.
- Fetch and post image-region threads exactly as the parity spec describes.

There is no dynamic DZI endpoint in parity. The only tile-like route is the vendored OpenSeadragon image asset path under `/_/assets/openseadragon/images/`. If a future deep-zoom route is added, it must use the same staged-root path guard as `view=image` and must not fetch remote tiles server-side without `RemoteFetchGuard`.

`view=code` renders a UTF-8 text view with replacement for invalid bytes, escaped lines, clickable `data-line` elements, line-thread grouping, and resolve or reopen calls to `POST /_/api/threads/<id>/resolve`.

## Publish safety decision

Decision: restrict HTTP publish to non-active file types. Do not ship a same-origin `POST /_/api/publish` route that can write HTML, SVG, JavaScript, or other active browser content.

Justification:

- The service has no authentication and relies on a trusted tailnet.
- Review APIs are same-origin and unauthenticated.
- CLI push requires local shell access, but HTTP publish would allow any network writer to plant content.
- Restricting publish to non-active types preserves the existing viewer and feedback widget behavior for local CLI-pushed artifacts.
- It is the shortest safe mitigation and does not require a second origin, reverse proxy split, or widget redesign.

Exact publish policy when `POST /_/api/publish` is implemented:

| Control | Required behavior |
|---|---|
| Default state | `REVIEW_SERVE_PUBLISH_ENABLED=0`; route returns 404 or 501 until enabled by deployment config. |
| Extension allowlist | Match the upload allowlist: `.png .jpg .jpeg .webp .gif .bmp .tif .tiff .pdf .txt .md .log .csv .json .yaml .yml .toml .zip .tar .gz .7z .fig .psd .xcf .sketch .mp4 .webm .mov`. |
| Active extension blocklist | Always reject `.html .htm .xhtml .svg .js .mjs .exe .dll .sh .bash .zsh .bat .cmd .ps1 .com`, even if a future allowlist is edited incorrectly. |
| MIME rejection | Reject `text/html`, `image/svg+xml`, `application/javascript`, `text/javascript`, `application/ecmascript`, and `text/ecmascript`. Extension checks remain authoritative because MIME can lie. |
| Path safety | Publish only under a new staged artifact directory selected by validated project, subdir, and artifact id. Reject path traversal after full path resolution. |
| Response headers | Published file responses include `X-Content-Type-Options: nosniff`. Content-Disposition follows the upload route rule: inline only for known safe image, PDF, and plain text types; attachment otherwise. |
| Tests | Add table-driven tests for every allowed extension, every blocked active extension, MIME mismatch, traversal, oversized body, and same-origin script planting regression. |

This does not change current parity endpoints, so the `artifact-serve` skill can keep working unchanged. If a future skill version starts using HTTP publish, it must document the non-active allowlist and tell agents to use CLI push for HTML review pages.

A token write gate can be added later, but it does not replace this same-origin active-content mitigation.

## SSRF guard

The parity backend should not fetch arbitrary remote URLs. If any server-side fetch is added later, including publish by URL, import by URL, clipping, preview generation, metadata extraction, or remote tiles, use `RemoteFetchGuard` based on the closed `agent-workbench-h5u` pattern from `scripts/kb-clip.py`.

Required behavior:

1. Parse the URL and require `http` or `https`.
2. Resolve the hostname with `Dns.GetHostAddressesAsync` before connecting.
3. Reject loopback, private, link-local, multicast, unspecified, reserved, and IPv4-mapped forms of those ranges.
4. Explicitly reject cloud metadata `169.254.169.254`.
5. Explicitly reject CGNAT and Tailscale range `100.64.0.0/10`.
6. Disable automatic redirects with `AllowAutoRedirect = false`.
7. For each redirect, resolve and validate the next URL before following it.
8. Fail closed on DNS errors, parse errors, too many redirects, unsupported schemes, or any validation uncertainty.

Address ranges to reject include at least:

| Family | Ranges |
|---|---|
| IPv4 | `0.0.0.0/8`, `10.0.0.0/8`, `100.64.0.0/10`, `127.0.0.0/8`, `169.254.0.0/16`, `172.16.0.0/12`, `192.168.0.0/16`, multicast, reserved, and `169.254.169.254/32`. |
| IPv6 | `::/128`, `::1/128`, IPv4-mapped rejected after mapping check, `fc00::/7`, `fe80::/10`, multicast `ff00::/8`, and reserved ranges that .NET marks non-global. |

Tests must include initial URL denial and redirect-hop denial for each protected range.

## Container hardening plan

### Image

Use a multi-stage Containerfile:

```text
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble@sha256:<pinned-sdk-digest> AS build
WORKDIR /src
COPY apps/artifact-review/backend/ ./apps/artifact-review/backend/
RUN dotnet publish apps/artifact-review/backend/src/ArtifactReview.Backend/ArtifactReview.Backend.csproj -c Release -o /out /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble-chiseled@sha256:<pinned-runtime-digest>
WORKDIR /app
COPY --from=build /out ./
USER $APP_UID
ENV ASPNETCORE_URLS=http://0.0.0.0:9099
ENV REVIEW_SERVE_HOST=0.0.0.0
ENV REVIEW_SERVE_PORT=9099
HEALTHCHECK CMD curl -fsS http://127.0.0.1:9099/ || exit 1
ENTRYPOINT ["dotnet", "ArtifactReview.Backend.dll"]
```

Before implementation merges, replace placeholder digests with real digests. The digest pin is mandatory.

If the chiseled runtime image lacks `curl`, use a tiny self-contained healthcheck binary or switch to an aspnet image variant that contains a supported healthcheck tool. Do not add a shell just for convenience unless the final image remains slim and pinned.

### Runtime controls

Keep the current hardening controls:

| Control | Required config |
|---|---|
| Host bind | Publish only `127.0.0.1:9099:9099`. |
| App bind in container | `0.0.0.0:9099`. |
| Root filesystem | Read-only. |
| Capabilities | `cap_drop: [ALL]` or Quadlet `DropCapability=ALL`. |
| Privilege escalation | `no-new-privileges:true` or Quadlet `NoNewPrivileges=true`. |
| User | Rootless user, `User=%U`, `Group=%U`, `UserNS=keep-id` for Quadlet, UID and GID mapping for compose. |
| Tmpfs | `/tmp` tmpfs, with `/tmp/claude-artifacts` bind-mounted over the staging path when serving host-staged artifacts. |
| Mounts | Only `/tmp/claude-artifacts:/tmp/claude-artifacts:rw` and `~/.local/share/claude-artifacts:~/.local/share/claude-artifacts:rw`. No `$HOME`-wide mount. |
| Healthcheck | GET `http://127.0.0.1:9099/`. |
| SELinux | Preserve the current narrow bind behavior. If label disabling is needed, scope it to this container only. |

### Tailscale Serve

Host exposure remains outside the app:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:9099
```

The backend, container entrypoint, deploy scripts, and shutdown scripts must not call `tailscale serve --https=443 off`. Bundle-owned stop paths should stop only the app container or user service.

## Build and test seams

### Local build

From repo root:

```bash
dotnet restore apps/artifact-review/backend/ArtifactReview.sln
dotnet build apps/artifact-review/backend/ArtifactReview.sln --configuration Release
dotnet test apps/artifact-review/backend/ArtifactReview.sln --configuration Release
```

### Local run

Server-only local run:

```bash
REVIEW_SERVE_STAGE_ROOT=/tmp/claude-artifacts \
REVIEW_SERVE_FEEDBACK_ROOT="$HOME/.local/share/claude-artifacts" \
REVIEW_SERVE_HOST=127.0.0.1 \
REVIEW_SERVE_PORT=9099 \
dotnet run --project apps/artifact-review/backend/src/ArtifactReview.Backend/ArtifactReview.Backend.csproj
```

During migration, stage artifacts with the existing CLI:

```bash
python3 ~/.claude/skills/artifact-serve/scripts/review-serve.py push --project NAME --src /path/to/dir --id NAME/subdir
```

Then open:

```text
http://127.0.0.1:9099/_/review?artifact=NAME/subdir
```

### Required tests

| Test group | Required proof |
|---|---|
| API parity | Every route in the API table returns the same status codes and JSON shapes as the Python tests cover. |
| Publish to viewer to feedback loop | Stage an artifact, open gallery, open image review, create image-region thread, add reply, resolve, then read back through `feedback --artifact`. |
| Page widget loop | Serve a static HTML artifact, verify widget injection, create a page thread, upload an allowed file, and read upload bytes. |
| Code viewer loop | Open code view, create a `code_line` thread, verify escaped source and line grouping. |
| Legacy comments | `GET` and `POST /_/api/comments` preserve flattened page-comment compatibility. |
| SQLite migration | v1 DB migrates to schema version 2, remaps uploads, and remains idempotent. |
| Upload validation | Allowed and blocked extensions, filename sanitizer, body limits, missing `Content-Length`, and oversized uploads. |
| Artifact paths | Traversal rejection, symlink staging lookup, unknown artifact fallback, and `url` to artifact resolution. |
| bd mirror | With fake `agent-workbench` and `bd` commands, create, comment, close, and reopen calls are attempted and failures do not fail HTTP writes. |
| Publish policy | HTTP publish is disabled by default and rejects active extensions and MIME types when enabled. |
| SSRF guard | Initial URL and redirect hops reject protected address ranges. |
| Container | Healthcheck passes, rootfs is read-only, only narrow mounts are present, and host bind is `127.0.0.1:9099`. |

Use `WebApplicationFactory` for in-process API tests and temporary directories for stage and feedback roots. Do not use the real user feedback DB in tests.

### Implementation slices

The design supports independent implementation slices:

1. Project skeleton, options, Kestrel binding, root index route, and healthcheck.
2. SQLite schema, migration, settings, thread, reply, upload, and feedback queries.
3. Multipart validation and upload storage.
4. Static artifact serving, HTML injection, directory gallery, and vendored assets.
5. Review gallery, image viewer, and code viewer pages.
6. bd-board mirror.
7. Publish policy scaffold with route disabled by default.
8. Containerfile, compose or Quadlet updates, and integration tests.

Each slice should keep parity tests green before moving to the next slice.
