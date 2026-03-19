from datetime import datetime


def build_error_result(site, error_display):
    """
    Build result dictionary for failed fetch.

    Args:
        site (dict): Site information
        error_display (str): Error message

    Returns:
        dict: Structured error result
    """
    return {
        'name': site['name'],
        'url': site['url'],
        'group': site['group'],
        'strategy': 'ERROR',
        'strategy_tier': 'ERROR',
        'error_type': error_display,
        'redirected': False,
        'redirect_target': None,
        'timestamp': datetime.now().isoformat()
    }


def build_success_result(site, classification, redirected, redirect_info):
    """
    Build result dictionary for successful analysis.

    Args:
        site (dict): Site information
        classification (str): Classified defense strategy
        redirected (bool): Whether redirect occurred
        redirect_info (str): Redirect target or None

    Returns:
        dict: Structured success result
    """
    return {
        'name': site['name'],
        'url': site['url'],
        'group': site['group'],
        'classification': classification,
        'classification_tier': classification.split(':')[0].strip(),  # Extract "Tier X"
        'redirected': redirected,
        'redirect_target': redirect_info if redirected else None,
        'timestamp': datetime.now().isoformat()
    }
