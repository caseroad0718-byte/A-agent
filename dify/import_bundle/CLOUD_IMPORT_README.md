# Dify Cloud Import Bundle

Generated for Python Core endpoint:

```text
https://a-stock-system.onrender.com
```

## Files

- `custom_tool_openapi.public.yaml`: OpenAPI schema with the public server URL.
- `custom_tool_console_payload.sample.json`: Dify console payload shape for `/workspaces/current/tool-provider/api/add`. It uses `${A_STOCK_API_KEY}` as a placeholder.
- `dsl/*.dsl.yaml`: Dify app DSL skeletons using `version: 0.6.0`. JSON is valid YAML.
- `*.import_payload.sample.json`: request bodies for Dify console `/apps/imports`.

## Import Order

1. Import `custom_tool_openapi.public.yaml` as Custom Tool `A Stock AI Research System 5.0 API`.
2. Configure auth as request header Bearer token: `Authorization: Bearer <A_STOCK_API_KEY>`.
3. Create or import `A股AI投研 PM Console`, then bind:
   - model: `deepseek-v4-pro`
   - knowledge base: `a_stock_research_kb`
   - Custom Tool operations: daily report, candidates, market state, approve, exit, review, guard.
4. Import the four workflow DSL skeletons, then bind their tool nodes to the Custom Tool if Dify marks any provider as unresolved.
5. Bind every Knowledge Retrieval node with empty `dataset_ids` to `a_stock_research_kb`.
6. Publish the PM Console and each workflow.
7. Run `scripts/verify_dify_cloud_state.py --base-url https://a-stock-system.onrender.com`.

## Model Rule

- PM Console, Weekly Deep Research, Monthly Review and Quarterly Meta-Learning must use `deepseek-v4-pro`.
- Daily Report Composer may use `deepseek-v4-flash`.
- Do not set every LLM node to Flash.

## Safety

Dify App API keys cannot create or modify apps. Dify console import endpoints require your logged-in workspace session, so this bundle avoids storing browser cookies or real keys. Replace placeholders only inside Dify Cloud or your deployment secret manager.
