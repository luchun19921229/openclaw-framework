# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-source release preparation

## [1.0.0] - 2026-04-10

### Added
- **Core runtime** (`@openclaw/core`): Agent lifecycle management, gateway abstraction, memory system, and skill loader
- **CLI tool** (`@openclaw/cli`): Command-line interface for managing agents, gateways, and skills
- Agent runtime with support for message processing, tool invocation, and session management
- Gateway manager for connecting to LLM providers (OpenAI, Anthropic, local models)
- Pluggable memory system with short-term (session) and long-term (persistent) storage
- Skill system for loading and executing modular capabilities
- Multi-channel support framework (WeChat, Discord, Telegram, etc.)
- Basic agent example demonstrating core API usage
- GitHub Actions CI pipeline for lint, test, and build
- MIT License

### Security
- Established security policy and vulnerability reporting process

[Unreleased]: https://github.com/nexu-ai/openclaw/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nexu-ai/openclaw/releases/tag/v1.0.0
