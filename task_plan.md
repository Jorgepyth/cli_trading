# Task Plan

## Phases
- [x] **Phase 1: B - Blueprint** (Vision & Logic)
- [x] **Phase 2: L - Link** (Connectivity & Environment)
- [x] **Phase 3: A - Architect** (The 3-Layer Build)
- [x] **Phase 4: S - Stylize** (Refinement & UI)
- [ ] **Phase 5: T - Trigger** (Deployment & Safety)

## Goals
Develop a robust Python-based CLI on WSL for manual opening and closing of positions in Binance Futures. 
Priority is determinism, human validation, and pre-execution risk calculation (Target PnL vs Fees, and Account Equity at Stake).

## Checklists

### Protocol 0: Initialization
- [x] Create foundational files
- [x] Answer Discovery Questions
- [x] Define Data Schema in `gemini.md`
- [x] Define `.env` template
- [x] Approve `task_plan.md` Blueprint

### Phase 2: Link (Connectivity & Environment)
- [x] Initialize Python environment and `.env`.
- [x] Create simple tool to Ping Binance API on Testnet.
- [x] Log connections in `findings.md`.

### Phase 3: Architect (3-Layer Build)
- [x] Layer 1 (`architecture/`): SOPs for execution flow and risk validation.
- [x] Layer 2 (`cli` module): Interactive flow logic.
- [x] Layer 3 (`tools/`): Atomic Binance execution scripts.

### Phase 4: Stylize (Refinement & UI)
- [x] Implement CLI interaction (Prompts, Tables, Auth Screen).

### Phase 5: Trigger (Deployment)
- [ ] Test on Testnet.
- [ ] Implement Production toggle.
