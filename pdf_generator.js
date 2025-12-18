async function generateWasteCalendarPDF(events, year, month = null, locationName = null) {
    await loadScriptOnce("https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"); 
    await loadScriptOnce("resources/Caladea-Regular-normal.js")

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ unit: "mm", format: "a4" });

    pdf.addFileToVFS('Caladea-Regular-normal.ttf', font);
    pdf.addFont('Caladea-Regular-normal.ttf', 'Caladea-Regular', 'normal');
    pdf.setFont("Caladea-Regular")

    // =====================================================================
    //                      MESICNI KALENDAR
    // =====================================================================
    // global WASTE_TYPES (preklad typu na jmena) - required
    // global MONTHS (jmena mesicu) - required
    function drawMonthlyCalendar(monthIndex, locationName) {
        const left = 10;
        const top = 20;
        const cellW = (190 / 7);
        const cellH = 22;

        pdf.setFontSize(22);
        pdf.text(`Svoz odpadu ${locationName} – ${MONTHS[monthIndex].toLowerCase()} ${year}`, left, top);
        pdf.setFontSize(8);
        pdf.text('vytvořeno pomocí svoz.litovle.cz', left, top + 5);

        pdf.setFontSize(12);
        let y = top + 10;
        let x = left;

        // záhlaví
        for (let i = 0; i < 7; i++) {
            pdf.text(DAYS[i], x + 3, y);
            x += cellW;
        }

        y += 5;

        const start = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
        const days = new Date(year, monthIndex + 1, 0).getDate();

        let d = 1;
        let row = 0;

        while (d <= days) {
            x = left;

            for (let col = 0; col < 7; col++) {
                const cellX = x;
                const cellY = y + row * cellH;

                pdf.rect(cellX, cellY, cellW, cellH);

                if (row === 0 && col < start) {
                    x += cellW;
                    continue;
                }

                if (d > days) break;

                // číslo dne
                pdf.setFontSize(11);
                pdf.text(String(d), cellX + 2, cellY + 5);

                // svozy
                pdf.setFontSize(9);
                const evs = events.filter(ev => {
                    const dt = new Date(ev.date);
                    return (
                        dt.getFullYear() === year &&
                        dt.getMonth() === monthIndex &&
                        dt.getDate() === d
                    );
                });

                let yy = cellY + 10;
                evs.forEach(e => {
                    const padding = 1;
                    const rectY = yy - 4; // trochu nad textem
                    const rectH = 5; // výška pozadí
                    pdf.setFillColor(getBackgroundColorForType(e.type));
                    pdf.rect(cellX + padding, rectY, cellW - 2*padding, rectH, "F");

                    // nakresli text doprostřed pozadí
                    pdf.setFontSize(9);
                    const textColor = pdf.getTextColor();
                    pdf.setTextColor(getTextColorForType(e.type));
                    pdf.text(WASTE_TYPES[e.type], cellX + cellW/2, rectY + rectH/2, { align: "center", baseline: "middle" });
                    pdf.setTextColor(textColor);

                    yy += rectH + 1; // odsazení pro další event
                });

                d++;
                x += cellW;
            }
            row++;
        }

        drawFooter(pdf);
    }

    // =====================================================================
    //                            ROCNI
    // =====================================================================
    // global DAYS - jmena dnu, required
    function drawYearCalendar(pdf, events, year, locationName) {
        const margin = 5;
        const topOffset = 20; // prostor pro nadpis


        const pageW = pdf.internal.pageSize.width;
        const pageH = pdf.internal.pageSize.height;

        const monthCols = 3;
        const monthRows = 4;
        const monthW = (pageW - 20 - (monthCols - 1) * margin) / monthCols;
        const monthH = (pageH - 20 - topOffset - (monthRows - 1) * margin) / monthRows;

        // nadpis
        pdf.setFontSize(18);
        pdf.text(`Svoz odpadu ${locationName} – ${year}`, pageW / 2, 15, { align: "center" });
        pdf.setFontSize(8);
        pdf.text('vytvořeno pomocí svoz.litovle.cz', pageW / 2, 19, {align: "center"});

        for (let m = 0; m < 12; m++) {
            const col = m % monthCols;
            const row = Math.floor(m / monthCols);
            const x0 = 10 + col * (monthW + margin);
            const y0 = topOffset + row * (monthH + margin);

            // měsíc
            pdf.setFontSize(14);
            pdf.text(MONTHS[m], x0 + monthW/2, y0 + 8, { align: "center" });

            const cellW = monthW / 7;
            const cellH = (monthH - 12) / 6; // odečíst místo pro název a dny v týdnu

            // dny v týdnu
            pdf.setFontSize(9);
            for (let d = 0; d < 7; d++) {
                pdf.text(DAYS[d], x0 + d*cellW + cellW/2, y0 + 15, { align: "center", baseline: "middle" });
            }

            const first = new Date(year, m, 1).getDay() || 7;
            let day = 1;
            const daysInMonth = new Date(year, m+1, 0).getDate();

            for (let r = 0; r < 6; r++) {
                for (let c = 0; c < 7; c++) {
                    const cellX = x0 + c * cellW;
                    const cellY = y0 + 20 + r * cellH;

                    if ((r === 0 && c + 1 < first) || day > daysInMonth) continue;

                    const evs = events.filter(ev => {
                        const dt = new Date(ev.date);
                        return dt.getFullYear() === year &&
                            dt.getMonth() === m &&
                            dt.getDate() === day;
                    });

                    // pozadí podle typu
                    if (evs.length === 1) {
                        const type = evs[0].type;
                        pdf.setFillColor(getBackgroundColorForType(type));
                        pdf.rect(cellX, cellY, cellW, cellH, "F");
                    } else if (evs.length === 2) {
                        // dvě události → rozděl buňku diagonálně nebo horizontálně
                        const type1 = evs[0].type;
                        const type2 = evs[1].type;

                        // horizontální poloviny
                        pdf.setFillColor(getBackgroundColorForType(type1));
                        pdf.rect(cellX, cellY, cellW, cellH/2, "F"); // horní polovina

                        pdf.setFillColor(getBackgroundColorForType(type2));
                        pdf.rect(cellX, cellY + cellH/2, cellW, cellH/2, "F"); // dolní polovina
                    } else {
                        //TODO 3 a více událostí - resit az nastane
                    }

                    pdf.rect(cellX, cellY, cellW, cellH);

                    drawDateInYearCalendarCell(pdf, day, cellX, cellY, cellW, cellH)

                    day++;
                }
            }
        }

        drawFooter(pdf);
    }

    function drawDateInYearCalendarCell(pdf, day, cellX, cellY, cellW, cellH) {
        const originalTextColor = pdf.getTextColor()
        const x = cellX + cellW/2;
        const y = cellY + cellH/2;
        const radius = Math.min(cellW, cellH)/3.5;

        // bílý kruh pro kontrast
        pdf.setFillColor(255,255,255);
        pdf.circle(x, y, radius, "F");

        // číslo dne
        pdf.setFont("Caladea-Regular", "normal");
        pdf.setFontSize(10);
        pdf.setTextColor(0,0,0);
        pdf.text(String(day), x, y, { align: "center", baseline: "middle" });
        pdf.setTextColor(originalTextColor);
    }

    function drawFooter(pdf) {
        const date = new Date();
        const formatted =
            `Sestaveno z aktuálních dat ${date.toLocaleDateString()} v ${date.getHours()}:${String(date.getMinutes()).padStart(2,'0')}. Neobsahuje změny svozu po tomto datu.`;

        const pageW = pdf.internal.pageSize.width;
        const pageH = pdf.internal.pageSize.height;

        pdf.setFontSize(8);
        pdf.setTextColor('#747474');
        pdf.text(formatted, pageW / 2, pageH - 8, { align: "center" });
    }

    // =====================================================================
    //                           SPUŠTĚNÍ
    // =====================================================================

    if (month !== null) {
        drawMonthlyCalendar(month, locationName);
        pdf.save(`kalendar_svoz_${year}_${month}_${locationName}.pdf`);
    } else {
        drawYearCalendar(pdf, events, year, locationName);
        pdf.save(`kalendar_svoz_${year}_${locationName}.pdf`);
    }
}

