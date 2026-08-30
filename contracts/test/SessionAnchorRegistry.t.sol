// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {SessionAnchorRegistry} from "../SessionAnchorRegistry.sol";

contract SessionAnchorRegistryTest is Test {
    SessionAnchorRegistry reg;
    address owner = address(this);
    address stranger = address(0xBEEF);

    function setUp() public { reg = new SessionAnchorRegistry(); }

    function test_anchor_sets_timestamp_and_emits() public {
        bytes32 root = keccak256("r1");
        vm.expectEmit(true, false, false, true);
        emit SessionAnchorRegistry.BatchAnchored(root, 3, block.timestamp);
        reg.anchorBatch(root, 3);
        assertEq(reg.anchoredAt(root), block.timestamp);
    }

    function test_non_owner_reverts() public {
        vm.prank(stranger);
        vm.expectRevert(SessionAnchorRegistry.NotOwner.selector);
        reg.anchorBatch(keccak256("r"), 1);
    }

    function test_double_anchor_reverts() public {
        bytes32 root = keccak256("r2");
        reg.anchorBatch(root, 1);
        vm.expectRevert(SessionAnchorRegistry.AlreadyAnchored.selector);
        reg.anchorBatch(root, 1);
    }

    function test_empty_batch_reverts() public {
        vm.expectRevert(SessionAnchorRegistry.EmptyBatch.selector);
        reg.anchorBatch(keccak256("r3"), 0);
    }
}
