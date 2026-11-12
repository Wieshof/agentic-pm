# Operational Guardrails & Success Metrics

🇬🇧 English · 🇩🇪 [Deutsch](de/guardrails.md)

Giving an AI write access to project repositories and direct communication channels needs clear boundaries so the team can trust it.

## Tiered write permissions

| Tier | Examples | Behaviour |
|------|----------|-----------|
| **Low risk** | Log comments, attach retroactive docs, tag blockers, add labels | Runs automatically, with an audit trail |
| **Medium risk** | Change internal due dates, update status on the owner's behalf | Runs automatically if the owner confirmed in-channel; otherwise asks the owner |
| **High impact** | Delete tasks, reassign owners, move external/client deadlines | **Confirmation prompt to the relevant team lead** before running |

Tiers can be configured per project in `.agent-pm/policy.yaml` (planned).

## Consent & privacy

- Outbound and inbound voice calls include an **automatic disclosure** when transcription is active.
- All conversation logs are **scoped strictly to the project workspace**.
- **No training** of external foundation models on project data.
- Voice transcripts are kept only in RAM for the call's duration (see [data model](data-model.md)).
- Personal preferences stay in the user's own control (`team.yaml` / SSO).

## Target KPIs

| KPI | Target |
|-----|--------|
| Reduction in manual ticket-editing time | > 70 % |
| Mean time to surface a dependency blocker | < 2 h from status change |
| Cross-modality engagement rate | % of team members actively updating tickets via their chosen channel |

### Secondary (infrastructure-reduction) indicators

- Number of shadow trackers / reporting plugins decommissioned
- Tracker seats saved through proxy interaction
- Share of closed tickets with an attached how-to section
