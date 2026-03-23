"""
result_builder.py — Result Schema Factory

Single source of truth for result dict structure.
No logic — pure data transformation.
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# SCHEMA — all CSV columns in order


RESULT_COLUMNS = [
    # Identity
    "name", "url", "country", "group",
    # Classification (RQ1)
    "strategy", "strategy_tier", "tier_label", "tier_description",
    # Redirect
    "redirected", "redirect_target",
    # Conflicts (RQ2)
    "conflict_count", "has_conflicts", "conflict_types", "conflict_summary",
    # Compliance (RQ3)
    "compliance_status", "compliance_score", "gap_identified",
    "intended_optout", "effective_optout", "conflict_impact", "eu_ai_act_ref",
    # Meta
    "timestamp", "error_type",
]

# BUILDERS


def build_error_result(site, error_code):
    return {
        'name':             site['name'],
        'url':              site['url'],
        'country':          site.get('country', '??'),
        'group':            site['group'],
        'strategy':         'ERROR',
        'strategy_tier':    'ERROR',
        'tier_label':       None,
        'tier_description': None,
        'redirected':       False,
        'redirect_target':  None,
        'conflict_count':   None,
        'has_conflicts':    None,
        'conflict_types':   None,
        'conflict_summary': None,
        'compliance_status':  None,
        'compliance_score':   None,
        'gap_identified':     None,
        'intended_optout':    None,
        'effective_optout':   None,
        'conflict_impact':    None,
        'eu_ai_act_ref':      None,
        'timestamp':        datetime.now().isoformat(),
        'error_type':       error_code,
        'compliance':       {},
        'signals':          {},
    }


def build_success_result(site, classification, conflict, compliance,
                         redirected, redirect_info, raw_content="", line_map=None):
    return {
        'name':             site['name'],
        'url':              site['url'],
        'country':          site.get('country', '??'),
        'group':            site['group'],
        'strategy':         classification['display'],
        'strategy_tier':    classification['tier'],
        'tier_label':       classification['label'],
        'tier_description': classification['description'],
        'redirected':       redirected,
        'redirect_target':  redirect_info if redirected else None,
        'conflict_count':   conflict.get('conflict_count', 0),
        'has_conflicts':    conflict.get('has_conflicts', False),
        'conflict_types':   conflict.get('conflict_types', []),
        'conflict_summary': conflict.get('summary', ''),
        'compliance_status':  compliance.get('status'),
        'compliance_score':   compliance.get('score'),
        'gap_identified':     compliance.get('gap_identified'),
        'intended_optout':    compliance.get('intended_optout'),
        'effective_optout':   compliance.get('effective_optout'),
        'conflict_impact':    compliance.get('conflict_impact'),
        'eu_ai_act_ref':      compliance.get('eu_ai_act_ref'),
        'raw_content':      raw_content,
        'line_map':    line_map or {},
        'timestamp':        datetime.now().isoformat(),
        'error_type':       None,
        'compliance':       compliance,
        'signals':          classification.get('signals', {}),
    }
