# Product Requirements Document (PRD)

## RegAI Copilot: RAG-Powered Regulatory Intelligence System

---

## 1. Executive Summary

### Problem Statement
Capital markets compliance teams face increasing complexity in regulatory oversight. Regulations from multiple jurisdictions (US, UK, EU, APAC) change frequently, with tight implementation deadlines (30-90 days from publication to enforcement). Current manual processes require 3-5 days to complete initial impact assessments, creating operational bottlenecks and regulatory risk.

**Key Problem Insights:**
- Financial institutions navigate 50+ primary regulators globally
- Average regulation: 50-300 pages of dense legal text
- Amendment frequency: 30-60% of regulations amended within 3 years
- Manual monitoring across fragmented sources (websites, PDFs, email subscriptions)
- Analysis inconsistency across teams creates quality and audit risks

### Solution Overview
RegAI Copilot is a RAG-powered intelligence system that consolidates regulatory content across jurisdictions, enables semantic search, and provides AI-assisted analysis with mandatory source citation. The system augments human expertise rather than replacing regulatory judgment.

**Core Capabilities:**
- Multi-jurisdiction regulatory document consolidation and search
- Semantic search to find regulations by concept (not just keywords)
- AI-powered obligation extraction with source citation
- Amendment and version tracking
- Audit trail for regulatory examinations

### Target Users
- **Primary**: Regulatory Analysts (2-5 years experience; 20-40 per mid-size firm)
- **Secondary**: Compliance Managers (10+ years; oversight function; 3-5 per mid-size firm)
- **Tertiary**: Technology/Operations Leads (system implementation; 1-2 per firm affected by changes)

### Expected Outcomes
- **Efficiency**: 50-70% reduction in time to complete impact assessment (3-5 days → 4-8 hours)
- **Quality**: 98%+ citation accuracy; consistent analysis methodology
- **Risk**: Comprehensive regulatory coverage; audit-ready documentation
- **Knowledge**: Improved retention through institutional knowledge base

---

## 2. User Research

### Persona Profiles

See `docs/personas/` for detailed persona development. Key personas:

**Persona 1: Regulatory Analyst**
- 2-5 years experience; law or compliance background
- Goal: Complete impact assessment quickly and accurately
- Pain: Time pressure, fragmented information sources, difficulty finding related rules
- Success criteria: 4-8 hour assessment time (vs. 3-5 days current)

**Persona 2: Compliance Manager**
- 10+ years experience; oversees 5-20 analysts
- Goal: Ensure comprehensive coverage and consistent quality
- Pain: Quality review time-intensive, knowledge silos, staff turnover risk
- Success criteria: 30-minute review (vs. 3 hours current), confident in coverage

**Persona 3: Technology/Operations Lead**
- 8+ years; responsible for system implementation
- Goal: Clear requirements with sufficient lead time
- Pain: Late notification, vague requirements, scope creep
- Success criteria: Requirements received 4-6 weeks before deadline

### Journey Mapping

**Current State Workflow:**
1. Notification (email/website subscription)
2. Initial document review (30-60 min)
3. Search for related regulations (1-2 hours)
4. Impact assessment drafting (2-4 hours)
5. Manager quality review (3 hours)
6. Stakeholder communication (1-2 hours)
**Total: 3-5 days**

**Future State Workflow (with RegAI):**
1. Notification (same)
2. RegAI search for related regulations (<15 min)
3. System-assisted impact assessment drafting (1-2 hours)
4. Manager quality review (30 min)
5. Stakeholder communication (same)
**Total: 4-8 hours**

See `docs/journey-maps/` for detailed journey maps and workflow visualizations.

### Jobs-to-be-Done Framework

**Job 1:** "When a new regulation is published, I need to understand if it applies to my business so I can prioritize my work"
- Context: Analyst receives notification of regulatory change
- Desired outcome: Quick assessment of relevance; clear deadline
- Emotional: Confidence in completeness; pressure from deadline

