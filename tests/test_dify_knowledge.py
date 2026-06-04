from scripts.provision_dify_knowledge import collect_knowledge_files


def test_knowledge_file_collection_has_project_sources():
    files = collect_knowledge_files()
    names = {path.name for path in files}
    assert "knowledge_base_seed.md" in names
    assert "pm_console_prompt.md" in names
    assert "workflow_blueprints.md" in names
    assert "parameters.json" in names
    assert "watchlist.json" in names

