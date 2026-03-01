const WASTE_TYPES = {
    bio: 'Bio odpad',
    generic: 'Směsný odpad',
    plastics: 'Plasty',
    paper: 'Papír'
};

let wasteSchedule = [];
let uniqueLocations = [];
let filteredLocation = "";
let selectedYear = new Date().getFullYear();
let selectedMonth = new Date().getMonth();

const urlParams = new URLSearchParams(window.location.search);
const isKioskMode = urlParams.get('kiosk');
const isStreetPage =
    window.location.pathname.startsWith("/ulice/");

const initialLocation =
    window.STREET_NAME ||
    (isStreetPage ? null : urlParams.get('location')) ||
    getLocationFromPath();

const MONTHS = ["Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"];
const DAYS = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];

fetch('/waste_schedule.csv')
    .then(response => response.text())
    .then(csv => {
        parseCSV(csv);
        uniqueLocations = [...new Set(wasteSchedule.map(entry => entry.location).filter(loc => loc))];
        updateDataForInitialLocation(initialLocation, uniqueLocations);
        renderMonthCalendar(filteredLocation);

        if (isKioskMode) {
            ["mainHeader", "controls", "footerControls", "locationList"].forEach(id =>
                document.getElementById(id).style.display = "none"
            )
        } else {
            populateFilters();
        }
    });

function parseCSV(csv) {
    const lines = csv.split('\n');
    wasteSchedule = lines.map(line => {
        const [date, type, location] = line.split(',');
        if (!date || !type) return null;
        return { date: date.trim(), type: type.trim().toLowerCase(), location: location ? location.trim() : '' };
    }).filter(entry => entry);
}

function populateFilters() {
    const monthSelect = document.getElementById('monthSelect');
    const prevMonth = document.getElementById('prevMonth');
    const nextMonth = document.getElementById('nextMonth');
    const yearSelect = document.getElementById('yearSelect');
    const locationSearch = document.getElementById('locationSearch');
    const locationOptions = document.getElementById('locationOptions');
    const copyLink = document.getElementById('copyLink');
    const footerControls = document.getElementById('footerControls');
    const pdfYear = document.getElementById('pdfYear');
    const pdfMonth = document.getElementById('pdfMonth');
    const currentYear = new Date().getFullYear();

    MONTHS.forEach((month, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = month;
        if (index === selectedMonth) option.selected = true;
        monthSelect.appendChild(option);
    });

    for (let i = currentYear; i <= currentYear + 1; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = i;
        if (i === selectedYear) option.selected = true;
        yearSelect.appendChild(option);
    }
    
    function renderLocationOptions(query = "", forceDisplayNone = false) {
        locationOptions.innerHTML = "";
        const filtered = uniqueLocations.filter(loc => loc.toLowerCase().includes(query.toLowerCase()));

        filtered.forEach(location => {
            const optionDiv = document.createElement('div');
            optionDiv.textContent = location;

            optionDiv.addEventListener('click', () => {
                const slug = slugify(location);
                window.location.href = `/ulice/${slug}/`;   // 🔥 místo pushState
            });

            locationOptions.appendChild(optionDiv);
        });

        locationOptions.style.display = (filtered.length > 0 && !forceDisplayNone) ? "block" : "none";
    }

    locationSearch.addEventListener('input', (e) => {
        renderLocationOptions(e.target.value, false);
    });

    locationSearch.addEventListener('click', () => {
        renderLocationOptions("", false);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#locationDropdown')) {
            locationOptions.style.display = 'none';
        }
    });

    monthSelect.addEventListener('change', (e) => {
        selectedMonth = parseInt(e.target.value);
        renderMonthCalendar(filteredLocation);
    });

    prevMonth.addEventListener('click', () => {
        let month = selectedMonth;
        let year = selectedYear;
        month--;
        if (month < 0) {
            month = 11;
            year--;
        }
        selectedMonth = month;
        monthSelect.value = selectedMonth;
        selectedYear = year;
        yearSelect.value = selectedYear;
        renderMonthCalendar(filteredLocation)
    });

    nextMonth.addEventListener('click', () => {
        let month = selectedMonth;
        let year = selectedYear;
        month++;
        if (month > 11) {
            month = 0;
            year++;
        }
        selectedMonth = month;
        monthSelect.value = selectedMonth;
        selectedYear = year;
        yearSelect.value = selectedYear;
        renderMonthCalendar(filteredLocation)
    });

    yearSelect.addEventListener('change', (e) => {
        selectedYear = parseInt(e.target.value);
        renderMonthCalendar(filteredLocation);
    });

    resetFilter.addEventListener('click', () => {
        window.location.href = "/";   // 🔥 místo pushState + SEO manipulace
    });

    pdfYear.addEventListener("click", () => {
        generateWasteCalendarPDF(
            wasteSchedule.filter(entry => entry.location === filteredLocation),
            selectedYear,
            null,
            filteredLocation
        );
    });

    pdfMonth.addEventListener("click", () => {
        generateWasteCalendarPDF(
            wasteSchedule.filter(entry => entry.location === filteredLocation),
            selectedYear,
            selectedMonth,
            filteredLocation
        );
    });

    copyLink.addEventListener('click', (e) => {
        e.preventDefault();
        const icsUrl = copyLink.getAttribute('data-url');
        navigator.clipboard.writeText(icsUrl);
    });

    renderLocationOptions("", initialLocation);
}

