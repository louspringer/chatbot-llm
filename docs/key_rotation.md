# Key Rotation Technical Guide

## Overview

This document provides technical instructions for running and managing the key rotation scripts. For high-level process flows and use cases, see [Key Rotation Use Cases](use_cases/key_rotation/README.md).

## Prerequisites

### Environment Setup
These environment variables are required for all key rotation operations described in [UC1: Scheduled Key Rotation](use_cases/key_rotation/scheduled-rotation.md) and [UC2: Manual Key Rotation](use_cases/key_rotation/manual-rotation.md).

```bash
# Required environment variables
SNOWFLAKE_ACCOUNT=<account>
SNOWFLAKE_USER=<user>
SNOWFLAKE_ROLE=ACCOUNTADMIN  # Must be ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=<warehouse>
```

### Dependencies
Required for all key rotation operations:
```yaml
dependencies:
  - openssl: ">=1.1.1"  # For key generation
  - snowsql: ">=1.2"    # For Snowflake interaction
  - python: ">=3.8"     # For script execution
```

## Script Usage

### Automated Key Rotation
Implementation of [UC1: Scheduled Key Rotation](use_cases/key_rotation/scheduled-rotation.md):

```bash
# Run scheduled key rotation
python teams_bot/scripts/rotate_secrets.py --component snowflake

# Options:
#   --component    Component to rotate keys for (snowflake, bot, all)
#   --force       Force rotation even if not due
#   --dry-run     Show what would be done without making changes
```

### Manual Key Rotation
Implementation of [UC2: Manual Key Rotation](use_cases/key_rotation/manual-rotation.md):

```bash
# Manual key rotation with monitoring
python teams_bot/scripts/rotate_secrets.py --component snowflake --interactive

# Options:
#   --interactive    Show progress and prompt for confirmation
#   --backup-dir    Custom backup directory location
#   --no-backup     Skip backup creation (not recommended)
```

### Emergency Recovery
Implementation of [UC3: Emergency Key Recovery](use_cases/key_rotation/emergency-recovery.md):

```bash
# List available backups
python teams_bot/scripts/rotate_secrets.py --list-backups

# Restore from backup
python teams_bot/scripts/rotate_secrets.py --restore <backup-timestamp>

# Generate emergency keys
python teams_bot/scripts/rotate_secrets.py --emergency-keygen
```

## Monitoring and Validation
These tools support the [Monitoring Requirements](use_cases/key_rotation/monitoring.md) defined in the use cases.

### Health Checks
```bash
# Verify current key status
python teams_bot/scripts/rotate_secrets.py --health-check

# Test Snowflake connectivity
python teams_bot/scripts/rotate_secrets.py --test-connection
```

### Logs and Metrics
Implements monitoring requirements from use cases:
- Logs are written to: `logs/key_rotation.log`
- Metrics are emitted to CloudWatch under namespace: `KeyRotation`
- Alerts are sent to configured Slack channels

## Troubleshooting
Technical solutions for handling [Error Categories](use_cases/key_rotation/error-handling.md#error-categories) defined in use cases.

### Common Issues

1. **Permission Errors**
   Related to [Environment Errors](use_cases/key_rotation/error-handling.md#environment-errors):
   ```bash
   # Verify role
   snowsql -q "SELECT CURRENT_ROLE()"
   
   # Verify privileges
   snowsql -q "SHOW GRANTS TO ROLE ACCOUNTADMIN"
   ```

2. **Key Generation Failures**
   Related to [Operation Errors](use_cases/key_rotation/error-handling.md#operation-errors):
   ```bash
   # Verify OpenSSL installation
   openssl version
   
   # Test key generation
   openssl genrsa 2048
   ```

3. **Backup Issues**
   Related to [Recovery Errors](use_cases/key_rotation/error-handling.md#recovery-errors):
   ```bash
   # Check backup directory permissions
   ls -la teams_bot/config/keys/backup
   
   # Verify backup integrity
   python teams_bot/scripts/rotate_secrets.py --verify-backup <timestamp>
   ```

## Security Considerations
Implementation details for security requirements mentioned in [UC1: Scheduled Key Rotation](use_cases/key_rotation/scheduled-rotation.md) and [Future Enhancements](use_cases/key_rotation/future-enhancements.md).

1. **Key Storage**
   - Keys are stored in: `teams_bot/config/keys/`
   - Directory permissions should be: `700`
   - Keys should be encrypted at rest

2. **Access Control**
   - Script requires ACCOUNTADMIN role
   - Access logs are maintained
   - Failed attempts are monitored

3. **Backup Security**
   - Backups are encrypted
   - Access is restricted
   - Regular integrity checks

## Related Documentation

- [Key Rotation Use Cases](use_cases/key_rotation/README.md)
- [Security Requirements](security_requirements.md)
- [Monitoring Guide](monitoring_guide.md)
