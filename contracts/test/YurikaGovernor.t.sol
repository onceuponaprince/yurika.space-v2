// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ShardToken} from "../src/ShardToken.sol";
import {YurikaGovernor} from "../src/YurikaGovernor.sol";

/// Trivial target contract that the governor can `call`.
contract Counter {
    uint256 public n;
    function set(uint256 v) external { n = v; }
}

contract YurikaGovernorTest is Test {
    ShardToken token;
    YurikaGovernor gov;
    Counter target;

    address founder = address(0xB2);
    address alice   = address(0xC3);
    address bob     = address(0xC4);

    uint256 constant VOTING_PERIOD = 100;       // blocks
    uint256 constant QUORUM_BPS    = 5_000;     // 50%
    uint256 constant PROPOSE_THRESHOLD = 10e18; // 10 shards

    function setUp() public {
        token = new ShardToken(
            "Yurika yurika.space", "yYRK",
            1000e18, 0.01 ether, 5 ether, 30 days,
            keccak256("yurika.space"),
            address(0xDEAD), founder, address(0)
        );
        gov = new YurikaGovernor(token, VOTING_PERIOD, QUORUM_BPS, PROPOSE_THRESHOLD);
        target = new Counter();

        // Give alice + bob some shards by buying them.
        vm.deal(alice, 10 ether);
        vm.prank(alice);
        token.buyShards{value: 3 ether}(300e18); // 300 shards

        vm.deal(bob, 10 ether);
        vm.prank(bob);
        token.buyShards{value: 2 ether}(200e18); // 200 shards
    }

    // ── Constructor validation ───────────────────────────────────

    function test_constructor_revertsOnZeroToken() public {
        vm.expectRevert(YurikaGovernor.InvalidConfig.selector);
        new YurikaGovernor(ShardToken(payable(address(0))), 100, 5000, 10e18);
    }

    function test_constructor_revertsOnZeroPeriod() public {
        vm.expectRevert(YurikaGovernor.InvalidConfig.selector);
        new YurikaGovernor(token, 0, 5000, 10e18);
    }

    function test_constructor_revertsOnQuorumOverflow() public {
        vm.expectRevert(YurikaGovernor.InvalidConfig.selector);
        new YurikaGovernor(token, 100, 10_001, 10e18);
    }

    // ── propose() ────────────────────────────────────────────────

    function test_propose_createsProposal() public {
        bytes memory data = abi.encodeWithSelector(Counter.set.selector, uint256(42));
        vm.prank(alice);
        uint256 id = gov.propose(address(target), data, "set counter to 42");

        assertEq(id, 0);
        assertEq(gov.proposalCount(), 1);
        YurikaGovernor.Proposal memory p = gov.getProposal(id);
        assertEq(p.proposer, alice);
        assertEq(p.target, address(target));
        assertEq(p.endBlock, block.number + VOTING_PERIOD);
    }

    function test_propose_revertsBelowThreshold() public {
        bytes memory data = "";
        address noShards = address(0xDADA);
        vm.prank(noShards);
        vm.expectRevert(YurikaGovernor.BelowProposalThreshold.selector);
        gov.propose(address(target), data, "x");
    }

    // ── castVote() ───────────────────────────────────────────────

    function _proposeAsAlice() internal returns (uint256 id) {
        bytes memory data = abi.encodeWithSelector(Counter.set.selector, uint256(42));
        vm.prank(alice);
        id = gov.propose(address(target), data, "set counter to 42");
    }

    function test_castVote_for_accumulatesForVotes() public {
        uint256 id = _proposeAsAlice();
        vm.prank(alice);
        gov.castVote(id, true);

        YurikaGovernor.Proposal memory p = gov.getProposal(id);
        assertEq(p.forVotes, 300e18);
        assertEq(p.againstVotes, 0);
    }

    function test_castVote_against_accumulatesAgainstVotes() public {
        uint256 id = _proposeAsAlice();
        vm.prank(bob);
        gov.castVote(id, false);

        YurikaGovernor.Proposal memory p = gov.getProposal(id);
        assertEq(p.forVotes, 0);
        assertEq(p.againstVotes, 200e18);
    }

    function test_castVote_revertsOnDoubleVote() public {
        uint256 id = _proposeAsAlice();
        vm.prank(alice);
        gov.castVote(id, true);

        vm.prank(alice);
        vm.expectRevert(YurikaGovernor.AlreadyVoted.selector);
        gov.castVote(id, true);
    }

    function test_castVote_revertsAfterEnd() public {
        uint256 id = _proposeAsAlice();
        vm.roll(block.number + VOTING_PERIOD + 1);
        vm.prank(alice);
        vm.expectRevert(YurikaGovernor.ProposalNotActive.selector);
        gov.castVote(id, true);
    }

    function test_castVote_revertsForZeroBalance() public {
        uint256 id = _proposeAsAlice();
        address noShards = address(0xDADA);
        vm.prank(noShards);
        vm.expectRevert(YurikaGovernor.NoVotingPower.selector);
        gov.castVote(id, true);
    }

    // ── execute() ────────────────────────────────────────────────

    function test_execute_runsCallWhenMajorityWithQuorum() public {
        uint256 id = _proposeAsAlice();
        vm.prank(alice); gov.castVote(id, true);   // 300
        vm.prank(bob);   gov.castVote(id, true);   // 200
        // total 500 / supply 1000 = 50% = quorum exactly

        vm.roll(block.number + VOTING_PERIOD + 1);

        gov.execute(id);

        // Side effect of executing the proposal: counter set to 42
        assertEq(target.n(), 42);
        assertTrue(gov.getProposal(id).executed);
    }

    function test_execute_revertsBeforeEnd() public {
        uint256 id = _proposeAsAlice();
        vm.expectRevert(YurikaGovernor.VotingNotEnded.selector);
        gov.execute(id);
    }

    function test_execute_revertsOnFailedMajority() public {
        uint256 id = _proposeAsAlice();
        // alice for 300, bob against 200 — for wins, would pass.
        // To test failure: alice against, bob against.
        vm.prank(alice); gov.castVote(id, false); // 300 against
        vm.prank(bob);   gov.castVote(id, false); // 200 against
        vm.roll(block.number + VOTING_PERIOD + 1);

        vm.expectRevert(YurikaGovernor.VoteFailed.selector);
        gov.execute(id);
    }

    function test_execute_revertsOnInsufficientQuorum() public {
        uint256 id = _proposeAsAlice();
        // Only alice votes (300). Quorum needs 50% of 1000 = 500.
        vm.prank(alice); gov.castVote(id, true);
        vm.roll(block.number + VOTING_PERIOD + 1);

        vm.expectRevert(YurikaGovernor.QuorumNotMet.selector);
        gov.execute(id);
    }

    function test_execute_revertsOnDoubleExecute() public {
        uint256 id = _proposeAsAlice();
        vm.prank(alice); gov.castVote(id, true);
        vm.prank(bob);   gov.castVote(id, true);
        vm.roll(block.number + VOTING_PERIOD + 1);
        gov.execute(id);

        vm.expectRevert(YurikaGovernor.AlreadyExecuted.selector);
        gov.execute(id);
    }
}
