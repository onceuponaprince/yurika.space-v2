// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ShardToken} from "./ShardToken.sol";
import {YurikaVault} from "./YurikaVault.sol";

/**
 * @title ShardFactory
 * @notice Deploys one ShardToken per vaulted domain and tells the
 *         Vault about the resulting contract address.
 *
 * Why a factory:
 *   - Per-campaign deploys are noisy; users would otherwise have to
 *     copy bytecode + constructor args around.
 *   - The factory holds the governance address it needs to call
 *     `vault.linkShardContract()`, so the vault doesn't have to
 *     expose that to every founder.
 *
 * Permission model: anyone who owns a domain in the vault may
 * `deploy()` a ShardToken for it. The factory itself acts as
 * governance for the vault's link call — set at construction.
 */
contract ShardFactory {
    YurikaVault public immutable vault;

    /// domainId => deployed ShardToken (zero if none yet)
    mapping(bytes32 => address) public shardTokenOf;

    /// All deployed shard tokens, indexed for off-chain enumeration.
    address[] public deployed;

    // ── Events ────────────────────────────────────────────────────

    event ShardTokenDeployed(
        bytes32 indexed domainId,
        address indexed shardToken,
        address indexed founder,
        address paymentToken
    );

    // ── Errors ────────────────────────────────────────────────────

    error NotDomainOwner();
    error AlreadyDeployed();
    error VaultInactive();

    // ── Constructor ───────────────────────────────────────────────

    constructor(YurikaVault _vault) {
        vault = _vault;
    }

    // ── Core ──────────────────────────────────────────────────────

    /**
     * @notice Deploy a ShardToken for a vaulted domain. Caller MUST
     *         be the domain's vaulted owner; the factory then asks
     *         the vault to link the new contract.
     *
     *         For this to succeed, the vault must have been
     *         constructed with this factory as `governance` (so the
     *         link call can succeed).
     */
    function deploy(
        bytes32 domainId,
        string calldata name,
        string calldata symbol,
        uint256 totalSupply,
        uint256 pricePerShard,
        uint256 fundingTarget,
        uint256 campaignDuration,
        address paymentToken
    ) external returns (address tokenAddr) {
        if (shardTokenOf[domainId] != address(0)) revert AlreadyDeployed();

        YurikaVault.VaultedDomain memory v = vault.getVault(domainId);
        if (!v.isActive) revert VaultInactive();
        if (v.owner != msg.sender) revert NotDomainOwner();

        ShardToken t = new ShardToken(
            name,
            symbol,
            totalSupply,
            pricePerShard,
            fundingTarget,
            campaignDuration,
            domainId,
            address(vault),
            msg.sender,
            paymentToken
        );
        tokenAddr = address(t);

        shardTokenOf[domainId] = tokenAddr;
        deployed.push(tokenAddr);

        // The factory is governance, so this call is authorized.
        vault.linkShardContract(domainId, tokenAddr);

        emit ShardTokenDeployed(domainId, tokenAddr, msg.sender, paymentToken);
    }

    // ── Views ─────────────────────────────────────────────────────

    function deployedCount() external view returns (uint256) {
        return deployed.length;
    }
}
