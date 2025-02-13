Security vulnerability in dependency chain preventing critical updates. See full details in docs/security/msrc-report-2024-03.md

## Quick Summary
- botbuilder-ai 4.16.2 requires aiohttp==3.10.5
- aiohttp 3.10.5 has known vulnerabilities (CVE-2024-52303, CVE-2024-52304)
- Cannot update to secure aiohttp 3.10.11 due to strict version constraint

## Impact
- Medium to High severity
- Affects all Bot Framework applications using botbuilder-ai
- Remote exploitation possible

## Status
- [ ] Submit to Microsoft Security Response Center
- [ ] Implement temporary mitigations
- [ ] Monitor for upstream fix

## Next Steps
1. Submit detailed report to Microsoft
2. Implement protective middleware
3. Document workarounds for users

## References
- Full Report: docs/security/msrc-report-2024-03.md
- aiohttp Security Fixes: https://github.com/aio-libs/aiohttp/releases/tag/v3.10.11 