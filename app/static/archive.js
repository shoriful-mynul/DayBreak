window.setDaybreakEditionDate = function(timestamp) {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) return;

  document.getElementById("today").textContent =
    "Edition created " +
    date.toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    });
};

const readerStorageKey = "daybreak.reader.v1";

let readerId = localStorage.getItem(readerStorageKey);

if (!readerId) {
  readerId = crypto.randomUUID();
  localStorage.setItem(readerStorageKey, readerId);
}

window.daybreakReaderId = readerId;

function showSavedEdition(paper) {
  renderCoverage(paper);
  window.setDaybreakEditionDate(paper.created_at);

  stories.replaceChildren();

  paper.articles.forEach(story => {
    stories.appendChild(createStory(story));
  });

  const created = new Date(paper.created_at).toLocaleString();

  editionInfo.textContent =
    `${paper.count} stories · ` +
    `About ${paper.estimated_reading_minutes} min · ` +
    `Created ${created}`;

  warningsElement.textContent =
    (paper.warnings || []).join(" ");

  form.hidden = true;
  edition.hidden = false;

  window.daybreakEditionId = paper.edition_id;

  statusElement.textContent =
    "Opened a saved edition. Its stories have not changed.";

  edition.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

async function loadArchive() {
  const archiveList = document.getElementById("archive-list");
  const archiveStatus = document.getElementById("archive-status");

  archiveStatus.textContent = "Loading saved papers...";

  try {
    const response = await fetch("/api/editions", {
      headers: {
        "X-Reader-ID": window.daybreakReaderId
      }
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();

    archiveList.replaceChildren();

    if (!data.editions.length) {
      archiveStatus.textContent =
        "No saved papers yet. Create your first paper above.";
      return;
    }

    archiveStatus.textContent =
      `${data.editions.length} saved editions`;

    data.editions.forEach(item => {
      const button = document.createElement("button");

      const created = new Date(item.created_at).toLocaleString();

      button.type = "button";
      button.textContent =
        `${created} · ${item.count} stories · ` +
        item.topics.join(", ");

      button.style.display = "block";
      button.style.margin = "10px 0";
      button.style.textAlign = "left";
      button.style.lineHeight = "1.5";

      button.addEventListener("click", async () => {
        button.disabled = true;
        archiveStatus.textContent = "Opening saved paper...";

        try {
          const response = await fetch(
            `/api/editions/${item.edition_id}`,
            {
              headers: {
                "X-Reader-ID": window.daybreakReaderId
              }
            }
          );

          if (!response.ok) {
            throw new Error("Could not open this edition.");
          }

          const paper = await response.json();

          showSavedEdition(paper);
          archiveStatus.textContent = "Saved paper opened.";
        } catch (error) {
          archiveStatus.textContent = error.message;
        } finally {
          button.disabled = false;
        }
      });

      archiveList.appendChild(button);
    });
  } catch (error) {
    archiveStatus.textContent =
      `Could not load archive: ${error.message}`;
  }
}

window.loadDaybreakArchive = loadArchive;

loadArchive();


const downloadPdfButton = document.getElementById("download-pdf");

downloadPdfButton.addEventListener("click", async () => {
  const editionId = window.daybreakEditionId;

  if (!editionId) {
    statusElement.textContent =
      "Create a paper or open a saved edition first.";
    return;
  }

  downloadPdfButton.disabled = true;
  downloadPdfButton.textContent = "Preparing PDF...";

  try {
    const response = await fetch(
      `/api/editions/${editionId}/pdf`,
      {
        headers: {
          "X-Reader-ID": window.daybreakReaderId
        }
      }
    );

    if (!response.ok) {
      throw new Error(`PDF request failed: ${response.status}`);
    }

    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = `daybreak-${editionId.slice(0, 8)}.pdf`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    setTimeout(() => {
      URL.revokeObjectURL(downloadUrl);
    }, 10000);

    statusElement.textContent =
      "PDF download requested for the edition currently displayed.";
  } catch (error) {
    statusElement.textContent =
      `Could not download PDF. ${error.message}`;
  } finally {
    downloadPdfButton.disabled = false;
    downloadPdfButton.textContent = "Download PDF";
  }
});


const learningStatus = document.getElementById("learning-status");

function displayLearning(weights) {
  const entries = Object.entries(weights);

  learningStatus.textContent = entries.length
    ? "Learned topic adjustments: " +
      entries.map(([topic, value]) => {
        const prefix = value > 0 ? "+" : "";
        return `${topic} ${prefix}${value.toFixed(1)}`;
      }).join(" · ")
    : "No feedback yet. Tell us what you want more or less of.";
}

async function refreshLearning() {
  try {
    const response = await fetch("/api/learning", {
      headers: {
        "X-Reader-ID": window.daybreakReaderId
      }
    });

    if (!response.ok) {
      throw new Error("Could not load learned preferences.");
    }

    const data = await response.json();
    displayLearning(data.weights);
  } catch (error) {
    learningStatus.textContent = error.message;
  }
}

window.createFeedbackControls = function(story) {
  const controls = document.createElement("div");

  controls.style.display = "flex";
  controls.style.flexWrap = "wrap";
  controls.style.gap = "8px";
  controls.style.marginTop = "16px";

  const buttons = [];

  for (const [action, label] of [
    ["more", "More like this"],
    ["less", "Less like this"]
  ]) {
    const button = document.createElement("button");

    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-pressed", "false");
    button.style.fontSize = "12px";
    button.style.padding = "9px 11px";

    button.addEventListener("click", async () => {
      const editionId = window.daybreakEditionId;

      if (!editionId) {
        statusElement.textContent =
          "Open a saved edition before giving feedback.";
        return;
      }

      buttons.forEach(item => {
        item.disabled = true;
      });

      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Reader-ID": window.daybreakReaderId
          },
          body: JSON.stringify({
            edition_id: editionId,
            article_id: story.id,
            action
          })
        });

        if (!response.ok) {
          throw new Error("Feedback could not be saved.");
        }

        const data = await response.json();

        buttons.forEach(item => {
          item.setAttribute(
            "aria-pressed",
            item === button ? "true" : "false"
          );

          item.style.outline =
            item === button ? "2px solid #242424" : "none";

          item.style.outlineOffset = "2px";
        });

        displayLearning(data.weights);

        statusElement.textContent =
          `Feedback saved for ${data.topic}. ` +
          "Update this paper or create a new one to apply it.";
      } catch (error) {
        statusElement.textContent = error.message;
      } finally {
        buttons.forEach(item => {
          item.disabled = false;
        });
      }
    });

    buttons.push(button);
    controls.appendChild(button);
  }

  return controls;
};

