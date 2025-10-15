const translations = {
  ko: {
    title: "현재 시각 타이머",
    mapHint: "지도 위 도시를 클릭해 시간대를 바꿔보세요.",
    languageButton: "English",
    languageAria: "영어로 전환",
    day: "낮",
    night: "밤",
    msSuffix: "밀리초",
    period: { AM: "오전", PM: "오후" },
    selectPrompt: (name) => `${name} 시간대로 변경`,
    glanceActive: "선택됨",
  },
  en: {
    title: "World Timer",
    mapHint: "Click a city to change the timezone.",
    languageButton: "한국어",
    languageAria: "Switch to Korean",
    day: "Day",
    night: "Night",
    msSuffix: "ms",
    period: { AM: "AM", PM: "PM" },
    selectPrompt: (name) => `Switch to ${name} timezone`,
    glanceActive: "Active",
  },
};

const cityData = [
  {
    id: "seoul",
    names: { ko: "서울", en: "Seoul" },
    timeZone: "Asia/Seoul",
    coords: { x: 78, y: 42 },
  },
  {
    id: "tokyo",
    names: { ko: "도쿄", en: "Tokyo" },
    timeZone: "Asia/Tokyo",
    coords: { x: 83, y: 41 },
  },
  {
    id: "sydney",
    names: { ko: "시드니", en: "Sydney" },
    timeZone: "Australia/Sydney",
    coords: { x: 90, y: 70 },
  },
  {
    id: "dubai",
    names: { ko: "두바이", en: "Dubai" },
    timeZone: "Asia/Dubai",
    coords: { x: 64, y: 48 },
  },
  {
    id: "mumbai",
    names: { ko: "뭄바이", en: "Mumbai" },
    timeZone: "Asia/Kolkata",
    coords: { x: 69, y: 50 },
  },
  {
    id: "london",
    names: { ko: "런던", en: "London" },
    timeZone: "Europe/London",
    coords: { x: 47, y: 35 },
  },
  {
    id: "newyork",
    names: { ko: "뉴욕", en: "New York" },
    timeZone: "America/New_York",
    coords: { x: 29, y: 40 },
  },
  {
    id: "saopaulo",
    names: { ko: "상파울루", en: "São Paulo" },
    timeZone: "America/Sao_Paulo",
    coords: { x: 36, y: 60 },
  },
];

const state = {
  language: "ko",
  selectedCity: cityData.find((city) => city.id === "seoul") ?? cityData[0],
  previousSecond: null,
  previousMinute: null,
};

const dom = {
  root: document.querySelector("[data-app-root]"),
  title: document.querySelector("[data-i18n='title']"),
  mapHint: document.querySelector("[data-i18n='mapHint']"),
  languageToggle: document.getElementById("languageToggle"),
  period: document.getElementById("period"),
  time: document.getElementById("time"),
  milliseconds: document.getElementById("milliseconds"),
  timezoneLabel: document.getElementById("timezoneLabel"),
  utcOffset: document.getElementById("utcOffset"),
  cityMarkers: document.getElementById("cityMarkers"),
  cityGlance: document.getElementById("cityGlance"),
  mapWrapper: document.getElementById("mapWrapper"),
  clockPanel: document.querySelector(".clock-panel"),
};

const cityElements = new Map();
const cityCards = new Map();
const timeFormatterCache = new Map();
const offsetFormatterCache = new Map();

function getTimeFormatter(timeZone) {
  if (!timeFormatterCache.has(timeZone)) {
    timeFormatterCache.set(
      timeZone,
      new Intl.DateTimeFormat("en-US", {
        timeZone,
        hour12: true,
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      }),
    );
  }
  return timeFormatterCache.get(timeZone);
}

function getOffsetFormatter(timeZone) {
  if (!offsetFormatterCache.has(timeZone)) {
    offsetFormatterCache.set(
      timeZone,
      new Intl.DateTimeFormat("en-US", {
        timeZone,
        timeZoneName: "shortOffset",
        hour: "2-digit",
        minute: "2-digit",
      }),
    );
  }
  return offsetFormatterCache.get(timeZone);
}

