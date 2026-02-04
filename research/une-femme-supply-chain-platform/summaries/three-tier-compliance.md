# Three-Tier Alcohol Distribution System: Compliance Framework & Data Sharing Implications

## Executive Summary

The U.S. alcohol beverage system operates under a federally-established but state-executed three-tier regulatory framework implemented since Prohibition's repeal in 1933. This structure mandates strict separation between suppliers (Tier 1: producers/importers), wholesalers (Tier 2: distributors), and retailers (Tier 3: direct sellers), with vertical integration explicitly prohibited through ownership restrictions. For wine supply chain platforms like Une Femme, the three-tier system creates both operational constraints and opportunities: data cannot flow directly between tiers without regulatory oversight, automated systems must accommodate state-by-state licensing variations, and platform design must respect inter-tier transactional boundaries while enabling transparency within permissible channels. The framework was intentionally designed to prevent monopolistic control and ensure fair competition for smaller producers, making it a foundational constraint for any wine distribution intelligence platform.

## Key Concepts & Definitions

### The Three-Tier System Architecture

**Tier 1 - Suppliers (Producers):** U.S. producers (wineries, breweries, distilleries) or importers who manufacture and package alcoholic beverages. These entities obtain federal Alcohol and Tobacco Tax and Trade Bureau (TTB) permits and state-by-state ABC licenses before selling to Tier 2 entities only.

**Tier 2 - Wholesalers/Distributors:** Licensed intermediaries who purchase exclusively from Tier 1 suppliers and distribute exclusively to Tier 3 retailers. This tier manages logistics, inventory, and supply chain operations but cannot sell directly to consumers or own production facilities.

**Tier 3 - Retailers:** Licensed establishments that sell to consumers only, classified as either "off-premise" (liquor stores, grocery stores, e-commerce) or "on-premise" (bars, restaurants, wine clubs).

### State Regulatory Categories

**Open States:** The majority of U.S. states where suppliers sell directly to distributors, who then sell to retailers. This is the standard operational model for most wine producers and distributors.

**Control States:** A minority of states where government-run wholesaling systems operate. The state itself acts as the distributor and retailer, purchasing directly from suppliers. This variant creates fundamentally different data and compliance pathways that platforms must accommodate separately.

### Critical Compliance Definitions

**COLA (Certificate of Label Approval):** Federal approval required from TTB for all alcohol product labels before any sale. This is a prerequisite document that all Tier 2 and Tier 3 entities must verify exists for any product they handle.

**ABC Licenses:** State-level alcohol beverage control licenses required for each state in which an entity operates. These are state-specific and cannot transfer across jurisdictions.

**Nexus:** The legal connection that triggers sales tax obligations. For wine distributed across state lines, nexus laws determine in which states a supplier owes sales tax on wholesale transactions.

**Excise Tax:** Federal (products >7% ABV) and state-level taxes applied to alcohol products, with varying rates and application points depending on distribution channel (direct-to-consumer vs. wholesale vs. retail).

## Main Arguments & Findings

### 1. Vertical Integration Prohibition as Core Constraint

The three-tier system's foundational principle is prevention of vertical monopolies. Ownership restrictions explicitly prevent any single entity from operating across multiple tiers - a supplier cannot own a distributor or retailer, and a retailer cannot own a distributor. This creates a hard architectural boundary for supply chain platforms: data ownership and access must respect tier separation, and any platform claiming to provide "end-to-end visibility" must do so through aggregation of separately-owned data sources rather than direct system integration.

**Implication for Une Femme platform:** The platform cannot assume direct database access across tiers. Instead, it must function as a data aggregation and intelligence layer that third-party systems voluntarily feed into, respecting each tier's operational independence.

### 2. Multi-Layered Licensing & Compliance Architecture

Alcohol beverage companies operate under cascading regulatory requirements:

- **Federal Layer:** TTB permits + COLA label approvals (one-time per product, but subject to modification reviews)
- **State Layer:** ABC licenses in each operating state + state-specific product registration
- **Ongoing Obligations:** Continuous license modifications, tax filing, returns documentation, and compliance audits

