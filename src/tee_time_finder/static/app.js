const MINUTES_MIN = 300;
const MINUTES_MAX = 1200;
const RESULTS_PER_PAGE = 15;

const state = {
  courses: [],
  hasSearched: false,
  results: [],
  currentPage: 1,
};

const elements = {
  form: document.querySelector("#search-form"),
  dateInput: document.querySelector("#date-input"),
  playersSegmented: document.querySelector("#players-segmented"),
  timeStart: document.querySelector("#time-start"),
  timeEnd: document.querySelector("#time-end"),
  timeStartChip: document.querySelector("#time-start-chip"),
  timeEndChip: document.querySelector("#time-end-chip"),
  rangeTrack: document.querySelector("#range-track"),
  courseGroups: document.querySelector("#course-groups"),
  selectedCourseCount: document.querySelector("#selected-course-count"),
  searchButton: document.querySelector("#search-button"),
  allOnButton: document.querySelector("#all-on-button"),
  allOffButton: document.querySelector("#all-off-button"),
  resultsTitle: document.querySelector("#results-title"),
  resultsMeta: document.querySelector("#results-meta"),
  resultsWindowChip: document.querySelector("#results-window-chip"),
  resultsHolesChip: document.querySelector("#results-holes-chip"),
  statusBanner: document.querySelector("#status-banner"),
  resultsGrid: document.querySelector("#results-grid"),
  resultsPagination: document.querySelector("#results-pagination"),
  paginationPrev: document.querySelector("#pagination-prev"),
  paginationNext: document.querySelector("#pagination-next"),
  paginationInfo: document.querySelector("#pagination-info"),
};

document.addEventListener("DOMContentLoaded", () => {
  initializePage().catch((error) => {
    showStatus(error.message || "Unable to load the tee time page right now.");
  });
});

async function initializePage() {
  applyDateDefault();
  wireRangeInputs();
  wireCourseButtons();
  wireForm();
  wireDropdownDismissal();
  wirePagination();
  await loadCourses();
  renderIdleState();
}

function applyDateDefault() {
  const today = new Date();
  elements.dateInput.value = today.toISOString().slice(0, 10);
}

function wireRangeInputs() {
  const handleRangeInput = (event) => {
    const isStart = event.target === elements.timeStart;
    let start = Number(elements.timeStart.value);
    let end = Number(elements.timeEnd.value);

    if (start > end) {
      if (isStart) {
        end = start;
        elements.timeEnd.value = String(end);
      } else {
        start = end;
        elements.timeStart.value = String(start);
      }
    }

    updateRangeDisplay(start, end);
  };

  elements.timeStart.addEventListener("input", handleRangeInput);
  elements.timeEnd.addEventListener("input", handleRangeInput);
  updateRangeDisplay(Number(elements.timeStart.value), Number(elements.timeEnd.value));
}

function wireCourseButtons() {
  elements.allOnButton.addEventListener("click", () => {
    setAllCoursesChecked(true);
  });
  elements.allOffButton.addEventListener("click", () => {
    setAllCoursesChecked(false);
  });
}

function wireForm() {
  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runSearch();
  });

  elements.playersSegmented.addEventListener("change", updateSummaryChips);
  elements.form.querySelectorAll('input[name="holes"]').forEach((input) => {
    input.addEventListener("change", updateSummaryChips);
  });
}

async function loadCourses() {
  const response = await fetch("/api/courses");
  if (!response.ok) {
    throw new Error("Could not load your configured courses.");
  }
  state.courses = await response.json();
  renderCourseGroups(state.courses);
  updateCourseSummary();
  updateSummaryChips();
}

