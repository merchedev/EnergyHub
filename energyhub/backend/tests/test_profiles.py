from __future__ import annotations

from app.services import profiles


def test_builtin_profiles_are_available() -> None:
    profile = profiles.get_profile("pepe_variable")
    assert profile["company"] == "Pepe Energy"
    assert profile["supports_pepephone_discount"] is True
    assert profile["price_api_url"].startswith("https://shared-api.pepeenergy.com/")
    defaults = profiles.profile_defaults("pepe_variable")
    assert defaults["price_source"] == "pepe_api_variable"
    assert defaults["service_fee_eur_month"] > 0


def test_community_catalog_is_loaded() -> None:
    profile = profiles.get_profile("endesa_personalizada")
    assert profile["company"] == "Endesa"
    assert profile["requires_manual_prices"] is True
    assert len(profiles.all_profiles()) >= 6


def test_pvpc_profile_supports_bono_social() -> None:
    defaults = profiles.profile_defaults("pvpc_2td")
    assert defaults["bono_social_eligible"] is True
    assert defaults["service_fee_eur_month"] == 0.0
