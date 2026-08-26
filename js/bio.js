function bioNormalize(value) {
    return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function bioRank(item, query) {
    const label = bioNormalize(item.label);
    const typeRank = item.type === "location" ? 0 : 1;
    if (label === query) return typeRank;
    if (label.startsWith(query)) return 2 + typeRank;
    return 4 + typeRank;
}

function bioPragueToday() {
    const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: "Europe/Prague",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
}

function bioDate(isoDate, includeWeekday = false) {
    const date = new Date(`${isoDate}T12:00:00Z`);
    return new Intl.DateTimeFormat("cs-CZ", {
        timeZone: "Europe/Prague",
        weekday: includeWeekday ? "long" : undefined,
        day: "numeric",
        month: "numeric",
        year: "numeric",
    }).format(date);
}

function bioSiteName(site) {
    if (site.locality === "Litovel" || site.name === site.locality) return site.name;
    return `${site.locality} – ${site.name}`;
}

function bioMapUrl(coordinates) {
    const latitude = coordinates.latitude.toFixed(6);
    const longitude = coordinates.longitude.toFixed(6);
    return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=18/${latitude}/${longitude}`;
}

function buildBioLocationCard(item) {
    const card = document.createElement("article");
    card.className = "nearby-bio-card";

    const marker = document.createElement("div");
    marker.className = `nearby-bio-marker nearby-bio-marker-${item.status}`;
    marker.setAttribute("aria-hidden", "true");
    marker.textContent = "●";

    const site = document.createElement("div");
    site.className = "nearby-bio-site";
    const strong = document.createElement("strong");
    const siteLink = document.createElement("a");
    siteLink.href = `/bio/stanoviste/${encodeURIComponent(item.site.id)}/`;
    siteLink.textContent = bioSiteName(item.site);
    strong.appendChild(siteLink);
    const date = document.createElement("span");
    date.textContent = item.status === "current"
        ? `Odvoz: ${bioDate(item.placement.date_through, true)}`
        : `Přistavení: ${bioDate(item.placement.date_from)}, odvoz: ${bioDate(item.placement.date_through)}`;
    site.append(strong, date);

    const distance = document.createElement("div");
    distance.className = "nearby-bio-distance";
    distance.textContent = window.SVOZ_BIO_LOGIC.formatDistance(item.distanceKm, item.approximate);
    card.append(marker, site, distance);

    if (item.site.coordinates.accuracy === "precise") {
        const map = document.createElement("a");
        map.className = "nearby-bio-map";
        map.href = bioMapUrl(item.site.coordinates);
        map.target = "_blank";
        map.rel = "noopener";
        map.textContent = "Mapa";
        card.appendChild(map);
    }
    return card;
}

function renderBioLocationOptions(container, options) {
    container.innerHTML = "";
    const current = options.current;
    const upcoming = options.upcoming;

    if (current.length) {
        const heading = document.createElement("h3");
        heading.textContent = "Nejbližší přistavené kontejnery";
        const list = document.createElement("div");
        list.className = "nearby-bio-list ui-data-list";
        current.forEach(item => list.appendChild(buildBioLocationCard(item)));
        container.append(heading, list);
        return;
    }

    const status = document.createElement("p");
    status.textContent = "Právě nyní není přistaven žádný kontejner.";
    container.appendChild(status);

    if (upcoming.length) {
        const heading = document.createElement("h3");
        heading.textContent = "Nejbližší další přistavení";
        const list = document.createElement("div");
        list.className = "nearby-bio-list ui-data-list";
        upcoming.forEach(item => list.appendChild(buildBioLocationCard(item)));
        container.append(heading, list);
        return;
    }

    if (options.collectionYard?.coordinates) {
        const fallback = document.createElement("p");
        fallback.append("Větší množství bioodpadu můžete odevzdat ");
        const map = document.createElement("a");
        map.href = bioMapUrl(options.collectionYard.coordinates);
        map.target = "_blank";
        map.rel = "noopener";
        map.textContent = "ve sběrném dvoře";
        fallback.append(map, ".");
        container.appendChild(fallback);
    }
}

function getBioPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("unsupported"));
            return;
        }
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 300000,
        });
    });
}

function bioLocationErrorMessage(error) {
    if (error?.code === 1) return "Přístup k poloze nebyl povolen. Zadejte ulici nebo místní část výše.";
    if (error?.code === 2) return "Polohu se nepodařilo zjistit. Zadejte ulici nebo místní část výše.";
    if (error?.code === 3) return "Zjištění polohy trvalo příliš dlouho. Zkuste to znovu nebo zadejte ulici.";
    if (error?.message === "unsupported") return "Tento prohlížeč zjištění polohy nepodporuje. Zadejte ulici nebo místní část výše.";
    return "Nejbližší kontejnery se nepodařilo načíst. Zkuste to znovu.";
}

function initializeBioLocation() {
    const button = document.getElementById("bioUseLocation");
    const result = document.getElementById("bioLocationResult");
    if (!button || !result) return;

    button.addEventListener("click", async () => {
        button.disabled = true;
        result.classList.add("loading");
        result.textContent = "Zjišťuji nejbližší kontejnery…";
        try {
            if (!window.SVOZ_BIO_LOGIC) throw new Error("Bio location logic is unavailable");
            const [position, response] = await Promise.all([
                getBioPosition(),
                fetch("/bio_schedule.json", { cache: "no-cache" }),
            ]);
            if (!response.ok) throw new Error(`Bio schedule request failed: ${response.status}`);
            const release = await response.json();
            const options = window.SVOZ_BIO_LOGIC.nearestBioOptions(
                release,
                {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                },
                bioPragueToday(),
                3,
            );
            renderBioLocationOptions(result, options);
        } catch (error) {
            console.error("Failed to locate nearby bio containers:", error);
            result.textContent = bioLocationErrorMessage(error);
        } finally {
            result.classList.remove("loading");
            button.disabled = false;
        }
    });
}

function initializeBioFinder() {
    const input = document.getElementById("bioSearch");
    const suggestions = document.getElementById("bioSuggestions");
    const finder = document.getElementById("bioFinder");
    const items = Array.isArray(window.BIO_SEARCH_ITEMS) ? window.BIO_SEARCH_ITEMS : [];
    let activeIndex = -1;
    let rendered = [];

    function close() {
        suggestions.innerHTML = "";
        suggestions.hidden = true;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        activeIndex = -1;
    }

    function setActive(index) {
        const options = [...suggestions.querySelectorAll('[role="option"]')];
        if (!options.length) return;
        activeIndex = (index + options.length) % options.length;
        options.forEach((option, optionIndex) => {
            option.classList.toggle("active", optionIndex === activeIndex);
            option.setAttribute("aria-selected", optionIndex === activeIndex ? "true" : "false");
        });
        input.setAttribute("aria-activedescendant", options[activeIndex].id);
        options[activeIndex].scrollIntoView({ block: "nearest" });
    }

    function render() {
        const query = bioNormalize(input.value);
        const matches = items
            .filter(item => !query || bioNormalize(item.label).includes(query))
            .sort((a, b) => bioRank(a, query) - bioRank(b, query) || a.label.localeCompare(b.label, "cs"));
        rendered = query
            ? matches.slice(0, 20)
            : [
                ...matches.filter(item => item.type === "location").slice(0, 10),
                ...matches.filter(item => item.type === "site").slice(0, 10),
            ];
        suggestions.innerHTML = "";
        activeIndex = -1;
        if (!rendered.length) {
            const empty = document.createElement("p");
            empty.className = "bio-suggestion-empty";
            empty.textContent = "Nenalezeno žádné stanoviště ani lokalita.";
            suggestions.appendChild(empty);
        } else {
            rendered.forEach(item => {
                const option = document.createElement("a");
                option.id = `bio-option-${suggestions.querySelectorAll('[role="option"]').length}`;
                option.href = item.url;
                option.setAttribute("role", "option");
                option.setAttribute("aria-selected", "false");

                const label = document.createElement("span");
                label.className = "bio-suggestion-label";
                label.textContent = item.label;

                const action = document.createElement("span");
                action.className = "bio-suggestion-action";
                action.textContent = item.type === "location"
                    ? "Najít nejbližší kontejnery v okolí"
                    : "Zobrazit konkrétní stanoviště a termíny";

                option.append(label, action);
                option.addEventListener("mousedown", event => event.preventDefault());
                suggestions.appendChild(option);
            });
        }
        suggestions.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    input.addEventListener("input", render);
    input.addEventListener("focus", render);
    input.addEventListener("keydown", event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setActive(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
        } else if (event.key === "Enter" && activeIndex >= 0) {
            event.preventDefault();
            const options = [...suggestions.querySelectorAll('[role="option"]')];
            options[activeIndex]?.click();
        } else if (event.key === "Escape") {
            close();
        }
    });
    document.addEventListener("click", event => {
        if (!finder.contains(event.target)) close();
    });
    close();
}

if (document.querySelector(".bio-page:not(.bio-detail-page)")) {
    initializeBioFinder();
    initializeBioLocation();
}
