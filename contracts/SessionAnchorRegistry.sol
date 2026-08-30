// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Binds a Merkle root (of a batch of agent-session chain heads) to a
/// block timestamp, once, irreversibly. Owner-only writes.
contract SessionAnchorRegistry {
    address public immutable owner;

    /// merkleRoot => block.timestamp it was anchored at. 0 = never anchored.
    mapping(bytes32 => uint256) public anchoredAt;

    event BatchAnchored(bytes32 indexed root, uint256 sessionCount, uint256 timestamp);

    error NotOwner();
    error AlreadyAnchored();
    error EmptyBatch();

    constructor() {
        owner = msg.sender;
    }

    function anchorBatch(bytes32 root, uint256 sessionCount) external {
        if (msg.sender != owner) revert NotOwner();
        if (sessionCount == 0) revert EmptyBatch();
        if (anchoredAt[root] != 0) revert AlreadyAnchored();
        anchoredAt[root] = block.timestamp;
        emit BatchAnchored(root, sessionCount, block.timestamp);
    }
}