function renderCourseGroups(courses) {
  const groups = groupCourses(courses);
  elements.courseGroups.innerHTML = "";

  for (const [groupName, items] of groups.entries()) {
    const card = document.createElement("section");
    card.className = "group-card";
    card.dataset.group = groupName;
    card.dataset.open = "false";

    const header = document.createElement("div");
    header.className = "group-header";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "group-toggle";
    toggle.innerHTML = `
      <span class="group-toggle-indicator">▾</span>
      <span>
        <p class="group-name">${escapeHtml(groupName)}</p>
        <p class="group-meta"><span data-selected-count>${items.length}</span> of ${items.length} courses selected</p>
      </span>
    `;
    toggle.addEventListener("click", () => {
      const isOpen = card.dataset.open !== "false";
      closeAllCourseGroups(card);
      card.dataset.open = String(!isOpen);
    });

    const groupMaster = document.createElement("label");
    groupMaster.className = "group-master";
    groupMaster.innerHTML = `
      <input type="checkbox" class="group-master-input" checked>
      <span>Whole group</span>
    `;
    const groupMasterInput = groupMaster.querySelector("input");
    groupMasterInput.addEventListener("change", () => {
      card.querySelectorAll(".course-checkbox").forEach((checkbox) => {
        checkbox.checked = groupMasterInput.checked;
      });
      syncGroupState(card);
      updateCourseSummary();
    });

    header.append(toggle, groupMaster);
    card.append(header);

    const body = document.createElement("div");
    body.className = "group-body";
    for (const course of items) {
      const courseChoice = document.createElement("label");
      courseChoice.className = "course-choice";
      courseChoice.innerHTML = `
        <input type="checkbox" class="course-checkbox" data-course-id="${escapeHtml(course.id)}" checked>
        <span>${escapeHtml(course.name)}</span>
      `;
      const checkbox = courseChoice.querySelector("input");
      checkbox.addEventListener("change", () => {
        syncGroupState(card);
        updateCourseSummary();
      });
      body.append(courseChoice);
    }

    card.append(body);
    elements.courseGroups.append(card);
    syncGroupState(card);
  }
}

function wireDropdownDismissal() {
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".group-card")) {
      closeAllCourseGroups();
    }
  });
}

function wirePagination() {
  elements.paginationPrev.addEventListener("click", () => {
    if (state.currentPage <= 1) {
      return;
    }
    state.currentPage -= 1;
    renderResultsPage();
  });

  elements.paginationNext.addEventListener("click", () => {
    if (state.currentPage >= totalResultPages()) {
      return;
    }
    state.currentPage += 1;
    renderResultsPage();
  });
}

function closeAllCourseGroups(exceptCard = null) {
  document.querySelectorAll(".group-card").forEach((card) => {
    if (card !== exceptCard) {
      card.dataset.open = "false";
    }
  });
}

function groupCourses(courses) {
  const groups = new Map();
  for (const course of courses) {
    const group = course.group || "Other";
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group).push(course);
  }
  return groups;
}

function syncGroupState(groupCard) {
  const courseCheckboxes = [...groupCard.querySelectorAll(".course-checkbox")];
  const groupMasterInput = groupCard.querySelector(".group-master-input");
  const selectedCount = courseCheckboxes.filter((checkbox) => checkbox.checked).length;
  const totalCount = courseCheckboxes.length;

  groupMasterInput.checked = selectedCount === totalCount;
  groupMasterInput.indeterminate = selectedCount > 0 && selectedCount < totalCount;
  groupCard.querySelector("[data-selected-count]").textContent = String(selectedCount);
}

function setAllCoursesChecked(checked) {
  document.querySelectorAll(".course-checkbox").forEach((checkbox) => {
    checkbox.checked = checked;
  });
  document.querySelectorAll(".group-card").forEach(syncGroupState);
  updateCourseSummary();
}

function updateCourseSummary() {
  const selectedCount = selectedCourseIds().length;
  const totalCount = document.querySelectorAll(".course-checkbox").length;
  elements.selectedCourseCount.textContent = `${selectedCount} of ${totalCount} selected`;
  updateSummaryChips();
}

function updateSummaryChips() {
  const start = Number(elements.timeStart.value);
  const end = Number(elements.timeEnd.value);
  elements.resultsWindowChip.textContent = `${formatMinutesDisplay(start)} to ${formatMinutesDisplay(end)}`;

  const holesValue = selectedHolesValue();
  elements.resultsHolesChip.textContent = holesValue === "either" ? "Either holes" : `${holesValue} holes`;
}

function updateRangeDisplay(start, end) {
  const startPercent = ((start - MINUTES_MIN) / (MINUTES_MAX - MINUTES_MIN)) * 100;
  const endPercent = ((end - MINUTES_MIN) / (MINUTES_MAX - MINUTES_MIN)) * 100;
  elements.rangeTrack.style.setProperty("--range-start", `${startPercent}%`);
  elements.rangeTrack.style.setProperty("--range-end", `${endPercent}%`);
  elements.timeStartChip.textContent = formatMinutesDisplay(start);
  elements.timeEndChip.textContent = formatMinutesDisplay(end);
  updateSummaryChips();
}

