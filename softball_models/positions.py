from dataclasses import dataclass

@dataclass(frozen=True, eq=False)
class Position:
    name: str
    weight: float

    def __eq__(self, value):
        return self.name == value.name and self.weight == value.weight
    
    def __hash__(self):
        return hash((self.name, self.weight))


