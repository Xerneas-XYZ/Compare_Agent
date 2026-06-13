COMPLIANCE_REGISTRY = {
    ("usa", "banking"): {"agencies": ["Federal Reserve", "OCC", "FDIC", "CFPB"], "key_regs": ["Dodd-Frank", "BSA/AML", "GLBA", "Basel III"]},
    ("usa", "insurance"): {"agencies": ["NAIC", "State DOIs", "FIO"], "key_regs": ["ACA", "ERISA"]},
    ("usa", "healthcare"): {"agencies": ["CMS", "FDA", "OCR"], "key_regs": ["HIPAA", "HITECH", "ACA"]},
    ("uk", "banking"): {"agencies": ["PRA", "FCA", "Bank of England"], "key_regs": ["FSMA 2000", "SMCR", "PSD2"]},
    ("uk", "insurance"): {"agencies": ["PRA", "FCA"], "key_regs": ["Solvency II", "Consumer Duty"]},
    ("uk", "healthcare"): {"agencies": ["CQC", "MHRA", "NHS England"], "key_regs": ["Health & Social Care Act 2012"]},
    ("india", "banking"): {"agencies": ["RBI", "SEBI", "FIU-IND"], "key_regs": ["Banking Regulation Act", "FEMA", "PMLA"]},
    ("india", "insurance"): {"agencies": ["IRDAI"], "key_regs": ["Insurance Act 1938", "PMLA"]},
    ("india", "healthcare"): {"agencies": ["CDSCO", "NMC", "NABH"], "key_regs": ["Drugs & Cosmetics Act", "DPDP Act 2023"]},
}

def get_agencies(country: str, industry: str) -> dict:
    return COMPLIANCE_REGISTRY.get((country.lower(), industry.lower()), {"agencies": [], "key_regs": []})

ROLE_PERMISSIONS = {
    "compliance_officer": {"can_see_pii": False, "can_export": True, "analysis_depth": "full", "show_risk_scores": True},
    "legal_consultant": {"can_see_pii": False, "can_export": True, "analysis_depth": "full", "show_risk_scores": True},
    "general_user": {"can_see_pii": False, "can_export": False, "analysis_depth": "summary", "show_risk_scores": False},
}
