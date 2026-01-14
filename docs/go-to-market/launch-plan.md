# Launch Plan

## Phase 1: Internal Pilot (Weeks 1-8)

**Objective:** Validate core functionality with friendly internal users; identify critical bugs and UX issues before external launch.

**Scope:**
- Deploy MVP with core search and basic analysis features
- Select 5-10 internal users from compliance team (mix of roles)
- Run real regulatory research workflows
- Iterate based on feedback

**Activities:**
- **Week 1-2**: Environment setup, user training, kickoff
- **Week 3-6**: Daily usage, feedback collection, bug fixes
- **Week 7-8**: Synthesis of findings, documentation of learnings, roadmap adjustments

**Success Criteria:**
- Zero critical bugs blocking core workflow
- 80%+ user satisfaction with search relevance
- <2 second search latency consistently
- Positive feedback on citation accuracy

**Key Risks:**
- Retrieval quality insufficient for real workflows (LLM accuracy issues)
- Performance issues with live regulations database
- **Mitigation**: Benchmark on test dataset before pilot; have fallback keyword search

---

## Phase 2: Limited Beta (Weeks 9-16)

**Objective:** Test product-market fit with external customers in controlled environment; gather evidence of value.

**Scope:**
- Invite 5-10 "friendly customer" organizations (existing relationships, early adopters)
- Expand to 2-3 jurisdictions (US, UK, EU)
- Structured support and feedback collection
- Targeted on high-value use cases (new major regulation analysis)

**Customer Selection Criteria:**
- Current customer or strong relationship with founder/CRO
- Stated interest in regulatory AI solutions
- Sufficient compliance team scale (20+ analysts)
- English-speaking primary business
- Willingness to provide structured feedback

**Activities:**
- **Week 9-10**: Customer onboarding, training, support setup
- **Week 11-14**: Production usage, weekly feedback calls, bug triage
- **Week 15**: Consolidate feedback, identify feature requests
- **Week 16**: Analyze metrics, document learnings, plan for GA

**Measurement & Metrics:**
- **Engagement**: Daily active users, queries per user
- **Adoption**: Feature usage, time spent in system
- **Quality**: Search relevance ratings (1-5 scale), citation accuracy spot checks
- **Business**: Time to complete regulatory assessment (before/after)
- **Satisfaction**: NPS scores, willingness to expand

**Success Criteria:**
- 90%+ citation accuracy (spot checks by customer compliance team)
- 70%+ search relevance ratings
- 50%+ of target user base (analysts) active weekly
- Positive NPS (>40)
- Evidence of time savings (30%+ reduction in assessment time)

**Support Model:**
- Dedicated customer success manager per customer
- Slack channel for support and feature requests
- Weekly feedback calls with product team

**Key Risks:**
- Customers discover critical gaps (missing regulation types, jurisdictions)
- Data privacy concerns about regulatory documents in cloud
- Integration challenges with internal systems
- **Mitigation**: 
  - Pre-assess data sensitivity; offer on-premise option if needed
  - Provide pre-built connectors for major systems
  - Have legal pre-review ToS before customer engagement

---

## Phase 3: General Availability (Week 17 onward)

**Objective:** Phased commercial launch targeting initial market segment; establish product-market fit; begin revenue generation.

### Phased Rollout Strategy

**Wave 1 (Weeks 17-24): US Mid-Market Banks**
- Target: 10-15 new customers
- Focus: US regulatory focus (SEC, CFTC primary)
- Support: Scalable onboarding program, knowledge base, community
- Pricing: $1M-$1.5M ACV (negotiated based on team size)
- Sales: Founder-led sales, warm introductions, case study references

**Wave 2 (Weeks 25-32): US Expansion + UK Entry**
- Target: 10-15 additional US customers + 5-8 UK customers
- Product: EU regulations added, multi-language support roadmap
- Support: Sales engineering hire, scaled onboarding
- Metrics: Retain 90%+ of Wave 1 customers

