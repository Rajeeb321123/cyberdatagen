# Cyber Synthetic Data Generation

A modular Python toolkit for generating and validating synthetic cybersecurity datasets across different operational environments: Enterprise, Cloud, and EDTC (Educational Technology). This project guides you through:

1. Defining cybersecurity problems by environment
2. Creating small, hand‑crafted seed datasets
3. Validating seed datasets with LLM-based assessment
4. Generating large synthetic datasets using LLMs
5. Validating synthetic datasets with quality evaluation metrics
6. Creating confidence levels for generated datasets

## 📋 Core Features

- **Environment-specific problems**: Enterprise, Cloud, and EDTC security scenarios
- **LLM-powered generation**: Leverages OpenAI models for high-quality synthetic data
- **Comprehensive validation**: Both seed and synthetic datasets undergo thorough validation
- **Modular architecture**: Components can be used independently or in sequence
- **CSV and JSON export**: All datasets available in multiple formats

## To-do
- add log support
- load prompt from file


## 📂 Project Structure

```bash
./
├── README.md               # Project overview
├── pyproject.toml          # Project dependencies (Poetry)
├── src/
│   └── cyberdata/          # Main package
│       ├── __init__.py
│       ├── config/
│       │   └── problems_init.json  # Initial problem definitions
│       ├── process/
│       │   ├── problems.py         # Step 1: Define problems
│       │   ├── small_dataset.py    # Step 2: Seed dataset generation
│       │   ├── validate_small.py   # Step 3: Seed validation
│       │   ├── generator.py        # Step 4: Synthetic data generation
│       │   ├── validate_large.py   # Step 5: Synthetic data validation
│       │   └── json_to_csv.py      # CSV converter utility
│       └── utils/
│           ├── llm_invoke.py       # LLM integration utilities
│           └── logger_config.py    # Logging configuration
└── data/
    ├── seeds/               # Small seed datasets
    │   ├── Enterprise/      # Enterprise-specific data
    │   │   ├── json/        # JSON format
    │   │   └── csv/         # CSV format
    │   ├── Cloud/           # Cloud-specific data
    │   └── EDTC/            # EDTC-specific data
    ├── large_samples/       # Large synthetic datasets
    ├── validation_reports/  # Validation results for seeds
    └── quality_reports/     # Quality metrics for synthetic data
```

## ⚙️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cyber_synth_data.git
   cd cyber_synth_data
   ```

2. Set up with Poetry (recommended):
   ```bash
   poetry install
   ```

3. Set up your OpenAI API key:
   ```bash
   # Create a .env file in the project root
   echo "OPENAI_API_KEY=your-api-key-here" > .env
   ```

## 🔄 Workflow

The toolkit follows a six-step process:

1. **Problem Definition**: Generate or update cybersecurity problem definitions
   ```bash
   python -m cyberdata.process.problems
   ```

2. **Seed Generation**: Create small example datasets for each problem
   ```bash
   python -m cyberdata.process.small_dataset
   ```

3. **Seed Validation**: Validate the quality of seed examples
   ```bash
   python -m cyberdata.process.validate_small
   ```

4. **Large Dataset Generation**: Generate comprehensive synthetic datasets
   ```bash
   python -m cyberdata.process.generator
   ```

5. **Synthetic Data Validation**: Evaluate the quality of generated data
   ```bash
   python -m cyberdata.process.validate_large
   ```

6. **Format Conversion**: Convert JSON datasets to CSV format
   ```bash
   python -m cyberdata.process.json_to_csv
   ```

## 🧠 Models Used

This toolkit leverages LLM models for data generation and validation:
- Default model: `gpt-4.1-mini`
- Configurable via the `MODEL_NAME` parameter in relevant modules

## 📊 Dataset Examples

The system generates data for various cybersecurity scenarios, including:

### Enterprise
- Phishing attacks
- Insider data exfiltration
- Privilege escalation

### Cloud
- Misconfigured storage
- API key leakage
- Container escape vulnerabilities

### EDTC (Educational Technology)
- Insecure LMS login
- Student data privacy issues
- Unpatched educational software

## 📜 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
