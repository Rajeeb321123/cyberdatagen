# Cyber Synthetic Data Generation

A modular Python toolkit for generating and validating synthetic cybersecurity datasets across different operational environments: enterprise, cloud, and personal. This project walks you through:

1. Defining cybersecurity problems by environment.
2. Creating small, hand‑crafted seed datasets.
3. Validating seed datasets with a simple ML check.
4. Generating large synthetic datasets using LLM or CTGAN.
5. Validating the synthetic datasets with statistical tests.
6. Create the confidence level for the generate datasets
---

## 📂 Project Structure

```bash
cyber_synth_data/
├── README.md               # This file
├── requirements.txt        # Project dependencies
├── setup.py                # Package installation script
├── cyber_synth_data/       # Main package
│   ├── __init__.py
│   ├── problems.py         # Step 1: Define problems
│   ├── small_dataset.py    # Step 2: Seed dataset generation
│   ├── validate_small.py   # Step 3: Seed validation
│   ├── generator.py        # Step 4: Synthetic data generation
│   ├── validate_large.py   # Step 5: Synthetic data validation
│   └── utils.py            # Shared helpers
└── examples/
    └── run_all.py          # Example script tying all steps together
```

---

## ⚙️ Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/your-org/cyber_synth_data.git
   cd cyber_synth_data
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

> **Requirements**:
> - Python 3.8+
> - pandas
> - scikit-learn
> - sdv (for CTGAN)
> - scipy

---

## ▶️ Usage

Run the end-to-end example to see all steps in action:
```bash
python examples/run_all.py
```

You can also import and use individual modules:

```python
from cyber_synth_data.problems import get_problems_by_env
from cyber_synth_data.small_dataset import make_seed_dataset
from cyber_synth_data.validate_small import validate_seed
from cyber_synth_data.generator import synthesize
from cyber_synth_data.validate_large import compare_distributions

# Define problems
env_problems = get_problems_by_env()
# Create seed data
seed_df = make_seed_dataset("Phishing email detection", "enterprise")
# Validate seed
acc = validate_seed(seed_df)
# Generate synthetic data
synth_df = synthesize(seed_df, n_samples=500)
# Validate synthetic
ks_results = compare_distributions(seed_df, synth_df)
print("KS test p-values:", ks_results)
```

---

## 📄 Modules Overview

- **problems.py**: Lists representative cybersecurity problems per environment.
- **small_dataset.py**: Hand‑craft small seed datasets for each problem.
- **validate_small.py**: Quick ML validation (cross‑val) to ensure seed data is learnable.
- **generator.py**: Uses CTGAN to fit and sample large synthetic datasets.
- **validate_large.py**: Compares distributions (e.g., KS test) between seed and synthetic data.
- **utils.py**: Utility functions (e.g., data loaders, common preprocessing).
- **examples/run_all.py**: Example driver script.

---

## ✍️ Contributing

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add awesome feature"
   ```
4. Push to the branch:
   ```bash
   git push origin feature/your-feature
   ```
5. Open a Pull Request.

Please follow the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide.

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