async function runSearch() {
  const courseIds = selectedCourseIds();
  if (courseIds.length === 0) {
    showStatus("Select at least one course before running a search.");
    state.results = [];
    state.currentPage = 1;
    renderEmptyState("No courses are selected right now.");
    clearPagination();
    return;
  }

  state.hasSearched = true;
  const params = new URLSearchParams({
    date: elements.dateInput.value,
    players: selectedPlayersValue(),
    earliest: formatMinutesValue(Number(elements.timeStart.value)),
    latest: formatMinutesValue(Number(elements.timeEnd.value)),
  });

  const holesValue = selectedHolesValue();
  if (holesValue !== "either") {
    params.set("holes", holesValue);
  }
  courseIds.forEach((courseId) => params.append("course_id", courseId));

  setLoading(true);
  hideStatus();
  elements.resultsTitle.textContent = "Searching";
  elements.resultsMeta.textContent = `${courseIds.length} courses selected.`;

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Search failed.");
    }
    renderResults(payload);
  } catch (error) {
    showStatus(error.message || "Search failed.");
    state.results = [];
    state.currentPage = 1;
    renderEmptyState("Search failed.");
    clearPagination();
  } finally {
    setLoading(false);
  }
}

function renderResults(results) {
  state.results = Array.isArray(results) ? results : [];
  state.currentPage = 1;
  renderResultsPage();
}

function renderResultsPage() {
  if (!Array.isArray(state.results) || state.results.length === 0) {
    elements.resultsTitle.textContent = "No tee times found";
    elements.resultsMeta.textContent = "Change filters and search again.";
    renderEmptyState("No matches for this search.");
    clearPagination();
    return;
  }

  const totalResults = state.results.length;
  const totalPages = totalResultPages();
  state.currentPage = Math.min(Math.max(state.currentPage, 1), totalPages);

  const startIndex = (state.currentPage - 1) * RESULTS_PER_PAGE;
  const endIndex = Math.min(startIndex + RESULTS_PER_PAGE, totalResults);
  const pageResults = state.results.slice(startIndex, endIndex);
  const maxRetrievedAt = state.results
    .map((result) => new Date(result.retrieved_at))
    .sort((left, right) => right - left)[0];
  elements.resultsTitle.textContent = `${totalResults} tee times found`;
  elements.resultsMeta.textContent = `Fetched ${formatSnapshot(maxRetrievedAt)}. Showing ${startIndex + 1}-${endIndex} of ${totalResults}.`;

  const fragment = document.createDocumentFragment();
  pageResults.forEach((result, index) => {
    const card = document.createElement("article");
    card.className = "tee-card";
    card.style.animationDelay = `${Math.min(index, 10) * 35}ms`;

    const startsAt = new Date(result.starts_at);
    const stats = [
      { label: "Time", value: formatTeeTime(startsAt), className: "" },
      { label: "Holes", value: formatHoles(result), className: "" },
      { label: "Players", value: formatPlayers(result), className: "" },
      { label: "Price", value: formatPriceRange(result), className: "price" },
    ];

    const statsMarkup = stats
      .map(
        (stat) => `
          <div class="stat">
            <span class="stat-label">${escapeHtml(stat.label)}</span>
            <span class="stat-value ${stat.className}">${escapeHtml(String(stat.value))}</span>
          </div>
        `
      )
      .join("");

    const metaPills = [
      `<span class="meta-pill">${escapeHtml(displayGroupForCourse(result.course_id))} • ${escapeHtml(result.provider)}</span>`,
      result.rate_name ? `<span class="meta-pill rate">${escapeHtml(result.rate_name)}</span>` : "",
    ]
      .filter(Boolean)
      .join("");

    card.innerHTML = `
      <div class="tee-card__top">
        <div>
          <p class="tee-card__course">${escapeHtml(result.course_name)}</p>
          <p class="tee-card__group">${escapeHtml(formatDateForCard(startsAt))}</p>
        </div>
        ${result.booking_url ? `<a class="tee-card__book" href="${escapeAttribute(result.booking_url)}" target="_blank" rel="noreferrer">Book</a>` : ""}
      </div>
      <div class="tee-card__stats">${statsMarkup}</div>
      <div class="tee-card__meta">${metaPills}</div>
    `;
    fragment.append(card);
  });

  elements.resultsGrid.innerHTML = "";
  elements.resultsGrid.append(fragment);
  renderPagination(totalResults, totalPages, startIndex, endIndex);
}

