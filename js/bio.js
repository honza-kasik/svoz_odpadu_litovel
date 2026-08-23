function bioNormalize(value) {
    return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function bioRank(item, query) {
    const label = bioNormalize(item.label);
    if (label === query) return 0;
    if (label.startsWith(query)) return 1;
    return 2;
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

    function select(item) {
        window.location.href = item.url;
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
        const grouped = ["site", "location"].map(type =>
            matches.filter(item => item.type === type).slice(0, 10)
        );
        rendered = grouped.flat();
        suggestions.innerHTML = "";
        activeIndex = -1;
        if (!rendered.length) {
            const empty = document.createElement("p");
            empty.className = "bio-suggestion-empty";
            empty.textContent = "Nenalezeno žádné stanoviště ani lokalita.";
            suggestions.appendChild(empty);
        } else {
            [
                [grouped[0], "Stanoviště"],
                [grouped[1], "Ulice a místní části"],
            ].forEach(([group, heading]) => {
                if (!group.length) return;
                const label = document.createElement("div");
                label.className = "bio-suggestion-group";
                label.textContent = heading;
                suggestions.appendChild(label);
                group.forEach(item => {
                    const option = document.createElement("div");
                    option.id = `bio-option-${suggestions.querySelectorAll('[role="option"]').length}`;
                    option.setAttribute("role", "option");
                    option.setAttribute("aria-selected", "false");
                    option.textContent = item.label;
                    option.addEventListener("mousedown", event => event.preventDefault());
                    option.addEventListener("click", () => select(item));
                    suggestions.appendChild(option);
                });
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
}