const loadedScripts = new Set();

function loadScriptOnce(src) {
    return new Promise((resolve, reject) => {
        if (loadedScripts.has(src)) {
            resolve();
            return;
        }

        const s = document.createElement("script");
        s.src = src;
        s.async = true;

        s.onload = () => {
            loadedScripts.add(src);
            resolve();
        };

        s.onerror = reject;

        document.head.appendChild(s);
    });
}

function getBackgroundColorForType(type) {
    if (type === null) {
        type = '';
    }
    switch (type.toLowerCase()) {
        case "plastics": return '#ffd900';
        case "paper": return '#0044ff';
        case "bio": return '#683200';
        case "generic": '#000000';
        default: return '#000000'; // fallback
    }
}

function getTextColorForType(type) {
    if (type === null) {
        type = '';
    }
    switch (type.toLowerCase()) {
        case "plastics": return '#000000';
        case "paper": return  '#ffffff';
        case "bio": return  '#ffffff';
        case "generic": '#ffffff';
        default: return '#ffffff'; // fallback
    }
}


async function waitForFont(pdf, fontName, style = "normal", timeout = 3000) {
    const interval = 10; // ms
    const maxTries = timeout / interval;
    let tries = 0;

    while (tries < maxTries) {
        const fontList = pdf.getFontList();
        if (fontList[fontName] && fontList[fontName].includes(style)) {
            return; // font registered
        }
        await new Promise(r => setTimeout(r, interval));
        tries++;
    }
    throw new Error(`Font "${fontName}" not registered after ${timeout}ms`);
}
