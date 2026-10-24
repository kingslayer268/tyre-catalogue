from collections import UserList
from dataclasses import dataclass, asdict


@dataclass
class Tyre:
    brand: str
    prefix: str
    width: int
    ratio: int
    rim_size: int
    pattern: str
    source_file: str
    source_row: int
    mrp: float | None = None
    rcp: float | None = None
    invoice_price: float | None = None
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            brand=data['brand'],
            prefix=data['prefix'],
            width=data['width'],
            ratio=data['ratio'],
            rim_size=data['rim_size'],
            pattern=data['pattern'],
            source_file=data['source_file'],
            source_row=data['source_row'],
            mrp=data['mrp'],
            rcp=data['rcp'],
            invoice_price=data['invoice_price']
        )
    def to_dict(self):
        return asdict(self)

    def to_tuple(self):
        self._tuple = (
            self.brand,
            self.prefix,
            self.width,
            self.ratio,
            self.rim_size,
            self.pattern,
            self.mrp,
            self.rcp,
            self.invoice_price,
            self.source_file,
            self.source_row,
        )       
        return self._tuple


class TyreSet(UserList):

    def _validate(self, item):
        if not isinstance(item, Tyre):
            raise TypeError(f"TyreSet only accepts Tyre objects, got {type(item).__name__}")
    def __init__(self):
        super().__init__(None)
    def __setitem__(self, index, item):
        self._validate(item)
        super().__setitem__(index, item)

    def append(self, item):
        self._validate(item)
        super().append(item)

    def extend(self, other):
        for item in other:
            self._validate(item)
        super().extend(other)

    def insert(self, i, item):
        self._validate(item)
        super().insert(i, item)
