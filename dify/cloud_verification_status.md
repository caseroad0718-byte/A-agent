# Dify Cloud Verification Status

Generated: 2026-06-04 10:00 Asia/Shanghai

Machine-readable status: `dify/cloud_verification_status.json`

Current gate summary: 4 passed / 10 total, overall `not_verified`.

## Verified

- Python Core is running in simulation-only mode behind a temporary Cloudflare Quick Tunnel.
- Public health endpoint is reachable: `https://statistical-session-telescope-seeker.trycloudflare.com/health`.
- Dynamic Dify OpenAPI endpoint is reachable: `https://statistical-session-telescope-seeker.trycloudflare.com/openapi.yaml`.
- Dify Custom Tool flow smoke test passed against the public endpoint:
  - `health`
  - `runPipeline`
  - `getDailyReport`
  - `getCandidates`
  - `getReview`
  - `getGuardStatus`
- Deployment readiness check passed with missing production secrets allowed for local packaging.
- Dify App API key was accepted in the saved diagnostic and the app is published.
- PM Console prompt is published in the existing Dify app.
- PM Console LLM node was changed to `deepseek-v4-pro`; the system is not configured as all-Flash.
- Local Dify specs require strong/light model separation:
  - PM Console, Research, Monthly Review, Quarterly Meta-Learning: `deepseek-v4-pro`
  - Daily light summary only: `deepseek-v4-flash`

## Not Yet Fully Verified In Dify Cloud

- The existing Dify app still reports the display name `RO` through the saved App API diagnostic. It must be renamed to `A股AI投研 PM Console`.
- The PM Console app can answer acceptance prompts, but its App API responses may still include `<think>` reasoning tags despite the UI setting being enabled.
- `scripts/accept_dify_app_api.py` now treats `<think>` and `</think>` as global acceptance failures; the previous saved report is no longer considered acceptable evidence.
- Custom Tool OpenAPI import reached the Dify UI and Dify recognized all 11 operations, but the Dify Cloud auth/save modal repeatedly timed out in browser automation before final save could be verified.
- The imported Custom Tool is therefore not yet verified as saved in the Dify workspace.
- The Custom Tool is not yet verified as bound to the PM Console Chatflow.
- Knowledge Base `a_stock_research_kb` is planned locally, but cloud upload/indexing is not yet verified.
- The four report workflows are specified locally, but cloud creation/publishing is not yet verified:
  - `Daily Report Composer`
  - `Weekly Deep Research Brief`
  - `Monthly Review Composer`
  - `Quarterly Meta-Learning Review`
- A stable production Python Core deployment has not replaced the temporary Cloudflare Quick Tunnel.

## Remaining Acceptance Gates

1. Rename the Dify app to `A股AI投研 PM Console`.
2. Save the Custom Tool in Dify with:
   - URL: `/openapi.yaml` on the production Python Core HTTPS host
   - Auth type: request header
   - Header key: `Authorization`
   - Header prefix: `Bearer`
   - Value: the same token as `A_STOCK_API_KEY`
3. Bind the Custom Tool operations to PM Console and the four report workflows.
4. Create/index `a_stock_research_kb` with the PDF, SOP, parameter files, prompts, and generated reports.
5. Replace the temporary tunnel with Render/Railway/Fly or another stable HTTPS deployment.
6. Rerun:
   - `python scripts/check_dify_readiness.py --base-url <production-url>`
   - `python scripts/smoke_dify_tool_flow.py --base-url <production-url>`
   - `python scripts/inspect_dify_app_api.py`
   - `python scripts/accept_dify_app_api.py`
