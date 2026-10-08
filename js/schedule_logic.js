(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    } else {
        root.SVOZ_SCHEDULE_LOGIC = api;
    }
}(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

    function isValidIsoDate(value) {
        if (!ISO_DATE.test(value)) return false;
        const parsed = new Date(`${value}T00:00:00Z`);
        return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
    }

    function parseScheduleCsv(csv, allowedTypes) {
        if (typeof csv !== "string") throw new Error("Schedule must be text");
        const allowed = new Set(allowedTypes);
        const events = [];

        csv.split(/\r?\n/).forEach((rawLine, index) => {
            if (!rawLine.trim()) return;
            const columns = rawLine.split(",");
            if (columns.length !== 4) {
                throw new Error(`Invalid schedule row ${index + 1}`);
            }
            const [dateRaw, typeRaw, locationRaw, overrideRaw] = columns;
            const date = dateRaw.trim();
            const type = typeRaw.trim().toLowerCase();
            const location = locationRaw.trim();
            const isOverrideRaw = overrideRaw.trim();
            if (!isValidIsoDate(date) || !allowed.has(type) || !location || !["0", "1"].includes(isOverrideRaw)) {
                throw new Error(`Invalid schedule row ${index + 1}`);
            }
            events.push({
                date,
                type,
                location,
                isOverride: isOverrideRaw === "1",
            });
        });

        if (!events.length) throw new Error("Schedule contains no events");
        return events;
    }

    function availableYears(events) {
        return [...new Set(events.map(event => Number(event.date.slice(0, 4))))]
            .filter(Number.isInteger)
            .sort((a, b) => a - b);
    }

    function upcomingCollections(events, location, today) {
        if (!isValidIsoDate(today)) throw new Error("Invalid reference date");
        const upcoming = {};
        for (const event of events) {
            if (event.location !== location || event.date < today) continue;
            if (!upcoming[event.type] || event.date < upcoming[event.type].date) {
                upcoming[event.type] = event;
            }
        }
        return upcoming;
    }

    function collectionDateLabels(date, today) {
        if (!isValidIsoDate(date) || !isValidIsoDate(today)) {
            throw new Error("Invalid collection or reference date");
        }
        // Compare calendar days in UTC so Prague's DST changes cannot alter the count.
        const parsed = new Date(`${date}T00:00:00Z`);
        const days = (parsed - new Date(`${today}T00:00:00Z`)) / 86400000;
        if (days < 0) throw new Error("Collection date must not be in the past");
        const weekdays = ["neděle", "pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota"];
        const [year, month, day] = date.split("-").map(Number);
        return {
            dateLabel: `${weekdays[parsed.getUTCDay()]} ${day}. ${month}. ${year}`,
            relativeLabel: days === 0 ? "dnes" : days === 1 ? "zítra" : `za ${days} ${days <= 4 ? "dny" : "dní"}`
        };
    }

    function pragueDate(now = new Date()) {
        const parts = new Intl.DateTimeFormat("en", {
            timeZone: "Europe/Prague", year: "numeric", month: "2-digit", day: "2-digit"
        }).formatToParts(now);
        const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${values.year}-${values.month}-${values.day}`;
    }

    function initialYear(years, currentYear) {
        if (!years.length) throw new Error("No schedule years are available");
        if (years.includes(currentYear)) return currentYear;
        const past = years.filter(year => year < currentYear);
        return past.length ? past[past.length - 1] : years[0];
    }

    function shiftMonth(years, year, month, direction) {
        const yearIndex = years.indexOf(year);
        if (yearIndex < 0 || ![-1, 1].includes(direction)) return { year, month };
        if (direction === -1) {
            if (month > 0) return { year, month: month - 1 };
            return yearIndex > 0
                ? { year: years[yearIndex - 1], month: 11 }
                : { year, month };
        }
        if (month < 11) return { year, month: month + 1 };
        return yearIndex < years.length - 1
            ? { year: years[yearIndex + 1], month: 0 }
            : { year, month };
    }

    function canShiftMonth(years, year, month, direction) {
        const shifted = shiftMonth(years, year, month, direction);
        return shifted.year !== year || shifted.month !== month;
    }

    return {
        parseScheduleCsv,
        availableYears,
        upcomingCollections,
        collectionDateLabels,
        pragueDate,
        initialYear,
        shiftMonth,
        canShiftMonth,
    };
}));
