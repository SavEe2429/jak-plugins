"""Read-only migration inventory for legacy profile compatibility adapters."""


def build_migration_report(registry, project_name="MigrationSample"):
    profiles = []
    for adapter in sorted(registry.list_all(), key=lambda item: (item.domain, item.stack_id)):
        provider = adapter.to_template_provider(project_name, include_ci=True)
        legacy_files = [
            item.rel_path
            for item in adapter.get_entry_points(project_name)
            + adapter.get_smoke_tests(project_name)
            + adapter.get_supporting_files()
        ]
        workflow = adapter.get_ci_workflow(project_name)
        if workflow:
            legacy_files.append(".github/workflows/ci.yml")
        provider_files = [item["path"] for item in provider.payload.get("files", [])]
        legacy_directories = sorted(adapter.get_directories())
        provider_directories = sorted(
            item["path"] for item in provider.payload.get("directories", [])
        )
        verification_provider = getattr(adapter, "verification_provider", None)
        project_policy = (
            verification_provider.payload.get("project_policy", {}) if verification_provider else {}
        )
        legacy_fields = (
            "config_manifests",
            "module_boundary_patterns",
            "test_commands",
            "build_commands",
            "mandatory_categories",
            "na_categories",
            "build_command",
        )
        legacy_only = [field for field in legacy_fields if field in getattr(adapter, "_data", {})]
        profile_path = getattr(adapter, "_profile_path", None)
        source = (
            ("%s/%s" % (profile_path.parent.name, profile_path.name)) if profile_path else "unknown"
        )
        old_file_set = set(legacy_files)
        new_file_set = set(provider_files)
        profiles.append(
            {
                "domain": adapter.domain,
                "stack": adapter.stack_id,
                "source": source,
                "legacy_schema": "combined-profile",
                "compatibility_provider": provider.id,
                "verification_provider": verification_provider.id
                if verification_provider
                else None,
                "verification_contract": {
                    "status": "provider-backed" if verification_provider else "legacy-only",
                    "check_count": len(verification_provider.payload.get("checks", []))
                    if verification_provider
                    else 0,
                    "policy_fields": sorted(project_policy),
                },
                "template_bridge_parity": {
                    "directories_match": set(legacy_directories) == set(provider_directories),
                    "files_match": old_file_set == new_file_set,
                    "directory_delta": {
                        "added": sorted(set(provider_directories) - set(legacy_directories)),
                        "removed": sorted(set(legacy_directories) - set(provider_directories)),
                    },
                    "file_delta": {
                        "added": sorted(new_file_set - old_file_set),
                        "removed": sorted(old_file_set - new_file_set),
                    },
                },
                "legacy_only_capabilities": legacy_only,
                "migration_status": (
                    "provider-migrated"
                    if verification_provider and not legacy_only
                    else "partial-compatibility-bridge"
                ),
            }
        )
    return {
        "status": "inventory-only",
        "profile_count": len(profiles),
        "profiles": profiles,
        "limitations": [
            "The report does not rewrite or delete profile files.",
            "Template bridge parity covers generated directories and files only.",
            "Domain/stack discovery and generated template declarations remain in compatibility profiles.",
        ],
    }
