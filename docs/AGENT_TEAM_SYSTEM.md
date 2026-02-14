# Agent Team System Documentation

## Overview

The Agent Team System is a multi-agent AI system designed to automate GitHub issue management, code analysis, and project workflows. It consists of 7 specialized agents working together to process issues from triage to release.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT TEAM SYSTEM                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Agent 1   │  │  Agent 2   │  │  Agent 3   │            │
│  │  Triager   │─▶│  Analyzer  │─▶│  Designer  │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Agent 4   │  │  Agent 5   │  │  Agent 6   │            │
│  │ Implementer│─▶│     QA     │─▶│ Documenter │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│         │                │                │                  │
│         └────────────────┴────────────────┘                 │
│                          │                                   │
│                   ┌────────────┐                            │
│                   │  Agent 7   │                            │
│                   │  Releaser  │                            │
│                   └────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Agent Roles

### Agent 1: Issue Triager
**Responsibility:** Categorize and prioritize incoming issues

**Capabilities:**
- Classify issues (bug, feature, docs, performance, security, UI)
- Assign priority levels (low, medium, high, critical)
- Apply appropriate labels
- Suggest assignees
- Recommend milestones

**Decision Logic:**
- Security issues → Critical priority
- Bugs with crashes → High priority
- Performance issues → Medium priority
- Feature requests → Low to medium priority

### Agent 2: Code Analyzer
**Responsibility:** Analyze codebase for issues

**Capabilities:**
- Run linters (ESLint, Prettier)
- Perform security scans (npm audit, Snyk)
- Check performance metrics
- Measure test coverage
- Identify code smells

**Output:**
- List of lint issues
- Security vulnerabilities
- Performance bottlenecks
- Test coverage gaps

### Agent 3: Solution Designer
**Responsibility:** Design solutions for identified issues

**Capabilities:**
- Propose fix approaches
- Identify affected files
- Plan required tests
- List documentation needs
- Specify dependencies

**Design Patterns:**
- Bug fixes → Targeted fix + regression test
- Features → Full implementation + integration tests
- Performance → Optimization + benchmarks

### Agent 4: Implementation Agent
**Responsibility:** Implement approved solutions

**Capabilities:**
- Create feature branches
- Write code implementations
- Add/update tests
- Make commits with meaningful messages
- Handle merge conflicts

**Workflow:**
1. Create branch: `fix/issue-{number}` or `feature/issue-{number}`
2. Implement solution
3. Run local tests
4. Commit changes
5. Push to remote

### Agent 5: Quality Assurance
**Responsibility:** Test and validate implementations

**Capabilities:**
- Run unit tests
- Execute integration tests
- Verify code coverage
- Perform security checks
- Run performance benchmarks

**Quality Gates:**
- All tests pass ✓
- Lint passes ✓
- Coverage >= 80% ✓
- No security vulnerabilities ✓
- Performance within limits ✓

### Agent 6: Documentation Agent
**Responsibility:** Create and update documentation

**Capabilities:**
- Update changelogs
- Modify README files
- Generate API documentation
- Create tutorials
- Update diagrams

**Documentation Types:**
- CHANGELOG.md entries
- README.md updates
- API reference docs
- Usage guides
- Architecture diagrams

### Agent 7: Release Manager
**Responsibility:** Manage releases and deployments

**Capabilities:**
- Version bumping (semver)
- Create git tags
- Generate release notes
- Build release assets
- Trigger deployments

**Release Process:**
1. Determine version (major.minor.patch)
2. Update version files
3. Create git tag
4. Generate release notes
5. Build and publish

## Usage

### Basic Usage

```javascript
const AgentTeam = require('./agent-team');

// Initialize agent team
const agentTeam = new AgentTeam({
    repoOwner: 'your-username',
    repoName: 'your-repo',
    githubToken: process.env.GITHUB_TOKEN
});

// Process a single issue
const issue = {
    number: 42,
    title: 'Fix search validation',
    body: 'Search crashes with special characters',
    labels: []
};

const result = await agentTeam.processIssue(issue);
console.log('Issue processed:', result);
```

### Batch Processing

```javascript
// Process multiple issues in parallel
const issues = [
    { number: 1, title: 'Bug fix', body: '...' },
    { number: 2, title: 'New feature', body: '...' },
    { number: 3, title: 'Performance', body: '...' }
];

const results = await agentTeam.processIssues(issues);

// Generate report
const report = agentTeam.generateReport();
console.log('Team Report:', report);
```

### Custom Configuration

