from . import constants as C


def _bounds(parameter: str) -> tuple[float, float]:
    """(suspect_max, plausible_max) selon le parametre."""
    if parameter == C.PARAM_LIMNI:
        return C.SUSPECT_MAX_CM, C.PLAUSIBLE_MAX_CM
    return C.SUSPECT_MAX_MM, C.PLAUSIBLE_MAX_MM


def quality_flag(value: float | None, parameter: str) -> str:
    if value is None:
        return C.FLAG_MANQUANT
    suspect_max, plausible_max = _bounds(parameter)
    if value < 0 or value > plausible_max:
        return C.FLAG_ABERRANT
    if value > suspect_max:
        return C.FLAG_SUSPECT
    return C.FLAG_OK