The Avalara source notes that "License modifications when legal name, ownership, or address changes occur" and "Continuous product registration updates" are ongoing obligations, not one-time procedures. This means compliance data is dynamic and error-prone.

**Implication for Une Femme platform:** The platform must continuously track and surface compliance status changes. A wine product that passes federal COLA approval may fail state registration in a particular jurisdiction, creating a gap between federal and state compliance status that distribution decisions depend on.

### 3. Complex Tax Topology

Alcohol taxation involves multiple simultaneous tax types applied at different tiers and rates:

- **Federal Excise Tax:** Applied uniformly to products >7% ABV by federal government
- **State Excise Tax:** Varies by state and distribution channel (wholesale vs. direct-to-consumer rates differ)
- **Sales Tax:** Required in non-NOMAD states, varies by state and triggered by nexus
- **Markup Taxes:** Applied in limited states on retail value

The existence of NOMAD (direct-to-consumer) exemptions means that taxation for the same wine product varies depending on the distribution channel used. A wine sold directly to consumers via NOMAD may be exempt from sales tax, while the same wine sold through Tier 2-3 channels incurs full tax liability.

**Implication for Une Femme platform:** Pricing and profitability analysis must account for channel-dependent taxation. The platform cannot provide a single "cost of goods sold" calculation without knowing the intended distribution channel.

### 4. State-by-State Regulatory Variation

The three-tier system is not federally mandated but rather state-adopted, creating significant variation:

- **Open States (majority):** Standard supplier → distributor → retailer flow
- **Control States (minority):** Government-run state monopoly systems where the state is both distributor and retailer

Control state systems create fundamentally different data flows: there is no private wholesale tier in these states, and sales data from the state monopoly distributor to the state monopoly retailer may be subject to different confidentiality rules or availability than in open states.

**Implication for Une Femme platform:** The platform must maintain separate data pipelines and business logic for control states vs. open states. Analytics about "wholesale velocity" or "distributor margins" cannot be applied uniformly across all U.S. states.

### 5. Data Sharing Prohibitions Between Tiers

While the sources do not explicitly detail forbidden data sharing practices, the vertical integration prohibition and tier separation create implicit data boundaries: Tier 1 suppliers cannot directly access Tier 3 consumer purchase data without intermediation through Tier 2 distributors, and the distributor's own competitive interests may limit transparency. A supplier cannot require a distributor to share detailed end-consumer sales data as a condition of wholesale supply because the distributor's competitive advantage depends on controlling customer relationships.

This is particularly critical for wine, where brand owners (Tier 1) have strong incentives to understand consumer preferences and purchasing patterns, but the three-tier system intentionally creates friction between supply-side and demand-side data visibility.

**Implication for Une Femme platform:** The platform cannot facilitate direct access by wine producers to retailer-level purchase data without consent from each distributor and retailer in the chain. Any "wine supply chain intelligence" must be aggregated and anonymized across multiple independent data sources.

### 6. Fair Competition & Market Diversity Rationale

The Southern Glazers source explicitly notes: "The three-tier system creates a level playing field, so smaller players with fewer resources can still compete fairly." The system's purpose is to maintain market diversity and prevent large conglomerates from controlling both production and distribution, which would allow them to favor their own products and block competitors' products from reaching consumers.

This rationale means that regulatory bodies actively scrutinize any system that might re-concentrate information control or competitive advantage. A platform that provides superior supply chain visibility to large wine companies but not smaller ones could face regulatory scrutiny.

**Implication for Une Femme platform:** Platform features must be offered equitably across company sizes. Tiered pricing or access models that create information asymmetries between small producers and large producers could trigger regulatory concern about restoring the vertical monopoly dynamics the three-tier system was designed to prevent.

## Evidence & Examples

### Specific Compliance Requirements

From Avalara whitepaper:

1. **Federal Requirements:**
   - TTB permit required first (before any state licenses)
   - COLA (Certificate of Label Approval) for every product label

2. **State Requirements:**
   - ABC licenses in each operating state
   - Out-of-state licensing including Secretary of State registration, bonds, and tax permits for non-resident dealers
   - State-by-state product registration

