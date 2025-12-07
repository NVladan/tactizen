from .poseidon_constants import *  # Import from same package
MODULUS = 21888242871839275222246405745257275088548364400416034343698204186575808495617


class InvalidInputError(Exception):
    """Raised when the input is not a list of numbers."""
    pass

class NumberOutOfFieldError(Exception):
    """Raised when a number is larger than the field."""
    pass

class ArrayLengthExceededError(Exception):
    """Raised when the array length exceeds 16."""
    pass


def pow5(input):
    """Raise the input to the power of 5 modulo the field."""
    return pow(input, 5, MODULUS)


def ark_func(t, C, r, input):
    """ARK function for Poseidon hash."""
    out = [(input[i] + C[i + r]) % MODULUS for i in range(t)]
    return out


def mix_func(t, M, input):
    """Mix function for Poseidon hash."""
    out = [sum(M[j][i] * input[j] for j in range(t)) % MODULUS for i in range(t)]
    return out


def mix_last_func(t, M, s, input):
    """Final mix step for Poseidon hash."""
    lc = sum(M[j][s] * input[j] for j in range(t)) % MODULUS
    return lc


def mix_s_func(t, S, r, input):
    """S-Box mixing function for Poseidon hash."""
    out = [0] * t
    lc = sum(S[(t * 2 - 1) * r + i] * input[i] for i in range(t)) % MODULUS
    out[0] = lc
    for i in range(1, t):
        out[i] = (input[i] + input[0] * S[(t * 2 - 1) * r + t + i - 1]) % MODULUS
    return out


def posedion_ex(nOuts, inputs, initialState):
    """Main Poseidon hashing function."""
    t = len(inputs) + 1
    N_ROUNDS_F = 8
    N_ROUNDS_P = [56, 57, 56, 60, 60, 63, 64, 63, 60, 66, 60, 65, 70, 60, 64, 68][t - 2]

    C = poseidon_c_const_arr(t)
    S = poseidon_s_const_arr(t)
    M = poseidon_m_const_arr(t)
    P = poseidon_p_const_arr(t)

    ark, pow5F, pow5P, mix, mixS, mixLast = [], [], [], [], [], []

    input = [inputs[j-1] if j > 0 else initialState for j in range(t)]
    ark.append(ark_func(t, C, 0, input))

    # Full round calculations
    for r in range(N_ROUNDS_F // 2 - 1):
        pow5F.append([pow5(ark[0][j] if r == 0 else mix[r-1][j]) for j in range(t)])
        ark.append(ark_func(t, C, (r + 1) * t, pow5F[r]))
        mix.append(mix_func(t, M, ark[-1]))

    pow5F.append([pow5(mix[-1][j]) for j in range(t)])
    ark.append(ark_func(t, C, (N_ROUNDS_F // 2) * t, pow5F[-1]))
    mix.append(mix_func(t, P, ark[-1]))

    # Partial round calculations
    for r in range(N_ROUNDS_P):
        pow5P.append(pow5(mix[-1][0] if r == 0 else mixS[-1][0]))
        mixS.append(mix_s_func(t, S, r, [pow5P[-1] + C[(N_ROUNDS_F // 2 + 1) * t + r] if j == 0 else mix[-1][j] for j in range(t)]))

    for r in range(N_ROUNDS_F // 2 - 1):
        pow5F.append([pow5(mixS[-1][j]) for j in range(t)])
        ark.append(ark_func(t, C, (N_ROUNDS_F // 2 + 1) * t + N_ROUNDS_P + r * t, pow5F[-1]))
        mix.append(mix_func(t, M, ark[-1]))

    pow5F.append([pow5(mix[-1][j]) for j in range(t)])
    mixLast = [mix_last_func(t, M, i, pow5F[-1]) for i in range(nOuts)]

    return mixLast


def poseidon(inputs):
    """Poseidon hash function."""
    if not isinstance(inputs, list) or not all(isinstance(n, (int, float)) for n in inputs):
        raise InvalidInputError("Input must be a list of numbers.")
    
    if any(num > MODULUS for num in inputs):
        raise NumberOutOfFieldError(f"One or more numbers exceed the field limit of {MODULUS}.")
    
    if len(inputs) > 16:
        raise ArrayLengthExceededError("Poseidon does not support more than 16 inputs.")
    
    return posedion_ex(1, inputs, 0)[0]
