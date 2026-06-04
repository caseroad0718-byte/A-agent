from pathlib import Path
import subprocess
import sys


def test_openapi_contract_exists():
    path = Path(__file__).resolve().parents[1] / "dify" / "custom_tool_openapi.yaml"
    text = path.read_text(encoding="utf-8")
    for operation in [
        "getDailyReport",
        "getMarketState",
        "getCandidates",
        "approveDecision",
        "exitTrade",
        "getReview",
        "getGuardStatus",
        "upsertWatchlistItem",
        "runResearch",
    ]:
        assert f"operationId: {operation}" in text
    assert "operationId: hermesObserve" in text
    assert "Hermes output is supplemental context only" in text


def test_dynamic_openapi_endpoint_is_implemented():
    path = Path(__file__).resolve().parents[1] / "api_server.py"
    text = path.read_text(encoding="utf-8")
    assert 'parsed.path == "/openapi.yaml"' in text
    assert 'parsed.path == "/dify/manifest"' in text
    assert "YOUR_PUBLIC_API_HOST" in text


def test_dify_app_spec_contract_exists():
    spec_path = Path(__file__).resolve().parents[1] / "dify" / "app_spec.json"
    spec = __import__("json").loads(spec_path.read_text(encoding="utf-8"))
    assert spec["chatflow"]["name"] == "A股AI投研 PM Console"
    assert len(spec["workflows"]) == 4
    assert "approveDecision" in spec["custom_tool"]["required_operations"]
    assert spec["mode"] == "simulation_only"
    assert spec["knowledge_base"]["provision_script"] == "scripts/provision_dify_knowledge.py"
    assert spec["chatflow"]["acceptance_script"] == "scripts/accept_dify_app_api.py"
    assert spec["model_provider"]["pm_console_model"] == "deepseek-v4-pro"
    assert spec["model_provider"]["fast_model"] == "deepseek-v4-flash"
    assert "hermesObserve" in spec["custom_tool"]["optional_operations"]
    hermes_tool = spec["dify_native_tools"]["recommended_enabled_tools"][0]
    assert hermes_tool["name"] == "Hermes Agent 交互"
    assert "不得替代 PM/Risk/Guard" in hermes_tool["decision_boundary"]


def test_dify_app_acceptance_cases_cover_spec_prompts():
    root = Path(__file__).resolve().parents[1]
    spec = __import__("json").loads((root / "dify" / "app_spec.json").read_text(encoding="utf-8"))
    cases = __import__("json").loads((root / "dify" / "app_acceptance_cases.json").read_text(encoding="utf-8"))
    assert "<think>" in cases["global_must_not_include"]
    assert "</think>" in cases["global_must_not_include"]
    case_queries = {case["query"] for case in cases["cases"]}
    assert set(spec["chatflow"]["acceptance_prompts"]).issubset(case_queries)
    for case in cases["cases"]:
        assert case["must_not_include"]


def test_pdf_requirement_matrix_has_cloud_verification_gate():
    root = Path(__file__).resolve().parents[1]
    matrix = __import__("json").loads((root / "audit" / "pdf_requirement_matrix.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in matrix["requirements"]}
    assert "dify_cloud_final_verification" in ids
    assert "arch_9_agents" in ids


def test_workflow_node_specs_cover_four_workflows():
    root = Path(__file__).resolve().parents[1]
    spec = __import__("json").loads((root / "dify" / "workflow_node_specs.json").read_text(encoding="utf-8"))
    names = {workflow["name"] for workflow in spec["workflows"]}
    assert names == {
        "Daily Report Composer",
        "Weekly Deep Research Brief",
        "Monthly Review Composer",
        "Quarterly Meta-Learning Review",
    }
    for workflow in spec["workflows"]:
        assert workflow["nodes"][0]["type"] == "start"
        assert workflow["nodes"][-1]["type"] == "answer"


def test_dify_model_strategy_is_not_all_flash():
    root = Path(__file__).resolve().parents[1]
    params = __import__("json").loads((root / "config" / "parameters.json").read_text(encoding="utf-8"))
    profiles = params["llm"]["profiles"]
    assert profiles["strong"]["default_model"] == "deepseek-v4-pro"
    assert profiles["fast"]["default_model"] == "deepseek-v4-flash"
    assert profiles["strong"]["default_model"] != profiles["fast"]["default_model"]

    spec = __import__("json").loads((root / "dify" / "workflow_node_specs.json").read_text(encoding="utf-8"))
    llm_nodes = [
        node
        for workflow in spec["workflows"]
        for node in workflow["nodes"]
        if node["type"] == "llm"
    ]
    assert any(node.get("model_profile") == "strong" for node in llm_nodes)
    assert any(node.get("model_profile") == "fast" for node in llm_nodes)
    assert not all(node.get("model") == "deepseek-v4-flash" for node in llm_nodes)


def test_bootstrap_and_operator_runbook_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "bootstrap_local.ps1").exists()
    assert (root / "scripts" / "bootstrap_local.sh").exists()
    runbook = (root / "dify" / "OPERATOR_RUNBOOK.md").read_text(encoding="utf-8")
    assert "accept_dify_app_api.py" in runbook
    assert "A_STOCK_API_KEY" in runbook


def test_dify_app_acceptance_reports_unpublished_workflow():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "accept_dify_app_api.py").read_text(encoding="utf-8")
    assert "User-Agent" in script
    assert "Workflow not published" in script
    assert "app_not_published" in script
    assert "global_must_not_include" in script


