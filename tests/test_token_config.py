"""Tests for the hardcoded token and contract configuration.

These are offline consistency checks. They cannot prove an address is correct
on-chain, but they catch the two ways this config has already gone wrong:
a stale symbol left behind after a rename, and an address pointing at a
network that no longer exists.

The live check lives in test_token_config_onchain.py, which is opt-in.
"""

import pytest

from celo_mcp.config.contracts import (
    CELO_SEPOLIA_ADDRESSES,
    MAINNET_ADDRESSES,
    get_all_addresses,
    get_contract_address,
    get_governance_address,
)
from celo_mcp.tokens.models import MentoStableTokens
from celo_mcp.tokens.service import CELO_TOKENS, STABLE_TOKENS

RETIRED_SYMBOLS = ("cUSD", "cEUR", "cREAL", "eXOF", "cKES", "PUSO", "cCOP", "cGHS")
MENTO_SYMBOLS = ("USDm", "EURm", "BRLm", "XOFm", "KESm", "PHPm", "COPm", "GHSm")


class TestMentoRename:
    def test_no_retired_symbol_is_used_as_a_key(self):
        for retired in RETIRED_SYMBOLS:
            assert retired not in STABLE_TOKENS
            assert retired not in CELO_TOKENS

    def test_no_retired_symbol_is_reported_to_callers(self):
        reported = {t["symbol"] for t in STABLE_TOKENS.values()}
        assert reported.isdisjoint(RETIRED_SYMBOLS)

    def test_every_mento_symbol_is_present(self):
        for symbol in MENTO_SYMBOLS:
            assert symbol in STABLE_TOKENS, f"{symbol} missing from STABLE_TOKENS"

    def test_key_matches_the_symbol_it_reports(self):
        for key, token in STABLE_TOKENS.items():
            assert key == token["symbol"], f"{key} reports symbol {token['symbol']}"

    @pytest.mark.parametrize("symbol", ("USDm", "EURm", "BRLm", "XOFm", "GHSm"))
    def test_mento_tokens_are_named_mento(self, symbol):
        """The rename covered display names too, not only tickers."""
        assert STABLE_TOKENS[symbol]["name"].startswith("Mento ")

    def test_mainnet_addresses_were_not_changed_by_the_rename(self):
        """Mainnet contracts were renamed in place; the addresses must not move."""
        assert (
            STABLE_TOKENS["USDm"]["address"]
            == "0x765DE816845861e75A25fCA122bb6898B8B1282a"
        )
        assert (
            STABLE_TOKENS["EURm"]["address"]
            == "0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73"
        )
        assert (
            STABLE_TOKENS["BRLm"]["address"]
            == "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787"
        )

    def test_model_fields_use_the_current_names(self):
        fields = set(MentoStableTokens.model_fields)
        assert {"USDm", "EURm", "BRLm"} <= fields
        assert not any(f.startswith(("cUSD", "cEUR", "cREAL")) for f in fields)


class TestCeloSepoliaReplacesAlfajores:
    DEAD_ALFAJORES = {
        "0x874069Fa1Eb16D44d622F2e0Ca25eeA172369bC1",  # cUSD
        "0x10c892A6EC43a53E45D0B916B4b7D383B1b78C0F",  # cEUR
        "0xE4D517785D091D3c54818832dB6094bcc2744545",  # cREAL
        "0xF194afDf50B03e69Bd7D057c1Aa9e10c9954E4C9",  # CELO
        "0xAA963FC97281d9632d96700aB62A4D1340F9a28a",  # Governance
    }

    def test_no_dead_alfajores_address_remains(self):
        configured = {t["testnet"] for t in CELO_TOKENS.values()}
        configured |= set(CELO_SEPOLIA_ADDRESSES.values())
        configured |= {
            getattr(MentoStableTokens(), f)
            for f in MentoStableTokens.model_fields
            if f.endswith("_testnet")
        }
        assert configured.isdisjoint(self.DEAD_ALFAJORES)

    def test_every_token_has_a_celo_sepolia_address(self):
        for symbol, networks in CELO_TOKENS.items():
            assert networks.get("testnet"), f"{symbol} has no testnet address"

    def test_celo_is_the_same_address_on_both_networks(self):
        """GoldToken resolves to one address across Celo networks."""
        assert CELO_TOKENS["CELO"]["mainnet"] == CELO_TOKENS["CELO"]["testnet"]

    def test_sepolia_core_addresses_differ_from_mainnet(self):
        """A copy-paste slip would leave mainnet addresses on the testnet."""
        for name, address in CELO_SEPOLIA_ADDRESSES.items():
            assert address != MAINNET_ADDRESSES[name], f"{name} duplicates mainnet"

    def test_both_networks_define_the_same_contracts(self):
        assert set(CELO_SEPOLIA_ADDRESSES) == set(MAINNET_ADDRESSES)


class TestNetworkLookup:
    @pytest.mark.parametrize("name", ("celo-sepolia", "Celo-Sepolia", "sepolia"))
    def test_sepolia_names_resolve_to_sepolia(self, name):
        assert get_all_addresses(name) == CELO_SEPOLIA_ADDRESSES
        assert get_governance_address(name) == CELO_SEPOLIA_ADDRESSES["Governance"]

    def test_mainnet_is_the_default(self):
        assert get_all_addresses() == MAINNET_ADDRESSES
        assert get_governance_address() == MAINNET_ADDRESSES["Governance"]

    def test_unknown_network_falls_back_to_mainnet(self):
        assert get_all_addresses("something-else") == MAINNET_ADDRESSES

    def test_unknown_contract_raises(self):
        with pytest.raises(ValueError, match="Unknown contract"):
            get_contract_address("NotAContract")
