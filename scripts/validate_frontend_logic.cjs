#!/usr/bin/env node

const assert = require("node:assert/strict");
const schedule = require("../js/schedule_logic.js");
const bio = require("../js/bio_logic.js");

const csv = [
    "2025-12-31,bio,Palackého,0",
    "2026-01-02,paper,Palackého,1",
    "2028-03-04,generic,Unčovice,0",
    "",
].join("\n");
const events = schedule.parseScheduleCsv(csv, ["bio", "paper", "generic"]);
assert.equal(events.length, 3);
assert.equal(events[1].isOverride, true);
assert.deepEqual(schedule.availableYears(events), [2025, 2026, 2028]);
assert.equal(schedule.initialYear([2025, 2026], 2026), 2026);
assert.equal(schedule.initialYear([2025, 2026], 2027), 2026);
assert.equal(schedule.initialYear([2027, 2028], 2026), 2027);
assert.deepEqual(schedule.shiftMonth([2025, 2027], 2025, 11, 1), { year: 2027, month: 0 });
assert.deepEqual(schedule.shiftMonth([2025, 2027], 2025, 0, -1), { year: 2025, month: 0 });
assert.equal(schedule.canShiftMonth([2025], 2025, 0, -1), false);
assert.throws(() => schedule.parseScheduleCsv("", ["bio"]));
assert.throws(() => schedule.parseScheduleCsv("2026-02-30,bio,Palackého,0", ["bio"]));
assert.throws(() => schedule.parseScheduleCsv("2026-02-02,unknown,Palackého,0", ["bio"]));

const release = {
    sites: [
        {
            id: "near-current",
            locality: "Litovel",
            name: "Blízké stanoviště",
            coordinates: { latitude: 49.7, longitude: 17.07, accuracy: "precise" },
        },
        {
            id: "far-current",
            locality: "Litovel",
            name: "Vzdálené stanoviště",
            coordinates: { latitude: 49.75, longitude: 17.15, accuracy: "precise" },
        },
        {
            id: "future",
            locality: "Unčovice",
            name: "u hasičárny",
            coordinates: { latitude: 49.71, longitude: 17.08, accuracy: "provisional" },
        },
    ],
    placements: [
        { site_id: "near-current", date_from: "2026-08-21", date_through: "2026-08-24" },
        { site_id: "far-current", date_from: "2026-08-21", date_through: "2026-08-24" },
        { site_id: "future", date_from: "2026-08-28", date_through: "2026-08-31" },
        { site_id: "future", date_from: "2026-09-25", date_through: "2026-09-28" },
    ],
    collection_yard: {
        name: "Sběrný dvůr Litovel",
        coordinates: { latitude: 49.68, longitude: 17.05, accuracy: "precise" },
    },
};
const origin = { latitude: 49.7, longitude: 17.07 };
const current = bio.nearestBioOptions(release, origin, "2026-08-22", 3);
assert.deepEqual(current.current.map(item => item.site.id), ["near-current", "far-current"]);
assert.deepEqual(current.upcoming.map(item => item.site.id), ["future"]);
assert.equal(current.upcoming[0].placement.date_from, "2026-08-28");
assert.equal(current.upcoming[0].approximate, true);
assert.equal(current.collectionYard.name, "Sběrný dvůr Litovel");

const future = bio.nearestBioOptions(release, origin, "2026-08-25", 3);
assert.equal(future.current.length, 0);
assert.deepEqual(future.upcoming.map(item => item.site.id), ["future"]);
assert.equal(bio.formatDistance(0.123, true), "cca 100 m");
assert.equal(bio.formatDistance(1.26, false), "1,3 km");
assert.ok(bio.haversineDistanceKm(origin, origin) < 0.000001);

const expired = bio.nearestBioOptions(release, origin, "2027-01-01", 3);
assert.equal(expired.current.length, 0);
assert.equal(expired.upcoming.length, 0);
assert.equal(expired.unavailable.length, 3);

console.log("validated calendar and bio frontend logic");
