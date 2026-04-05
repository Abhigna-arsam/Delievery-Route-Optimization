function initializeEnhancements(distance) {

    // Carbon calculation (frontend simulation)
    const mileage = 15;
    const co2Rate = 2.31;

    const fuel = (distance / mileage).toFixed(2);
    const co2 = (fuel * co2Rate).toFixed(2);
    const score = Math.min(100, 75 + Math.floor(co2 / 5));

    document.getElementById("fuelValue").innerText = fuel + " L";
    document.getElementById("co2Value").innerText = co2 + " kg";
    document.getElementById("scoreValue").innerText = score;

    // ETA simulation
    const hour = new Date().getHours();
    const peak = (hour >= 8 && hour <= 10) || (hour >= 17 && hour <= 19);

    const traffic = peak ? 1.5 : 1.1;
    const eta = ((distance / 40) * 60 * traffic).toFixed(1);

    document.getElementById("etaValue").innerText = eta;
    document.getElementById("peakInfo").innerText =
        peak ? "Peak hour traffic applied" : "Normal traffic conditions";

    // Dummy analytics graph (static image)
    document.getElementById("analyticsGraph").src =
        "https://dummyimage.com/600x300/cccccc/000000&text=Efficiency+Graph";
}
