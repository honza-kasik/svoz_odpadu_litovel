import unicodedata
import re
from datetime import datetime, timedelta

def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text

def date_range(start_date: datetime, end_date: datetime):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)