3. **Ongoing Obligations:**
   - License modifications when legal name, ownership, or address changes
   - Continuous product registration updates
   - Federal and state excise tax payments
   - Reporting and returns documentation

4. **Tax Application:**
   - Federal excise tax: Products >7% ABV (covers most wines)
   - State excise tax: Varies by state and distribution channel
   - Sales tax: Required in non-NOMAD states based on nexus laws
   - Markup taxes: Applied on retail value in limited states

### Tier Definitions from Southern Glazers

- **Tier 1 - Suppliers:** "Breweries, wineries, distilleries, and importers manufacture and package alcoholic beverages for sale to licensed distributors."
- **Tier 2 - Distributors:** "Licensed entities purchase products from suppliers and distribute them to retailers, managing logistics and supply chain operations."
- **Tier 3 - Retailers:** "Licensed establishments sell beverages to consumers, classified as either off-premise (liquor stores, grocery stores) or on-premise (bars, restaurants)."

### Market Structure Rationale

Southern Glazers: "The three-tier system creates a level playing field, so smaller players with fewer resources can still compete fairly." This explicit statement about competitive equity has regulatory implications for how platforms serving this market should operate.

## Methodology & Source Quality

### Source 1: Avalara (avalara.com)

**Quality Assessment:** High credibility. Avalara is a professional tax compliance software company with deep expertise in multi-jurisdictional regulatory requirements. Their whitepaper on alcohol compliance is intended for tax professionals and business operators. The information is specific, detailed, and technical rather than promotional. The source reflects practical compliance requirements rather than ideal-state scenarios.

**Strengths:**
- Specific enumeration of federal (TTB) and state (ABC) requirements
- Clear distinction between one-time (COLA, permits) and ongoing (tax filing, license modifications) obligations
- Detailed tax topology including federal excise, state excise, sales tax, and markup taxes
- Addresses out-of-state and non-resident dealer requirements

**Limitations:**
- Does not address data sharing restrictions between tiers explicitly
- Limited discussion of control state variations
- Whitepaper format means it may not capture the most recent regulatory changes

### Source 2: Southern Glazers (southernglazers.com)

**Quality Assessment:** Medium-high credibility. Southern Glazers is one of the largest spirits and wine distributors in the United States, so this represents a Tier 2 entity's perspective on the system. The information is accurate but reflects a distributor's framing and interests. The emphasis on "fair competition" may be partly self-serving (distributors benefit from the tier system) but is factually supported.

**Strengths:**
- Clear definitions of each tier and their functions
- Explicit statement about the competitive equity purpose of the system
- Distinction between open states and control states
- Accessible language suitable for partner education

**Limitations:**
- Limited detail on compliance mechanics (focused on high-level structure)
- Distributor-centric perspective (Tier 2) rather than balanced across all tiers
- Does not address data privacy or sharing restrictions
- Less detail on tax and regulatory mechanics than Avalara

### Combined Coverage Assessment

The two sources complement each other: Avalara provides compliance mechanics and regulatory detail, while Southern Glazers provides tier architecture and market structure context. Together, they provide strong coverage of the three-tier system's structure and requirements, but leave gaps around:

1. **Data sharing restrictions:** Neither source explicitly addresses what data can or cannot flow between tiers
2. **Automation constraints:** No discussion of how digital platforms can operate within tier restrictions
3. **State-specific variations:** Limited detail on how control states or specific states modify the system
4. **Emerging issues:** No discussion of direct-to-consumer (DTC) wine sales and how they interact with the three-tier system

## Relevance to Une Femme Supply Chain Platform

### Critical Design Constraints

The three-tier system imposes four non-negotiable design constraints on Une Femme:

1. **Tier Separation Constraint:** The platform cannot assume unified data ownership or direct system access across tiers. It must operate as a data aggregation layer with voluntary participation from independent Tier 1, 2, and 3 entities.

2. **Multi-State Compliance Complexity:** The platform must accommodate fundamentally different regulatory models in open states vs. control states. Analytics, forecasting, and visibility features cannot be identical across all U.S. markets.