function getTimeParts(date, timeZone) {
  const parts = getTimeFormatter(timeZone).formatToParts(date);
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const rawHour = parseInt(lookup.hour, 10);
  const period = (lookup.dayPeriod || "AM").toUpperCase();
  const minute = lookup.minute;
  const second = lookup.second;
  const hour12 = Number.isNaN(rawHour) ? 0 : rawHour;
  const hour24 =
    period === "PM"
      ? hour12 === 12
        ? 12
        : hour12 + 12
      : hour12 === 12
        ? 0
        : hour12;
  return {
    hourDisplay: String(hour12).padStart(2, "0"),
    minute,
    second,
    period,
    hour24,
  };
}

function getOffsetString(date, timeZone) {
  try {
    const formatter = getOffsetFormatter(timeZone);
    const parts = formatter.formatToParts(date);
    const tzName = parts.find((part) => part.type === "timeZoneName");
    if (tzName && tzName.value) {
      return tzName.value.replace("GMT", "UTC");
    }
  } catch (error) {
    // Ignore and fall back below.
  }
  const utcDate = new Date(date.toLocaleString("en-US", { timeZone }));
  const offsetMinutes = (utcDate.getTime() - date.getTime()) / 60000;
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absolute / 60)).padStart(2, "0");
  const minutes = String(Math.floor(absolute % 60)).padStart(2, "0");
  return `UTC${sign}${hours}:${minutes}`;
}

function createCityMarkers() {
  cityData.forEach((city) => {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "city-marker";
    marker.style.left = `${city.coords.x}%`;
    marker.style.top = `${city.coords.y}%`;
    marker.dataset.cityId = city.id;

    const dot = document.createElement("span");
    dot.className = "marker-dot";

    const name = document.createElement("span");
    name.className = "city-name";
    name.textContent = city.names[state.language];

    const daystate = document.createElement("span");
    daystate.className = "city-daystate";

    marker.append(dot, name, daystate);
    marker.addEventListener("click", () => {
      setSelectedCity(city);
    });

    dom.cityMarkers.appendChild(marker);
    cityElements.set(city.id, { marker, name, state: daystate });
  });
}

function createCityCards() {
  dom.cityGlance.setAttribute("role", "list");
  cityData.forEach((city) => {
    const card = document.createElement("div");
    card.className = "glance-card";
    card.dataset.cityId = city.id;
    card.setAttribute("role", "listitem");

    const header = document.createElement("div");
    header.className = "glance-header";

    const cityName = document.createElement("span");
    cityName.className = "glance-city";
    cityName.textContent = city.names[state.language];

    const stateLabel = document.createElement("span");
    stateLabel.className = "glance-state";

    header.append(cityName, stateLabel);

    const timeValue = document.createElement("div");
    timeValue.className = "glance-time";

    const periodLabel = document.createElement("span");
    periodLabel.className = "glance-period";

    card.append(header, timeValue, periodLabel);
    dom.cityGlance.appendChild(card);

    cityCards.set(city.id, {
      card,
      cityName,
      stateLabel,
      timeValue,
      periodLabel,
    });
  });
}

function applyLanguage() {
  const lang = state.language;
  const copy = translations[lang];
  document.documentElement.lang = lang;
  document.title = copy.title;
  dom.title.textContent = copy.title;
  dom.mapHint.textContent = copy.mapHint;
  dom.languageToggle.textContent = copy.languageButton;
  dom.languageToggle.setAttribute("aria-label", copy.languageAria);
}

function setSelectedCity(city) {
  state.selectedCity = city;
  state.previousMinute = null;
  state.previousSecond = null;

  cityElements.forEach(({ marker }, cityId) => {
    const isActive = cityId === city.id;
    marker.classList.toggle("is-active", isActive);
    marker.setAttribute("aria-pressed", String(isActive));
  });

  cityCards.forEach(({ card }, cityId) => {
    const isActive = cityId === city.id;
    card.classList.toggle("is-active", isActive);
  });

  updateClock();
}

