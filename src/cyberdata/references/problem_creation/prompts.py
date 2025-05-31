extension_prompt = """

{
  "problems": [
    {
      "area": "Phishing Attack",
      "nature": "credential_harvesting",
      "description": "Attackers send deceptive emails impersonating trusted entities to trick users into submitting their login credentials on fake websites.",
      "risk_reduction": [
        "Implement multi-factor authentication (MFA) to reduce impact of stolen credentials",
        "Deploy advanced email filtering and anti-phishing tools",
        "Conduct regular user awareness training and simulated phishing campaigns"
      ]
    },
    {
      "area": "Phishing Attack",
      "nature": "spear_phishing",
      "description": "Highly targeted phishing emails crafted using personal information to deceive specific individuals, often executives, into revealing sensitive data or authorizing fraudulent transactions.",
      "risk_reduction": [
        "Use threat intelligence to identify and block targeted phishing attempts",
        "Train high-risk users on recognizing spear phishing tactics",
        "Enforce strict verification procedures for sensitive requests"
      ]
    },
    {
      "area": "Phishing Attack",
      "nature": "malicious_attachments",
      "description": "Phishing emails contain attachments with malware payloads that execute upon opening, compromising the victim’s system.",
      "risk_reduction": [
        "Implement sandboxing and antivirus scanning of email attachments",
        "Restrict execution of macros and scripts in attachments",
        "Educate users to avoid opening unexpected or suspicious files"
      ]
    },
    {
      "area": "Man-in-the-Middle (MITM) Attack",
      "nature": "wifi_eavesdropping",
      "description": "Attackers intercept communications on unsecured or poorly secured Wi-Fi networks to capture sensitive data such as passwords and session tokens.",
      "risk_reduction": [
        "Use strong WPA3 encryption on wireless networks",
        "Encourage use of VPNs when accessing public Wi-Fi",
        "Disable automatic connection to open Wi-Fi networks"
      ]
    },
    {
      "area": "Man-in-the-Middle (MITM) Attack",
      "nature": "ssl_stripping",
      "description": "Attackers downgrade HTTPS connections to HTTP by intercepting and modifying traffic, exposing sensitive data transmitted in plaintext.",
      "risk_reduction": [
        "Enforce HTTPS with HSTS (HTTP Strict Transport Security)",
        "Use certificate pinning in applications",
        "Regularly monitor and audit SSL/TLS configurations"
      ]
    },
    {
      "area": "Man-in-the-Middle (MITM) Attack",
      "nature": "dns_spoofing",
      "description": "Attackers manipulate DNS responses to redirect users to malicious sites without their knowledge, enabling credential theft or malware delivery.",
      "risk_reduction": [
        "Deploy DNSSEC to validate DNS responses",
        "Use trusted DNS resolvers with filtering capabilities",
        "Monitor DNS traffic for anomalies and unauthorized changes"
      ]
    },

    // ---------------- Additional Domains to Be Filled ----------------
    {
      "area": "Malware & Ransomware",
      "nature": "ransomware_encryption",
      "description": "Malicious software encrypts the victim's data and demands payment for the decryption key.",
      "risk_reduction": [
        "Maintain regular offline backups",
        "Use endpoint detection and response (EDR) tools",
        "Patch vulnerable software promptly"
      ]
    },
    {
      "area": "Web Application Attack",
      "nature": "sql_injection",
      "description": "Attackers inject malicious SQL queries into input fields to manipulate or access database content.",
      "risk_reduction": [
        "Use parameterized queries and ORM frameworks",
        "Implement web application firewalls (WAF)",
        "Regularly test for injection flaws"
      ]
    },
    {
      "area": "Insider Threat",
      "nature": "privilege_abuse",
      "description": "Employees or contractors misuse their access rights to steal, leak, or sabotage data or systems.",
      "risk_reduction": [
        "Enforce least privilege principles",
        "Implement user activity monitoring",
        "Conduct periodic access reviews"
      ]
    },
    {
      "area": "Denial of Service (DoS)",
      "nature": "volumetric_attack",
      "description": "Attackers flood a service or network with massive traffic, rendering it unavailable to legitimate users.",
      "risk_reduction": [
        "Use DDoS mitigation services",
        "Implement rate limiting and traffic filtering",
        "Monitor traffic patterns for anomalies"
      ]
    },
    {
      "area": "Cloud Misconfiguration",
      "nature": "public_s3_bucket",
      "description": "Cloud storage buckets are left publicly accessible, exposing sensitive data to unauthorized users.",
      "risk_reduction": [
        "Use automated tools to detect misconfigurations",
        "Apply least privilege access control to cloud resources",
        "Enable cloud provider logging and auditing"
      ]
    }
  ]
}

"""


verfication_prompt = """

I have a structured JSON list of cybersecurity problems. Each entry includes:

- `area`: High-level category of the threat (e.g., Phishing Attack)
- `nature`: Specific subtype (e.g., spear_phishing)
- `description`: Explanation of the threat
- `risk_reduction`: Recommended mitigations

Please evaluate the list along the following dimensions:

1. **Categorization Structure**:
   - Is the use of `area` and `nature` fields effective and scalable?
   - Would a hierarchical taxonomy (e.g., `area > category > variant`) improve clarity?
   - Should any standard taxonomy (MITRE ATT&CK, NIST, VERIS, etc.) be used for alignment?

2. **Opportunities for Merging or Reclassification**:
   - Identify any entries that could be logically merged under a broader umbrella category (e.g., consolidate phishing subtypes).
   - Suggest a more unified or normalized structure if applicable.

3. **Coverage of Emerging and Important Threats**:
   - Identify if the list is missing any **recent or rising cyberattacks** (2023–2025).
   - Recommend at least **5 newly relevant or high-impact threats**, including their categories and brief descriptions.
   - Include areas such as AI-generated attacks, supply chain risks, cloud misconfigurations, or adversarial ML attacks.

4. **Optional Enhancement Suggestions**:
   - Suggest adding new fields (e.g., `attack_vector`, `asset_targeted`, `kill_chain_phase`, `impact_level`) to make the dataset more useful for incident classification or training datasets.

Here is the JSON list for evaluation:
[INSERT YOUR JSON HERE]

"""
