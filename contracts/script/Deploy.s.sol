// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {YurikaVault} from "../src/YurikaVault.sol";
import {ShardFactory} from "../src/ShardFactory.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

/**
 * @title Deploy
 * @notice Single-run deploy script for the Yurika contract suite.
 *
 *  1. Predicts the ShardFactory's address using CREATE-nonce math.
 *  2. Deploys YurikaVault with that predicted address as governance.
 *  3. Deploys ShardFactory pointing at the vault. The factory IS the
 *     vault's governance — the only address allowed to link shard
 *     contracts to vaulted domains.
 *  4. On testnets, additionally deploys MockUSDC so dev curators can
 *     pay for shards in a stablecoin without real-USDC plumbing.
 *
 * Usage:
 *   # Local anvil:
 *   anvil &
 *   forge script script/Deploy.s.sol \
 *     --rpc-url http://127.0.0.1:8545 \
 *     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
 *     --broadcast
 *
 *   # Base Sepolia (requires .env):
 *   source .env
 *   forge script script/Deploy.s.sol \
 *     --rpc-url base_sepolia \
 *     --private-key $DEPLOYER_PRIVATE_KEY \
 *     --broadcast --verify
 */
contract Deploy is Script {
    function run() external {
        // Read deployer info — used for nonce prediction.
        address deployer = msg.sender;
        uint256 nonce = vm.getNonce(deployer);

        // After deploying the vault (nonce N), the factory will be deployed
        // at nonce N+1. Predict that address so the vault knows its governance.
        address predictedFactory = vm.computeCreateAddress(deployer, nonce + 1);
        console.log("Deployer:           ", deployer);
        console.log("Predicted factory:  ", predictedFactory);

        vm.startBroadcast();

        // 1. Vault
        YurikaVault vault = new YurikaVault(predictedFactory);
        console.log("YurikaVault:        ", address(vault));

        // 2. Factory (becomes the vault's only governance address)
        ShardFactory factory = new ShardFactory(vault);
        console.log("ShardFactory:       ", address(factory));
        require(address(factory) == predictedFactory, "factory address mismatch");

        // 3. MockUSDC — only useful on testnets / local. On mainnet, point
        //    real ShardTokens at the canonical USDC address instead.
        MockUSDC usdc = new MockUSDC();
        console.log("MockUSDC:           ", address(usdc));

        vm.stopBroadcast();

        console.log("");
        console.log("=== Deployed addresses ===");
        console.log("VAULT_ADDRESS=", address(vault));
        console.log("FACTORY_ADDRESS=", address(factory));
        console.log("MOCK_USDC_ADDRESS=", address(usdc));
    }
}
