import re

from openpyxl import load_workbook

from errors import *
from tyre import Tyre, TyreSet

EXTRACT_PATTERN = re.compile(
    r"\b(?P<prefix>LT|P)?"
    r"(?P<width>\d{3})/"
    r"(?P<aspect_ratio>\d{2})"
    r"\s*[ZR]?[Rr]"
    r"(?P<rim_diameter>\d{2})",
    re.IGNORECASE,
)


def _safer_get(key, d: dict, ty, default=None):

    MISSING = object()
    val = d.get(key, MISSING)

    if MISSING or val == None:
        return None

    try:
        return ty(val)
    except (TypeError, ValueError):
        raise InvalidFieldType(f"The field {key} must be of type {ty}")


def _parse_price(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        value = value.replace(",", "").replace("₹", "").strip()
        if value.upper().startswith("RS.") or value.upper().startswith("RS "):
            value = value[3:].strip()
    try:
        float(value)
    except ValueError:
        return None
    return float(value)


class Extractor:
    def __init__(self, filename, brand, flags: dict):
        self._filename = filename
        self.size_col = _safer_get("size_col", flags, int, None)
        self.mrp_col = _safer_get("mrp_col", flags, int, None)
        self.pattern_col = _safer_get("pattern_col", flags, int, None)
        self.rcp_col = _safer_get("rcp_col", flags, int, None)
        self.inv_price_col = _safer_get("invoice_price", flags, int, None)
        self.row_start = _safer_get("row_start", flags, int, None)
        self.tyre_set = TyreSet()
        self.failed_set = []
        self.brand = brand
        prices = (self.mrp_col, self.rcp_col, self.inv_price_col)
        if all(price is None for price in prices):
            raise MissingFieldError("At least one price column needs to be provided.")

        if self.size_col is None:
            raise MissingFieldError("Size column not provided in flags")

        if self.row_start == None:
            raise MissingFieldError("row_start column is not provided.")

        try:
            if self._filename.split(".")[-1] != "xlsx":
                raise FileError
        except IndexError:
            raise FileError

    def parse_tyre_string(self, tyre_string):
        match = EXTRACT_PATTERN.search(tyre_string)
        if not match:
            raise TyreDataParsingError
        parsed_text = {}
        parsed_text["prefix"] = match.group("prefix") or ""
        parsed_text["width"] = match.group("width")
        parsed_text["ratio"] = match.group("aspect_ratio")
        parsed_text["rim"] = match.group("rim_diameter")
        p = [
            tyre_string[i]
            for i in range(len(tyre_string))
            if match.start() > i or i >= match.end()
        ]  # match end positions are exculisve??
        parsed_text["pattern"] = "".join(p).strip().upper()
        parsed_text["mrp"] = None
        parsed_text["rcp"] = None
        parsed_text["inv_price"] = None
        return parsed_text

    def extract(self):
        ws = load_workbook(filename=self._filename).active
        if ws is None:
            raise FileError
        if self.size_col is None:
            raise TyreDataParsingError("Size Column not provided")
        self.failed_set.clear()
        self.tyre_set.clear()
        for ind, row in enumerate(ws.values):
            if ind < self.row_start:
                continue
            raw_tyre_text = row[self.size_col]
            if not isinstance(raw_tyre_text, str):
                self.failed_set.append(
                    {
                        "position": ind + 1,
                        "filename": self._filename,
                        "data": raw_tyre_text,
                        "reason": "Could not read the size_column",
                    }
                )
                continue
            try:
                parsed_data = self.parse_tyre_string(raw_tyre_text)
            except TyreDataParsingError:
                self.failed_set.append(
                    {
                        "position": ind + 1,
                        "filename": self._filename,
                        "data": raw_tyre_text,
                        "reason": "Unsupported Tyre Format",
                    }
                )
                continue

            if self.mrp_col is not None:
                parsed_data["mrp"] = _parse_price(row[self.mrp_col])
            if self.rcp_col is not None:
                parsed_data["rcp"] = _parse_price(row[self.rcp_col])
            if self.inv_price_col is not None:
                parsed_data["inv_price"] = _parse_price(row[self.inv_price_col])
            if self.pattern_col is not None and isinstance(row[self.pattern_col], str):
                    parsed_data["pattern"] = str(row[self.pattern_col]).strip().upper()

            tyre = Tyre(
                source_row=ind + 1,
                source_file=self._filename,
                brand=self.brand,
                prefix=parsed_data["prefix"],
                width=parsed_data["width"],
                ratio=parsed_data["ratio"],
                rim_size=parsed_data["rim"],
                pattern=parsed_data["pattern"],
                mrp=parsed_data["mrp"],
                rcp=parsed_data["rcp"],
                invoice_price=parsed_data["inv_price"],
            )
            prices = (tyre.mrp, tyre.rcp, tyre.invoice_price)
            if all(price is None for price in prices):
                self.failed_set.append(
                    {
                        "position": ind + 1,
                        "filename": self._filename,
                        "data": raw_tyre_text,
                        "reason": "No pricing info available",
                    }
                )
                continue
            self.tyre_set.append(tyre)

        return self.tyre_set, self.failed_set
