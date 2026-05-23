# robot_txt_thesis

# robot.txt (Semantic Configuration Analyzer)

 (academically designated as the **Semantic Configuration Analyzer**) is an advanced static analysis tool for RFC 9309 (`robots.txt`). It is engineered to detect high-severity syntactic conflicts, evaluate automated crawler defenses

Traditional binary parsers (like Python’s `urllib.robotparser`) blindly accept syntactically valid files, often missing structural logic breaks.this project evaluates the effective protective state of a domain by calculating byte-length specificity and boolean inheritance rules, successfully detecting vulnerabilities like the **Enumeration Fallacy**.

---

# Core Features

## Enumeration Fallacy Detection
Identifies overlapping `Allow` and `Disallow` directives that trigger protocol octet-counting defaults, forcing unintended open-access states.

## Defense Tier Classification
Routes domains into a deterministic 5-Tier system based on infrastructure and application-layer crawler blocking efficiency.

## Fractional Layer Weighting
Evaluates domains beyond standard binary logic, assessing fractional exposure to specific bot taxonomies (e.g., SEO bots vs. AI training crawlers vs. AI assistant agents).

## Automated Batch Auditing
Capable of executing high-throughput, delay-optimized incremental crawls across large datasets such as GDELT.

---

# Architecture

RoboLint is built on a standard **Model-View-Controller (MVC)** architecture to ensure modularity and extensibility for future protocol updates.

## Pipeline Control Agent (Controller)
Manages the execution flow, from initiating the web scraper to coordinating downstream processing.

## Core Processing Modules (Model)

### Classifier
Assigns the 5-Tier defense state.

### Conflict Detector
Executes longest-path specificity rules and identifies protocol conflicts.

### Compliance Analyzer
Translates technical exposure into legal and regulatory risk metrics.

## Presentation Layer (View)
Generates terminal UI outputs, compliance reports, and `matplotlib` data visualizations.

---

# Defense Tier Classification System

RoboLint automatically categorizes domains into one of the following defense states:

| Tier | Classification | Description |
|---|---|---|
| **Tier 5** | True Nuclear | Global wildcard block. Maximum protection; SEO sacrificed. |
| **Tier 4b** | Secured Nuclear | Global block + Google Search exceptions + explicit Google-Extended block. |
| **Tier 4a** | SEO-Captive Nuclear | Global block + Google Search exceptions without AI block. Vulnerable. |
| **Tier 3** | Surgical | Explicitly blocks both application-layer and infrastructure-layer AI bots. Targeted and effective. |
| **Tier 2** | Porous | Blocks visible bots but misses underlying training infrastructure. Performative defense. |
| **Tier 1** | Open | No AI-specific blocking detected. Fully accessible. |

---

# Installation

Clone the repository and install the required dependencies.

## Clone Repository

```bash
git clone https://github.com/yourusername/robolint.git
cd robolint
```

## Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Usage

## Single Domain Analysis

Run RoboLint against a specific domain to output its defense tier and conflict status.

```bash
python main.py analyze --url https://example.com
```

## Batch Processing (Dataset Audit)

Execute a pipeline run across a CSV of domains (e.g., `gdelt_domains.csv`). The script automatically handles HTTP retries, `404` responses, and polite crawling delays.

```bash
python main.py batch \
    --input data/gdelt_domains.csv \
    --output results/audit_report.json
```

---

# Academic Context and Validation

This tool was developed as the core artifact for the thesis:

> **Structural Vulnerabilities in Machine-Readable Opt-Outs: A Defense Tier Classification of
REP Efficacy Against Generative AI
Web Crawlers**

During its initial deployment across an 806-domain European news dataset, RoboLint achieved a **100% concordance rate** against a manually audited, stratified purposive sample, demonstrating strict adherence to RFC 9309 mandates while minimizing the risk of algorithmic classification bias.

---

# Research Objectives

- Evaluate the real-world efficacy of `robots.txt` as an AI crawler defense mechanism.
- Detect structural protocol weaknesses hidden beneath syntactic validity.
- Measure divergence between declared crawler restrictions and effective accessibility states.
- Provide reproducible, machine-auditable compliance assessments for large-scale domain ecosystems.

---

# Technologies Used

- Python 3.x
- Requests
- BeautifulSoup4
- Pandas
- Matplotlib
- RFC 9309 Parsing Logic
- Incremental Web Crawling Pipelines

---

# License

This project is intended for academic research, compliance analysis, and cybersecurity auditing purposes.

License information to be added.
