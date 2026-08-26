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
        initialYear,
        shiftMonth,
        canShiftMonth,
    };
}));
