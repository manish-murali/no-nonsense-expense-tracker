from parsers.sbi_savings  import load_statement        as _sbi_savings_load
from parsers.axis_savings import load_statement        as _axis_savings_load
from parsers.sbi_loan     import load_statement        as _sbi_loan_load
from parsers.cbi_loan     import load_statement        as _cbi_loan_load

# Each entry: func returns list[dict] of transactions (savings) or list[dict] (loan)
PARSER_REGISTRY: dict[str, dict] = {
    "sbi_savings":  {"func": _sbi_savings_load,  "account_type": "SAVINGS", "bank": "SBI"},
    "axis_savings": {"func": _axis_savings_load,  "account_type": "SAVINGS", "bank": "AXIS"},
    "sbi_loan":     {"func": _sbi_loan_load,      "account_type": "LOAN",    "bank": "SBI"},
    "cbi_loan":     {"func": _cbi_loan_load,      "account_type": "LOAN",    "bank": "CBI"},
}
