# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | ✅ Active support  |
| < 1.0   | ❌ Not supported   |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in OpenClaw, please report it responsibly:

1. **Email**: Send details to [security@openclaw.dev](mailto:security@openclaw.dev)
2. **Subject**: Include `[SECURITY]` in the subject line
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Depends on severity, typically within 2 weeks for critical issues

## Disclosure Policy

- We will coordinate with you on the disclosure timeline
- We aim to release a fix before or simultaneously with public disclosure
- Credit will be given to the reporter (unless anonymity is requested)

## Security Best Practices for Users

- Keep OpenClaw and its dependencies up to date
- Never commit API keys, tokens, or secrets to version control
- Use environment variables for sensitive configuration
- Review and audit skills before installing from untrusted sources
- Run agents with minimal required permissions

## Scope

This policy covers:
- `@openclaw/core` and `@openclaw/cli` packages
- Official GitHub Actions workflows
- Documentation site

Out of scope:
- Third-party skills or plugins
- User-deployed configurations
