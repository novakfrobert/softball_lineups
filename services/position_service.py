from softball_models.positions import Position

_CF = Position("CF", 80)
_LF = Position("LF", 90)
_RF = Position("RF", 15)
_LCF = Position("LCF", 85)
_RCF = Position("RCF", 30)
_SS = Position("SS", 100)
_3B = Position("3B", 95)
_2B = Position("2B", 60)
_1B = Position("1B", 70)
_C = Position("C", 5)
_P = Position("P", 90)

_POSITIONS = {
    "CF": _CF,
    "LCF": _LCF,
    "RCF": _RCF,
    "LF": _LF,
    "RF": _RF,
    "SS": _SS,
    "3B": _3B,
    "2B": _2B,
    "1B": _1B,
    "C": _C,
    "P": _P
}

def get_position(pos: str):
    if pos not in _POSITIONS:
        raise Exception("Invalid position", pos)
    
    return _POSITIONS[pos]

def get_positions(num_players, allow_not_enough=False):
    positions = []

    if num_players >= 10:
        positions = [_P, _SS, _LF, _LCF, _3B, _1B, _2B, _RCF, _RF, _C]
    elif num_players == 9:
        positions = [_P, _SS, _LF, _CF, _3B, _1B, _2B, _RF, _C]
    elif num_players <= 8:
        positions = [_P, _SS, _LF, _CF, _3B, _1B, _2B, _RF]

    # Ensure they are sorted by most important
    positions.sort(key = lambda pos: -1*pos.weight)

    if allow_not_enough:
        # Get the n most important positions and return them
        positions = positions[:num_players]
    elif num_players < 8:
        # Don't allow less than 8 players
        raise Exception(f"Invalid number of players {num_players}")
    
    return positions
