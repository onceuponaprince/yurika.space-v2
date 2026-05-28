// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ShardToken} from "../src/ShardToken.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract ShardTokenTest is Test {
    address founder = address(0xB2);
    address alice   = address(0xC3);
    address bob     = address(0xC4);
    address vault   = address(0xD1);

    bytes32 constant DOMAIN_ID = keccak256("yurika.space");
    uint256 constant SUPPLY = 1_000e18;            // 1000 shards
    uint256 constant PRICE_WEI = 0.01 ether;       // 0.01 ETH per shard
    uint256 constant TARGET_WEI = 5 ether;         // close at 5 ETH raised
    uint256 constant DURATION = 30 days;

    // ── ETH PATH ─────────────────────────────────────────────────

    function _ethToken() internal returns (ShardToken) {
        return new ShardToken(
            "Yurika yurika.space",
            "yYRK",
            SUPPLY,
            PRICE_WEI,
            TARGET_WEI,
            DURATION,
            DOMAIN_ID,
            vault,
            founder,
            address(0)  // ETH path
        );
    }

    function test_eth_constructor_setsState() public {
        ShardToken t = _ethToken();
        assertEq(t.totalSupply(), SUPPLY);
        assertEq(t.balanceOf(address(t)), SUPPLY);
        assertEq(t.founder(), founder);
        assertEq(t.pricePerShard(), PRICE_WEI);
        assertTrue(t.campaignActive());
        assertTrue(t.isEthPaid());
    }

    function test_eth_buyShards_happyPath() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        t.buyShards{value: 0.5 ether}(50e18); // 50 shards * 0.01 = 0.5 ETH

        assertEq(t.balanceOf(alice), 50e18);
        assertEq(t.balanceOf(address(t)), SUPPLY - 50e18);
        assertEq(t.fundingRaised(), 0.5 ether);
        assertEq(t.pendingWithdrawals(founder), 0.5 ether);
    }

    function test_eth_buyShards_revertsOnUnderpayment() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        vm.expectRevert(ShardToken.InsufficientPayment.selector);
        t.buyShards{value: 0.1 ether}(50e18); // cost = 0.5 ETH
    }

    function test_eth_overpayment_queuedAsRefund() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        t.buyShards{value: 1 ether}(50e18); // cost 0.5, refund 0.5

        assertEq(t.pendingWithdrawals(alice), 0.5 ether);
        assertEq(t.pendingWithdrawals(founder), 0.5 ether);
    }

    function test_eth_buyShards_autoClosesAtTarget() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 10 ether);

        // 500 shards * 0.01 ETH = 5 ETH = TARGET
        vm.prank(alice);
        t.buyShards{value: 5 ether}(500e18);

        assertFalse(t.campaignActive());
        assertEq(t.fundingRaised(), TARGET_WEI);
    }

    function test_eth_buyShards_revertsAfterClose() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 10 ether);

        vm.prank(alice);
        t.buyShards{value: 5 ether}(500e18); // hits target, closes

        vm.deal(bob, 1 ether);
        vm.prank(bob);
        vm.expectRevert(ShardToken.CampaignNotActive.selector);
        t.buyShards{value: 0.1 ether}(10e18);
    }

    function test_eth_buyShards_revertsAfterDeadline() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.warp(block.timestamp + DURATION + 1);

        vm.prank(alice);
        vm.expectRevert(ShardToken.CampaignNotActive.selector);
        t.buyShards{value: 0.5 ether}(50e18);
    }

    function test_eth_withdrawPayout_sendsFunds() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        t.buyShards{value: 0.5 ether}(50e18);

        uint256 founderBalBefore = founder.balance;
        vm.prank(founder);
        t.withdrawPayout();
        assertEq(founder.balance - founderBalBefore, 0.5 ether);
        assertEq(t.pendingWithdrawals(founder), 0);
    }

    function test_eth_withdrawPayout_revertsOnZero() public {
        ShardToken t = _ethToken();
        vm.prank(founder);
        vm.expectRevert(ShardToken.NothingToWithdraw.selector);
        t.withdrawPayout();
    }

    // ── ERC-20 (USDC) PATH ───────────────────────────────────────

    function _usdcToken(MockUSDC usdc) internal returns (ShardToken) {
        return new ShardToken(
            "Yurika yurika.space",
            "yYRK",
            SUPPLY,
            5e6,       // 5 USDC per shard (USDC has 6 decimals)
            2_500e6,   // 2500 USDC target
            DURATION,
            DOMAIN_ID,
            vault,
            founder,
            address(usdc)
        );
    }

    function test_usdc_constructor_isErc20Path() public {
        MockUSDC usdc = new MockUSDC();
        ShardToken t = _usdcToken(usdc);
        assertFalse(t.isEthPaid());
        assertEq(address(t.paymentToken()), address(usdc));
    }

    function test_usdc_buyShards_happyPath() public {
        MockUSDC usdc = new MockUSDC();
        ShardToken t = _usdcToken(usdc);

        usdc.mint(alice, 1000e6);
        vm.startPrank(alice);
        usdc.approve(address(t), 500e6);
        t.buyShards(100e18); // 100 shards * 5 USDC = 500 USDC
        vm.stopPrank();

        assertEq(t.balanceOf(alice), 100e18);
        assertEq(usdc.balanceOf(address(t)), 500e6);
        assertEq(t.pendingWithdrawals(founder), 500e6);
    }

    function test_usdc_buyShards_rejectsAttachedEth() public {
        MockUSDC usdc = new MockUSDC();
        ShardToken t = _usdcToken(usdc);

        usdc.mint(alice, 1000e6);
        vm.deal(alice, 1 ether);
        vm.startPrank(alice);
        usdc.approve(address(t), 500e6);
        vm.expectRevert(ShardToken.UseErc20Path.selector);
        t.buyShards{value: 1 wei}(100e18);
        vm.stopPrank();
    }

    function test_usdc_withdrawPayout_sendsTokens() public {
        MockUSDC usdc = new MockUSDC();
        ShardToken t = _usdcToken(usdc);

        usdc.mint(alice, 1000e6);
        vm.startPrank(alice);
        usdc.approve(address(t), 500e6);
        t.buyShards(100e18);
        vm.stopPrank();

        vm.prank(founder);
        t.withdrawPayout();

        assertEq(usdc.balanceOf(founder), 500e6);
        assertEq(t.pendingWithdrawals(founder), 0);
    }

    // ── ERC-20 transfers (the shard token itself) ────────────────

    function test_transfer_movesShards() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        t.buyShards{value: 0.5 ether}(50e18);

        vm.prank(alice);
        t.transfer(bob, 20e18);

        assertEq(t.balanceOf(alice), 30e18);
        assertEq(t.balanceOf(bob), 20e18);
    }

    function test_transferFrom_decreasesAllowance() public {
        ShardToken t = _ethToken();
        vm.deal(alice, 1 ether);

        vm.prank(alice);
        t.buyShards{value: 0.5 ether}(50e18);

        vm.prank(alice);
        t.approve(bob, 30e18);

        vm.prank(bob);
        t.transferFrom(alice, bob, 25e18);

        assertEq(t.balanceOf(alice), 25e18);
        assertEq(t.balanceOf(bob), 25e18);
        assertEq(t.allowance(alice, bob), 5e18);
    }
}
