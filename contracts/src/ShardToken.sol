// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "./IERC20.sol";

/**
 * @title ShardToken
 * @notice ERC-20 fractional-ownership token + payment-agnostic sale
 *         campaign for a single vaulted domain.
 *
 * Payment model is chosen at construction:
 *   - paymentToken == address(0)  → ETH-priced (msg.value)
 *   - paymentToken != address(0)  → ERC-20-priced (USDC-style)
 *
 * `pricePerShard` is expressed in the smallest unit of the chosen
 * payment medium (wei for ETH, 1e6 for USDC, etc.). One whole shard
 * = 1e18 token units.
 *
 * v0.7.0 model: 100% of received payment accrues to `founder`'s
 * pendingWithdrawals balance. Platform / referral / participation
 * fee routing lands in a later patch when our backend has off-chain
 * accounting for it.
 */
contract ShardToken {
    // ── ERC-20 state ──────────────────────────────────────────────

    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // ── Campaign state ────────────────────────────────────────────

    bytes32 public immutable domainId;       // Vault reference
    address public immutable vault;          // YurikaVault address
    address public immutable factory;        // deployer
    address public immutable founder;        // payouts go here
    IERC20  public immutable paymentToken;   // address(0) = ETH path
    uint256 public immutable pricePerShard;  // unit: payment token smallest
    uint256 public immutable fundingTarget;  // unit: payment token smallest
    uint256 public fundingRaised;
    uint256 public immutable campaignEndsAt;
    bool public campaignActive;

    mapping(address => uint256) public pendingWithdrawals;

    // ── Events ────────────────────────────────────────────────────

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event ShardsPurchased(address indexed buyer, uint256 shards, uint256 paid);
    event CampaignEnded(uint256 totalRaised, uint256 timestamp);
    event PayoutWithdrawn(address indexed recipient, uint256 amount);

    // ── Errors ────────────────────────────────────────────────────

    error InsufficientBalance();
    error InsufficientAllowance();
    error CampaignNotActive();
    error InsufficientPayment();
    error ExceedsSupply();
    error TransferFailed();
    error NothingToWithdraw();
    error InvalidConstructorArg();
    error EthNotAccepted();
    error UseErc20Path();

    // ── Constructor ───────────────────────────────────────────────

    /**
     * @param _name             ERC-20 name (e.g. "Yurika · yurika.space")
     * @param _symbol           ERC-20 symbol (e.g. "yYRK")
     * @param _totalSupply      Total shard supply (18 decimals)
     * @param _pricePerShard    Price for 1e18 shards, in paymentToken's smallest unit
     * @param _fundingTarget    Target raised; auto-closes campaign when hit
     * @param _campaignDuration Seconds from deploy until campaignEndsAt
     * @param _domainId         Vault key for the underlying domain
     * @param _vault            YurikaVault contract address
     * @param _founder          Address receiving payment payouts
     * @param _paymentToken     Address(0) = ETH path; ERC-20 address = token path
     */
    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _totalSupply,
        uint256 _pricePerShard,
        uint256 _fundingTarget,
        uint256 _campaignDuration,
        bytes32 _domainId,
        address _vault,
        address _founder,
        address _paymentToken
    ) {
        if (_totalSupply == 0) revert InvalidConstructorArg();
        if (_pricePerShard == 0) revert InvalidConstructorArg();
        if (_fundingTarget == 0) revert InvalidConstructorArg();
        if (_founder == address(0)) revert InvalidConstructorArg();
        if (_vault == address(0)) revert InvalidConstructorArg();
        if (_campaignDuration == 0) revert InvalidConstructorArg();

        name = _name;
        symbol = _symbol;
        domainId = _domainId;
        vault = _vault;
        factory = msg.sender;
        founder = _founder;
        pricePerShard = _pricePerShard;
        fundingTarget = _fundingTarget;
        paymentToken = IERC20(_paymentToken);
        campaignEndsAt = block.timestamp + _campaignDuration;
        campaignActive = true;

        // Mint the entire supply to the contract itself; buyers receive
        // shards out of this escrow via buyShards().
        totalSupply = _totalSupply;
        balanceOf[address(this)] = _totalSupply;
        emit Transfer(address(0), address(this), _totalSupply);
    }

    // ── Purchase ──────────────────────────────────────────────────

    /**
     * @notice Buy shards.
     *  - ETH path (paymentToken == address(0)): send ETH via msg.value.
     *    Overpayment is queued for the buyer in pendingWithdrawals.
     *  - ERC-20 path: caller must approve `cost` of paymentToken first.
     *    msg.value MUST be 0; this contract never escrows ETH on the
     *    ERC-20 path.
     */
    function buyShards(uint256 shardsRequested) external payable {
        if (!campaignActive || block.timestamp > campaignEndsAt) {
            revert CampaignNotActive();
        }
        if (balanceOf[address(this)] < shardsRequested) revert ExceedsSupply();

        uint256 cost = (shardsRequested * pricePerShard) / 1e18;
        bool isEthPath = address(paymentToken) == address(0);

        if (isEthPath) {
            if (msg.value < cost) revert InsufficientPayment();
        } else {
            if (msg.value != 0) revert UseErc20Path();
            // Pull payment from caller; reverts on failed transfer.
            bool ok = paymentToken.transferFrom(msg.sender, address(this), cost);
            if (!ok) revert TransferFailed();
        }

        balanceOf[address(this)] -= shardsRequested;
        balanceOf[msg.sender] += shardsRequested;
        fundingRaised += cost;

        emit Transfer(address(this), msg.sender, shardsRequested);
        emit ShardsPurchased(msg.sender, shardsRequested, cost);

        // 100% of cost accrues to the founder (in whatever token).
        pendingWithdrawals[founder] += cost;

        // ETH-path-only: any overpayment is queued for refund.
        if (isEthPath && msg.value > cost) {
            pendingWithdrawals[msg.sender] += (msg.value - cost);
        }

        // Auto-close if target hit.
        if (fundingRaised >= fundingTarget) {
            campaignActive = false;
            emit CampaignEnded(fundingRaised, block.timestamp);
        }
    }

    /// @dev Block bare ETH transfers on the ERC-20 path.
    receive() external payable {
        if (address(paymentToken) != address(0)) revert EthNotAccepted();
    }

    // ── ERC-20 ────────────────────────────────────────────────────

    function transfer(address to, uint256 amount) external returns (bool) {
        if (balanceOf[msg.sender] < amount) revert InsufficientBalance();
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        if (balanceOf[from] < amount) revert InsufficientBalance();
        uint256 a = allowance[from][msg.sender];
        if (a < amount) revert InsufficientAllowance();
        if (a != type(uint256).max) allowance[from][msg.sender] = a - amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }

    // ── Withdraw (pull-payment pattern) ───────────────────────────

    /**
     * @notice Withdraw the caller's pending balance.
     *         Used by founder (sale proceeds) and any buyer who overpaid
     *         on the ETH path (refunds).
     */
    function withdrawPayout() external {
        uint256 amount = pendingWithdrawals[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        pendingWithdrawals[msg.sender] = 0;

        if (address(paymentToken) == address(0)) {
            (bool sent,) = payable(msg.sender).call{value: amount}("");
            if (!sent) revert TransferFailed();
        } else {
            bool ok = paymentToken.transfer(msg.sender, amount);
            if (!ok) revert TransferFailed();
        }

        emit PayoutWithdrawn(msg.sender, amount);
    }

    // ── Views ─────────────────────────────────────────────────────

    /// @notice Funding percentage in basis points (10000 = 100%).
    function fundingPercentage() external view returns (uint256) {
        if (fundingTarget == 0) return 0;
        return (fundingRaised * 10_000) / fundingTarget;
    }

    /// @notice Shards still in escrow (not yet sold).
    function shardsAvailable() external view returns (uint256) {
        return balanceOf[address(this)];
    }

    /// @notice True when paid in native ETH (false for ERC-20 paths).
    function isEthPaid() external view returns (bool) {
        return address(paymentToken) == address(0);
    }
}
