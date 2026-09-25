// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title EmergencyRecovery
 * @dev Guardian-based social recovery mechanism inspired by EIP-4337 (Account Abstraction).
 * Allows users to register 3 Guardians. If a device or private key is lost, ownership of the
 * account can be transferred to a new address provided at least 2 out of the 3 guardians approve (2/3 multi-sig).
 */
contract EmergencyRecovery is Ownable, ReentrancyGuard {
    uint256 public constant GUARDIAN_COUNT = 3;
    uint256 public constant REQUIRED_APPROVALS = 2; // 2 out of 3 multi-sig threshold

    struct WalletConfig {
        address[3] guardians;
        address currentOwner;
        bool isConfigured;
    }

    struct RecoveryRequest {
        address proposedNewOwner;
        uint256 approvalCount;
        bool executed;
        bool active;
    }

    // Wallet address => Config (3 guardians, current owner)
    mapping(address => WalletConfig) private _walletConfigs;

    // Wallet address => Active recovery request
    mapping(address => RecoveryRequest) private _recoveryRequests;

    // Wallet address => (Guardian address => Has Approved)
    mapping(address => mapping(address => bool)) private _hasApproved;

    // Wallet address => Quarantine status (for AI-triggered high risk fraud response)
    mapping(address => bool) private _isQuarantined;

    // Events
    event GuardiansConfigured(address indexed wallet, address[3] guardians);
    event RecoveryInitiated(address indexed wallet, address indexed initiator, address proposedNewOwner);
    event RecoveryApproved(address indexed wallet, address indexed guardian, uint256 currentApprovals);
    event RecoveryExecuted(address indexed wallet, address indexed previousOwner, address indexed newOwner);
    event RecoveryCancelled(address indexed wallet, address indexed cancelledBy);
    event WalletQuarantined(address indexed wallet, string reason);
    event WalletUnquarantined(address indexed wallet);

    modifier onlyWalletOwner(address wallet) {
        require(_walletConfigs[wallet].isConfigured, "EmergencyRecovery: Wallet not configured");
        require(_walletConfigs[wallet].currentOwner == msg.sender, "EmergencyRecovery: Only current wallet owner can perform this");
        _;
    }

    modifier onlyGuardian(address wallet) {
        require(_walletConfigs[wallet].isConfigured, "EmergencyRecovery: Wallet not configured");
        require(_isGuardian(wallet, msg.sender), "EmergencyRecovery: Caller is not an authorized guardian");
        _;
    }

    constructor() Ownable(msg.sender) {}

    /**
     * @notice Initializes 3 Guardian addresses for the caller's wallet.
     * @param guardians An array of exactly 3 distinct, non-zero guardian addresses.
     */
    function configureGuardians(address[3] calldata guardians) external nonReentrant {
        require(!_walletConfigs[msg.sender].isConfigured, "EmergencyRecovery: Wallet guardians already configured");

        for (uint256 i = 0; i < GUARDIAN_COUNT; i++) {
            require(guardians[i] != address(0), "EmergencyRecovery: Guardian cannot be zero address");
            require(guardians[i] != msg.sender, "EmergencyRecovery: Owner cannot be their own guardian");
            for (uint256 j = i + 1; j < GUARDIAN_COUNT; j++) {
                require(guardians[i] != guardians[j], "EmergencyRecovery: Guardian addresses must be unique");
            }
        }

        _walletConfigs[msg.sender] = WalletConfig({
            guardians: guardians,
            currentOwner: msg.sender,
            isConfigured: true
        });

        emit GuardiansConfigured(msg.sender, guardians);
    }

    /**
     * @notice Initiates a recovery request to transfer wallet ownership to a new address.
     * Can be triggered by any of the assigned guardians.
     * @param wallet The target wallet account undergoing recovery.
     * @param newOwner The proposed replacement address for the account.
     */
    function initiateRecovery(address wallet, address newOwner) external onlyGuardian(wallet) nonReentrant {
        require(newOwner != address(0), "EmergencyRecovery: New owner cannot be zero address");
        require(newOwner != _walletConfigs[wallet].currentOwner, "EmergencyRecovery: New owner cannot be current owner");

        RecoveryRequest storage req = _recoveryRequests[wallet];
        require(!req.active || req.executed, "EmergencyRecovery: Another recovery request is already active");

        // Clear previous approval flags for all 3 guardians
        address[3] memory gList = _walletConfigs[wallet].guardians;
        for (uint256 i = 0; i < GUARDIAN_COUNT; i++) {
            _hasApproved[wallet][gList[i]] = false;
        }

        // Initialize new request and record initiator's approval
        _recoveryRequests[wallet] = RecoveryRequest({
            proposedNewOwner: newOwner,
            approvalCount: 1,
            executed: false,
            active: true
        });

        _hasApproved[wallet][msg.sender] = true;

        emit RecoveryInitiated(wallet, msg.sender, newOwner);
        emit RecoveryApproved(wallet, msg.sender, 1);
    }

    /**
     * @notice A guardian approves an active recovery request.
     * If this approval reaches the 2-out-of-3 threshold, the recovery can be executed.
     * @param wallet The target wallet account.
     */
    function approveRecovery(address wallet) external onlyGuardian(wallet) nonReentrant {
        RecoveryRequest storage req = _recoveryRequests[wallet];
        require(req.active, "EmergencyRecovery: No active recovery request found");
        require(!req.executed, "EmergencyRecovery: Recovery request has already been executed");
        require(!_hasApproved[wallet][msg.sender], "EmergencyRecovery: Guardian has already approved this request");

        _hasApproved[wallet][msg.sender] = true;
        req.approvalCount += 1;

        emit RecoveryApproved(wallet, msg.sender, req.approvalCount);

        // Automatically execute if 2-of-3 threshold is reached
        if (req.approvalCount >= REQUIRED_APPROVALS) {
            _executeRecoveryInternal(wallet);
        }
    }

    /**
     * @notice Manually triggers recovery execution if the 2-of-3 threshold has been satisfied.
     * @param wallet The target wallet account.
     */
    function executeRecovery(address wallet) external nonReentrant {
        RecoveryRequest storage req = _recoveryRequests[wallet];
        require(req.active, "EmergencyRecovery: No active recovery request");
        require(!req.executed, "EmergencyRecovery: Recovery already executed");
        require(req.approvalCount >= REQUIRED_APPROVALS, "EmergencyRecovery: Insufficient approvals (minimum 2 required)");

        _executeRecoveryInternal(wallet);
    }

    /**
     * @notice The current wallet owner can cancel an erroneous or malicious recovery attempt.
     * @param wallet The target wallet account.
     */
    function cancelRecovery(address wallet) external onlyWalletOwner(wallet) nonReentrant {
        RecoveryRequest storage req = _recoveryRequests[wallet];
        require(req.active && !req.executed, "EmergencyRecovery: No active recovery request to cancel");

        req.active = false;

        // Reset approvals
        address[3] memory gList = _walletConfigs[wallet].guardians;
        for (uint256 i = 0; i < GUARDIAN_COUNT; i++) {
            _hasApproved[wallet][gList[i]] = false;
        }

        emit RecoveryCancelled(wallet, msg.sender);
    }

    /**
     * @dev Internal helper to transfer ownership and emit event.
     */
    function _executeRecoveryInternal(address wallet) internal {
        RecoveryRequest storage req = _recoveryRequests[wallet];
        address previousOwner = _walletConfigs[wallet].currentOwner;
        address newOwner = req.proposedNewOwner;

        _walletConfigs[wallet].currentOwner = newOwner;
        req.executed = true;
        req.active = false;

        emit RecoveryExecuted(wallet, previousOwner, newOwner);
    }

    function _isGuardian(address wallet, address account) internal view returns (bool) {
        address[3] memory gList = _walletConfigs[wallet].guardians;
        return (gList[0] == account || gList[1] == account || gList[2] == account);
    }

    // --- View Functions ---

    function getGuardians(address wallet) external view returns (address[3] memory) {
        require(_walletConfigs[wallet].isConfigured, "EmergencyRecovery: Wallet not configured");
        return _walletConfigs[wallet].guardians;
    }

    function getWalletOwner(address wallet) external view returns (address) {
        require(_walletConfigs[wallet].isConfigured, "EmergencyRecovery: Wallet not configured");
        return _walletConfigs[wallet].currentOwner;
    }

    function isWalletConfigured(address wallet) external view returns (bool) {
        return _walletConfigs[wallet].isConfigured;
    }

    function isGuardianOf(address wallet, address account) external view returns (bool) {
        return _isGuardian(wallet, account);
    }

    function hasGuardianApproved(address wallet, address guardian) external view returns (bool) {
        return _hasApproved[wallet][guardian];
    }

    function getRecoveryStatus(address wallet) external view returns (
        address proposedNewOwner,
        uint256 approvalCount,
        bool executed,
        bool active
    ) {
        RecoveryRequest memory req = _recoveryRequests[wallet];
        return (req.proposedNewOwner, req.approvalCount, req.executed, req.active);
    }

    // --- AI-Triggered Quarantine Protection ---

    /**
     * @notice Quarantines an account when AI fraud detection detects high risk (risk > 70).
     * Only contract owner / authorized admin can trigger this.
     */
    function quarantineWallet(address wallet, string calldata reason) external onlyOwner nonReentrant {
        require(wallet != address(0), "EmergencyRecovery: Invalid wallet address");
        _isQuarantined[wallet] = true;
        emit WalletQuarantined(wallet, reason);
    }

    /**
     * @notice Lifts the quarantine status after investigation.
     */
    function unquarantineWallet(address wallet) external onlyOwner nonReentrant {
        require(wallet != address(0), "EmergencyRecovery: Invalid wallet address");
        _isQuarantined[wallet] = false;
        emit WalletUnquarantined(wallet);
    }

    /**
     * @notice Checks whether a wallet is currently under quarantine.
     */
    function isWalletQuarantined(address wallet) external view returns (bool) {
        return _isQuarantined[wallet];
    }
}
