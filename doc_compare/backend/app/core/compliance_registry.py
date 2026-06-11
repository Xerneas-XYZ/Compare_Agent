"""
Compliance Agency Registry
Maps (country, industry) → list of regulatory bodies + key regulation refs.
Single source of truth used by both backend analysis and frontend filters.
"""

COMPLIANCE_REGISTRY = {
    # ── USA ──────────────────────────────────────────────────────────────────
    ("usa", "banking"): {
        "agencies": ["Federal Reserve", "OCC", "FDIC", "CFPB", "FinCEN"],
        "key_regs": ["Dodd-Frank Act", "BSA/AML", "CRA", "GLBA", "Basel III"],
    },
    ("usa", "insurance"): {
        "agencies": ["NAIC", "State DOIs", "FHFA", "FIO"],
        "key_regs": ["ACA", "ERISA", "McCarran-Ferguson Act", "Solvency II (equiv)"],
    },
    ("usa", "healthcare"): {
        "agencies": ["CMS", "FDA", "OIG", "HHS", "OCR"],
        "key_regs": ["HIPAA", "HITECH", "ACA", "21st Century Cures Act"],
    },
    # ── UK ───────────────────────────────────────────────────────────────────
    ("uk", "banking"): {
        "agencies": ["PRA", "FCA", "Bank of England", "PSR"],
        "key_regs": ["FSMA 2000", "Basel III/IV", "SMCR", "PSD2", "UK GDPR"],
    },
    ("uk", "insurance"): {
        "agencies": ["PRA", "FCA", "Lloyd's of London"],
        "key_regs": ["Solvency II", "IDD", "Consumer Duty", "UK GDPR"],
    },
    ("uk", "healthcare"): {
        "agencies": ["CQC", "MHRA", "NHS England", "ICO"],
        "key_regs": ["Health & Social Care Act 2012", "UK GDPR", "MDR 2002"],
    },
    # ── India ─────────────────────────────────────────────────────────────────
    ("india", "banking"): {
        "agencies": ["RBI", "SEBI", "IRDAI", "FIU-IND"],
        "key_regs": ["Banking Regulation Act", "FEMA", "PMLA", "Basel III"],
    },
    ("india", "insurance"): {
        "agencies": ["IRDAI"],
        "key_regs": ["Insurance Act 1938", "IRDAI Regulations", "PMLA"],
    },
    ("india", "healthcare"): {
        "agencies": ["CDSCO", "NMC", "MoHFW", "NABH"],
        "key_regs": ["Drugs & Cosmetics Act", "Clinical Establishments Act", "DPDP Act 2023"],
    },
    # ── China ─────────────────────────────────────────────────────────────────
    ("china", "banking"): {
        "agencies": ["PBOC", "CBIRC", "CSRC", "SAFE"],
        "key_regs": ["Commercial Banking Law", "PBOC Law", "Data Security Law", "PIPL"],
    },
    ("china", "insurance"): {
        "agencies": ["CBIRC"],
        "key_regs": ["Insurance Law of PRC", "CBIRC Circulars", "PIPL"],
    },
    ("china", "healthcare"): {
        "agencies": ["NMPA", "NHC", "NHSA"],
        "key_regs": ["Drug Administration Law", "Medical Device Regulations", "PIPL"],
    },
    # ── Russia ────────────────────────────────────────────────────────────────
    ("russia", "banking"): {
        "agencies": ["Bank of Russia (CBR)"],
        "key_regs": ["Federal Law on Banks", "AML/CFT Law 115-FZ", "Federal Law 86-FZ"],
    },
    ("russia", "insurance"): {
        "agencies": ["Bank of Russia (CBR)"],
        "key_regs": ["Law on Insurance Business", "OSAGO Law", "CBR Regulations"],
    },
    ("russia", "healthcare"): {
        "agencies": ["Roszdravnadzor", "Rospotrebnadzor"],
        "key_regs": ["Federal Law 323-FZ", "Personal Data Law 152-FZ"],
    },
    # ── Germany ───────────────────────────────────────────────────────────────
    ("germany", "banking"): {
        "agencies": ["BaFin", "Bundesbank", "ECB (SSM)", "EBA"],
        "key_regs": ["KWG", "MiFID II", "Basel III/IV", "GDPR", "DORA"],
    },
    ("germany", "insurance"): {
        "agencies": ["BaFin"],
        "key_regs": ["VAG", "Solvency II", "IDD", "GDPR"],
    },
    ("germany", "healthcare"): {
        "agencies": ["BfArM", "Paul-Ehrlich-Institut", "GKV-SV"],
        "key_regs": ["SGB V", "GDPR", "MDR 2017/745", "DIGA Regulation"],
    },
}


def get_agencies(country: str, industry: str) -> dict:
    """Return agency/regulation data for a given country+industry pair."""
    key = (country.lower(), industry.lower())
    return COMPLIANCE_REGISTRY.get(key, {"agencies": [], "key_regs": []})


def get_all_agencies_flat(country: str) -> list:
    """Return all agencies for a country across all industries."""
    agencies = []
    for industry in ["banking", "insurance", "healthcare"]:
        data = get_agencies(country, industry)
        agencies.extend(data["agencies"])
    return list(dict.fromkeys(agencies))  # dedupe while preserving order


ROLE_PERMISSIONS = {
    "compliance_officer": {
        "can_see_pii": False,
        "can_export": True,
        "analysis_depth": "full",
        "show_risk_scores": True,
    },
    "legal_consultant": {
        "can_see_pii": False,
        "can_export": True,
        "analysis_depth": "full",
        "show_risk_scores": True,
    },
    "general_user": {
        "can_see_pii": False,
        "can_export": False,
        "analysis_depth": "summary",
        "show_risk_scores": False,
    },
}