function formatMs(date) {
  return String(date.getMilliseconds()).padStart(3, "0");
}

function triggerAnimation(element, className) {
  element.classList.remove(className);
  // Reflow to restart the animation.
  void element.offsetWidth;
  element.classList.add(className);
}

function updateDayNightOverlay(date) {
  const minutes = date.getUTCHours() * 60 + date.getUTCMinutes() + date.getUTCSeconds() / 60;
  const fraction = minutes / (24 * 60);
  let sunLongitude = fraction * 360 - 180;
  sunLongitude = ((sunLongitude + 540) % 360) - 180;
  const position = ((sunLongitude + 180) / 360) * 100;
  dom.mapWrapper.style.setProperty("--day-center", `${position}%`);
}

function updateCityVisuals(now) {
  const lang = state.language;
  const copy = translations[lang];

  cityData.forEach((city) => {
    const info = getTimeParts(now, city.timeZone);
    const isDay = info.hour24 >= 6 && info.hour24 < 18;
    const markerRefs = cityElements.get(city.id);
    const cardRefs = cityCards.get(city.id);

    if (markerRefs) {
      markerRefs.marker.classList.toggle("is-day", isDay);
      markerRefs.marker.classList.toggle("is-night", !isDay);
      markerRefs.name.textContent = city.names[lang];
      markerRefs.state.textContent = copy[isDay ? "day" : "night"];
      markerRefs.marker.setAttribute("aria-label", copy.selectPrompt(city.names[lang]));
    }

    if (cardRefs) {
      cardRefs.card.classList.toggle("is-day", isDay);
      cardRefs.card.classList.toggle("is-night", !isDay);
      cardRefs.cityName.textContent = city.names[lang];
      cardRefs.stateLabel.textContent = `${copy[isDay ? "day" : "night"]}${
        state.selectedCity.id === city.id ? ` · ${copy.glanceActive}` : ""
      }`;
      cardRefs.timeValue.textContent = `${info.hourDisplay}:${info.minute}:${info.second}`;
      cardRefs.periodLabel.textContent = copy.period[info.period] ?? info.period;
    }
  });
}

function updateClock() {
  const now = new Date();
  const lang = state.language;
  const copy = translations[lang];
  const city = state.selectedCity;
  const info = getTimeParts(now, city.timeZone);

  dom.period.textContent = copy.period[info.period] ?? info.period;
  const formattedTime = `${info.hourDisplay}:${info.minute}:${info.second}`;
  dom.time.textContent = formattedTime;
  dom.milliseconds.textContent = `${formatMs(now)} ${copy.msSuffix}`;
  dom.timezoneLabel.textContent = city.names[lang];
  dom.utcOffset.textContent = getOffsetString(now, city.timeZone);

  const secondNumber = parseInt(info.second, 10);
  if (state.previousSecond !== secondNumber) {
    triggerAnimation(dom.time, "tick-second");
    state.previousSecond = secondNumber;
  }

  const minuteNumber = parseInt(info.minute, 10);
  if (state.previousMinute !== minuteNumber) {
    triggerAnimation(dom.clockPanel, "tick-minute");
    state.previousMinute = minuteNumber;
  }

  updateDayNightOverlay(now);
  updateCityVisuals(now);
}

function toggleLanguage() {
  state.language = state.language === "ko" ? "en" : "ko";
  applyLanguage();
  updateClock();
}

function init() {
  if (!dom.root) {
    return;
  }
  createCityMarkers();
  createCityCards();
  applyLanguage();
  dom.languageToggle.addEventListener("click", toggleLanguage);
  setSelectedCity(state.selectedCity);

  const tick = () => {
    updateClock();
    window.requestAnimationFrame(tick);
  };
  window.requestAnimationFrame(tick);
}

init();
