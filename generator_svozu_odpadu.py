from datetime import datetime, timedelta
from icalendar import Calendar, Event

from rules import *
from streets import all_streets

date_start =  datetime(2025, 1, 1)
date_end =  datetime(2025, 12, 31)

def date_range(start_date: datetime, end_date: datetime):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)

def validate_street(street: str) -> bool:
    #todo throw exception
    return street in all_streets

def generate_generic_waste_dates_for_street(street: str):
    validate_street(street)
    dates = []
    for date in date_range(date_start, date_end):
        if date.isocalendar().week % 2 == 0:
            #sudy tyden
            if date.weekday() == 0 and street in litovel_lokace_3:
                #je pondeli a ulice je v seznamu na pondeli
                dates.append(date)
            if date.weekday() == 3 and street in litovel_lokace_7:
                #je ctvrtek 
                dates.append(date)
        else:
            if date.weekday() == 0 and street in litovel_lokace_2:
                dates.append(date)
            if date.weekday() == 1 and street in litovel_lokace_4:
                dates.append(date)
            if date.weekday() == 2 and street in litovel_lokace_5:
                dates.append(date)
            if date.weekday() == 3 and street in litovel_lokace_6:
                dates.append(date)
    return dates

def generate_plastics_dates_for_street(street: str):
    validate_street(street)
    dates = []
    for date in date_range(date_start, date_end):
        if date.isocalendar().week % 2 == 0:
            #sudy tyden
            if date.weekday() == 0 and street in litovel_lokace_plast_0:
                dates.append(date)
            else:
                if date.weekday() == 0 and street in litovel_lokace_plast_1:
                    dates.append(date)
    return dates

def generate_bio_dates_for_street(street: str):
    validate_street(street)
    dates = []
    for date in date_range(date_start, date_end):
        if date.isocalendar().week % 2 == 0:
            pass #sudy tyden, zadny svoz
        else:
            if date.weekday() == 3 and street in litovel_lokace_bio_0:
                dates.append(date)
            if date.weekday() == 2 and street in litovel_lokace_bio_1:
                dates.append(date)
    return dates

def generate_dates_for_street(street: str):
    cal = Calendar()
    for date in generate_generic_waste_dates_for_street(street):
        event = Event()
        event.add('summary', f'Směsný odpad svoz - {street}')
        event.add('dtstart', date.date())
        event.add('dtend', (date.date() + timedelta(days=1)))
        cal.add_component(event)
    for date in generate_bio_dates_for_street(street):
        event = Event()
        event.add('summary', f'Bioodpad svoz - {street}')
        event.add('dtstart', date.date())
        event.add('dtend', (date.date() + timedelta(days=1)))
        cal.add_component(event)
    for date in generate_plastics_dates_for_street(street):
        event = Event()
        event.add('summary', f'Plasty svoz - {street}')
        event.add('dtstart', date.date())
        event.add('dtend', (date.date() + timedelta(days=1)))
        cal.add_component(event)

    with open(f"calendars/{street}.ics", "wb") as f:
        f.write(cal.to_ical())
    
for street in all_streets['Litovel']:
    generate_dates_for_street(street)
