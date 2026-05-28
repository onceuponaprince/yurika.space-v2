// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {YurikaVault} from "../src/YurikaVault.sol";

contract YurikaVaultTest is Test {
    YurikaVault vault;
    address governance = address(0xA1);
    address founder    = address(0xB2);
    address other      = address(0xC3);

    bytes32 constant DOMAIN_ID    = keccak256("yurika.space");
    bytes32 constant METADATA_HASH = keccak256("ipfs://Qm...");

    function setUp() public {
        vault = new YurikaVault(governance);
    }

    // ── Constructor ──────────────────────────────────────────────

    function test_constructor_setsGovernance() public view {
        assertEq(vault.governance(), governance);
    }

    function test_constructor_revertsOnZeroGovernance() public {
        vm.expectRevert(YurikaVault.InvalidGovernance.selector);
        new YurikaVault(address(0));
    }

    function test_constructor_paused_isFalse() public view {
        assertEq(vault.paused(), false);
    }

    // ── vault() ──────────────────────────────────────────────────

    function test_vault_recordsDomain() public {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        YurikaVault.VaultedDomain memory v = vault.getVault(DOMAIN_ID);
        assertEq(v.owner, founder);
        assertEq(v.metadataHash, METADATA_HASH);
        assertTrue(v.isActive);
        assertEq(v.shardContract, address(0));
        assertEq(v.vaultedAt, block.timestamp);
    }

    function test_vault_emitsEvent() public {
        vm.prank(founder);
        vm.expectEmit(true, true, false, true);
        emit YurikaVault.DomainVaulted(DOMAIN_ID, founder, METADATA_HASH, block.timestamp);
        vault.vault(DOMAIN_ID, METADATA_HASH);
    }

    function test_vault_revertsOnDoubleVault() public {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        vm.prank(founder);
        vm.expectRevert(YurikaVault.AlreadyVaulted.selector);
        vault.vault(DOMAIN_ID, METADATA_HASH);
    }

    function test_vault_revertsWhenPaused() public {
        vm.prank(governance);
        vault.pause();

        vm.prank(founder);
        vm.expectRevert(YurikaVault.VaultIsPaused.selector);
        vault.vault(DOMAIN_ID, METADATA_HASH);
    }

    function test_vault_appendsToOwnerDomains() public {
        bytes32 d2 = keccak256("yurika.io");
        vm.startPrank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);
        vault.vault(d2, METADATA_HASH);
        vm.stopPrank();

        bytes32[] memory mine = vault.getOwnerDomains(founder);
        assertEq(mine.length, 2);
        assertEq(mine[0], DOMAIN_ID);
        assertEq(mine[1], d2);
    }

    // ── withdraw() ───────────────────────────────────────────────

    function test_withdraw_marksInactive() public {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        vm.prank(founder);
        vault.withdraw(DOMAIN_ID);

        assertFalse(vault.getVault(DOMAIN_ID).isActive);
    }

    function test_withdraw_revertsForNonOwner() public {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        vm.prank(other);
        vm.expectRevert(YurikaVault.NotOwner.selector);
        vault.withdraw(DOMAIN_ID);
    }

    // ── linkShardContract() ──────────────────────────────────────

    function test_link_setsShardContract() public {
        address shardAddr = address(0xDEADBEEF);
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        vm.prank(governance);
        vault.linkShardContract(DOMAIN_ID, shardAddr);

        assertEq(vault.getVault(DOMAIN_ID).shardContract, shardAddr);
    }

    function test_link_revertsForNonGovernance() public {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);

        vm.prank(founder);
        vm.expectRevert(YurikaVault.NotGovernance.selector);
        vault.linkShardContract(DOMAIN_ID, address(0x1));
    }

    function test_link_revertsIfDomainInactive() public {
        vm.prank(governance);
        vm.expectRevert(YurikaVault.DomainNotFound.selector);
        vault.linkShardContract(DOMAIN_ID, address(0x1));
    }

    // ── pause / unpause ──────────────────────────────────────────

    function test_pause_onlyGovernance() public {
        vm.prank(other);
        vm.expectRevert(YurikaVault.NotGovernance.selector);
        vault.pause();
    }

    function test_pause_then_unpause_restoresVaulting() public {
        vm.prank(governance);
        vault.pause();
        assertTrue(vault.paused());

        vm.prank(governance);
        vault.unpause();
        assertFalse(vault.paused());

        // Vaulting works again after unpause.
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);
        assertTrue(vault.getVault(DOMAIN_ID).isActive);
    }

    // ── domainIdOf helper ────────────────────────────────────────

    function test_domainIdOf_matchesKeccak() public view {
        bytes32 computed = vault.domainIdOf("yurika.space");
        assertEq(computed, keccak256(abi.encodePacked("yurika.space")));
    }
}