```javascript
const agentTeam = new AgentTeam({
    repoOwner: 'heat-project',
    repoName: 'heat',
    githubToken: process.env.GITHUB_TOKEN,
    autoImplement: true,        // Auto-implement non-critical issues
    requireApproval: ['critical', 'high'], // Require approval for these
    notifySlack: true,          // Send Slack notifications
    slackWebhook: process.env.SLACK_WEBHOOK
});
```

## Integration with GitHub Actions

```yaml
# .github/workflows/agent-team.yml
name: Agent Team Automation

on:
  issues:
    types: [opened, labeled]
  pull_request:
    types: [opened, synchronize]

jobs:
  process-issue:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm install
      
      - name: Run Agent Team
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: node build/agent-team.js
```

## Monitoring & Reporting

### Agent Team Report

```json
{
  "totalProcessed": 15,
  "byPriority": {
    "critical": 2,
    "high": 5,
    "medium": 6,
    "low": 2
  },
  "byCategory": {
    "bug": 8,
    "feature": 4,
    "security": 2,
    "documentation": 1
  },
  "successRate": "93.3%",
  "avgProcessingTime": "12.4s"
}
```

### Individual Issue Workflow

```json
{
  "issue": { "number": 42, "title": "..." },
  "triage": {
    "labels": ["bug", "ui", "priority-high"],
    "priority": "high",
    "assignee": "frontend-team",
    "milestone": "Next Release"
  },
  "analysis": {
    "lintIssues": [],
    "securityIssues": [],
    "performanceIssues": []
  },
  "solution": {
    "approach": "Fix validation logic with input sanitization",
    "files": ["ui-enhancements.js", "data-validator.js"],
    "tests": ["Add validation tests"]
  },
  "implementation": {
    "branch": "fix/issue-42",
    "commits": ["abc123", "def456"],
    "pr": "#43"
  },
  "qa": {
    "passed": true,
    "checks": {
      "testsPass": true,
      "lintPass": true,
      "coveragePass": true
    }
  },
  "documentation": {
    "changelog": ["Fixed issue #42: Search validation"],
    "readme": []
  }
}
```

## Best Practices

### 1. Issue Templates
Create GitHub issue templates to ensure consistent information:

```markdown
### Bug Report
- **Description:** [Clear description]
- **Steps to Reproduce:** [Numbered steps]
- **Expected Behavior:** [What should happen]
- **Actual Behavior:** [What actually happens]
- **Environment:** [Browser, OS, version]
```

### 2. Labeling Strategy
Use consistent labels for agent categorization:
- `bug`, `feature`, `documentation`, `performance`, `security`, `ui`
- `priority-low`, `priority-medium`, `priority-high`, `priority-critical`
- `good-first-issue`, `help-wanted`, `blocked`, `wontfix`

### 3. Branch Naming
Follow consistent branch naming:
- Bugs: `fix/issue-{number}-{short-description}`
- Features: `feature/issue-{number}-{short-description}`
- Docs: `docs/issue-{number}-{short-description}`

### 4. Commit Messages
Use conventional commits:
```
type(scope): subject

- fix(search): validate input before processing
- feat(analytics): add PDF export capability
- docs(readme): update installation instructions
```

### 5. Testing Requirements
- Unit test coverage >= 80%
- All tests pass before merge
- Integration tests for new features
- Performance benchmarks for optimizations

## Troubleshooting

### Agent Fails to Process Issue

**Problem:** Agent encounters error during processing

**Solutions:**
1. Check agent logs for specific error
2. Verify GitHub token has correct permissions
3. Ensure issue has required fields
4. Check network connectivity

### Quality Checks Fail

**Problem:** QA agent reports failing checks

**Solutions:**
1. Review test output
2. Check lint errors
3. Verify code coverage
4. Address security vulnerabilities

### Documentation Not Generated

**Problem:** Documentation agent doesn't create docs

**Solutions:**
1. Verify file paths are correct
2. Check write permissions
3. Ensure templates exist
4. Review documentation config

## Future Enhancements

- [ ] AI-powered code generation (GPT-4)
- [ ] Automatic PR reviews
- [ ] Visual regression testing
- [ ] Performance regression detection
- [ ] Automated security patching
- [ ] Multi-repo coordination
- [ ] Slack/Discord integration
- [ ] Custom agent plugins
- [ ] Machine learning for priority prediction
- [ ] Automated hotfix deployment

## Contributing

To add a new agent:

1. Add agent definition in `initializeAgents()`
2. Implement agent's `process()` function
3. Add agent to workflow in `processIssue()`
4. Update documentation
5. Add tests for new agent

## License

Part of the HEAT project - Licensed under HEAT Ethical Use License v1.0

## Support

For issues or questions about the agent system:
- Create a GitHub issue with label `agent-system`
- Priority will be automatically assigned by the triager agent
- The agent team will process and respond