const updatePaperButton = document.getElementById("update-paper");

updatePaperButton.addEventListener("click", async () => {
  const editionId = window.daybreakEditionId;

  if (!editionId) {
    statusElement.textContent =
      "Create a paper or open an edition first.";
    return;
  }

  updatePaperButton.disabled = true;
  updatePaperButton.textContent = "Updating...";

  try {
    const response = await fetch(
      `/api/editions/${editionId}/revise`,
      {
        method: "POST",
        headers: {
          "X-Reader-ID": window.daybreakReaderId
        }
      }
    );

    if (!response.ok) {
      const error = await response.json();

      throw new Error(
        error.detail || "Could not update this paper."
      );
    }

    const paper = await response.json();

    showSavedEdition(paper);

    statusElement.textContent =
      "Updated revision saved using the same collected stories " +
      "and your latest feedback.";

    await loadArchive();
    await refreshLearning();
  } catch (error) {
    statusElement.textContent = error.message;
  } finally {
    updatePaperButton.disabled = false;
    updatePaperButton.textContent = "Update this paper";
  }
});

refreshLearning();

function openTodayForReturningReader() {
  try {
    const saved = JSON.parse(
      localStorage.getItem("daybreak.preferences.v1")
    );

    const allowedTopics = [
      "technology",
      "science",
      "world"
    ];

    const validTopics =
      Array.isArray(saved?.topics) &&
      saved.topics.length > 0 &&
      saved.topics.every(topic => allowedTopics.includes(topic));

    const validReadingTime =
      [5, 10, 15].includes(Number(saved?.reading_minutes));

    if (!validTopics || !validReadingTime) {
      return;
    }

    form.requestSubmit();
  } catch (error) {
    console.warn("Automatic daily opening was skipped.");
  }
}

openTodayForReturningReader();