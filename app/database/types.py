from sqlalchemy import Numeric

# Exact decimal storage for money, prices and share counts: NUMERIC(18, 8) in PostgreSQL.
# asdecimal=False keeps the Python side as float (existing arithmetic keeps working);
# values are rounded to 8 decimals when written, and SQL sums/comparisons are exact.
MONEY_PRECISION = 18
MONEY_SCALE = 8
Money = Numeric(MONEY_PRECISION, MONEY_SCALE, asdecimal=False)
