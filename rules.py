from streets import all_streets

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

#svoz směsného odpadu
#liche pondeli
litovel_lokace_2 = [
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
litovel_lokace_3 = [
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
litovel_lokace_4 = [
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
litovel_lokace_5 = [
    'Vítězná',
    'Lidická',
    'Kysucká'
]
#lichy ctvrtek
litovel_lokace_6 = [
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
litovel_lokace_7 = [
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
