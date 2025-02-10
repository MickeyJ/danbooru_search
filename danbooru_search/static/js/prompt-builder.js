const searchInput = document.getElementById("searchInput");
const resultsDiv = document.getElementById("results");
const promptArea = document.getElementById("promptArea");
const hiddenPromptArea = document.getElementById("hiddenPromptArea");
const copyButton = document.getElementById("copyButton");
const clearButton = document.getElementById("clearButton");

let timeoutId;
searchInput.addEventListener("input", function () {
  clearTimeout(timeoutId);
  timeoutId = setTimeout(() => {
    const query = this.value.trim();
    if (query) {
      fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then((response) => response.json())
        .then((data) => {
          updateResults(data);

          // Add click handlers to new tag results
          document.querySelectorAll(".tag-result").forEach((tag) => {
            tag.addEventListener("click", function () {
              addTagToPrompt(this.dataset.tag);
            });
          });
        });
    } else {
      resultsDiv.innerHTML = "";
    }
  }, 300);
});

// Load saved prompt from localStorage on page load
document.addEventListener("DOMContentLoaded", () => {
  const savedPrompt = localStorage.getItem("savedPrompt");
  if (savedPrompt) {
    const tags = JSON.parse(savedPrompt);
    tags.forEach((tag) => addTagToPrompt(tag));
  }
});

function addTagToPrompt(tag) {
  // Check if tag already exists
  const existingTags = Array.from(promptArea.children).map(
    (el) => el.textContent
  );
  if (existingTags.includes(tag)) return;

  const tagElement = document.createElement("div");
  tagElement.className = "prompt-tag";
  tagElement.draggable = true;
  tagElement.textContent = tag;

  tagElement.addEventListener("dragstart", handleDragStart);
  tagElement.addEventListener("dragend", handleDragEnd);
  tagElement.addEventListener("dragover", handleDragOver);
  tagElement.addEventListener("drop", handleDrop);

  promptArea.appendChild(tagElement);
  updateHiddenPromptArea();
  saveToLocalStorage();
}

let draggedElement = null;

function handleDragStart(e) {
  draggedElement = this;
  this.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move";
}

function handleDragEnd(e) {
  this.classList.remove("dragging");
  draggedElement = null;
}

function handleDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";

  if (this === draggedElement) return;

  const boundingRect = this.getBoundingClientRect();
  const offset = boundingRect.x + boundingRect.width / 2;

  if (e.clientX - offset > 0) {
    this.parentNode.insertBefore(draggedElement, this.nextSibling);
  } else {
    this.parentNode.insertBefore(draggedElement, this);
  }
}

function handleDrop(e) {
  e.preventDefault();
  updateHiddenPromptArea();
}

function updateHiddenPromptArea() {
  const tags = Array.from(promptArea.children).map((tag) => tag.textContent);
  hiddenPromptArea.value = tags.join(", ");
  saveToLocalStorage();
}

function saveToLocalStorage() {
  const tags = Array.from(promptArea.children).map((tag) => tag.textContent);
  localStorage.setItem("savedPrompt", JSON.stringify(tags));
}

function updateResults(data) {
  resultsDiv.innerHTML =
    data.results.length > 0
      ? data.results
          .map(
            (item) =>
              `<div class="tag-result" data-tag="${item.tag}">
                <span class="tag-name">${item.tag}</span>
                <span class="usage-count">${item.times_used} uses</span>
               </div>`
          )
          .join("")
      : "<div class='no-results'>No results found</div>";
}

copyButton.addEventListener("click", function () {
  // Update hidden textarea with current tags
  updateHiddenPromptArea();

  // Copy from hidden textarea
  hiddenPromptArea.style.display = "block";
  hiddenPromptArea.select();
  document.execCommand("copy");
  hiddenPromptArea.style.display = "none";

  // Visual feedback
  const originalText = this.textContent;
  this.textContent = "Copied!";
  setTimeout(() => {
    this.textContent = originalText;
  }, 1500);
});

clearButton.addEventListener("click", function () {
  if (promptArea.children.length > 0) {
    if (confirm("Are you sure you want to clear all tags?")) {
      promptArea.innerHTML = "";
      hiddenPromptArea.value = "";
      localStorage.removeItem("savedPrompt");
    }
  }
});
