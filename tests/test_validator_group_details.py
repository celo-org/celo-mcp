"""Regression tests for get_validator_group_details.

Both code paths reached for the locked-gold estimate through a name that was never
defined, so any request that took the fallback died with NameError instead of the
estimate the code was written to apply. The multicall path took it on every call
because its asyncio.gather was passed one awaitable and unpacked into two.

The chain is stubbed at the contract boundary: these tests must not need a network.
"""

from unittest.mock import MagicMock

from web3 import Web3

from celo_mcp.staking.service import StakingService

GROUP = "0x0861a61Bf679A30680510EcC238ee43B82C5e843"
MEMBER = "0x1234567890123456789012345678901234567890"

TOTAL_LOCKED_GOLD = 5_000_000 * 10**18
VOTES = 1_000 * 10**18


class _Functions:
    """Dispatches `functions.<name>(...).call` to a canned value or exception."""

    def __init__(self, returns):
        self._returns = returns

    def __getattr__(self, name):
        value = self._returns[name]

        def build(*_args, **_kwargs):
            holder = MagicMock()
            if isinstance(value, Exception):
                holder.call.side_effect = value
            else:
                holder.call.return_value = value
            return holder

        return build


class _Contract:
    def __init__(self, returns):
        self.functions = _Functions(returns)


def _service(**overrides):
    """A StakingService whose every contract call answers from a canned map."""
    client = MagicMock()
    service = StakingService(client)

    group_info = [0] * (service._last_slashed_index + 1)
    group_info[0] = [MEMBER]
    group_info[service._last_slashed_index] = 0

    returns = {
        "getValidatorGroup": group_info,
        "getEligibleValidatorGroups": [Web3.to_checksum_address(GROUP)],
        "getActiveVotesForGroup": VOTES,
        # index 3 is the score, index 4 the signer
        "getValidator": ["ecdsa", "bls", [], 900_000_000_000_000_000, MEMBER, 0],
        "getName": "Member One",
        "getTotalLockedGold": TOTAL_LOCKED_GOLD,
        "getRegisteredValidators": [MEMBER] * 120,
    }
    returns.update(overrides)

    client.w3.eth.contract = lambda **_kwargs: _Contract(returns)

    async def _batch(_addresses):
        return {GROUP: {"group_info": group_info, "name": "Test Group"}}

    service._batch_validator_group_calls = _batch
    return service


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
    assert group.capacity > 0, "capacity must be computed, not defaulted to nothing"


async def test_multicall_path_uses_the_real_locked_gold():
    """The capacity must come from getTotalLockedGold, not from a votes-based guess.

    Pins that the gather actually fetches it: capacity is derived from total locked
    gold, so a votes-sized estimate would land orders of magnitude lower.
    """
    service = _service()

    group = await service._get_validator_group_details_multicall(GROUP)

    # capacity = total_locked * (members + 1) / min(110, total_validators)
    assert group.capacity == int((TOTAL_LOCKED_GOLD * 2) / 110)


async def test_individual_path_estimates_when_locked_gold_is_unavailable():
    """The degraded path must apply its estimate rather than raise.

    This is the branch the code writes a warning for and then, before the fix,
    immediately died in.
    """
    service = _service(getTotalLockedGold=RuntimeError("RPC down"))

    group = await service._get_validator_group_details_individual(GROUP)

    assert group.num_members == 1
    assert group.capacity > 0, "an unavailable locked-gold call must fall back"


async def test_individual_path_works_normally():
    """The healthy individual path keeps returning what it always did."""
    service = _service()

    group = await service._get_validator_group_details_individual(GROUP)

    assert group.capacity == int((TOTAL_LOCKED_GOLD * 2) / 110)
