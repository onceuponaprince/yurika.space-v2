// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title YurikaVault
 * @notice Secure custody contract for domain ownership credentials.
 *
 * Flow:
 *   1. Founder calls `vault()` with a domainId (keccak256 of fqdn) and
 *      a metadata hash (IPFS CID or off-chain proof hash).
 *   2. Contract records the entry and emits `DomainVaulted`.
 *   3. Governance links the ShardToken contract once the shard
 *      campaign is deployed.
 *   4. Founder can `withdraw()` to un-vault — separate from shard
 *      withdrawal logic.
 *
 * One vault contract serves all founders; per-domain state is keyed
 * by the bytes32 domainId. The Django backend stores the same hash
 * in `vault_contract_address` + an off-chain mapping.
 */
contract YurikaVault {
    // ── Types ─────────────────────────────────────────────────────

    struct VaultedDomain {
        address owner;
        bytes32 metadataHash;   // IPFS CID or off-chain proof hash
        uint256 vaultedAt;
        bool isActive;
        address shardContract;  // Set by governance after ShardToken deploy
    }

    // ── State ─────────────────────────────────────────────────────

    mapping(bytes32 => VaultedDomain) public vaults;
    mapping(address => bytes32[]) public ownerDomains;

    address public immutable governance;
    bool public paused;

    // ── Events ────────────────────────────────────────────────────

    event DomainVaulted(
        bytes32 indexed domainId,
        address indexed owner,
        bytes32 metadataHash,
        uint256 timestamp
    );

    event DomainWithdrawn(
        bytes32 indexed domainId,
        address indexed owner,
        uint256 timestamp
    );

    event ShardContractLinked(
        bytes32 indexed domainId,
        address indexed shardContract
    );

    event VaultPaused(address by);
    event VaultUnpaused(address by);

    // ── Errors ────────────────────────────────────────────────────

    error NotOwner();
    error AlreadyVaulted();
    error DomainNotFound();
    error VaultIsPaused();
    error NotGovernance();
    error InvalidGovernance();

    // ── Modifiers ─────────────────────────────────────────────────

    modifier onlyOwnerOf(bytes32 domainId) {
        if (vaults[domainId].owner != msg.sender) revert NotOwner();
        _;
    }

    modifier onlyGovernance() {
        if (msg.sender != governance) revert NotGovernance();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert VaultIsPaused();
        _;
    }

    // ── Constructor ───────────────────────────────────────────────

    constructor(address _governance) {
        if (_governance == address(0)) revert InvalidGovernance();
        governance = _governance;
    }

    // ── Core ──────────────────────────────────────────────────────

    /**
     * @notice Vault a domain. domainId = keccak256(abi.encodePacked(fqdn)).
     * @param domainId     Stable identifier of the domain.
     * @param metadataHash IPFS CID / proof hash of ownership credentials.
     */
    function vault(bytes32 domainId, bytes32 metadataHash)
        external
        whenNotPaused
    {
        if (vaults[domainId].isActive) revert AlreadyVaulted();

        vaults[domainId] = VaultedDomain({
            owner: msg.sender,
            metadataHash: metadataHash,
            vaultedAt: block.timestamp,
            isActive: true,
            shardContract: address(0)
        });

        ownerDomains[msg.sender].push(domainId);

        emit DomainVaulted(domainId, msg.sender, metadataHash, block.timestamp);
    }

    /**
     * @notice Un-vault a domain. Caller must be the original founder.
     *
     * NOTE: a more conservative version would require shard-holder
     * supermajority approval if shards are outstanding. v0.7.0 keeps
     * the simpler founder-only model; shard-governance withdrawal
     * lands in a later patch.
     */
    function withdraw(bytes32 domainId)
        external
        onlyOwnerOf(domainId)
        whenNotPaused
    {
        vaults[domainId].isActive = false;
        emit DomainWithdrawn(domainId, msg.sender, block.timestamp);
    }

    /**
     * @notice Governance links the ShardToken contract once deployed.
     */
    function linkShardContract(bytes32 domainId, address shardContract)
        external
        onlyGovernance
    {
        if (!vaults[domainId].isActive) revert DomainNotFound();
        vaults[domainId].shardContract = shardContract;
        emit ShardContractLinked(domainId, shardContract);
    }

    // ── Emergency controls ────────────────────────────────────────

    function pause() external onlyGovernance {
        paused = true;
        emit VaultPaused(msg.sender);
    }

    function unpause() external onlyGovernance {
        paused = false;
        emit VaultUnpaused(msg.sender);
    }

    // ── Views ─────────────────────────────────────────────────────

    function getVault(bytes32 domainId) external view returns (VaultedDomain memory) {
        return vaults[domainId];
    }

    function getOwnerDomains(address owner) external view returns (bytes32[] memory) {
        return ownerDomains[owner];
    }

    /// @notice Convenience helper: keccak256(fqdn) for off-chain callers.
    function domainIdOf(string calldata fqdn) external pure returns (bytes32) {
        return keccak256(abi.encodePacked(fqdn));
    }
}
