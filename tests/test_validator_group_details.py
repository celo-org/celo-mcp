"""Regression tests for get_validator_group_details.

Both code paths reached for the locked-gold estimate through a name that was never
defined, so any request that took the fallback died with NameError instead of the
estimate the code was written to apply. The multicall path took it on every call
because its asyncio.gather was passed one awaitable and unpacked into two, and
because that path is the default, the public tool silently served every request
from the slow fallback.

The chain is stubbed at the contract boundary, keyed by contract address so that
calling the right function on the wrong contract fails here the way it would fail
against a real node. These tests must not need a network.
"""

import logging
from unittest.mock import MagicMock

import pytest
from web3 import Web3

from celo_mcp.staking.service import StakingService

GROUP = "0x0861a61Bf679A30680510EcC238ee43B82C5e843"
MEMBER = "0x1234567890123456789012345678901234567890"

TOTAL_LOCKED_GOLD = 5_000_000 * 10**18
TOTAL_VOTES = 4_000_000 * 10**18
VOTES = 1_000 * 10**18
REGISTERED_VALIDATORS = 120


class _Functions:
    """Dispatches `functions.<name>(...).call` to a canned value or exception."""

    def __init__(self, returns):
        self._returns = returns

    def __getattr__(self, name):
        if name not in self._returns:
            # web3 raises ABIFunctionNotFound (an AttributeError) when a function
            # is absent from the contract's ABI. Modelling that is the point of
            # keying these by address: it catches calls aimed at the wrong contract.
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
    # MulticallService builds a contract during __init__, before the
    # address-keyed dispatcher below replaces the factory.
    service = StakingService(client=MagicMock())

    group_info = [0] * (service._last_slashed_index + 1)
    group_info[0] = [MEMBER]
    group_info[service._last_slashed_index] = 0

    by_address = {
        service.ELECTION_ADDRESS: {
            "getEligibleValidatorGroups": [Web3.to_checksum_address(GROUP)],
            "getActiveVotesForGroup": VOTES,
            "getTotalVotes": TOTAL_VOTES,
        },
        service.VALIDATORS_ADDRESS: {
            "getValidatorGroup": group_info,
            # index 3 is the score, index 4 the signer
            "getValidator": ["ecdsa", "bls", [], 900_000_000_000_000_000, MEMBER, 0],
            "getRegisteredValidators": [MEMBER] * REGISTERED_VALIDATORS,
        },
        service.ACCOUNTS_ADDRESS: {"getName": "Member One"},
        service.LOCKED_GOLD_ADDRESS: {"getTotalLockedGold": TOTAL_LOCKED_GOLD},
    }

    # overrides are keyed by function name; route each to the contract that owns it
    for name, value in overrides.items():
        for functions in by_address.values():
            if name in functions:
                functions[name] = value
                break
        else:  # pragma: no cover - guards against a typo silently doing nothing
            raise KeyError(f"{name} is not on any stubbed contract")

    checksummed = {
        Web3.to_checksum_address(addr): _Contract(fns)
        for addr, fns in by_address.items()
    }

    def contract(address, abi=None, **_kwargs):
        return checksummed[address]

    service.client.w3.eth.contract = contract

    batched_addresses = []

    async def _batch(addresses):
        batched_addresses.append(list(addresses))
        return {GROUP: {"group_info": group_info, "name": "Test Group"}}

    service._batch_validator_group_calls = _batch
    service.batched_addresses = batched_addresses
    return service


async def _expected_capacity(service, total_locked_gold):
    return await service._calculate_group_capacity(
        1, total_locked_gold, REGISTERED_VALIDATORS, max_electable_validators=110
    )


async def test_multicall_path_returns_instead_of_raising():
    """The multicall path failed on every call, so the tool always took the fallback.

    Its gather was passed one awaitable and unpacked into two, and the handler that
    caught the resulting ValueError then read an undefined name.
    """
    service = _service()

    group = await service._get_validator_group_details_multicall(GROUP)

    assert group.address == GROUP
    assert group.num_members == 1
    assert group.votes == VOTES
    assert service.batched_addresses == [[GROUP]]


