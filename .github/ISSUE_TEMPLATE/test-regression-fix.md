# Security Scanner Test Failures - Issue #15

## Problem Description

Multiple security scanner tests are failing in `tests/test_security_scanners_integration.py` due to various issues:

1. Safety scanner authentication requirements
2. Timeout issues during package scanning
3. Insufficient number of available scanners
4. Ontology integration problems
5. Package installation regression issues

## Current Status

The following tests have been disabled:

1. `test_vulnerable_package_detection`: Failing due to safety scanner authentication and timeout issues
2. `test_secure_package_validation`: Failing due to safety scanner authentication issues
3. `test_multiple_scanners_consistency`: Failing due to insufficient number of available scanners
4. `test_ontology_integration`: Failing due to ontology integration issues
5. `test_package_addition_regression`: Failing due to conda installation timeout issues

Key issues identified:

- Safety scanner requires authentication but test environment lacks credentials
- Timeouts during package scanning (30s) are too short for some packages
- Pip-audit fallback not consistently working
- Ontology updates not properly persisting during tests
- Inconsistent timeout values across codebase
- Test environment isolation issues

## Required Changes

1. [ ] Safety Scanner Authentication
   - [ ] Add support for safety API key configuration
   - [ ] Document authentication setup process
   - [ ] Improve error handling for missing credentials
   - [ ] Add test configurations for authenticated and unauthenticated scenarios

2. [ ] Timeout Handling
   - [ ] Standardize timeout configurations across codebase
   - [ ] Increase default scan timeout for larger packages
   - [ ] Add configurable timeouts via environment variables
   - [ ] Improve timeout error messages and logging

3. [ ] Scanner Integration
   - [ ] Improve pip-audit fallback mechanism
   - [ ] Better handling of scanner availability checks
   - [ ] Add support for multiple scanner configurations
   - [ ] Enhance scanner result validation

4. [ ] Ontology Management
   - [ ] Fix ontology persistence in test environment
   - [ ] Improve cleanup between tests
   - [ ] Add validation for ontology updates
   - [ ] Better error handling for ontology operations

5. [ ] Test Environment
   - [ ] Improve test isolation
   - [ ] Add proper cleanup procedures
   - [ ] Handle pre-installed packages
   - [ ] Support for different Python/conda versions

## Expected Outcomes

- All security scanner tests passing reliably
- Proper handling of authenticated and unauthenticated scenarios
- Consistent timeout behavior
- Reliable ontology updates
- Clean test environment management

## Branch

`fix/security-scanner-tests`

## Related Files

- tests/test_security_scanners_integration.py
- clpm.py
- security.ttl
- schemas/security_vulnerability.json
- environment.yml
- pyproject.toml

## Additional Notes

The issues appear to be interconnected, with authentication and timeout problems cascading into ontology integration issues. The fix should take a holistic approach to:

1. Improve error handling and logging
2. Better test environment isolation
3. More robust scanner integration
4. Proper credential management
5. Consistent configuration across the codebase

Priority should be given to fixing the authentication and timeout issues first, as these are blocking other test improvements.
