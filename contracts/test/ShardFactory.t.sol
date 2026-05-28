// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {YurikaVault} from "../src/YurikaVault.sol";
import {ShardFactory} from "../src/ShardFactory.sol";
import {ShardToken} from "../src/ShardToken.sol";

contract ShardFactoryTest is Test {
    YurikaVault vault;
    ShardFactory factory;

    address founder = address(0xB2);
    address other   = address(0xC3);

    bytes32 constant DOMAIN_ID    = keccak256("yurika.space");
    bytes32 constant METADATA_HASH = keccak256("ipfs://Qm...");

    function setUp() public {
        // Two-step deploy: vault first with a temp governance, then
        // overwrite governance to the factory. We use the trick of
        // deploying factory pointing at the vault and granting it
        // governance at construction time.
        //
        // Simpler approach: predict factory address using CREATE2, OR
        // use a deployer pattern. For tests we deploy vault with the
        // forthcoming factory address as governance via vm.computeAddress.
        // Actual pattern: deploy a "placeholder" governance, then
        // upgrade. But our YurikaVault has immutable governance.
        //
        // Simplest test approach: predict factory address.
        address predictedFactory = vm.computeCreateAddress(
            address(this),
            vm.getNonce(address(this)) + 1
        );
        vault = new YurikaVault(predictedFactory);
        factory = new ShardFactory(vault);
        assertEq(vault.governance(), address(factory));
    }

    function _vaultDomain() internal {
        vm.prank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);
    }

    // ── deploy() ─────────────────────────────────────────────────

    function test_deploy_createsShardTokenAndLinksVault() public {
        _vaultDomain();

        vm.prank(founder);
        address shardAddr = factory.deploy(
            DOMAIN_ID,
            "Yurika yurika.space",
            "yYRK",
            1000e18,
            0.01 ether,
            5 ether,
            30 days,
            address(0) // ETH path
        );

        assertEq(factory.shardTokenOf(DOMAIN_ID), shardAddr);
        assertEq(vault.getVault(DOMAIN_ID).shardContract, shardAddr);

        ShardToken token = ShardToken(payable(shardAddr));
        assertEq(token.domainId(), DOMAIN_ID);
        assertEq(token.founder(), founder);
        assertEq(token.totalSupply(), 1000e18);
    }

    function test_deploy_revertsForNonDomainOwner() public {
        _vaultDomain();

        vm.prank(other);
        vm.expectRevert(ShardFactory.NotDomainOwner.selector);
        factory.deploy(
            DOMAIN_ID,
            "x", "x", 1000e18, 0.01 ether, 5 ether, 30 days, address(0)
        );
    }

    function test_deploy_revertsOnInactiveVault() public {
        // never vaulted
        vm.prank(founder);
        vm.expectRevert(ShardFactory.VaultInactive.selector);
        factory.deploy(
            DOMAIN_ID,
            "x", "x", 1000e18, 0.01 ether, 5 ether, 30 days, address(0)
        );
    }

    function test_deploy_revertsOnDoubleDeploy() public {
        _vaultDomain();
        vm.startPrank(founder);
        factory.deploy(DOMAIN_ID, "x", "x", 1000e18, 0.01 ether, 5 ether, 30 days, address(0));
        vm.expectRevert(ShardFactory.AlreadyDeployed.selector);
        factory.deploy(DOMAIN_ID, "x", "x", 1000e18, 0.01 ether, 5 ether, 30 days, address(0));
        vm.stopPrank();
    }

    function test_deployedCount_tracksDeploys() public {
        bytes32 d2 = keccak256("yurika.io");
        vm.startPrank(founder);
        vault.vault(DOMAIN_ID, METADATA_HASH);
        vault.vault(d2, METADATA_HASH);

        factory.deploy(DOMAIN_ID, "a", "a", 1000e18, 0.01 ether, 5 ether, 30 days, address(0));
        assertEq(factory.deployedCount(), 1);

        factory.deploy(d2, "b", "b", 1000e18, 0.01 ether, 5 ether, 30 days, address(0));
        assertEq(factory.deployedCount(), 2);
        vm.stopPrank();
    }
}
