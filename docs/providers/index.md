# Providers

sltasks supports multiple storage backends (providers) for managing your tasks. Each provider stores and retrieves tasks differently but provides the same TUI experience.

## Available Providers

### File Provider (Default)

Store tasks as local markdown files in your project. Zero configuration required.

- **Best for:** Personal projects, git-tracked task management, offline use
- **Setup:** Just run `sltasks --generate` or start with no config
- **Data location:** `.tasks/` directory with individual `.md` files

[File Provider Guide](file-provider.md)

### GitHub Provider

Sync with GitHub Projects V2. Manage GitHub issues and PRs directly from your terminal.

- **Best for:** Team projects using GitHub, issue tracking integration
- **Setup:** Run `sltasks --github-setup` with your project URL
- **Data location:** GitHub Projects (issues and PRs)

[GitHub Provider Guide](github-provider.md)

## Choosing a Provider

| Aspect | File Provider | GitHub Provider |
|--------|---------------|-----------------|
| Setup complexity | None | Requires GitHub auth + project |
| Offline support | Full | Read-only (cached) |
| Collaboration | Via git | Native GitHub collaboration |
| Issue tracking | Manual | Integrated with GitHub Issues |
| Data portability | Markdown files | GitHub API |

Most users should start with the **File Provider** for simplicity. Switch to **GitHub Provider** when you need GitHub Issues integration or team collaboration through GitHub Projects.
