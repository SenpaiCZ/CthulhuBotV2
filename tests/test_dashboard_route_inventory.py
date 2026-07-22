import re
import pytest
from dashboard.app import app

# Fixed historical baseline captured before the blueprint split began (commit 0548eb3,
# via `len(list(app.url_map.iter_rules()))` — includes Quart's auto-registered "static"
# endpoint alongside the 156 real routes). Hardcoded, not recomputed, so this test can
# actually detect a route silently vanishing in a later commit — recomputing it live
# would make the comparison a tautology that can never fail.
#
# Updated to 158 when the update-rollback feature (Phase A, Task 7) intentionally added
# POST /api/backup/restore — a deliberate new route, not a regression.
EXPECTED_RULE_COUNT = 158


def _dummy_path(rule_str):
    """Replace every <converter:name> or <name> placeholder with a harmless dummy value."""
    return re.sub(r"<(?:[a-zA-Z_]+:)?([a-zA-Z_]+)>", "1", rule_str)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


def test_registered_route_count_is_stable():
    """Phase 1 must not add or remove routes — only move them between files."""
    actual = len(list(app.url_map.iter_rules()))
    assert actual == EXPECTED_RULE_COUNT, f"expected {EXPECTED_RULE_COUNT} routes, found {actual}"


# Routes confirmed to 404 from their own business logic on dummy-arg data, not from
# routing failure — excluded so the sweep only flags real regressions:
#   - serve_fonts / serve_image (dashboard/app.py): send_from_directory() 404s because
#     no file literally named "1" exists in the fonts/images folder.
#   - render_character_view (dashboard/app.py): explicit dict lookup 404s because no
#     guild/character with id "1" exists in player_stats data.
_BUSINESS_LOGIC_404_EXCLUSIONS = {
    "/fonts/<path:filename>",
    "/images/<path:filename>",
    "/render/character/<guild_id>/<user_id>",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_str",
    sorted(
        {r.rule for r in app.url_map.iter_rules() if r.endpoint != "static"}
        - _BUSINESS_LOGIC_404_EXCLUSIONS
    ),
)
async def test_every_route_resolves_without_404_or_500(client, rule_str):
    """
    Every currently-registered route must still resolve to *some* handler after a GET
    request — not a routing-level 404 (route vanished / URL prefix typo) and not a 500
    (import error, missing dependency, broken handler). A 405 (wrong HTTP method, e.g.
    GET against a POST-only route), 401/403 (auth-gated), or 302 (redirect to login) are
    all fine — they prove the route still exists and its handler ran far enough to make
    an auth/method decision.
    """
    path = _dummy_path(rule_str)
    response = await client.get(path)
    assert response.status_code not in (404, 500), (
        f"{rule_str} -> {path}: got {response.status_code}"
    )
