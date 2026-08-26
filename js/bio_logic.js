(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    } else {
        root.SVOZ_BIO_LOGIC = api;
    }
}(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    function haversineDistanceKm(first, second) {
        const radius = 6371.0088;
        const radians = value => value * Math.PI / 180;
        const lat1 = radians(first.latitude);
        const lon1 = radians(first.longitude);
        const lat2 = radians(second.latitude);
        const lon2 = radians(second.longitude);
        const deltaLat = lat2 - lat1;
        const deltaLon = lon2 - lon1;
        const value = Math.sin(deltaLat / 2) ** 2
            + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
        return radius * 2 * Math.asin(Math.sqrt(value));
    }

    function nearestBioOptions(release, position, referenceDate, limit = 3) {
        if (!release || !Array.isArray(release.sites) || !Array.isArray(release.placements)) {
            throw new Error("Invalid bio schedule");
        }
        if (!/^\d{4}-\d{2}-\d{2}$/.test(referenceDate)) {
            throw new Error("Invalid reference date");
        }
        const sites = new Map(release.sites.map(site => [site.id, site]));
        const current = release.placements.filter(
            placement => placement.date_from <= referenceDate && referenceDate <= placement.date_through
        );
        const currentSiteIds = new Set(current.map(placement => placement.site_id));
        const nextBySite = new Map();
        release.placements.forEach(placement => {
            if (placement.date_from <= referenceDate || currentSiteIds.has(placement.site_id)) return;
            const previous = nextBySite.get(placement.site_id);
            if (!previous || placement.date_from < previous.date_from) {
                nextBySite.set(placement.site_id, placement);
            }
        });

        const currentResults = nearestDistinct(current, sites, position, "current", limit);
        const upcomingResults = nearestDistinct(
            [...nextBySite.values()], sites, position, "upcoming", limit
        );
        let unavailableResults = [];
        if (!currentResults.length && !upcomingResults.length) {
            const latestBySite = new Map();
            release.placements.forEach(placement => {
                const previous = latestBySite.get(placement.site_id);
                if (!previous || placement.date_through > previous.date_through) {
                    latestBySite.set(placement.site_id, placement);
                }
            });
            unavailableResults = nearestDistinct(
                [...latestBySite.values()], sites, position, "schedule-unavailable", limit
            );
        }
        return {
            current: currentResults,
            upcoming: upcomingResults,
            unavailable: unavailableResults,
            collectionYard: release.collection_yard || null,
        };
    }

    function nearestDistinct(placements, sites, position, status, limit) {
        const seen = new Set();
        const results = [];
        placements.forEach(placement => {
            if (seen.has(placement.site_id)) return;
            seen.add(placement.site_id);
            const site = sites.get(placement.site_id);
            if (!site || !validCoordinates(site.coordinates)) return;
            results.push({
                placement,
                site,
                status,
                distanceKm: haversineDistanceKm(position, site.coordinates),
                approximate: site.coordinates.accuracy !== "precise",
            });
        });
        return results
            .sort((a, b) => a.distanceKm - b.distanceKm || a.site.id.localeCompare(b.site.id))
            .slice(0, limit);
    }

    function validCoordinates(value) {
        return value
            && Number.isFinite(value.latitude)
            && Number.isFinite(value.longitude)
            && value.latitude >= -90 && value.latitude <= 90
            && value.longitude >= -180 && value.longitude <= 180;
    }

    function formatDistance(distanceKm, approximate) {
        const prefix = approximate ? "cca " : "";
        if (distanceKm < 1) {
            return `${prefix}${Math.round(distanceKm * 1000 / 50) * 50} m`;
        }
        return `${prefix}${distanceKm.toFixed(1).replace(".", ",")} km`;
    }

    return { haversineDistanceKm, nearestBioOptions, formatDistance };
}));
