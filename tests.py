from rules import *
from streets import *
from generator_svozu_odpadu import *

locations = litovel_lokace_smes_0 + litovel_lokace_smes_1 + litovel_lokace_smes_2 + litovel_lokace_smes_3 + litovel_lokace_smes_4 + litovel_lokace_smes_5
print("locations - all")
print(list(set(locations) - set(all_streets['Litovel'])))
print("all - locations")
print(list(set(all_streets['Litovel']) - set(locations)))

print("all - plast union")
print(list(set(all_streets['Litovel']) - set(litovel_lokace_plast_0 + litovel_lokace_plast_1)))

print("all - bio union")
print(list(set(all_streets['Litovel']) - set(litovel_lokace_bio_0 + litovel_lokace_bio_1)))

print(generate_generic_waste_dates_for_street('Lidická'))
