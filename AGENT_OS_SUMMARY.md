# Tachi

**Agent-native apps.**

## The Problem

Building AI-powered business applications today requires stitching together:
- LLM APIs and prompt engineering
- Custom databases and data pipelines
- Authentication and user management
- File storage and processing
- Multiple frontend interfaces
- DevOps and deployment infrastructure

The result: 6-12 months to build what should take days.

## The Solution

Tachi is a complete runtime for AI agents. Developers define **what** the agent does. The platform handles **everything else**.

```
Developer writes:          Platform provides:

- Role (who the agent is)  - AI runtime
- Ontology (what it works  - Data layer
  with)                    - Authentication
- Skills (what it can do)  - File processing
- Data sources             - Web & mobile apps
                           - Deployment
                           - Scaling
```

## How It Works

**For Developers:**

Edit a few text files in a browser. Save. App is live.

- `PROMPT.md` - Define the agent's role
- `schema.yaml` - Define what entities exist
- Select skills from a curated library
- Connect data sources (we handle credentials)

No code. No deployment. No infrastructure.

**For Users:**

Three interfaces, same underlying system:

| Chat | Lake | CRUD |
|------|------|------|
| Talk to the agent | Browse & edit files | Tables & forms |
| "How's deliverability?" | Click, edit, save | Looks like Salesforce |
| Agent does the work | Agent assists | Agent invisible |

Users pick their preferred experience. Data stays in sync.

## Technical Architecture

**Stateless, Serverless, Git-Backed**

- **Cloud Run**: Long-running FastAPI services, scale to zero
- **Git**: Every workspace is a repo (users never see this)
- **Optimistic concurrency**: Multiple interfaces, no conflicts
- **Background agents**: Propose cleanups via branches, users approve

**Component Stack:**

| Layer | Technology |
|-------|------------|
| Agent Runtime | Claude Agent SDK |
| Data Layer | Git + MCP protocol |
| External Data | Connectors (Marketo, Salesforce, Databricks) |
| Web/Mobile | Vercel + React Native |
| Auth | Clerk |
| Compute | Google Cloud Run |
| Storage | Cloud Source Repositories |

## Market

**Target Users:**
- Operations teams (Marketing Ops, Rev Ops, Sales Ops)
- Business analysts
- Non-technical knowledge workers

**Target Developers:**
- Agencies building for clients
- Internal tools teams
- Consultants

**Wedge:**
- Marketing operations (Marketo, HubSpot, Salesforce)
- Expand to broader business operations

## Business Model

- **Free tier**: 1 workspace, community skills
- **Pro**: $X/user/month, multiple workspaces, premium skills
- **Enterprise**: Custom data connectors, dedicated support

## Traction

- 3 production applications built on platform
- Deployed for enterprise marketing operations team
- Full platform architecture validated

## Team

Building since 2024. Deep expertise in:
- AI/ML systems
- Developer tools
- Enterprise software

## The Ask

Raising seed to:
- Build self-serve developer experience
- Expand data connector library
- Scale infrastructure
- Hire founding team

---

**Tachi: Agent-native apps.**
