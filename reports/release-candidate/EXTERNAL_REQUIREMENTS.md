# Remaining access, resources and reviews

No secret values are requested in chat. Use owner dashboards, local secret stores and private environment injection.

| Requirement | Who supplies it | Exact purpose / gate |
| --- | --- | --- |
| Render workspace/service access or owner-assisted session | Existing deployment owner | Read exact deployed SHA/configuration; designate staging; approve drain/restart/deploy; capture hosted acceptance evidence |
| Explicit source publication authorization | Repository/deployment owner | Reviewed RC is only local. Render cannot deploy an uncommitted tree; future push or existing-registry image publication requires separate approval |
| Neon access and staging DB credentials | `pact-deploy` owner | Verify current target/schema/server, obtain matched backup, restore to approved empty target, run staging-only migration/drift checks |
| Existing isolated staging service/branch/prefix, or approval to provision missing isolation | Infrastructure owner | Avoid changing production/shared teammate data. New resources, plan upgrades and billing are not authorized |
| Private artifact storage credentials/policy and stable signing secret | Storage/app owner | Object read/write plus missing-key lookup permissions on the approved store, match database metadata, persistence over restart and original signature verification; AWS HEAD requires GetObject and missing-key 404 also depends on ListBucket |
| Docker/Podman engine or approved container build host | Local/CI infrastructure owner | Actual OCI build, base/image digest capture, image advisory scan, container PostgreSQL/storage/signal tests. Existing WSL Linux smoke has passed but has no container engine |
| Existing validated NVIDIA host and new staging-scoped runner credentials | Hardware owner + producer | One real hosted GPU job with pinned runtime/weights and measured output evidence. The same host can be reused; no second GPU is needed for a single-host hosted demo |
| Consumer/producer accounts, reviewer invitation/authority, operator availability | Demo owner/reviewer | Approve actual feasible policy, execute cross-tenant workflow, authorize/review recovery/restarts |
| Manual accessibility reviewer and assistive technology | Designated human reviewer | Native zoom, screen-reader announcements/reading order, populated forms/errors and chart comprehension; automation remains scoped |
| Exact GPU wheel advisory/provenance review | Security owner/vendor-capable reviewer | Close skipped torch/torchvision advisory coverage before production; record any scoped demo risk acceptance explicitly |
| Independent security and operational review | Security/operations owners | Public release gate: deployed threat review, SLO/monitoring, retention, incident/restore ownership, identity/accounting decisions |
| Two authorized hosts/teams, workload agreement and observation period | Pilot partners/owners | Restricted pilot gate; not a prerequisite for one-host academic hosted demonstration |
| Independent agreement/support labels and research/license review | Researchers/human annotators | Generalization/submission gate; do not invent labels or represent frozen modeled replay as measured field impact |
| LLM provider credentials/quota | Optional provider owner | Only if live assistance is part of the demo; deterministic fallback avoids this dependency |

The critical hosted path is: approved staging and source transfer → image gate → matched backup/restore and writer drain → schema/config deployment → durable-store and role checks → genuine hosted GPU run/recovery → human acceptance. Public production and partner-pilot requirements remain distinct. Nothing in this list authorizes production changes, new accounts or spending.
