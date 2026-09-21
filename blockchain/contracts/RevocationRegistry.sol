// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title RevocationRegistry
 * @dev W3C Verifiable Credentials ve Bitstring Status List iptal (revocation) durumunu zincirde tutan sözleşme.
 */
contract RevocationRegistry {
    struct StatusListAnchor {
        bytes32 rootHash;
        uint256 version;
        uint256 updatedAt;
    }

    struct CredentialRevocation {
        bool isRevoked;
        bytes32 reasonHash;
        uint256 revokedAt;
        address revokedBy;
    }

    address public owner;
    
    // Issuer address => (statusListId => StatusListAnchor)
    mapping(address => mapping(string => StatusListAnchor)) private _statusLists;

    // Credential Hash => CredentialRevocation
    mapping(bytes32 => CredentialRevocation) private _revokedCredentials;

    event StatusListAnchored(address indexed issuer, string indexed statusListId, bytes32 rootHash, uint256 version, uint256 timestamp);
    event CredentialRevoked(bytes32 indexed credentialHash, address indexed revokedBy, bytes32 reasonHash, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "RevocationRegistry: Yalnizca yetkili yonetici");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Bir W3C Bitstring Status List'in güncel root hash'ini ve versiyonunu zincire demler (anchor).
     */
    function anchorStatusList(string calldata statusListId, bytes32 rootHash, uint256 version) external {
        require(rootHash != bytes32(0), "RevocationRegistry: Gecersiz root hash");

        _statusLists[msg.sender][statusListId] = StatusListAnchor({
            rootHash: rootHash,
            version: version,
            updatedAt: block.timestamp
        });

        emit StatusListAnchored(msg.sender, statusListId, rootHash, version, block.timestamp);
    }

    /**
     * @notice Tekil bir kimlik belgesini (credential) kalıcı olarak iptal eder.
     */
    function revokeCredential(bytes32 credentialHash, bytes32 reasonHash) external {
        require(credentialHash != bytes32(0), "RevocationRegistry: Gecersiz credential hash");
        require(!_revokedCredentials[credentialHash].isRevoked, "RevocationRegistry: Zaten iptal edilmis");

        _revokedCredentials[credentialHash] = CredentialRevocation({
            isRevoked: true,
            reasonHash: reasonHash,
            revokedAt: block.timestamp,
            revokedBy: msg.sender
        });

        emit CredentialRevoked(credentialHash, msg.sender, reasonHash, block.timestamp);
    }

    /**
     * @notice Bir credential'ın iptal durumunu sorgular.
     */
    function isCredentialRevoked(bytes32 credentialHash) external view returns (bool) {
        return _revokedCredentials[credentialHash].isRevoked;
    }

    /**
     * @notice Status List anchor bilgisini getirir.
     */
    function getStatusListAnchor(address issuer, string calldata statusListId) external view returns (bytes32 rootHash, uint256 version, uint256 updatedAt) {
        StatusListAnchor memory anchor = _statusLists[issuer][statusListId];
        return (anchor.rootHash, anchor.version, anchor.updatedAt);
    }
}