3. **Dynamic Compliance Tracking:** Licensing, registration, and tax status are not static. The platform must surface compliance status changes (failed state registrations, license modifications, expired COLAs) as data quality issues that affect distribution decisions.

4. **Channel-Dependent Economics:** Profitability analysis, pricing decisions, and supply chain optimization cannot use uniform tax or regulatory assumptions. The same wine product has different total cost of ownership depending on whether it's distributed through traditional three-tier channels or direct-to-consumer NOMAD channels.

### Specific Feature Implications

**Supply Forecast Module:**
- Cannot assume uniform wholesale demand across states (control states have different demand patterns than open states)
- Must account for regulatory approval delays (COLA approvals, state registrations) as potential bottlenecks in product launch timelines
- Should flag state registrations that are pending or expired as risks to forecast accuracy

**Distributor Performance Analytics:**
- Cannot compare distributor performance metrics uniformly across states (control state monopoly distributors operate under different constraints than open state wholesalers)
- Must isolate the impact of tax changes on distributor margins by state
- Should provide separate views for open-state vs. control-state performance

**Compliance & Risk Module:**
- Should provide dashboard of COLA status, ABC license status, and product registration status by state
- Must surface compliance gaps (product registered in Tier 1 but not yet registered in target Tier 3 states) as distribution risks
- Should trigger alerts when licenses expire or modifications are required

**Pricing & Profitability Analysis:**
- Must incorporate state-by-state tax topology (federal excise, state excise, sales tax, markup taxes, NOMAD exemptions)
- Should model channel-dependent profitability (traditional three-tier vs. direct-to-consumer)
- Must separate tax liability from product cost in profitability calculations

### Market Position Implications

The three-tier system's purpose is to maintain competitive equity for smaller producers. Une Femme's positioning as a supply chain intelligence platform should emphasize how it helps smaller wine producers compete fairly by providing supply chain visibility that was previously only available to large enterprises with dedicated compliance and logistics teams. This aligns the platform with the regulatory intent of the three-tier system rather than working against it.

## Practical Implications & Action Items

### For Platform Architecture

1. **Data Model:** Design the platform's data model to accommodate three separate participant types (suppliers, distributors, retailers) with different data access rights, rather than assuming unified data ownership.

2. **State Variation Handling:** Create distinct data pipelines and business logic for open states vs. control states. Do not attempt to unify analytics across these fundamentally different regulatory models.

3. **Compliance Data Integration:** Integrate with TTB and state ABC databases (where publicly available) to automatically surface compliance status changes. Build workflows to flag products that fail state registration or have lapsed COLAs.

4. **Tax Calculation Engine:** Implement a modular tax calculation engine that accounts for federal excise, state excise, sales tax, and markup taxes by state and channel. Make tax assumptions transparent and updatable.

### For Regulatory Compliance

1. **Data Privacy Policies:** Develop clear policies about what data the platform collects from each tier and how it's shared or aggregated. Ensure policies do not create competitive advantages for large entities over small ones.

2. **Terms of Service:** Define explicit restrictions on how distributor-level data can be accessed by suppliers, and how retailer-level data can be accessed by distributors or suppliers. Respect the tier separation principle in ToS.

3. **Audit Readiness:** Maintain documentation of compliance-related features and design decisions, as regulators may eventually scrutinize alcohol supply chain platforms to ensure they don't circumvent the three-tier system.

### For Product Strategy

1. **Segmentation:** Consider separate product tiers or views for suppliers, distributors, and retailers, rather than a unified platform experience. Each tier has different data access rights and optimization priorities.

2. **Equity Focus:** Position the platform as enabling fair competition by democratizing supply chain intelligence. Ensure pricing and feature access don't create information asymmetries between small and large producers.

3. **State-Specific Features:** Build out state-specific compliance features (control state tracking, state-by-state tax calculations) as core differentiators rather than add-ons.

## Notable Quotes

**On the Purpose of the Three-Tier System:**
"The three-tier system creates a level playing field, so smaller players with fewer resources can still compete fairly." (Southern Glazers)