function renderEmptyState(message) {
  elements.resultsGrid.innerHTML = `<div class="placeholder-card">${escapeHtml(message)}</div>`;
}

function renderIdleState() {
  if (state.hasSearched) {
    return;
  }
  state.results = [];
  state.currentPage = 1;
  elements.resultsTitle.textContent = "Press Search";
  elements.resultsMeta.textContent = "Choose filters above, then search.";
  hideStatus();
  renderEmptyState("Press Search to load tee times.");
  clearPagination();
}

function renderPagination(totalResults, totalPages, startIndex, endIndex) {
  if (totalPages <= 1) {
    clearPagination();
    return;
  }
  elements.resultsPagination.classList.remove("hidden");
  elements.paginationPrev.disabled = state.currentPage === 1;
  elements.paginationNext.disabled = state.currentPage === totalPages;
  elements.paginationInfo.textContent = `Page ${state.currentPage} of ${totalPages} • ${startIndex + 1}-${endIndex} of ${totalResults}`;
}

function clearPagination() {
  elements.resultsPagination.classList.add("hidden");
  elements.paginationPrev.disabled = true;
  elements.paginationNext.disabled = true;
  elements.paginationInfo.textContent = "";
}

function totalResultPages() {
  return Math.max(Math.ceil(state.results.length / RESULTS_PER_PAGE), 1);
}

function setLoading(isLoading) {
  elements.searchButton.disabled = isLoading;
  elements.searchButton.textContent = isLoading ? "Searching..." : "Search Live Tee Times";
}

function selectedPlayersValue() {
  return elements.form.querySelector('input[name="players"]:checked').value;
}

function selectedHolesValue() {
  return elements.form.querySelector('input[name="holes"]:checked').value;
}

function selectedCourseIds() {
  return [...document.querySelectorAll(".course-checkbox:checked")].map((checkbox) => checkbox.dataset.courseId);
}

function displayGroupForCourse(courseId) {
  return state.courses.find((course) => course.id === courseId)?.group || "Other";
}

function showStatus(message) {
  elements.statusBanner.textContent = message;
  elements.statusBanner.classList.remove("hidden");
}

function hideStatus() {
  elements.statusBanner.classList.add("hidden");
}

function formatMinutesValue(minutes) {
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function formatMinutesDisplay(minutes) {
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  const meridiem = hours >= 12 ? "PM" : "AM";
  const normalized = hours % 12 || 12;
  return `${normalized}:${String(remaining).padStart(2, "0")} ${meridiem}`;
}

function formatTeeTime(dateValue) {
  return dateValue.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDateForCard(dateValue) {
  return dateValue.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function formatSnapshot(dateValue) {
  return dateValue.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatPrice(price) {
  if (price == null) {
    return "-";
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(price);
}

function formatPlayers(result) {
  if (Array.isArray(result.player_options) && result.player_options.length > 0) {
    return formatOptionValues(result.player_options, " or ");
  }
  return result.available_players ?? "-";
}

function formatHoles(result) {
  if (Array.isArray(result.hole_options) && result.hole_options.length > 0) {
    return formatOptionValues(result.hole_options, " - ");
  }
  return result.holes ? `${result.holes}` : "Either";
}

function formatPriceRange(result) {
  const low = result.price_min ?? result.price;
  const high = result.price_max ?? result.price;
  if (low == null && high == null) {
    return "-";
  }
  if (low != null && high != null && Math.abs(high - low) > 0.0001) {
    return `${formatPrice(low)} - ${formatPrice(high)}`;
  }
  return formatPrice(low ?? high);
}

function formatOptionValues(values, pairJoiner) {
  const ordered = [...new Set(values.map(Number))].sort((left, right) => left - right);
  if (ordered.length === 0) {
    return "-";
  }
  if (ordered.length === 1) {
    return String(ordered[0]);
  }
  if (isContiguous(ordered)) {
    if (ordered.length === 2) {
      return `${ordered[0]}${pairJoiner}${ordered[1]}`;
    }
    return `${ordered[0]} - ${ordered[ordered.length - 1]}`;
  }
  if (ordered.length === 2) {
    return `${ordered[0]}${pairJoiner}${ordered[1]}`;
  }
  return ordered.join(", ");
}

function isContiguous(values) {
  return values.every((value, index) => index === 0 || value - values[index - 1] === 1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
