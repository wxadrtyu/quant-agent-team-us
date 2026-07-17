# 2026-07-10 US Remote Split

summary: Local Git remotes were split so the original A-share repository remains available while this workspace targets the independent US-stock repository.
stage: repository-setup
kpi_version: kpi-unset
tags:
  - project:quant-agent-team
  - market:cn_a
  - freq:daily
  - stage:repository-setup
  - status:local-memory-fallback
  - repo:quant-agent-team-us
next_step: Create or confirm the GitHub repository `wxadrtyu/quant-agent-team-us`, then push the desired branch when ready.

Details:
- `cn-a` remote preserves the original A-share repository: `https://github.com/wxadrtyu/quant-agent-team`.
- `origin` now points to the independent US-stock repository path: `https://github.com/wxadrtyu/quant-agent-team-us.git`.
- `git ls-remote https://github.com/wxadrtyu/quant-agent-team-us.git` returned `Repository not found` before the remote switch, so the GitHub repository may still need to be created.
- MCP memory tools were not available in this session, so this record is a local fallback per project policy.
