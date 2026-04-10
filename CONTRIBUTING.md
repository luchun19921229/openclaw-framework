# Contributing to OpenClaw

Thank you for your interest in contributing to OpenClaw! This guide will help you get started.

## Code of Conduct

Please read and follow our [Code of Conduct](./CODE_OF_CONDUCT.md) before contributing.

## Getting Started

### Prerequisites

- Node.js >= 18
- pnpm >= 8 (recommended) or npm
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/nexu-ai/openclaw.git
cd openclaw

# Install dependencies
pnpm install

# Build all packages
pnpm build

# Run tests
pnpm test
```

## Project Structure

```
openclaw/
├── packages/
│   ├── core/          # Core runtime (agent, gateway, memory, skills)
│   └── cli/           # CLI tool
├── examples/          # Usage examples
├── docs/              # Nextra documentation site
└── .github/           # CI/CD and issue templates
```

## Development Workflow

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a branch** from `main` for your changes
4. **Make your changes** and ensure they follow our conventions
5. **Write or update tests** for your changes
6. **Run the test suite** to ensure nothing breaks
7. **Commit** with a clear, descriptive message
8. **Push** to your fork and open a **Pull Request**

### Branch Naming

- `feat/your-feature-name` — new features
- `fix/bug-description` — bug fixes
- `docs/update-description` — documentation changes
- `refactor/description` — code refactoring

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add memory persistence layer
fix: resolve gateway connection timeout
docs: update API reference for skills module
chore: upgrade dependencies
```

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Link related issues (e.g., `Closes #123`)
- Ensure all CI checks pass
- Request review from at least one maintainer

## Adding Skills

Skills are the primary extension mechanism. To add a new skill:

1. Create your skill directory under `skills/`
2. Include a `SKILL.md` with usage instructions
3. Follow the skill interface defined in `packages/core/src/skills.js`
4. Add an example in `examples/`

## Reporting Issues

- Use the [issue templates](https://github.com/nexu-ai/openclaw/issues/new/choose)
- Provide reproduction steps for bugs
- Include your environment details (OS, Node.js version, etc.)

## Questions?

Feel free to open a [Discussion](https://github.com/nexu-ai/openclaw/discussions) for questions, ideas, or general feedback.

Thank you for helping make OpenClaw better! 🐾
