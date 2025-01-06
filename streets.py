"""
Pevne lokace, ktere by se nemely menit, zadna logika krome "zbytku mesta".
"""

all_streets = {
    'Litovel': [
        '1. máje',
        'B. Němcové',
        'Bezručova',
        'Boskovicova',
        'Cholinská',
        'Družstevní',
        'Dukelská',
        'G. Frištenského',
        'Gemerská - rodinné domy',
        'Gemerská - sídliště',
        'Havlíčkova',
        'Hrnčířská',
        'Husova',
        'Javoříčská',
        'Jiráskova',
        'Jungmannova',
        'Karla Sedláka - sídliště',
        'Karlov',
        'Karlovská',
        'Kollárova',
        'Komenského',
        'Komárov',
        'Kosmonautů',
        'Kostelní',
        'Koupaliště',
        'Králova',
        'Kysucká',
        'Lesní zátiší',
        'Lidická',
        'Loštická',
        'Lužní',
        'Masarykova',
        'Mlýnská',
        'Nasobůrská',
        'Novosady - sídliště',
        'Nová',
        'Nábřežní',
        'Nádražní',
        'Nám. Př. Otakara',
        'Olomoucká',
        'Opletalova',
        'Palackého',
        'Pavlínka',
        'Poděbradova',
        'Polní',
        'Pošmýlská',
        'Příčná',
        'Revoluční',
        'Revúcká',
        'Rybníček',
        'Sadová',
        'Severní',
        'Smyčkova',
        'Sochova',
        'Sovova',
        'Staroměstské náměstí',
        'Studentů',
        'Sušilova',
        'Svatoplukova',
        'Tichá',
        'Třebízského',
        'Třídvorská',
        'U Stadionu',
        'Uničovská',
        'Uničovská - sídliště',
        'Vlašímova',
        'Vodní',
        'Vítězná',
        'Wolkerova',
        'Zahradní',
        'nám. Svobody',
        'Vítězná',
        'Vítězná - sídliště',
        'Červenská',
        'Čihadlo',
        'Čs. armády',
        'Šafaříkova',
        'Šargounská',
        'Šemberova',
        'Šerhovní',
        'Šmakalova',
        'Štefánikova',
        'Švermova',
        'Švédská',
        'Žerotínova',
        'Novosady - rodinné domy',
        'Severní - rodinné domy'
    ]
}

mistni_casti = ['Březové', 'Chořelice', 'Chudobín', 'Myslechovice', 'Nasobůrky', 'Nová Ves', 'Unčovice', 'Rozvadovice', 'Savín', 'Tři Dvory', 'Víska']

#jednotlive lokace, ktere se svazi ve stejny den
#svoz plastu
litovel_lokace_plast_0 = [
            'Kosmonautů',
            'Králova',
            'Nová',
            'Pavlínka',
            'Pošmýlská',
            'Sadová',
            'U Stadionu',
            'Wolkerova',
            'Zahradní'
        ]
litovel_lokace_plast_1 = [street for street in all_streets['Litovel'] if street not in litovel_lokace_plast_0]

#svoz bio
litovel_lokace_bio_0 = [
            'Kosmonautů',
            'Králova',
            'Nová',
            'Pavlínka',
            'Pošmýlská',
            'Sadová',
            'U Stadionu',
            'Wolkerova',
            'Zahradní',
            'Uničovská',
            'Loštická'
        ]
litovel_lokace_bio_1 = [street for street in all_streets['Litovel'] if street not in litovel_lokace_bio_0]

#svoz smesneho odpadu, cislo v nazvu je poradi v jakem je mnozina lokaci v letacku
#liche pondeli
litovel_lokace_smes_0 = [
    'Cholinská',
    'Štefánikova',
    'Svatoplukova',
    'Olomoucká',
    'Dukelská',
    'Komárov',
    'Javoříčská',
    'Nádražní',
    'Severní'
]
#sude pondeli
litovel_lokace_smes_1 = [
    'Čihadlo',
    'Husova',
    'Karlovská',
    'Šargounská',
    'Družstevní',
    'Sochova',
    'Jiráskova',
    'Šemberova',
    'Bezručova',
    'Šmakalova',
    'Lužní',
    'Švermova',
    'Revúcká',
    'Studentů',
    'Opletalova',
    'Čs. armády',
    'Severní'
]
#liche utery
litovel_lokace_smes_2 = [
    'Polní',
    'Červenská',
    'Novosady - rodinné domy',
    'Hrnčířská',
    'Žerotínova',
    'Sušilova',
    'Rybníček',
    'Uničovská',
    'Severní - rodinné domy',
    'Gemerská - rodinné domy'
]
#licha streda
litovel_lokace_smes_3 = [
    'Vítězná',
    'Lidická',
    'Kysucká'
]
#lichy ctvrtek
litovel_lokace_smes_4 = [
    'Zahradní',
    'Králova',
    'Loštická',
    'Staroměstské náměstí',
    'Sadová',
    'Pavlínka',
    'U Stadionu',
    'Pošmýlská',
    'Kosmonautů',
    'Wolkerova',
    'Nová',
    'Kollárova',
    'B. Němcové',
    'Mlýnská',
    'Komenského',
    'Revoluční',
    'nám. Svobody',
    'Karla Sedláka - sídliště',
    'Gemerská - sídliště',
    'Uničovská - sídliště',
    'Novosady - sídliště',
    'Vítězná - sídliště'
]
#sudy ctvrtek
litovel_lokace_smes_5 = [
    'Smyčkova',
    'Havlíčkova',
    'Jungmannova',
    'Třebízského',
    'Masarykova',
    'Vlašímova',
    'Nám. Př. Otakara',
    'Kostelní',
    'Boskovicova',
    '1. máje',
    'Poděbradova',
    'Šafaříkova',
    'Švédská',
    'Palackého',
    'Vodní',
    'Nasobůrská',
    'G. Frištenského',
    'Příčná',
    'Nábřežní',
    'Karla Sedláka - sídliště',
    'Gemerská - sídliště',
    'Uničovská - sídliště',
    'Novosady - sídliště',
    'Vítězná - sídliště'
]
