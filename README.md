# Cyber Synthetic Data Generation

A modular Python toolkit for generating and validating synthetic cybersecurity datasets across different operational environments: enterprise, cloud, and education/data/technology/communications (EDTC). This project provides a complete pipeline from problem definition to large-scale synthetic data generation with comprehensive validation.

## 🎯 Project Overview

CyberData walks you through a systematic approach to synthetic cybersecurity data generation:

1. **Define cybersecurity problems** by operational environment
2. **Create small, hand‑crafted seed datasets** with technical details
3. **Validate seed datasets** with LLM-based quality checks
4. **Generate large synthetic datasets** using LLM-based expansion
5. **Validate synthetic datasets** with statistical and quality metrics
6. **Create confidence levels** for generated datasets

## 📂 Project Structure

```
cyberdata/
├── src/cyberdata/
│   ├── scripts/                     # Core pipeline scripts
│   │   ├── problems.py              # Generate cybersecurity problems
│   │   ├── extend_problems.py       # Evaluate & enhance taxonomy
│   │   ├── small_dataset.py         # Create seed examples with technical data
│   │   ├── generator.py             # Generate large synthetic datasets
│   │   ├── validate_small.py        # Validate seed examples
│   │   └── validate_large.py        # Quality assessment of large datasets
│   └── utils/                       # Utility modules
│       ├── llm_invoke.py            # LLM API interface
│       ├── logger_config.py         # Logging configuration
│       ├── prompt_loader.py         # YAML prompt management
│       └── config_manager.py        # Centralized configuration management
├── config/                          # Configuration files (moved from src/)
│   ├── problems_init.json           # Initial problem definitions
│   ├── problems.json                # LLM-generated problems
│   ├── problems_updated.json        # Enhanced with taxonomy & new threats
│   ├── problems_evaluation_report.json  # Evaluation analysis
│   ├── acronyms.json                # Domain-specific acronyms
│   └── prompts/                     # YAML prompt templates
│       ├── problems_prompts.yaml
│       ├── extension_prompts.yaml
│       ├── seed_generation_prompts.yaml
│       ├── large_generation_prompts.yaml
│       └── validation_prompts.yaml
├── data/                            # Generated datasets
│   ├── seeds/                       # Seed examples by area
│   ├── large_samples/               # Large synthetic datasets
│   ├── validation_reports/          # Validation results
│   └── quality_reports/             # Quality assessment reports
├── logs/                            # Execution logs
└── pyproject.toml                   # Project dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12.2+
- OpenAI API key
- Poetry for dependency management

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd cyberdata
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Set up environment:**
   ```bash
   # Create .env file with your OpenAI API key
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   ```

### Basic Usage

**Run the complete pipeline:**
```bash
# Navigate to process directory
cd src/cyberdata/process

# 1. Generate initial problems (optional - problems.json included)
python problems.py

# 2. Evaluate and enhance taxonomy
python extend_problems.py

# 3. Create seed examples with technical details
python small_dataset.py

# 4. Validate seed examples
python validate_small.py

# 5. Generate large synthetic datasets
python generator.py --count 50

# 6. Validate large datasets
python validate_large.py
```

### Enhanced Schema

Each problem includes:
- **area**: High-level category (Social Engineering, Network Attacks, etc.)
- **category**: Specific attack type (Phishing, Man-in-the-Middle, etc.)
- **variant**: Attack subtype (Spear Phishing, SSL Stripping, etc.)
- **attack_vector**: Primary attack method (Email, Network, Cloud API, etc.)
- **asset_targeted**: Target resource type (User Credentials, Network Infrastructure, etc.)
- **kill_chain_phase**: MITRE ATT&CK tactic (Initial Access, Execution, etc.)
- **impact_level**: Severity assessment (Low, Medium, High, Critical)
- **detection_methods**: Recommended detection approaches

## 🔧 Configuration

### Environment Variables
```bash
OPENAI_API_KEY=your_openai_api_key
```

### Model Configuration
- **Default Model**: GPT-4.1-mini
- **Temperature**: 0.7 (generation), 0.0 (validation)
- **Max Tokens**: 16,384


## 🔍 Quality Assurance

The toolkit implements multi-layered quality assurance:

1. **Schema Validation**: Ensures consistent data structure
2. **LLM-based Quality Assessment**: Evaluates realism and technical accuracy
3. **Statistical Analysis**: Measures uniqueness and distribution
4. **Domain Expert Review**: Built-in cybersecurity expertise in prompts
5. **Comprehensive Logging**: Tracks all generation and validation steps


### Adding New Threat Types

1. **Update taxonomy** in `problems_init.json`
2. **Enhance prompts** in relevant scripts for domain-specific knowledge
3. **Add validation rules** for new data structures
4. **Update README** with new threat category documentation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📫 Contact
knowledgeivy01@gmail.com