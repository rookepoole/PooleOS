"""Typed PooleQ/P feature, probability, and spectrometry reference runtime."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Mapping, Sequence


CONTRACT_VERSION = "PDC-QP-0.1"
FEATURE_TYPE_TAG = "PDC.QP.Feature.v0.1"
PROBABILITY_TYPE_TAG = "PDC.QP.Probability.v0.1"
FOOTPRINT_TYPE_TAG = "PDC.QP.FootprintReadout.v0.1"
COLLAPSED_TYPE_TAG = "PDC.CollapsedState.v0.1"
NEIGHBOR_COUNT = 26
MAX_BRUTE_FORCE_NEIGHBORS = 16
FLOAT_ABS_TOLERANCE = 5e-13
FLOAT_REL_TOLERANCE = 5e-13
NULL_SIGNAL_THRESHOLD = 2.0
DEFAULT_EPSILON = 1e-12
DEFAULT_SOFTENING = 5.0

FEATURE_CHANNEL_ORDER = (
    "B5",
    "B6",
    "B7",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "O10+",
    "psi",
)
RESIDUE_CHANNEL_ORDER = ("B5", "B6", "B7", "S8", "S9")
BIRTH_GEOMETRY_CHANNELS = ("B5", "B6", "B7")
HIGH_SUPPORT_GEOMETRY_CHANNELS = ("S8", "S9", "O10+")
STRAIN_GEOMETRY_CHANNELS = ("psi_abs",)
COMBINED_GEOMETRY_CHANNELS = (
    *BIRTH_GEOMETRY_CHANNELS,
    *HIGH_SUPPORT_GEOMETRY_CHANNELS,
    *STRAIN_GEOMETRY_CHANNELS,
)


class PdcQpError(ValueError):
    """Raised when a Q/P input violates PDC-QP-0.1."""


class PdcQpProbabilityError(PdcQpError):
    """Raised when a probability or probability distribution is invalid."""


class PdcQpFootprintError(PdcQpError):
    """Raised when a defect-footprint input is outside the 3x3 contract."""


class PdcQpNullSignalError(PdcQpError):
    """Raised when a normalized geometry spectrum is requested for a null-like signal."""


def _require_bit(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise PdcQpError(f"{name} must be integer zero or one")
    return value


def _require_support(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= NEIGHBOR_COUNT:
        raise PdcQpError("support must be an integer in [0,26]")
    return value


def _require_probability(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdcQpProbabilityError(f"{name} must be a binary64-compatible real number")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise PdcQpProbabilityError(f"{name} must be finite and in [0,1]")
    return result


def _require_positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdcQpProbabilityError(f"{name} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise PdcQpProbabilityError(f"{name} must be a finite positive number")
    return result


def _require_nonnegative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdcQpProbabilityError(f"{name} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise PdcQpProbabilityError(f"{name} must be a finite nonnegative number")
    return result


def _validated_probabilities(probabilities: Sequence[object], *, exact_count: int | None = None) -> tuple[float, ...]:
    if isinstance(probabilities, (str, bytes, bytearray)):
        raise PdcQpProbabilityError("probabilities must be a sequence of real numbers")
    values = tuple(_require_probability(value, f"probabilities[{index}]") for index, value in enumerate(probabilities))
    if exact_count is not None and len(values) != exact_count:
        raise PdcQpProbabilityError(f"probability vector must contain exactly {exact_count} entries")
    if len(values) > NEIGHBOR_COUNT:
        raise PdcQpProbabilityError("probability vector exceeds the 26-neighbor Q/P limit")
    return values


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=FLOAT_REL_TOLERANCE, abs_tol=FLOAT_ABS_TOLERANCE)


def _validate_distribution(coefficients: Sequence[float], expected_count: int) -> tuple[float, ...]:
    values = tuple(coefficients)
    if len(values) != expected_count + 1:
        raise PdcQpProbabilityError("distribution coefficient count does not match the neighborhood")
    for index, value in enumerate(values):
        if not math.isfinite(value) or value < -FLOAT_ABS_TOLERANCE or value > 1.0 + FLOAT_ABS_TOLERANCE:
            raise PdcQpProbabilityError(f"distribution coefficient {index} is outside the probability range")
    total = math.fsum(values)
    if not _close(total, 1.0):
        raise PdcQpProbabilityError(f"probability distribution is not normalized: {total!r}")
    return values


@dataclass(frozen=True)
class QpFeature:
    state: int
    support: int
    B5: int
    B6: int
    B7: int
    S5: int
    S6: int
    S7: int
    S8: int
    S9: int
    O10plus: int
    psi: int
    collapsed_next_state: int

    def channel_vector(self) -> tuple[int, ...]:
        return (
            self.B5,
            self.B6,
            self.B7,
            self.S5,
            self.S6,
            self.S7,
            self.S8,
            self.S9,
            self.O10plus,
            self.psi,
        )

    def channel_map(self) -> dict[str, int]:
        return dict(zip(FEATURE_CHANNEL_ORDER, self.channel_vector(), strict=True))

    def to_dict(self) -> dict[str, object]:
        return {
            "type_tag": FEATURE_TYPE_TAG,
            "model_tag": "B5-7/S5-9",
            "state": self.state,
            "support": self.support,
            "channels": self.channel_map(),
            "collapsed": {
                "type_tag": COLLAPSED_TYPE_TAG,
                "next_state": self.collapsed_next_state,
                "channel_identity_preserved": False,
            },
        }


def feature(state: int, support: int) -> QpFeature:
    """Return the typed local feature without collapsing birth/survival identity."""

    normalized_state = _require_bit(state, "state")
    normalized_support = _require_support(support)
    births = {count: int(normalized_state == 0 and normalized_support == count) for count in (5, 6, 7)}
    survivals = {
        count: int(normalized_state == 1 and normalized_support == count)
        for count in (5, 6, 7, 8, 9)
    }
    capacity = 7 + 2 * normalized_state
    psi = max(0, normalized_support - capacity) - max(0, 5 - normalized_support)
    collapsed = int(5 <= normalized_support <= capacity)
    return QpFeature(
        state=normalized_state,
        support=normalized_support,
        B5=births[5],
        B6=births[6],
        B7=births[7],
        S5=survivals[5],
        S6=survivals[6],
        S7=survivals[7],
        S8=survivals[8],
        S9=survivals[9],
        O10plus=int(normalized_state == 1 and normalized_support >= 10),
        psi=psi,
        collapsed_next_state=collapsed,
    )


@dataclass(frozen=True)
class FootprintReadout:
    inputs: tuple[int, ...]
    bias_defects: int
    total_defects: int
    active_neighbor_support: int
    B5: int
    B6: int
    B7: int
    raw_birth: int

    def to_dict(self) -> dict[str, object]:
        return {
            "type_tag": FOOTPRINT_TYPE_TAG,
            "model_tag": "B5-7/S5-9.first_update_sheet_footprint",
            "inputs": list(self.inputs),
            "bias_defects": self.bias_defects,
            "total_defects": self.total_defects,
            "active_neighbor_support": self.active_neighbor_support,
            "birth_channels": {"B5": self.B5, "B6": self.B6, "B7": self.B7},
            "collapsed_raw_birth": {
                "type_tag": COLLAPSED_TYPE_TAG,
                "value": self.raw_birth,
                "channel_identity_preserved": False,
            },
        }


def footprint_readout(inputs: Sequence[int], bias_defects: int) -> FootprintReadout:
    if isinstance(inputs, (str, bytes, bytearray)):
        raise PdcQpFootprintError("footprint inputs must be a sequence of bits")
    normalized_inputs = tuple(_require_bit(value, f"inputs[{index}]") for index, value in enumerate(inputs))
    if len(normalized_inputs) > 9:
        raise PdcQpFootprintError("a 3x3 footprint has at most nine defect positions")
    if isinstance(bias_defects, bool) or not isinstance(bias_defects, int):
        raise PdcQpFootprintError("bias_defects must be an integer")
    if not 0 <= bias_defects <= 9 - len(normalized_inputs):
        raise PdcQpFootprintError("input and bias defects must fit in one 3x3 footprint")
    total_defects = bias_defects + sum(normalized_inputs)
    support = 9 - total_defects
    measured = feature(0, support)
    return FootprintReadout(
        inputs=normalized_inputs,
        bias_defects=bias_defects,
        total_defects=total_defects,
        active_neighbor_support=support,
        B5=measured.B5,
        B6=measured.B6,
        B7=measured.B7,
        raw_birth=measured.collapsed_next_state,
    )


def half_adder(inputs: Sequence[int]) -> dict[str, object]:
    if len(inputs) != 2:
        raise PdcQpFootprintError("half-adder requires exactly two input defects")
    readout = footprint_readout(inputs, 1)
    return {
        "type_tag": "PDC.QP.HalfAdderReadout.v0.1",
        "footprint": readout.to_dict(),
        "sum": readout.B7,
        "carry": readout.B6,
        "readout_requires_channel_identity": True,
    }


def full_adder(inputs: Sequence[int]) -> dict[str, object]:
    if len(inputs) != 3:
        raise PdcQpFootprintError("full-adder requires exactly three input defects")
    readout = footprint_readout(inputs, 1)
    return {
        "type_tag": "PDC.QP.FullAdderReadout.v0.1",
        "footprint": readout.to_dict(),
        "sum": int(bool(readout.B7 or readout.B5)),
        "carry": int(bool(readout.B6 or readout.B5)),
        "readout_requires_channel_identity": True,
    }


def poisson_binomial_dp(probabilities: Sequence[object]) -> tuple[float, ...]:
    """Evaluate coefficients with the fixed-order in-place manuscript recurrence."""

    values = _validated_probabilities(probabilities)
    coefficients = [1.0] + [0.0] * len(values)
    for step, probability in enumerate(values):
        complement = 1.0 - probability
        for count in range(step + 1, 0, -1):
            coefficients[count] = coefficients[count] * complement + coefficients[count - 1] * probability
        coefficients[0] *= complement
    return _validate_distribution(coefficients, len(values))


def _convolve(left: Sequence[float], right: Sequence[float]) -> tuple[float, ...]:
    output = [0.0] * (len(left) + len(right) - 1)
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            output[left_index + right_index] += left_value * right_value
    return tuple(output)


def poisson_binomial_polynomial(probabilities: Sequence[object]) -> tuple[float, ...]:
    """Evaluate the generating polynomial through balanced factor convolution."""

    values = _validated_probabilities(probabilities)

    def product(start: int, stop: int) -> tuple[float, ...]:
        if start == stop:
            return (1.0,)
        if stop - start == 1:
            probability = values[start]
            return (1.0 - probability, probability)
        midpoint = start + (stop - start) // 2
        return _convolve(product(start, midpoint), product(midpoint, stop))

    return _validate_distribution(product(0, len(values)), len(values))


def poisson_binomial_bruteforce(probabilities: Sequence[object]) -> tuple[float, ...]:
    """Enumerate all outcomes for small-neighborhood differential checks."""

    values = _validated_probabilities(probabilities)
    if len(values) > MAX_BRUTE_FORCE_NEIGHBORS:
        raise PdcQpProbabilityError(
            f"brute-force verification is limited to {MAX_BRUTE_FORCE_NEIGHBORS} neighbors"
        )
    coefficients = [0.0] * (len(values) + 1)
    for outcome in itertools.product((0, 1), repeat=len(values)):
        probability = 1.0
        for bit, active_probability in zip(outcome, values, strict=True):
            probability *= active_probability if bit else 1.0 - active_probability
        coefficients[sum(outcome)] += probability
    return _validate_distribution(coefficients, len(values))


def coefficient_derivatives(probabilities: Sequence[object]) -> tuple[tuple[float, ...], ...]:
    """Return d Pr[N=k] / d p_j for every neighbor and coefficient."""

    values = _validated_probabilities(probabilities)
    derivatives = []
    for removed_index in range(len(values)):
        excluded = poisson_binomial_dp(values[:removed_index] + values[removed_index + 1 :])
        row = []
        for count in range(len(values) + 1):
            lower = excluded[count - 1] if count > 0 else 0.0
            upper = excluded[count] if count < len(excluded) else 0.0
            row.append(lower - upper)
        derivatives.append(tuple(row))
    return tuple(derivatives)


def activation_probability(coefficients: Sequence[float], center_probability: object) -> float:
    values = _validate_distribution(coefficients, NEIGHBOR_COUNT)
    center = _require_probability(center_probability, "center_probability")
    return math.fsum(values[5:8]) + center * math.fsum(values[8:10])


def expected_feature_probabilities(
    coefficients: Sequence[float], center_probability: object
) -> dict[str, float]:
    values = _validate_distribution(coefficients, NEIGHBOR_COUNT)
    center = _require_probability(center_probability, "center_probability")
    inactive = 1.0 - center
    expected: dict[str, float] = {
        "B5": inactive * values[5],
        "B6": inactive * values[6],
        "B7": inactive * values[7],
        "S5": center * values[5],
        "S6": center * values[6],
        "S7": center * values[7],
        "S8": center * values[8],
        "S9": center * values[9],
        "O10+": center * math.fsum(values[10:]),
    }
    expected["psi"] = math.fsum(
        probability
        * ((1.0 - center) * feature(0, support).psi + center * feature(1, support).psi)
        for support, probability in enumerate(values)
    )
    return expected


@dataclass(frozen=True)
class QpProbabilityResult:
    center_probability: float
    neighbor_probabilities: tuple[float, ...]
    coefficients: tuple[float, ...]
    expected_channels: Mapping[str, float]
    activation_probability: float
    center_derivative: float
    neighbor_derivatives: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "type_tag": PROBABILITY_TYPE_TAG,
            "model_tag": "B5-7/S5-9.independent_bernoulli_product",
            "center_probability": self.center_probability,
            "neighbor_probabilities": list(self.neighbor_probabilities),
            "coefficients": list(self.coefficients),
            "expected_channels": dict(self.expected_channels),
            "activation_probability": self.activation_probability,
            "derivatives": {
                "center": self.center_derivative,
                "neighbors": list(self.neighbor_derivatives),
            },
            "collapsed_state_interpretation_allowed": False,
        }


def probability_layer(center_probability: object, neighbor_probabilities: Sequence[object]) -> QpProbabilityResult:
    center = _require_probability(center_probability, "center_probability")
    neighbors = _validated_probabilities(neighbor_probabilities, exact_count=NEIGHBOR_COUNT)
    coefficients = poisson_binomial_dp(neighbors)
    coefficient_gradient = coefficient_derivatives(neighbors)
    neighbor_gradient = tuple(
        math.fsum(row[5:8]) + center * math.fsum(row[8:10])
        for row in coefficient_gradient
    )
    center_gradient = math.fsum(coefficients[8:10])
    return QpProbabilityResult(
        center_probability=center,
        neighbor_probabilities=neighbors,
        coefficients=coefficients,
        expected_channels=expected_feature_probabilities(coefficients, center),
        activation_probability=activation_probability(coefficients, center),
        center_derivative=center_gradient,
        neighbor_derivatives=neighbor_gradient,
    )


def empirical_site_statistics(
    center_samples: Sequence[int], neighbor_samples: Sequence[Sequence[int]]
) -> dict[str, object]:
    if not center_samples or len(center_samples) != len(neighbor_samples):
        raise PdcQpError("empirical samples must be nonempty and aligned")
    centers = tuple(_require_bit(value, f"center_samples[{index}]") for index, value in enumerate(center_samples))
    neighborhoods = tuple(
        tuple(_require_bit(value, f"neighbor_samples[{sample_index}][{index}]") for index, value in enumerate(sample))
        for sample_index, sample in enumerate(neighbor_samples)
    )
    if any(len(sample) != NEIGHBOR_COUNT for sample in neighborhoods):
        raise PdcQpError("each empirical sample must contain exactly 26 neighbors")
    sample_count = len(centers)
    center_probability = math.fsum(centers) / sample_count
    neighbor_probabilities = tuple(
        math.fsum(sample[index] for sample in neighborhoods) / sample_count
        for index in range(NEIGHBOR_COUNT)
    )
    measured = [feature(center, sum(neighbors)) for center, neighbors in zip(centers, neighborhoods, strict=True)]
    empirical_rates = {
        channel: math.fsum(item.channel_map()[channel] for item in measured) / sample_count
        for channel in FEATURE_CHANNEL_ORDER
    }
    independent = probability_layer(center_probability, neighbor_probabilities)
    empirical_activation = math.fsum(item.collapsed_next_state for item in measured) / sample_count
    residues = {
        channel: empirical_rates[channel] - independent.expected_channels[channel]
        for channel in RESIDUE_CHANNEL_ORDER
    }
    return {
        "sample_count": sample_count,
        "center_probability": center_probability,
        "neighbor_probabilities": list(neighbor_probabilities),
        "empirical_channel_rates": empirical_rates,
        "independent_channel_rates": dict(independent.expected_channels),
        "empirical_activation_rate": empirical_activation,
        "independent_activation_probability": independent.activation_probability,
        "activation_residue": empirical_activation - independent.activation_probability,
        "channel_residue": residues,
        "coherence_contribution": math.fsum(value * value for value in residues.values()),
    }


def poole_coherence(residue_vectors: Sequence[Mapping[str, object]]) -> float:
    total = 0.0
    for site_index, residue in enumerate(residue_vectors):
        values = []
        for channel in RESIDUE_CHANNEL_ORDER:
            if channel not in residue:
                raise PdcQpError(f"residue vector {site_index} is missing {channel}")
            value = residue[channel]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise PdcQpError(f"residue vector {site_index} channel {channel} must be finite")
            values.append(float(value))
        total += math.fsum(value * value for value in values)
    return total


def _rate_value(mapping: Mapping[str, object], channel: str, label: str, *, nonnegative: bool = False) -> float:
    if channel not in mapping:
        raise PdcQpProbabilityError(f"{label} is missing channel {channel}")
    value = mapping[channel]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdcQpProbabilityError(f"{label}[{channel}] must be finite")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        qualifier = "finite and nonnegative" if nonnegative else "finite"
        raise PdcQpProbabilityError(f"{label}[{channel}] must be {qualifier}")
    return result


def robust_score(
    observed_rates: Mapping[str, object],
    null_means: Mapping[str, object],
    null_standard_deviations: Mapping[str, object],
    channels: Sequence[str],
    *,
    epsilon: object = DEFAULT_EPSILON,
    softening: object = DEFAULT_SOFTENING,
) -> float:
    normalized_epsilon = _require_positive(epsilon, "epsilon")
    normalized_softening = _require_positive(softening, "softening")
    channel_tuple = tuple(channels)
    if not channel_tuple or len(set(channel_tuple)) != len(channel_tuple):
        raise PdcQpProbabilityError("robust-score channels must be nonempty and unique")
    unknown = sorted(set(channel_tuple).difference(COMBINED_GEOMETRY_CHANNELS))
    if unknown:
        raise PdcQpProbabilityError(f"unknown geometry channels: {unknown}")
    transformed = []
    for channel in channel_tuple:
        observed = _rate_value(observed_rates, channel, "observed_rates")
        mean = _rate_value(null_means, channel, "null_means")
        standard_deviation = _rate_value(
            null_standard_deviations,
            channel,
            "null_standard_deviations",
            nonnegative=True,
        )
        normalized = ((observed - mean) / (standard_deviation + normalized_epsilon)) / normalized_softening
        transformed.append(math.asinh(normalized))
    return math.sqrt(math.fsum(value * value for value in transformed))


@dataclass(frozen=True)
class GeometrySignature:
    birth_window: float
    high_support: float
    strain: float
    combined: float

    def to_dict(self) -> dict[str, object]:
        return {
            "type_tag": "PDC.QP.GeometrySignature.v0.1",
            "R_B": self.birth_window,
            "R_H": self.high_support,
            "R_psi": self.strain,
            "R_C": self.combined,
        }


def geometry_signature(
    observed_rates: Mapping[str, object],
    null_means: Mapping[str, object],
    null_standard_deviations: Mapping[str, object],
    *,
    epsilon: object = DEFAULT_EPSILON,
    softening: object = DEFAULT_SOFTENING,
) -> GeometrySignature:
    arguments = {
        "epsilon": epsilon,
        "softening": softening,
    }
    return GeometrySignature(
        birth_window=robust_score(
            observed_rates,
            null_means,
            null_standard_deviations,
            BIRTH_GEOMETRY_CHANNELS,
            **arguments,
        ),
        high_support=robust_score(
            observed_rates,
            null_means,
            null_standard_deviations,
            HIGH_SUPPORT_GEOMETRY_CHANNELS,
            **arguments,
        ),
        strain=robust_score(
            observed_rates,
            null_means,
            null_standard_deviations,
            STRAIN_GEOMETRY_CHANNELS,
            **arguments,
        ),
        combined=robust_score(
            observed_rates,
            null_means,
            null_standard_deviations,
            COMBINED_GEOMETRY_CHANNELS,
            **arguments,
        ),
    )


def normalized_geometry_spectrum(
    signature: GeometrySignature,
    *,
    epsilon: object = DEFAULT_EPSILON,
    null_threshold: object = NULL_SIGNAL_THRESHOLD,
) -> dict[str, object]:
    normalized_epsilon = _require_positive(epsilon, "epsilon")
    threshold = _require_nonnegative(null_threshold, "null_threshold")
    components = (signature.birth_window, signature.high_support, signature.strain, signature.combined)
    if any(not math.isfinite(value) or value < 0.0 for value in components):
        raise PdcQpProbabilityError("geometry signature components must be finite and nonnegative")
    if signature.combined < threshold:
        raise PdcQpNullSignalError(
            f"geometry spectrum is undefined for null-like R_C={signature.combined!r} below {threshold!r}"
        )
    denominator = math.fsum(value * value for value in components[:3]) + normalized_epsilon
    shares = tuple(value * value / denominator for value in components[:3])
    return {
        "type_tag": "PDC.QP.GeometrySpectrum.v0.1",
        "R_C": signature.combined,
        "null_threshold": threshold,
        "epsilon": normalized_epsilon,
        "shares": {"B": shares[0], "H": shares[1], "psi": shares[2]},
        "share_sum": math.fsum(shares),
        "non_null": True,
    }