async def test_multicall_path_uses_the_real_locked_gold():
    """Capacity must come from getTotalLockedGold, not from an estimate.

    Pins that the gather actually fetches it: an estimate would land orders of
    magnitude away, so this also fails if the call is dropped from the gather.
    """
    service = _service()

    group = await service._get_validator_group_details_multicall(GROUP)

    assert group.capacity == await _expected_capacity(service, TOTAL_LOCKED_GOLD)
    assert group.capacity != await _expected_capacity(service, VOTES * 100)


@pytest.mark.parametrize(
    "path",
    [
        "_get_validator_group_details_multicall",
        "_get_validator_group_details_individual",
    ],
)
async def test_estimates_from_total_votes_when_locked_gold_is_unavailable(path):
    """The degraded branch must estimate rather than raise.

    System-wide total votes stands in for total locked gold; this group's own
    votes are smaller by a factor that varies with the group, so using them would
    report a wrong capacity - and zero for a group with no votes.
    """
    service = _service(getTotalLockedGold=RuntimeError("RPC down"))

    group = await getattr(service, path)(GROUP)

    assert group.capacity == await _expected_capacity(service, TOTAL_VOTES)
    assert group.capacity != await _expected_capacity(service, VOTES * 100)


@pytest.mark.parametrize(
    "path",
    [
        "_get_validator_group_details_multicall",
        "_get_validator_group_details_individual",
    ],
)
async def test_falls_back_to_group_votes_when_both_system_calls_fail(path):
    """Last resort: neither system-wide number is available."""
    service = _service(
        getTotalLockedGold=RuntimeError("RPC down"),
        getTotalVotes=RuntimeError("RPC down"),
    )

    group = await getattr(service, path)(GROUP)

    assert group.capacity == await _expected_capacity(service, VOTES * 100)


@pytest.mark.parametrize(
    "path",
    [
        "_get_validator_group_details_multicall",
        "_get_validator_group_details_individual",
    ],
)
async def test_defaults_the_validator_count_when_the_registry_is_unavailable(path):
    """An unavailable validator registry must not fail the request either."""
    service = _service(getRegisteredValidators=RuntimeError("RPC down"))

    group = await getattr(service, path)(GROUP)

    assert group.capacity == await service._calculate_group_capacity(
        1, TOTAL_LOCKED_GOLD, 110, max_electable_validators=110
    )


async def test_individual_path_works_normally():
    """The healthy individual path keeps returning what it always did."""
    service = _service()

    group = await service._get_validator_group_details_individual(GROUP)

    assert group.capacity == await _expected_capacity(service, TOTAL_LOCKED_GOLD)


async def test_both_paths_agree():
    """The revived multicall path must compute what the fallback was computing."""
    multicall = await _service()._get_validator_group_details_multicall(GROUP)
    individual = await _service()._get_validator_group_details_individual(GROUP)

    assert multicall.capacity == individual.capacity
    assert multicall.num_members == individual.num_members
    assert multicall.votes == individual.votes


async def test_public_call_does_not_fall_back(caplog):
    """The bug was invisible at the public boundary: only the log revealed it.

    Callers got correct data from the individual path while the multicall path
    raised on every request, so nothing but this assertion would notice a
    regression.
    """
    service = _service()
    assert service._use_multicall, "the multicall path is the one that ships"

    with caplog.at_level(logging.INFO, logger="celo_mcp.staking.service"):
        group = await service.get_validator_group_details(GROUP)

    assert group.num_members == 1
    assert "Falling back to individual contract calls" not in caplog.text
    assert "Error fetching validator group details" not in caplog.text


async def test_capacity_survives_a_contract_that_cannot_be_built():
    """Even a malformed contract must not fail the request.

    Capacity is a derived convenience; the group details the caller asked for are
    already in hand by this point.
    """
    service = _service()
    build = service.client.w3.eth.contract
    locked_gold = Web3.to_checksum_address(service.LOCKED_GOLD_ADDRESS)

    def contract(address, abi=None, **kwargs):
        if address == locked_gold:
            raise ValueError("bad ABI")
        return build(address, abi=abi, **kwargs)

    service.client.w3.eth.contract = contract

    group = await service._get_validator_group_details_multicall(GROUP)

    assert group.num_members == 1
    assert group.capacity == await _expected_capacity(service, VOTES * 100)