**Wave 3 (Months 9-12): EU Expansion**
- Target: 10+ EU customers
- Product: GDPR compliance for EU data handling, full multi-language support
- Sales: Partner channel (consulting firms, compliance service providers)

**Wave 4+ (Year 2): APAC + Horizontalization**
- Target: Expand to Singapore, Hong Kong, Japan
- Product: Extend to operational risk, AML compliance (adjacent use cases)

### Launch Messaging & Positioning

**Core Message:**
"RegAI Copilot helps compliance teams navigate regulatory complexity with speed and confidence—reducing analysis time from days to hours while maintaining control and audit readiness."

**Key Talking Points:**
- **For Analysts**: Find relevant regulations in minutes, not hours; complete impact assessments faster
- **For Managers**: Ensure comprehensive coverage, reduce analysis time, build institutional knowledge
- **For Executives**: Reduce compliance costs, improve speed-to-implementation, lower regulatory risk

**Sales Approach:**
- Lead with Time to Value (reduce assessment time 70-80%)
- Support with Quality metrics (citation accuracy, audit trail)
- Close with Strategic benefits (knowledge retention, scalability)

### Launch Activities

**Marketing:**
- White paper on regulatory AI best practices
- Webinar series on key regulations (MiFID III, Basel IV, etc.)
- Thought leadership content (blog, LinkedIn)
- Conference sponsorships (RegTech conferences)

**Sales:**
- Sales collateral (1-pager, deck, case study)
- Demo video walkthrough
- Free trial access (14-30 days) for qualifying prospects

**Community:**
- Customer advisory board for feature prioritization
- Case studies documenting customer wins
- User conference (annual) starting Year 2

### Adoption & Success Metrics

**Leading Indicators (Month 1-3):**
- Trial sign-ups: 50+ per month
- Trial-to-paid conversion: 30%+ (1-year contracts)
- Sales cycle: 6-8 weeks (discovery to signature)

**Lagging Indicators (Month 3-12):**
- New customer ARR: $10M+ by end of Year 1
- Gross retention: 90%+ (churn <10%)
- Net retention: 110%+ (expansion revenue)
- Customer satisfaction (NPS): >50

### Support & Onboarding at Scale

**Onboarding Program:**
1. **Pre-launch**: 1-hour orientation, credential setup, initial docs
2. **Week 1**: Live training session for analyst team + managers
3. **Week 2**: First real regulation search + feedback
4. **Month 1**: Check-in call, optimization opportunities, advanced features
5. **Quarterly**: Business review, roadmap discussion, expansion planning

**Support Tiers:**
- **Tier 1** (Self-service): Knowledge base, community forum, email support (48hr response)
- **Tier 2** (Standard): Phone support, feature requests, dedicated Slack channel
- **Tier 3** (Premium): Dedicated success manager, quarterly business reviews, priority support

**Scaling Support:**
- Months 1-3: Founder + 1 Customer Success hire
- Months 4-8: Add 1 more CS + Sales Engineering hire
- Month 9-12: Full team of 4 CS managers + 2 Sales Engineers

---

## Key Dependencies & Risks

**Critical Path Items:**
1. LLM API reliability and cost (OpenAI SLA)
2. Data quality of regulatory corpus
3. Customer success in first 2-3 implementations
4. Retention metrics post-MVP

**Go/No-Go Decision Points:**
- **Week 8 (End of Pilot)**: Internal satisfaction >75%, zero critical bugs → proceed to beta
- **Week 16 (End of Beta)**: Customer NPS >40, search relevance >70%, retention 90%+ → proceed to GA
- **Month 6 (Mid GA)**: Sales pipeline established, churn <10%, unit economics positive → expand to additional geographies

**Success Definition (End of Year 1):**
- 15-20 paying customers (US-focused)
- $10M+ ARR
- 90%+ gross retention
- Expansion revenue (multi-jurisdiction upgrades, additional seats)
- Positive path to profitability identified