**Job 2:** "When assessing impact, I need to find related regulations so I can ensure consistent interpretation"
- Context: Analyzing new regulation; want to reference prior versions or related rules
- Desired outcome: Find all related regulations; understand evolution/relationships
- Emotional: Confidence in consistency; fear of missing important context

**Job 3:** "When documenting analysis, I need to cite specific regulatory text so I can support my conclusions in audits"
- Context: Writing analysis document for internal stakeholders/auditors
- Desired outcome: Easy access to exact quotes; clear citations with page/section
- Emotional: Confidence in defensibility; fear of citation errors

---

## 3. Functional Requirements

### MVP Feature Set (Phase 1)

**3.1 Regulatory Search & Discovery**

**User Story 1:** Search by topic/concept
```
As a regulatory analyst, I want to search for regulations by topic or concept
so that I can find all relevant rules without knowing specific regulation names.

Acceptance Criteria:
- Search returns top 10 results ranked by relevance
- Latency <3 seconds for typical queries
- Results include jurisdiction, publication date, document type
- Can refine results by jurisdiction, document type, date range
- Search works across multi-jurisdiction corpus
```

**User Story 2:** Browse by jurisdiction
```
As a regulatory analyst, I want to browse regulations by jurisdiction
so that I can see all rules applicable to my assigned region.

Acceptance Criteria:
- Can select one or more jurisdictions (US, UK, EU, APAC)
- Displays count of regulations per jurisdiction
- Results filtered correctly by selection
- Clear indication of regulations effective vs. draft vs. proposed
```

**User Story 3:** View regulation details
```
As a regulatory analyst, I want to view complete regulation text with structure
so that I can understand the full requirement and context.

Acceptance Criteria:
- Display includes: title, jurisdiction, publication date, effective date
- Document structure preserved (articles, sections, subsections)
- Can navigate by section
- Related regulations identified and linked
- Citation information available (source URL, PDF link)
```

**User Story 4:** Track regulation versions
```
As a regulatory analyst, I want to see different versions of a regulation
so that I can understand how requirements have evolved.

Acceptance Criteria:
- Display version history with publication dates
- Can select any prior version to view
- Changes between versions highlighted or summarized
- Amendment notes captured (if available from source)
```

### Phase 1B: Analysis & Citations

**User Story 5:** Create impact analysis
```
As a regulatory analyst, I want to create an impact assessment documenting
which business lines and systems are affected, so that I can communicate findings.

Acceptance Criteria:
- Can create new analysis linked to regulation
- Add structured fields: affected business lines, affected systems, deadline, effort estimate
- Add narrative summary of key obligations
- Save as DRAFT (private) or SUBMIT (for review)
- Track creation timestamp and author
```

**User Story 6:** Cite source material
```
As a regulatory analyst, I want citations to automatically include specific text
with page/section references, so that my analysis is auditable and defensible.

Acceptance Criteria:
- Copy/paste functionality to include quote + citation
- Citation format: [Regulation Name, Article/Section X, Page Y]
- Citation validated against source (no manual errors)
- Can verify citation by clicking through to source document
- Citation accuracy >98% (spot-checked)
```

**User Story 7:** Manager review workflow
```
As a compliance manager, I want to review submitted analyses and provide feedback,
so that I can ensure quality and consistency.

Acceptance Criteria:
- View list of analyses waiting for review
- Open analysis and see all content with citations
- Can verify citations against source (side-by-side view)
- Approve, request revisions, or reassign
- Comments/feedback stored in audit trail
- Status tracking (SUBMITTED → APPROVED or REVISIONS_REQUESTED)
```

### Core Non-Functional Requirements

**Performance:**
- Search query latency: <2 seconds (95th percentile)
- Analysis generation: <15 seconds (standard depth)
- Page load: <2 seconds
- Support 50+ concurrent analysts

**Reliability:**
- 99.5% uptime SLA
- Graceful degradation if vector DB unavailable (fallback to keyword search)
- Automatic failover for LLM API timeouts

**Security:**
- Role-based access control (Analyst, Manager, Admin)
- Jurisdiction-based data filtering (users see only assigned jurisdictions)
- Encryption in transit (TLS 1.3) and at rest (AES-256)
- Audit logging of all queries and document access
- Session timeout (30 minutes inactivity)

