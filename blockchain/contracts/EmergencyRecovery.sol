// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title EmergencyRecovery
 * @dev EIP-4337 Account Abstraction prensipleriyle uyumlu, 3/5 Guardian çoklu imza ve Time-Lock tabanlı acil durum kurtarma sözleşmesi.
 */
contract EmergencyRecovery {
    struct RecoveryConfig {
        address[] guardians;
        uint256 threshold; // Default: 3
        uint256 timeLockPeriod; // Saniye cinsinden bekleme süresi (örn: 24 saat veya test için 60 sn)
        bool isConfigured;
    }

    struct RecoveryRequest {
        address targetWallet;
        address proposedNewKey;
        uint256 initiatedAt;
        uint256 executeAfter;
        uint256 approvalCount;
        bool executed;
        bool cancelled;
    }

    // Wallet address => RecoveryConfig
    mapping(address => RecoveryConfig) public configs;

    // Wallet address => Aktif RecoveryRequest
    mapping(address => RecoveryRequest) public activeRequests;

    // Wallet address => (Guardian address => Onayladi mi)
    mapping(address => mapping(address => bool)) public guardianApprovals;

    event RecoveryConfigured(address indexed wallet, address[] guardians, uint256 threshold, uint256 timeLockPeriod);
    event RecoveryInitiated(address indexed wallet, address indexed proposedNewKey, uint256 executeAfter);
    event GuardianApprovalCast(address indexed wallet, address indexed guardian, uint256 currentApprovals);
    event RecoveryExecuted(address indexed wallet, address indexed oldKey, address indexed newKey, uint256 timestamp);
    event RecoveryCancelled(address indexed wallet, address indexed cancelledBy, uint256 timestamp);

    modifier onlyWalletOwner(address wallet) {
        require(msg.sender == wallet, "EmergencyRecovery: Yalnizca cuzdan sahibi");
        _;
    }

    /**
     * @notice Kullanıcı cüzdanı için Guardian listesini ve M-of-N eşiğini yapılandırır (Örn: 5 guardian, 3 onay).
     */
    function configureRecovery(
        address[] calldata guardians,
        uint256 threshold,
        uint256 timeLockPeriod
    ) external {
        require(guardians.length >= threshold, "EmergencyRecovery: Yetersiz guardian sayisi");
        require(threshold >= 2, "EmergencyRecovery: Esik en az 2 olmalidir");
        require(guardians.length <= 10, "EmergencyRecovery: Maksimum 10 guardian");

        configs[msg.sender] = RecoveryConfig({
            guardians: guardians,
            threshold: threshold,
            timeLockPeriod: timeLockPeriod,
            isConfigured: true
        });

        emit RecoveryConfigured(msg.sender, guardians, threshold, timeLockPeriod);
    }

    /**
     * @notice Bir guardian veya yetkili yedek cihaz tarafından kurtarma süreci başlatılır.
     */
    function initiateRecovery(address wallet, address proposedNewKey) external {
        RecoveryConfig storage cfg = configs[wallet];
        require(cfg.isConfigured, "EmergencyRecovery: Cuzdan kurtarma yapilandirilmamis");
        require(proposedNewKey != address(0), "EmergencyRecovery: Gecersiz yeni anahtar");
        
        RecoveryRequest storage req = activeRequests[wallet];
        require(!req.executed, "EmergencyRecovery: Zaten tamamlanmis");
        if (req.initiatedAt > 0 && !req.cancelled) {
            require(block.timestamp > req.executeAfter + 7 days, "EmergencyRecovery: Aktif baska bir talep var");
        }

        uint256 executeAfter = block.timestamp + cfg.timeLockPeriod;

        activeRequests[wallet] = RecoveryRequest({
            targetWallet: wallet,
            proposedNewKey: proposedNewKey,
            initiatedAt: block.timestamp,
            executeAfter: executeAfter,
            approvalCount: 0,
            executed: false,
            cancelled: false
        });

        // Eğer başlatan kişi bir guardiansa otomatik onayını ver
        if (_isGuardian(wallet, msg.sender)) {
            guardianApprovals[wallet][msg.sender] = true;
            activeRequests[wallet].approvalCount = 1;
            emit GuardianApprovalCast(wallet, msg.sender, 1);
        }

        emit RecoveryInitiated(wallet, proposedNewKey, executeAfter);
    }

    /**
     * @notice Guardian kurtarma talebine onay verir.
     */
    function approveRecovery(address wallet) external {
        require(_isGuardian(wallet, msg.sender), "EmergencyRecovery: Arayan bir guardian degil");
        RecoveryRequest storage req = activeRequests[wallet];
        require(req.initiatedAt > 0, "EmergencyRecovery: Aktif kurtarma talebi yok");
        require(!req.executed && !req.cancelled, "EmergencyRecovery: Talep sonlandirilmis");
        require(!guardianApprovals[wallet][msg.sender], "EmergencyRecovery: Bu guardian zaten onay verdi");

        guardianApprovals[wallet][msg.sender] = true;
        req.approvalCount += 1;

        emit GuardianApprovalCast(wallet, msg.sender, req.approvalCount);
    }

    /**
     * @notice Gerekli M-of-N onay alındıktan ve Time-Lock süresi dolduktan sonra yeni anahtarı devreye alır.
     */
    function executeRecovery(address wallet) external {
        RecoveryConfig storage cfg = configs[wallet];
        RecoveryRequest storage req = activeRequests[wallet];

        require(req.initiatedAt > 0, "EmergencyRecovery: Talep bulunamadi");
        require(!req.executed, "EmergencyRecovery: Zaten icra edildi");
        require(!req.cancelled, "EmergencyRecovery: Talep iptal edilmis");
        require(req.approvalCount >= cfg.threshold, "EmergencyRecovery: Yetersiz guardian onayi (M-of-N saglanmadi)");
        require(block.timestamp >= req.executeAfter, "EmergencyRecovery: Time-lock suresi henuz dolmadi");

        req.executed = true;

        emit RecoveryExecuted(wallet, wallet, req.proposedNewKey, block.timestamp);
    }

    /**
     * @notice Cüzdan sahibi veya yetkili kötü niyetli bir kurtarma girişimini derhal iptal edebilir.
     */
    function cancelRecovery(address wallet) external onlyWalletOwner(wallet) {
        RecoveryRequest storage req = activeRequests[wallet];
        require(req.initiatedAt > 0 && !req.executed, "EmergencyRecovery: Iptal edilecek talep yok");
        
        req.cancelled = true;
        emit RecoveryCancelled(wallet, msg.sender, block.timestamp);
    }

    function _isGuardian(address wallet, address account) internal view returns (bool) {
        address[] memory gList = configs[wallet].guardians;
        for (uint256 i = 0; i < gList.length; i++) {
            if (gList[i] == account) {
                return true;
            }
        }
        return false;
    }
}