function renderMonthCalendar(renderedLocation = "") {
    const calendarContainer = document.getElementById('calendarContainer');
    calendarContainer.innerHTML = '';
    const today = new Date();
    const daysInMonth = new Date(selectedYear, selectedMonth + 1, 0).getDate();
    const firstDay = (new Date(selectedYear, selectedMonth, 1).getDay() + 6) % 7;

    const fallback = document.getElementById("seoFallback");
    if (fallback) {
        fallback.style.display = "none";
    }

    const table = document.createElement('table');
    table.className = 'calendar-month';

    const headerRow = document.createElement('tr');
    DAYS.forEach(day => {
        const th = document.createElement('th');
        th.textContent = day;
        headerRow.appendChild(th);
    });
    table.appendChild(headerRow);

    let row = document.createElement('tr');
    for (let i = 0; i < firstDay; i++) {
        row.appendChild(document.createElement('td'));
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const cell = document.createElement('td');
        const dateKey = `${selectedYear}-${(selectedMonth + 1).toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
        cell.textContent = day;

        const matchingEntries = wasteSchedule.filter(entry => entry.date === dateKey);

        const groupedEntries = {};
        matchingEntries.forEach(entry => {
            if (!renderedLocation || entry.location === renderedLocation) {
                if (!groupedEntries[entry.type]) {
                    groupedEntries[entry.type] = new Set();
                }
                groupedEntries[entry.type].add(entry.location);
            }
        });

        for (const [type, locations] of Object.entries(groupedEntries)) {
            const collectionDiv = document.createElement('div');
            collectionDiv.className = `collection ${type}`;
            const locationText = renderedLocation 
                ? Array.from(locations).join(', ')
                : `(${locations.size} lokací)`;
            collectionDiv.textContent = `${WASTE_TYPES[type]} ${locationText}`;
            cell.appendChild(collectionDiv);
        }

        if (day === today.getDate() && selectedYear === today.getFullYear() && selectedMonth === today.getMonth()) {
            cell.classList.add('today');
        }

        row.appendChild(cell);

        if ((firstDay + day) % 7 === 0) {
            table.appendChild(row);
            row = document.createElement('tr');
        }
    }

    table.appendChild(row);
    calendarContainer.appendChild(table);
}

function updateDataForInitialLocation(initialLocation, uniqueLocations) {
    if (initialLocation && uniqueLocations.includes(initialLocation)) {
        filteredLocation = initialLocation;
        const locationSearch = document.getElementById('locationSearch');
        const copyLink = document.getElementById('copyLink');
        const footerControls = document.getElementById('footerControls');

        if (locationSearch) locationSearch.value = initialLocation;
        if (copyLink) {
            copyLink.setAttribute('data-url',
                `${window.location.origin}/calendars/${encodeURIComponent(initialLocation)}.ics`
            );
        }
        if (footerControls) footerControls.style.display = 'flex';
    }
}

function slugify(text) {
    return text
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^\w\s-]/g, "")
        .trim()
        .replace(/[-\s]+/g, "-");
}

function decodeSlugToLocation(slug) {
    return uniqueLocations.find(loc =>
        slugify(loc) === slug
    );
}

function getLocationFromPath() {
    const parts = window.location.pathname.split('/').filter(Boolean);
    if (parts[0] === "ulice" && parts[1]) {
        return decodeURIComponent(parts[1]);
    }
    return null;
}