**Scalability:**
- Support 100K+ regulatory documents
- Handle 500K+ concurrent chunks in vector database
- Cost-efficient at 50 organizations × 30 users each

---

## 4. Success Metrics

### North Star Metric
**Time to Complete Initial Impact Assessment**: Reduction from 3-5 days to 4-8 hours (target: 70% improvement)

### Supporting Metrics

**Efficiency Metrics:**
- Analyst productivity: Assessments per analyst per month (target: 4x increase)
- Manager review time: Hours per assessment (target: 0.5 hours; baseline 3 hours)
- Document analysis time: Hours spent reading vs. analyzing (target: 50% reduction in reading)

**Quality Metrics:**
- Citation accuracy: % of citations verified correct (target: >98%)
- Search relevance: User ratings of results 1-5 (target: 4.0+ average)
- Analysis rework rate: % requiring revisions (target: <5%)
- Hallucination rate: % of AI-generated analysis containing unfounded claims (target: <1%)

**Adoption Metrics:**
- Daily active users: % of target analysts using system (target: >60%)
- Queries per session: Average search queries per user session (target: >3)
- Return user rate: % of users active weekly (target: >70%)
- Feature usage: % of analysts using analysis creation (target: >50%)

**Business Metrics:**
- Regulatory deadline achievement: % of implementations completed on time (target: >95%)
- Audit findings: Reduction in compliance-related findings (target: 50% reduction)
- Knowledge retention: Analyst onboarding time (target: 30% faster)
- Cost per assessment: Compliance cost per regulatory analysis (target: 60% reduction)

### Measurement Plan

**Instrumentation:**
- All queries logged with timestamp, user, query text, results returned
- User feedback: 1-click rating on search results ("Was this relevant?")
- Manual audits: Weekly sample of 10 analyses for citation accuracy verification
- Dashboard: Real-time metrics on adoption, quality, performance

**Reporting:**
- Daily: Performance metrics (latency, error rate, uptime)
- Weekly: Engagement metrics (active users, queries, new analyses)
- Monthly: Quality metrics (citation accuracy, search relevance, rework rate)
- Quarterly: Business impact metrics (time savings, deadline achievement, user satisfaction)

---

## 5. Feature Prioritization & Roadmap

### Value vs. Complexity Matrix

**Phase 1 (MVP):** High Value, Low Complexity
- Multi-jurisdiction search
- Semantic search capability
- Citation with source verification
- Basic version tracking
- Analysis creation and manager review

**Phase 2:** High Value, High Complexity
- AI-powered obligation extraction (structured requirements list)
- Advanced version comparison (highlight changes)
- Cross-regulation relationship mapping (automatic linking of related rules)
- Deadline extraction and calendar integration
- Obligation-to-system impact mapping

**Phase 3+:** Medium Value, Medium/High Complexity
- Email alerts (new regulations in subscribed areas)
- Advanced analytics (compliance readiness scoring)
- Integration with Jira/ServiceNow (automatic ticket creation)
- Change prediction (predict upcoming regulatory changes)
- Multi-language support

### MVP Rationale

**Why Phase 1 scope?**
- Core retrieval value is immediate and demonstrable
- Impact assessment analysis requires domain-specific tuning (better after user feedback)
- MVP validates RAG architecture and user fit before complex features
- Engineering effort allows 3-month development timeline
- First customer value can be realized from search alone (45% time savings)

### 3-Phase Roadmap

```
Phase 1 (Weeks 1-12): MVP - Search & Citation Foundation
├─ Ingestion pipeline & vector database
├─ Semantic search with hybrid retrieval
├─ Citation system with source validation
├─ Analysis creation workflow
└─ Manager review & approval

Phase 2 (Weeks 13-28): Enhancement - AI-Powered Analysis
├─ Obligation extraction from regulations
├─ Advanced version comparison
├─ Cross-regulation relationship mapping
├─ Deadline extraction & calendar integration
└─ Obligation-to-system impact mapping

Phase 3 (Weeks 29+): Scale - Operations & Integration
├─ Email alerts and subscriptions
├─ Workflow integration (Jira, ServiceNow, Outlook)
├─ Advanced analytics dashboard
├─ Multi-language support
└─ Industry vertical customization (banking, asset management, brokerage)
```

