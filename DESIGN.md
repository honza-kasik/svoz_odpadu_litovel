# Vizuální pravidla

Tento soubor je stručný zdroj pravdy pro vzhled webu. Nové rozhraní má používat níže uvedené prvky; nová varianta rámečku, karty, štítku nebo nadpisu se nepřidává bez úpravy těchto pravidel.

## Principy

- Hierarchii tvoří nejdříve obsah, typografie a mezery, až potom dekorace.
- Jeden obsahový celek smí mít nejvýše jeden povrch. Panely se nevnořují.
- Zaoblení označuje samostatný interaktivní nebo významově uzavřený celek, ne každý řádek.
- Oddělovače patří mezi opakované řádky seznamu. Nepoužívají se pro rozdělení běžného textového obsahu do sloupců.
- Barevný akcent vyjadřuje stav. Nesmí být pouze dekorativní.
- Pilulkové štítky jsou vyhrazené pro volitelné filtry. Lokality, odkazy ani běžné stavy se do nich nevkládají.
- Nadpisy a popisky používají běžnou větnou velikost písmen. Verzálky a přidané prostrkání písmen nepoužíváme.

## Povolené prvky

### Běžná sekce — `.ui-section`

Nadpis a obsah přímo na pozadí stránky. Bez rámečku, výplně a zaoblení. Používá se pro obsah, který nepotřebuje vlastní interakční hranici.

### Interaktivní panel — `.ui-panel`

Bílý povrch, jednotné vnitřní odsazení a poloměr. Používá se pro vyhledávání, rozbalovací blok nebo jiný samostatný ovládací prvek. Panel nesmí obsahovat další panel.

### Stavová zpráva — `.ui-status`

Bílý povrch s barevnou levou hranou. Odpovídá přímo na otázku uživatele, například zda je kontejner právě na místě. Barva musí nést význam stavu.

### Datový seznam — `.ui-data-list`

Opakované řádky bez samostatných karet. Jednotlivé řádky lze oddělit tenkou vodorovnou linkou. Čísla a data používají tabulkové číslice, pokud jim to pomáhá v zarovnání.

## Tokeny

Hodnoty jsou definované v `:root` v `styles.css`. Komponenty používají proměnné `--space-section`, `--space-panel`, `--space-panel-vertical`, `--radius-panel`, `--surface-panel`, `--border-subtle` a `--text-muted`; stejné hodnoty se nemají znovu zapisovat jako nové lokální varianty.

## Kontrola nové obrazovky

1. Lze obsah vyjádřit běžnou sekcí bez kontejneru?
2. Pokud používá panel, je celý panel jeden interaktivní nebo významový celek?
3. Neobsahuje panel další panel, kartu nebo dekorativní štítky?
4. Vyjadřuje barva skutečný stav?
5. Používá rozhraní existující tokeny a komponenty?

## Použití na webu

- Hlavní stránka: panel s volbou měsíce a ulice používá `.ui-panel`; nejbližší bio kontejnery používají jeden `.ui-panel` a uvnitř plochý `.ui-data-list`.
- Přehled bio kontejnerů: vyhledávání, volitelné výsledky podle polohy a rozbalovací roční harmonogram používají `.ui-panel`; výsledky polohy zůstávají plochým `.ui-data-list` uvnitř vyhledávání a aktuální a příští umístění jsou běžné `.ui-section`.
- Detail stanoviště: přímá odpověď používá `.ui-status`, termíny kombinaci `.ui-panel` a `.ui-data-list`.
- Průvodce zahradním bioodpadem: rychlé odkazy používají jeden `.ui-panel`; odpovědi podle materiálu a seznam dalších kroků jsou ploché `.ui-data-list`. Seznam zakázaného obsahu je běžná `.ui-section`, ne výstražná karta.
- Sběrný dvůr: poloha a odkaz na trasu tvoří jeden `.ui-panel`; provozní a zdrojové informace zůstávají běžnými sekcemi.
- Kalendářní buňky jsou oborová komponenta, nikoli obecný panel. Jejich samostatné pozadí a zaoblení vyjadřuje mřížku jednotlivých dnů.