def test_dify_app_inspector_exists_and_does_not_persist_keys():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "inspect_dify_app_api.py").read_text(encoding="utf-8")
    assert "/info" in script
    assert "/parameters" in script
    assert "/chat-messages" in script
    assert "DIFY_EXPECTED_APP_NAME" in script
    assert "app_name_mismatch" in script
    assert "DIFY_APP_API_KEY" in script
    assert "Authorization" in script
    assert "api_key" not in "dify/app_api_diagnostics.json"


def test_dify_cloud_state_verifier_tracks_remaining_cloud_gates():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "verify_dify_cloud_state.py").read_text(encoding="utf-8")
    assert "dify_app_name" in script
    assert "custom_tool_saved" in script
    assert "custom_tool_bound" in script
    assert "knowledge_base_indexed" in script
    assert "report_workflows_created" in script
    assert "<think>" in script
    readiness = (root / "scripts" / "check_dify_readiness.py").read_text(encoding="utf-8")
    assert "scripts/verify_dify_cloud_state.py" in readiness
    assert "scripts/install_dify_cloud_assets.py" in readiness


def test_dify_cloud_console_installer_is_safe_by_default():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "install_dify_cloud_assets.py").read_text(encoding="utf-8")
    assert "DIFY_CONSOLE_COOKIE" in script
    assert "DIFY_CONSOLE_CSRF_TOKEN" in script
    assert "DIFY_CONSOLE_AUTHORIZATION" in script
    assert "dry_run" in script
    assert "redact" in script
    assert "/workspaces/current/tool-provider/api/add" in script
    assert "/apps/imports" in script
    assert "localStorage" not in script
    assert "browser" not in script.lower()

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "install_dify_cloud_assets.py"),
            "--all",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = __import__("json").loads(result.stdout)
    assert output["execute"] is False
    assert "dry_run" in result.stdout
    assert "A_STOCK_API_KEY" not in result.stdout


def test_dify_import_bundle_exports_console_payload_and_dsl(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "bundle"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "export_dify_import_bundle.py"),
            "--public-base-url",
            "https://example.com",
            "--output-dir",
            str(out_dir),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    manifest = __import__("json").loads((out_dir / "dify_import_manifest.json").read_text(encoding="utf-8"))
    assert manifest["custom_tool"]["console_payload_file"] == "custom_tool_console_payload.sample.json"
    assert manifest["pm_console_dsl_file"] == "dsl/pm_console.chatflow.dsl.yaml"
    assert any(item["model_rule"] == "deepseek-v4-pro" for item in manifest["workflows"])
    assert any(item["model_rule"] == "deepseek-v4-flash" for item in manifest["workflows"])

    payload = __import__("json").loads((out_dir / "custom_tool_console_payload.sample.json").read_text(encoding="utf-8"))
    assert payload["credentials"]["auth_type"] == "api_key_header"
    assert payload["credentials"]["api_key_header"] == "Authorization"
    assert payload["credentials"]["api_key_header_prefix"] == "bearer"
    assert payload["credentials"]["api_key_value"] == "${A_STOCK_API_KEY}"
    assert "https://example.com" in payload["schema"]

    pm_dsl = (out_dir / "dsl" / "pm_console.chatflow.dsl.yaml").read_text(encoding="utf-8")
    weekly_dsl = (out_dir / "dsl" / "weekly_deep_research_brief.workflow.dsl.yaml").read_text(encoding="utf-8")
    daily_dsl = (out_dir / "dsl" / "daily_report_composer.workflow.dsl.yaml").read_text(encoding="utf-8")
    assert '"mode": "advanced-chat"' in pm_dsl
    assert "deepseek-v4-pro" in pm_dsl
    assert "deepseek-v4-pro" in weekly_dsl
    assert "knowledge-retrieval" in weekly_dsl
    assert "a_stock_research_kb" in (out_dir / "CLOUD_IMPORT_README.md").read_text(encoding="utf-8")
    assert "deepseek-v4-flash" in daily_dsl
    assert not all("deepseek-v4-flash" in text for text in [pm_dsl, weekly_dsl])

    bundle_text = "\n".join(path.read_text(encoding="utf-8") for path in out_dir.rglob("*") if path.is_file())
    assert "sk-" not in bundle_text
    assert "app-" not in bundle_text