---

## 6. Risk Register

| Risk | Category | Probability | Impact | Mitigation |
|------|----------|-------------|--------|-----------|
| LLM generates inaccurate analysis (hallucinations) | Technical | High | High | Mandatory source citation requirement; conservative prompting; confidence scoring; human review gate |
| Vector database cannot scale to 100K documents | Technical | Medium | High | Benchmark before production; use managed service (Pinecone/Weaviate); load testing in Phase 1 |
| Search relevance insufficient for real workflows | Technical | Medium | High | Early user testing in pilot; fallback to keyword search; continuous retraining |
| Users distrust AI-generated analysis | Adoption | Medium | High | Transparent design (cite sources); education on how system works; manager review requirement; early beta feedback |
| Regulatory changes require system updates | Operational | High | Medium | Automated ingestion pipeline; version control; change log; clear communication to users |
| Data privacy/compliance violations | Regulatory | Low | Critical | No PII in searches; on-premise option available; data residency controls; legal review |
| Vendor lock-in (LLM API) | Strategic | Medium | Medium | Use standard APIs; benchmark alternatives; consider fine-tuned alternatives if needed |
| User adoption slower than expected | Adoption | Medium | Medium | Structured onboarding; success metrics tracking; quarterly business reviews with customers |

### Mitigation Strategies

**Hallucination Mitigation:**
- Design requirement: All responses must cite specific source text
- Evaluation: Manual spot-checks of 50 analyses/month for unfounded claims
- User safeguards: Flagging uncertain responses; conservative defaults ("I don't know" preferred over speculation)

**User Adoption Mitigation:**
- Involve compliance team in design early (personas, feedback)
- Structured training before go-live
- Early wins focus (quick regulatory assessments vs. complex analyses)
- Success metrics tracking and optimization

**Scalability Mitigation:**
- Load testing for 50 concurrent users in Phase 1
- Managed vector database service (reduces operational burden)
- Query caching (Redis) for common searches
- CDN for document downloads

---

## 7. Stakeholder Analysis & Communication

### Power/Interest Matrix

**High Power, High Interest:** CRO, Chief Compliance Officer
- Decision-makers on product investment
- Concerned with: Risk reduction, audit readiness, regulatory approval
- Engagement: Monthly exec updates, quarterly reviews, early risk briefing

**High Power, Low Interest:** CFO, General Counsel
- Approval authority for budget/liability
- Concerned with: Cost, legal liability, ROI
- Engagement: Quarterly business reviews, liability framework review

**Low Power, High Interest:** Compliance analysts, managers
- Core users; early advocates
- Concerned with: Usability, time savings, quality
- Engagement: Daily standup, weekly feedback, pilot participants

**Low Power, Low Interest:** IT operations, other departments
- Support functions
- Concerned with: Integration, data access, security
- Engagement: Integration planning (Phase 2), security review

### Communication Plan

**Executives (CEO, CRO, CFO):**
- Message: "Reduce compliance costs by 50% while improving effectiveness"
- Cadence: Quarterly business review (30 min)
- Content: Progress, metrics, risks, budget

**Compliance Team (staff, managers, director):**
- Message: "Spend less time on document review; focus on judgment"
- Cadence: Weekly standup + monthly feedback session
- Content: Roadmap, beta invitations, feature feedback

**Engineering Team:**
- Message: "Build AI product that maintains compliance audit standards"
- Cadence: Sprint planning, bi-weekly technical reviews
- Content: Technical requirements, architecture, RAG best practices

**Board/Investors:**
- Message: "Significant market opportunity in regulatory tech; strong product-market fit signals"
- Cadence: Quarterly board update
- Content: Traction, customer feedback, financial projections
