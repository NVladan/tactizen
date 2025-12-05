// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ElectionResults
 * @dev Stores election results on-chain for transparency and auditability.
 * Results are published after elections end, with full data stored on IPFS
 * and a hash stored on-chain for verification.
 */
contract ElectionResults {
    // Election types
    enum ElectionType { PARTY_PRESIDENT, COUNTRY_PRESIDENT, CONGRESS }

    // Simplified election result structure
    struct ElectionResult {
        uint256 electionId;
        ElectionType electionType;
        uint256 countryId;
        uint256 partyId;
        uint256 winnerId;
        uint256 totalVotes;
        uint256 totalCandidates;
        string ipfsHash;
        bytes32 resultsHash;
        uint256 publishedAt;
        address publishedBy;
    }

    // Storage
    mapping(bytes32 => ElectionResult) public elections;
    bytes32[] public allElectionKeys;

    // Authorized publishers
    mapping(address => bool) public authorizedPublishers;
    address public owner;

    // Events
    event ElectionResultPublished(
        bytes32 indexed electionKey,
        uint256 indexed electionId,
        ElectionType electionType,
        uint256 winnerId,
        uint256 totalVotes,
        string ipfsHash
    );

    event PublisherAuthorized(address indexed publisher);
    event PublisherRevoked(address indexed publisher);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyAuthorized() {
        require(authorizedPublishers[msg.sender] || msg.sender == owner, "Not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedPublishers[msg.sender] = true;
    }

    /**
     * @dev Generate a unique key for an election
     */
    function getElectionKey(
        ElectionType electionType,
        uint256 electionId,
        uint256 countryId,
        uint256 partyId
    ) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(electionType, electionId, countryId, partyId));
    }

    /**
     * @dev Publish election results (any type)
     */
    function publishResult(
        uint256 electionId,
        ElectionType electionType,
        uint256 countryId,
        uint256 partyId,
        uint256 winnerId,
        uint256 totalVotes,
        uint256 totalCandidates,
        string calldata ipfsHash,
        bytes32 resultsHash
    ) external onlyAuthorized {
        bytes32 electionKey = getElectionKey(electionType, electionId, countryId, partyId);
        require(elections[electionKey].publishedAt == 0, "Already published");

        elections[electionKey] = ElectionResult({
            electionId: electionId,
            electionType: electionType,
            countryId: countryId,
            partyId: partyId,
            winnerId: winnerId,
            totalVotes: totalVotes,
            totalCandidates: totalCandidates,
            ipfsHash: ipfsHash,
            resultsHash: resultsHash,
            publishedAt: block.timestamp,
            publishedBy: msg.sender
        });

        allElectionKeys.push(electionKey);

        emit ElectionResultPublished(
            electionKey,
            electionId,
            electionType,
            winnerId,
            totalVotes,
            ipfsHash
        );
    }

    /**
     * @dev Verify results hash matches stored hash
     */
    function verifyResults(bytes32 electionKey, bytes32 providedHash) external view returns (bool) {
        return elections[electionKey].resultsHash == providedHash;
    }

    /**
     * @dev Get election result by key
     */
    function getElectionResult(bytes32 electionKey) external view returns (ElectionResult memory) {
        return elections[electionKey];
    }

    /**
     * @dev Get total number of published elections
     */
    function getTotalElections() external view returns (uint256) {
        return allElectionKeys.length;
    }

    /**
     * @dev Get election key by index
     */
    function getElectionKeyByIndex(uint256 index) external view returns (bytes32) {
        require(index < allElectionKeys.length, "Index out of bounds");
        return allElectionKeys[index];
    }

    // Admin functions
    function authorizePublisher(address publisher) external onlyOwner {
        authorizedPublishers[publisher] = true;
        emit PublisherAuthorized(publisher);
    }

    function revokePublisher(address publisher) external onlyOwner {
        authorizedPublishers[publisher] = false;
        emit PublisherRevoked(publisher);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
}