**On the Structure:**
"This structure prevents vertical integration through ownership restrictions across tiers." (Avalara)

**On Ongoing Compliance:**
"License modifications when legal name, ownership, or address changes occur" and "Continuous product registration updates" are listed as ongoing obligations, highlighting that compliance is a process, not a one-time event. (Avalara)

## Critical Evaluation

### Strengths of the Sources

- Both sources are from authoritative entities (professional tax services firm and major distributor)
- Information is specific and technical rather than promotional
- Clear distinction between federal and state requirements
- Explicit statement about the market-structure rationale for the three-tier system

### Gaps & Limitations

- **Data Sharing Restrictions:** Neither source explicitly addresses what data flow between tiers is prohibited or restricted. This is a critical gap for supply chain platform design.

- **Direct-to-Consumer Ambiguity:** The NOMAD exemption is mentioned in tax context but the sources don't clarify how direct-to-consumer wine sales interact with the three-tier system's ownership restrictions. Can a Tier 1 producer operate their own direct-to-consumer retailer?

- **Technology and Automation:** The sources do not address how digital systems, EDI, APIs, or data integration tools interact with tier restrictions. Are there special considerations for automated order fulfillment or data synchronization across tiers?

- **Control State Detail:** While the sources mention control states exist, they provide minimal detail on how their operation differs or which states are control states.

- **Interstate Commerce:** Limited discussion of how products move across state lines and how the three-tier system operates in multi-state distribution chains.

- **Recent Changes:** No discussion of recent regulatory developments, such as federal changes to direct-to-consumer rules or state-level modernizations of the alcohol regulatory framework.

### Reliability Assessment

**High Confidence Areas:**
- Basic three-tier structure and tier definitions
- Federal TTB and COLA requirements
- General tax types (federal excise, state excise, sales tax, markup taxes)
- Purpose of the system (fair competition, preventing vertical monopolies)

**Medium Confidence Areas:**
- Specific state variations and control state operations (sources acknowledge variation without detailed enumeration)
- Ongoing compliance obligations (examples given but not exhaustive)
- Data sharing restrictions (inferred from tier separation rather than explicitly stated)

**Low Confidence Areas:**
- Current regulatory interpretation of how digital platforms should operate within the three-tier system
- Specific state-by-state variations not detailed in sources
- How direct-to-consumer sales interact with three-tier ownership restrictions
- Recent regulatory changes or modernizations

## Synthesis for Une Femme PRD

The three-tier system is the foundational regulatory architecture that any wine supply chain intelligence platform must respect and accommodate. It is not a constraint to work around but rather a market reality that affects:

1. **Who has access to what data:** Data ownership is fundamentally constrained by tier separation; platforms cannot enable direct data sharing between tiers without explicit consent mechanisms.

2. **How analytics operate:** Analytics features cannot assume uniform regulatory or economic conditions across all U.S. markets; control states must be treated separately from open states.

3. **How compliance is managed:** Compliance is a continuous, multi-jurisdictional process involving federal (TTB) and state (ABC) layers; platforms must surface compliance gaps and risks.

4. **How profitability is calculated:** The same wine product has different total cost of ownership and regulatory burden depending on the distribution channel; pricing and profitability analysis must be channel-aware.

5. **How the platform is positioned:** The system is designed to maintain competitive equity for smaller producers; platforms should position themselves as democratizing supply chain intelligence rather than concentrating competitive advantage.

For Une Femme's initial implementation, the most critical implications are:

- **Phase 1:** Focus on compliance tracking (COLA, ABC registrations, tax permits) and state-specific regulatory status as core value propositions
- **Phase 2:** Develop distributor-focused analytics that respect the confidentiality of retailer relationships and treat control states separately
- **Phase 3:** Add supplier-focused forecasting that accommodates the fact that supplier visibility into downstream sales is limited by distributor competitive interests
- **Phase 4:** (Optional) develop sophisticated pricing and profitability analysis that models channel-specific tax and regulatory impacts

The three-tier system is well-established and unlikely to change fundamentally, making it a stable foundation for platform design assumptions.
