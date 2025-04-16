import json
from pathlib import Path
import pandas as pd


def load_problems(file_path: str = './config/problems.json') -> list:
    """
    Load the list of cybersecurity problems from a JSON file.
    Returns a list of problem dictionaries.
    """
    config_path = Path(file_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Problems config not found at {file_path}")
    data = json.loads(config_path.read_text(encoding='utf-8'))
    return data.get('problems', [])


def generate_seed_dataset(problem: dict) -> pd.DataFrame:
    """
    Generate a small, hand‑crafted seed dataset for a given problem entry.
    The dataset structure varies based on the problem nature.
    """
    nature = problem.get('nature')
    area = problem.get('area')

    # Sample records for each problem nature
    if nature == 'phishing':
        records = [
            {"sender_domain": "trusted.com", "num_links": 0, "has_attachment": False, "label": 0},
            {"sender_domain": "evil.co",     "num_links": 3, "has_attachment": True,  "label": 1},
            {"sender_domain": "enterprise.local","num_links": 1, "has_attachment": False, "label": 0},
        ]
    elif nature == 'insider_data_exfiltration':
        records = [
            {"user_id": "u001", "file_type": "pdf", "copied_bytes": 0,    "label": 0},
            {"user_id": "u002", "file_type": "csv", "copied_bytes": 1024, "label": 1},
            {"user_id": "u003", "file_type": "docx","copied_bytes": 512,  "label": 0},
        ]
    elif nature == 'privilege_escalation':
        records = [
            {"vuln_id": "CVE-2021-1234", "initial_role": "user", "escalated": True,  "label": 1},
            {"vuln_id": "CVE-2022-5678", "initial_role": "admin","escalated": False, "label": 0},
            {"vuln_id": "CVE-2020-0001", "initial_role": "user", "escalated": False, "label": 0},
        ]
    elif nature == 'misconfigured_storage':
        records = [
            {"bucket_name": "public-data",       "is_public": True,  "label": 1},
            {"bucket_name": "company-backup",    "is_public": False, "label": 0},
            {"bucket_name": "research-archive", "is_public": False, "label": 0},
        ]
    elif nature == 'api_key_leakage':
        records = [
            {"repository": "public/repo1", "key_found": True,  "label": 1},
            {"repository": "internal/repo2","key_found": False, "label": 0},
            {"repository": "dev/repo3",     "key_found": True,  "label": 1},
        ]
    elif nature == 'container_escape':
        records = [
            {"image_name": "vuln-image:v1",  "privileged_mode": True,  "label": 1},
            {"image_name": "safe-image:v2",  "privileged_mode": False, "label": 0},
            {"image_name": "test-image:v3",  "privileged_mode": False, "label": 0},
        ]
    elif nature == 'insecure_lms_login':
        records = [
            {"protocol": "HTTP",  "used_mfa": False, "login_success": True,  "label": 1},
            {"protocol": "HTTPS", "used_mfa": True,  "login_success": True,  "label": 0},
            {"protocol": "HTTP",  "used_mfa": False, "login_success": False, "label": 1},
        ]
    elif nature == 'student_data_privacy':
        records = [
            {"role": "staff",      "access_type": "export", "record_count": 1000, "label": 1},
            {"role": "teacher",    "access_type": "view",   "record_count": 10,   "label": 0},
            {"role": "administrator","access_type": "export","record_count": 0,  "label": 0},
        ]
    elif nature == 'unpatched_edu_software':
        records = [
            {"system": "lab-pc-01",   "patched": False, "known_vulns": 5, "label": 1},
            {"system": "lab-pc-02",   "patched": True,  "known_vulns": 0, "label": 0},
            {"system": "classroom-pc", "patched": False, "known_vulns": 1, "label": 1},
        ]
    else:
        # Unsupported nature
        records = []

    df = pd.DataFrame(records)
    if not df.empty:
        df['area'] = area
        df['nature'] = nature
    return df


def generate_all_seeds(output_dir: str = './data/seeds'):
    """
    Iterate through all problems, generate seed datasets, and save each as a CSV.
    """
    problems = load_problems()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for problem in problems:
        df = generate_seed_dataset(problem)
        if df.empty:
            print(f"Skipping unsupported nature: {problem.get('nature')}")
            continue
        filename = f"{problem.get('area').lower()}_{problem.get('nature')}_seed.csv"
        path = out_dir / filename
        df.to_csv(path, index=False)
        print(f"Saved seed dataset for {problem.get('nature')} to {path}")


if __name__ == '__main__':
    generate_all_seeds()
