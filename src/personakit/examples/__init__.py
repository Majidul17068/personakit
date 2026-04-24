"""Bundled reference specialists across multiple domains.

Each one is a realistic, production-shaped Specialist. Import them directly to
use in your own apps, or read the source as a template for authoring your own.

| Specialist                      | Domain                        |
| ------------------------------- | ----------------------------- |
| `CODE_REVIEWER`                 | engineering.software.review   |
| `CONTRACT_REVIEWER`             | legal.contracts.m_and_a       |
| `CUSTOMER_SUPPORT_TRIAGE`       | support.saas.b2c              |
| `FALLS_PREVENTION_NURSE`        | healthcare.clinical.falls     |
| `FINTECH_TRANSACTION_REVIEWER`  | finance.fintech.aml           |
| `MATH_TUTOR`                    | education.secondary           |
| `SCRUM_MASTER`                  | engineering.delivery.agile    |

Use `SpecialistRegistry()` to load many at once, filter by `.by_domain(...)`, and
route incoming cases to the right specialist.
"""

from __future__ import annotations

from .code_reviewer import CODE_REVIEWER
from .contract_reviewer import CONTRACT_REVIEWER
from .falls_nurse import FALLS_PREVENTION_NURSE
from .fintech_reviewer import FINTECH_TRANSACTION_REVIEWER
from .math_tutor import MATH_TUTOR
from .scrum_master import SCRUM_MASTER
from .support_triage import SUPPORT_TRIAGE as CUSTOMER_SUPPORT_TRIAGE

__all__ = [
    "CODE_REVIEWER",
    "CONTRACT_REVIEWER",
    "CUSTOMER_SUPPORT_TRIAGE",
    "FALLS_PREVENTION_NURSE",
    "FINTECH_TRANSACTION_REVIEWER",
    "MATH_TUTOR",
    "SCRUM_MASTER",
]
