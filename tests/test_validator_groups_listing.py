"""Regression tests for the get_validator_groups listing path.

`asyncio.gather(..., return_exceptions=True)` yields a value *or an exception
object*. The listing assigned one straight into a number, so when both
system-wide calls failed together - they share a gather to the same endpoint, so
one outage takes both - the exception travelled into capacity arithmetic and
amount formatting and failed a call whose group data was already in hand.

The chain is stubbed at the contract boundary, keyed by address. No network.
"""

from unittest.mock import MagicMock

import pytest
from web3 import Web3

from celo_mcp.staking.service import StakingService

GROUP = "0x0861a61Bf679A30680510EcC238ee43B82C5e843"
MEMBER = "0x1234567890123456789012345678901234567890"

GROUP_VOTES = 1_000 * 10**18
TOTAL_VOTES = 4_000_000 * 10**18
TOTAL_LOCKED_GOLD = 5_000_000 * 10**18


class _Functions:
    def __init__(self, returns):
        self._returns = returns

    def __getattr__(self, name):
        if name not in self._returns:
            raise AttributeError(f"function {name!r} is not in this contract's ABI")

        value = self._returns[name]

        def build(*_args, **_kwargs):
            class _Call:
                @staticmethod
                def call():
                    if isinstance(value, Exception):
                        raise value
                    return value

            return _Call

        return build


class _Contract:
    def __init__(self, returns):
        self.functions = _Functions(returns)


def _service(**overrides):
    """A StakingService whose contracts answer from per-address canned maps."""
    service = StakingService(client=MagicMock())

    group_info = [0] * (service._last_slashed_index + 1)
    group_info[0] = [MEMBER]

    by_address = {
        service.ELECTION_ADDRESS: {
            "getTotalVotesForEligibleValidatorGroups": [
                [Web3.to_checksum_address(GROUP)],
                [GROUP_VOTES],
            ],
            "getEligibleValidatorGroups": [Web3.to_checksum_address(GROUP)],
            "getActiveVotesForGroup": GROUP_VOTES,
            "getTotalVotes": TOTAL_VOTES,
            "getElectableValidators": [1, 110],
        },
        service.VALIDATORS_ADDRESS: {
            "getValidatorGroup": group_info,
            "getValidator": ["ecdsa", "bls", [], 900_000_000_000_000_000, MEMBER, 0],
            "getRegisteredValidators": [MEMBER] * 120,
        },
        service.ACCOUNTS_ADDRESS: {"getName": "Test Group"},
        service.LOCKED_GOLD_ADDRESS: {"getTotalLockedGold": TOTAL_LOCKED_GOLD},
    }

    for name, value in overrides.items():
        for functions in by_address.values():
            if name in functions:
                functions[name] = value
                break
        else:  # pragma: no cover
            raise KeyError(f"{name} is not on any stubbed contract")

    checksummed = {
        Web3.to_checksum_address(addr): _Contract(fns)
        for addr, fns in by_address.items()
    }

    def contract(address, abi=None, **_kwargs):
        return checksummed[address]

    service.client.w3.eth.contract = contract

    async def _batch(_addresses):
        return {GROUP: {"group_info": group_info, "name": "Test Group"}}

    service._batch_validator_group_calls = _batch
    return service


async def test_listing_works_normally():
    result = await _service()._get_validator_groups_multicall(page=1, page_size=10)

    assert len(result.groups) == 1
    assert result.groups[0].address == GROUP


async def test_listing_survives_locked_gold_alone_failing():
    """The documented fallback: total votes stands in for total locked gold."""
    service = _service(getTotalLockedGold=RuntimeError("RPC down"))

    result = await service._get_validator_groups_multicall(page=1, page_size=10)

    assert len(result.groups) == 1


@pytest.mark.parametrize(
    "eligible_call_fails",
    [False, True],
    ids=["primary_branch", "fallback_branch"],
)
async def test_listing_survives_both_system_calls_failing(eligible_call_fails):
    """The whole call used to raise TypeError while holding every group it needed.

    Both calls share one gather to one endpoint, so an outage takes them together.
    An exception object was assigned straight into a number and then travelled
    into capacity arithmetic and amount formatting.
    """
    overrides = {
        "getTotalLockedGold": RuntimeError("RPC down"),
        "getTotalVotes": RuntimeError("RPC down"),
    }
    if eligible_call_fails:
        overrides["getTotalVotesForEligibleValidatorGroups"] = RuntimeError("no method")

    service = _service(**overrides)

    result = await service._get_validator_groups_multicall(page=1, page_size=10)

    assert len(result.groups) == 1, "the group list was already in hand; return it"
    assert result.groups[0].address == GROUP


async def test_no_misleading_fallback_warning_when_total_votes_also_failed(caplog):
    """The warning claimed to use total votes as a fallback when it had none."""
    import logging

    service = _service(
        getTotalLockedGold=RuntimeError("RPC down"),
        getTotalVotes=RuntimeError("RPC down"),
    )

    with caplog.at_level(logging.WARNING, logger="celo_mcp.staking.service"):
        await service._get_validator_groups_multicall(page=1, page_size=10)

    assert "Could not get total votes" in caplog.text
    assert "unsupported operand type" not in caplog.text, (
        "capacity maths saw an exception object"
    )


async def test_fallback_uses_the_eligible_group_total_not_zero():
    """The per-group eligible votes are the breakdown of the missing total.

    Summing them keeps capacity meaningful; defaulting to zero would report every
    group as having no capacity at all, which reads as fact rather than as the
    guess it is.
    """
    service = _service(
        getTotalLockedGold=RuntimeError("RPC down"),
        getTotalVotes=RuntimeError("RPC down"),
    )

    result = await service._get_validator_groups_multicall(page=1, page_size=10)

    # total_locked_gold falls back to total votes, which falls back to the sum of
    # the eligible-group votes - a single group here, so GROUP_VOTES
    expected = await service._calculate_group_capacity(
        1, GROUP_VOTES, 120, max_electable_validators=110
    )
    assert result.groups[0].capacity == expected
    assert result.groups[0].capacity > 0
