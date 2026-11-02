"""Values shared by the tests: the reference date the data is coherent with, and test
customers from data/ (fictional)."""

from datetime import date, datetime

from emporio.config import STORE_TZ

REFERENCE_DATE = date(2026, 3, 25)  # a Wednesday, just after the last order in the data
STORE_NOW = datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)  # store open

ANA_PHONE = "(67) 99654-7821"  # customer 2, order 8 (shipped, late)
ANA_EMAIL = "anacarol.ferreira@coldmail.com"
LETICIA_PHONE = "67997890123"  # customer 14, order 7 (delivered)
LETICIA_EMAIL = "leticia.rocha@jmail.com"
