# Snowflake Key Rotation Activity Diagrams

## Scheduled Key Rotation Activity

```mermaid
stateDiagram-v2
    state "Environment Check" as check {
        [*] --> ValidateDependencies
        ValidateDependencies --> ValidateResources
        ValidateResources --> ValidatePermissions
        ValidatePermissions --> [*]
    }
    
    state "Key Generation" as gen {
        [*] --> GenerateRSAKey
        GenerateRSAKey --> ExtractPublicKey
        ExtractPublicKey --> ValidateKeyFormat
        ValidateKeyFormat --> [*]
    }
    
    state "Backup Process" as backup {
        [*] --> CreateBackupDir
        CreateBackupDir --> TimestampKeys
        TimestampKeys --> CopyKeys
        CopyKeys --> ValidateBackup
        ValidateBackup --> [*]
    }
    
    state "Snowflake Update" as update {
        [*] --> SetAccountAdmin
        SetAccountAdmin --> UpdatePublicKey
        UpdatePublicKey --> ValidateConnection
        ValidateConnection --> [*]
    }
    
    [*] --> check
    check --> gen : Success
    check --> FailureNotification : Failure
    gen --> backup : Success
    gen --> RetryGeneration : Failure
    RetryGeneration --> gen
    RetryGeneration --> FailureNotification : Max Retries
    backup --> update : Success
    backup --> FailureNotification : Failure
    update --> SuccessNotification : Success
    update --> RecoveryProcess : Failure
    RecoveryProcess --> FailureNotification
    SuccessNotification --> [*]
    FailureNotification --> [*]
```

## Manual Key Rotation Activity

```mermaid
stateDiagram-v2
    state "User Input" as input {
        [*] --> ValidateCommand
        ValidateCommand --> ParseOptions
        ParseOptions --> ConfirmExecution
        ConfirmExecution --> [*]
    }
    
    state "Progress Display" as display {
        [*] --> ShowStatus
        ShowStatus --> UpdateProgress
        UpdateProgress --> ShowCompletion
        ShowCompletion --> [*]
    }
    
    state "User Verification" as verify {
        [*] --> DisplayResults
        DisplayResults --> WaitForConfirmation
        WaitForConfirmation --> [*]
    }
    
    [*] --> input
    input --> EnvironmentCheck
    EnvironmentCheck --> display : Start Rotation
    EnvironmentCheck --> ErrorDisplay : Validation Failed
    display --> KeyRotationProcess
    KeyRotationProcess --> verify : Success
    KeyRotationProcess --> ErrorDisplay : Failure
    verify --> [*] : Confirmed
    verify --> RecoveryOptions : Not Confirmed
    RecoveryOptions --> KeyRotationProcess : Retry
    RecoveryOptions --> [*] : Abort
    ErrorDisplay --> RecoveryOptions
```

## Emergency Recovery Activity

```mermaid
stateDiagram-v2
    state "Issue Detection" as detect {
        [*] --> MonitorAlerts
        MonitorAlerts --> ValidateIssue
        ValidateIssue --> CategorizeIssue
        CategorizeIssue --> [*]
    }
    
    state "Backup Selection" as select {
        [*] --> ListBackups
        ListBackups --> ValidateBackups
        ValidateBackups --> SelectBackup
        SelectBackup --> [*]
    }
    
    state "Recovery Process" as recover {
        [*] --> RestoreBackup
        RestoreBackup --> ValidateRestore
        ValidateRestore --> UpdateConfiguration
        UpdateConfiguration --> [*]
    }
    
    state "Emergency Procedure" as emergency {
        [*] --> GenerateEmergencyKeys
        GenerateEmergencyKeys --> ManualUpdate
        ManualUpdate --> ValidateAccess
        ValidateAccess --> [*]
    }
    
    [*] --> detect
    detect --> select : Backup Available
    detect --> emergency : No Backup
    select --> recover
    recover --> VerifyAccess : Success
    recover --> TryAlternateBackup : Failure
    TryAlternateBackup --> recover
    TryAlternateBackup --> emergency : All Backups Failed
    emergency --> VerifyAccess
    VerifyAccess --> DocumentIncident : Success
    VerifyAccess --> EscalateIssue : Failure
    DocumentIncident --> [*]
    EscalateIssue --> [*]
```

## Monitoring and Metrics Activity

```mermaid
stateDiagram-v2
    state "Metric Collection" as collect {
        [*] --> GatherSystemMetrics
        GatherSystemMetrics --> GatherProcessMetrics
        GatherProcessMetrics --> GatherSecurityMetrics
        GatherSecurityMetrics --> [*]
    }
    
    state "Alert Processing" as alert {
        [*] --> EvaluateThresholds
        EvaluateThresholds --> CategorizeAlerts
        CategorizeAlerts --> DetermineRecipients
        DetermineRecipients --> [*]
    }
    
    state "Notification Dispatch" as notify {
        [*] --> FormatMessage
        FormatMessage --> SelectChannel
        SelectChannel --> SendNotification
        SendNotification --> VerifyDelivery
        VerifyDelivery --> [*]
    }
    
    [*] --> collect
    collect --> ProcessMetrics
    ProcessMetrics --> alert : Thresholds Exceeded
    ProcessMetrics --> StoreMetrics : Normal Range
    alert --> notify
    notify --> UpdateAlertStatus
    StoreMetrics --> [*]
    UpdateAlertStatus --> [*]
```

## Validation and Testing Activity

```mermaid
stateDiagram-v2
    state "Test Execution" as test {
        [*] --> SetupTestEnvironment
        SetupTestEnvironment --> RunUnitTests
        RunUnitTests --> RunIntegrationTests
        RunIntegrationTests --> [*]
    }
    
    state "Coverage Analysis" as coverage {
        [*] --> CollectCoverage
        CollectCoverage --> AnalyzeResults
        AnalyzeResults --> GenerateReport
        GenerateReport --> [*]
    }
    
    state "Validation Checks" as validate {
        [*] --> ValidatePermissions
        ValidatePermissions --> ValidateConnectivity
        ValidateConnectivity --> ValidateOperations
        ValidateOperations --> [*]
    }
    
    [*] --> test
    test --> coverage
    coverage --> validate
    validate --> ReportResults : All Passed
    validate --> FailureAnalysis : Failures Detected
    FailureAnalysis --> DocumentIssues
    DocumentIssues --> CreateTickets
    ReportResults --> [*]
    CreateTickets --> [*]
```

## Error Recovery Flow

```mermaid
stateDiagram-v2
    state "Error Detection" as detect {
        [*] --> MonitorOperations
        MonitorOperations --> DetectAnomaly
        DetectAnomaly --> CategorizeError
        CategorizeError --> [*]
    }
    
    state "Recovery Strategy" as strategy {
        [*] --> EvaluateError
        EvaluateError --> SelectStrategy
        SelectStrategy --> PrepareRecovery
        PrepareRecovery --> [*]
    }
    
    state "Recovery Execution" as execute {
        [*] --> BackupState
        BackupState --> ApplyFix
        ApplyFix --> ValidateRecovery
        ValidateRecovery --> [*]
    }
    
    [*] --> detect
    detect --> strategy
    strategy --> execute : Automatic Recovery
    strategy --> ManualIntervention : Manual Recovery
    execute --> ValidateSuccess
    ManualIntervention --> ValidateSuccess
    ValidateSuccess --> DocumentRecovery : Success
    ValidateSuccess --> EscalateIssue : Failure
    DocumentRecovery --> [*]
    EscalateIssue --> [*]
``` 