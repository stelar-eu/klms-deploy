from stelarctl.status import (
    JobStatus,
    ResourceStatus,
    calculate_progress,
    derive_phase,
    expected_components_for_model,
    expected_jobs_for_model,
    render_bar,
)
from stelarctl.platform_model import PlatformModel


def _model(tier: str = "core", enable_llm_search: bool = False) -> PlatformModel:
    return PlatformModel(
        platform="okeanos",
        k8s_context="ctx",
        namespace="lab",
        author="dev@example.com",
        tier=tier,
        infrastructure={
            "storage": {"dynamic_class": "longhorn", "provisioning_class": "longhorn"},
            "ingress_class": "nginx",
            "tls": {"mode": "cert-manager", "issuer": "letsencrypt"},
        },
        dns={"root": "example.com", "scheme": "https"},
        config={
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "apikey",
            "s3_console_url": "https://klms.example.com/s3/login",
            "enable_llm_search": enable_llm_search,
            "groq_api_url": "https://api.groq.com/",
            "groq_api_model": "llama",
        },
        secrets=[],
    )


def test_calculate_progress_uses_weighted_percentage():
    assert calculate_progress(3, 4, 8, 10) == 78


def test_render_bar_shows_percentage():
    assert render_bar(50, width=10) == "[#####-----] 50%"


def test_expected_resources_expand_for_full_tier_and_llm_search():
    model = _model(tier="full", enable_llm_search=True)

    component_names = [resource.name for resource in expected_components_for_model(model)]
    job_names = [resource.name for resource in expected_jobs_for_model(model)]

    assert "ontop" in component_names
    assert "previewer" in component_names
    assert "llmsearch" in component_names
    assert "ontopinit" in job_names
    assert "quayinit" in job_names


def test_derive_phase_reports_degraded_on_failures():
    jobs = [JobStatus("kcinit", "Keycloak Init", False, True, "job failed")]
    components = [ResourceStatus("deployment", "stelarapi", "STELAR API", False, "0/1 ready")]

    assert derive_phase(30, jobs, components, []) == "Degraded"


def test_derive_phase_reports_ready_at_full_completion():
    jobs = [JobStatus("kcinit", "Keycloak Init", True, False, "completed")]
    components = [ResourceStatus("deployment", "stelarapi", "STELAR API", True, "ready")]

    assert derive_phase(100, jobs, components, []) == "Ready"
