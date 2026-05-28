// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ShardToken} from "./ShardToken.sol";

/**
 * @title YurikaGovernor
 * @notice Minimal on-chain governance bound to a single ShardToken.
 *         Voting weight is the caller's ShardToken balance at the
 *         moment of voting.
 *
 * Lifecycle:
 *   propose(target, callData, description)
 *      → returns proposalId
 *   castVote(proposalId, support)            during votingPeriodBlocks
 *   execute(proposalId)                      after end, if quorum + majority
 *
 * LIMITATION (v0.7.0): voting weight is read at vote time, not a
 * snapshot at proposal creation. A holder can transfer shards to a
 * second wallet and vote twice. The mitigation is ERC-20Votes-style
 * snapshot tracking; we'll add it in a later patch when the
 * ShardToken upgrade story is in place.
 */
contract YurikaGovernor {
    // ── Types ─────────────────────────────────────────────────────

    struct Proposal {
        address proposer;
        address target;
        bytes callData;
        uint256 startBlock;
        uint256 endBlock;
        uint256 forVotes;
        uint256 againstVotes;
        bool executed;
        string description;
    }

    // ── State ─────────────────────────────────────────────────────

    ShardToken public immutable shardToken;
    uint256 public immutable votingPeriodBlocks;
    uint256 public immutable quorumBps;       // 5100 = 51%
    uint256 public immutable proposalThreshold; // min shards to propose

    Proposal[] public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    // ── Events ────────────────────────────────────────────────────

    event ProposalCreated(
        uint256 indexed proposalId,
        address indexed proposer,
        address indexed target,
        uint256 startBlock,
        uint256 endBlock,
        string description
    );

    event VoteCast(
        uint256 indexed proposalId,
        address indexed voter,
        bool support,
        uint256 weight
    );

    event ProposalExecuted(uint256 indexed proposalId, bool callSucceeded);

    // ── Errors ────────────────────────────────────────────────────

    error BelowProposalThreshold();
    error ProposalNotActive();
    error AlreadyVoted();
    error NoVotingPower();
    error VotingNotEnded();
    error AlreadyExecuted();
    error QuorumNotMet();
    error VoteFailed();
    error InvalidConfig();

    // ── Constructor ───────────────────────────────────────────────

    constructor(
        ShardToken _shardToken,
        uint256 _votingPeriodBlocks,
        uint256 _quorumBps,
        uint256 _proposalThreshold
    ) {
        if (address(_shardToken) == address(0)) revert InvalidConfig();
        if (_votingPeriodBlocks == 0) revert InvalidConfig();
        if (_quorumBps == 0 || _quorumBps > 10_000) revert InvalidConfig();

        shardToken = _shardToken;
        votingPeriodBlocks = _votingPeriodBlocks;
        quorumBps = _quorumBps;
        proposalThreshold = _proposalThreshold;
    }

    // ── Propose ───────────────────────────────────────────────────

    function propose(
        address target,
        bytes calldata callData,
        string calldata description
    ) external returns (uint256 proposalId) {
        if (shardToken.balanceOf(msg.sender) < proposalThreshold) {
            revert BelowProposalThreshold();
        }

        proposalId = proposals.length;
        proposals.push(
            Proposal({
                proposer: msg.sender,
                target: target,
                callData: callData,
                startBlock: block.number,
                endBlock: block.number + votingPeriodBlocks,
                forVotes: 0,
                againstVotes: 0,
                executed: false,
                description: description
            })
        );

        emit ProposalCreated(
            proposalId,
            msg.sender,
            target,
            block.number,
            block.number + votingPeriodBlocks,
            description
        );
    }

    // ── Vote ──────────────────────────────────────────────────────

    function castVote(uint256 proposalId, bool support) external {
        Proposal storage p = proposals[proposalId];
        if (block.number < p.startBlock || block.number > p.endBlock) {
            revert ProposalNotActive();
        }
        if (hasVoted[proposalId][msg.sender]) revert AlreadyVoted();

        uint256 weight = shardToken.balanceOf(msg.sender);
        if (weight == 0) revert NoVotingPower();

        hasVoted[proposalId][msg.sender] = true;
        if (support) {
            p.forVotes += weight;
        } else {
            p.againstVotes += weight;
        }

        emit VoteCast(proposalId, msg.sender, support, weight);
    }

    // ── Execute ───────────────────────────────────────────────────

    /**
     * @notice Execute a proposal after the voting period if quorum is
     *         met and forVotes > againstVotes. Reverts otherwise.
     */
    function execute(uint256 proposalId) external returns (bool) {
        Proposal storage p = proposals[proposalId];
        if (block.number <= p.endBlock) revert VotingNotEnded();
        if (p.executed) revert AlreadyExecuted();

        uint256 totalCast = p.forVotes + p.againstVotes;
        uint256 supply = shardToken.totalSupply();
        uint256 quorumThreshold = (supply * quorumBps) / 10_000;
        if (totalCast < quorumThreshold) revert QuorumNotMet();
        if (p.forVotes <= p.againstVotes) revert VoteFailed();

        p.executed = true;

        (bool ok,) = p.target.call(p.callData);
        emit ProposalExecuted(proposalId, ok);
        return ok;
    }

    // ── Views ─────────────────────────────────────────────────────

    function proposalCount() external view returns (uint256) {
        return proposals.length;
    }

    function getProposal(uint256 proposalId)
        external
        view
        returns (Proposal memory)
    {
        return proposals[proposalId];
    }
}
